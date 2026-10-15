"""Offline end-to-end evaluation through product service or immutable recorded runs.

No provider is constructed here. Failed/missing/uncertain predictions remain visible.
"""
from collections import Counter
from pathlib import Path
import tempfile
from src.domain.contracts import AnalysisRun, digest, idempotency_key
from src.application.analysis_service import AnalysisService
from src.application.analyzers import OfflineFake
from src.infrastructure.repository import Repository
from src.evaluation.core import FIELDS
from src.evaluation.e2e_schema import validate_dataset, dataset_hash
from src.evaluation.p2_report import percentile

SUMMARY_RUBRIC = ('key_facts','main_issue','no_hallucination','entities_and_request')
REPLY_RUBRIC = ('factuality','issue_coverage','no_unsupported_commitment','politeness_and_clarity','edit_readiness')

def ratio(num, den):
    return dict(numerator=num, denominator=den, rate=num/den if den else None)

def execute_offline(samples, repository):
    samples=validate_dataset(samples)
    service=AnalysisService(repository,OfflineFake())
    return [service.analyze(sample.email()) for sample in samples]

def output_hash(run):
    return digest(run.result.model_dump()) if run.result else None

def score_pairs(pairs):
    # Failure sentinels are not genuine classes and are never a correct unknown.
    labels=sorted({str(a) for a,b in pairs}|{str(b) for a,b in pairs if b not in ('<failed>','<missing>','<uncertain>','<fallback>')})
    per_class={};matrix={}
    for a,b in pairs:
        matrix.setdefault(str(a),{})[str(b)]=matrix.get(str(a),{}).get(str(b),0)+1
    for label in labels:
        tp=sum(str(a)==label and str(b)==label for a,b in pairs)
        fp=sum(str(a)!=label and str(b)==label for a,b in pairs)
        fn=sum(str(a)==label and str(b)!=label for a,b in pairs)
        p=tp/(tp+fp) if tp+fp else 0
        r=tp/(tp+fn) if tp+fn else 0
        per_class[label]=dict(precision=p,recall=r,f1=2*p*r/(p+r) if p+r else 0,support=tp+fn)
    correct=sum(a==b for a,b in pairs)
    return dict(correct=correct,denominator=len(pairs),accuracy=correct/len(pairs) if pairs else None,
                macro_f1=sum(m['f1'] for m in per_class.values())/len(labels) if labels else None,
                confusion_matrix=matrix,per_class=per_class)

def content_scores(kind,samples,runs,reviews):
    rubric=SUMMARY_RUBRIC if kind=='summary' else REPLY_RUBRIC
    eligible=[s for s in samples if kind in s.applicable_checks]
    accepted=[]
    for review in reviews:
        if review.get('kind')!=kind:continue
        sample=next((s for s in eligible if s.sample_id==review.get('sample_id')),None)
        run=runs.get(review.get('sample_id'))
        if not sample or not run or not run.result:raise ValueError('Review without eligible successful run')
        reference=getattr(sample,kind+'_reference')
        if reference.status!='approved':raise ValueError('Human reference pending')
        required={'sample_id','kind','run_id','input_hash','cohort_id','output_hash','rubric_version','reviewer','status','scores','critical_errors','evidence'}
        if set(review)!=required:raise ValueError('Incomplete review record')
        if any(review[k]!=v for k,v in dict(run_id=run.run_id,input_hash=sample.input_hash,cohort_id=run.cohort_id,output_hash=output_hash(run),rubric_version='content-rubric-v1').items()):
            raise ValueError('Review binding differs')
        if not review['reviewer'] or review['status']!='approved' or not review['evidence']:
            raise ValueError('Human review declaration/evidence missing')
        if set(review['scores'])!=set(rubric) or any(type(v)is not int or v not in (0,1,2) for v in review['scores'].values()):
            raise ValueError('Rubric scores must be explicit 0/1/2')
        if not isinstance(review['critical_errors'],list) or any(not isinstance(v,str) for v in review['critical_errors']):
            raise ValueError('Critical errors must be an explicit list')
        accepted.append(review)
    if len({r['sample_id'] for r in accepted})!=len(accepted):raise ValueError('Duplicate content review')
    passing=sum(not r['critical_errors'] and all(v==2 for v in r['scores'].values()) for r in accepted)
    status='PENDING' if len(accepted)<len(eligible) or not eligible else 'PASSED' if passing==len(eligible) else 'FAILED'
    return dict(status=status,eligible=len(eligible),evaluated=len(accepted),pending=len(eligible)-len(accepted),
                passed=ratio(passing,len(eligible)),rubric={k:dict(score_sum=sum(r['scores'][k] for r in accepted),reviewed=len(accepted),maximum_per_review=2) for k in rubric},
                critical_error_count=sum(len(r['critical_errors']) for r in accepted),
                **({'ready_to_send':False,'reason':'P4 approval and sending not implemented'} if kind=='reply' else {}))

def evaluate(samples,runs,reviews=(),mode='recorded_replay',freeze_manifest=None):
    samples=validate_dataset(samples)
    runs=[AnalysisRun.model_validate(r.model_dump() if isinstance(r,AnalysisRun) else r) for r in runs]
    by_id={r.email.email_id:r for r in runs};sample_ids={s.sample_id for s in samples}
    if len(by_id)!=len(runs) or len({r.run_id for r in runs})!=len(runs):raise ValueError('Duplicate sample or run')
    if set(by_id)-sample_ids:raise ValueError('Unexpected run outside dataset')
    if len({r.config.cohort_id for r in runs})>1:raise ValueError('Different versions must have separate reports')
    if mode not in ('recorded_replay','offline_service'):raise ValueError('Unsupported evaluation mode')
    for sample in samples:
        run=by_id.get(sample.sample_id)
        if not run:continue
        if run.email!=sample.email() or run.input_hash!=sample.input_hash or run.input_hash!=run.email.input_hash:
            raise ValueError('Sample/run input mismatch')
        if run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config):
            raise ValueError('Run version/idempotency binding mismatch')
        if run.config.taxonomy_version!=sample.taxonomy_version or run.config.schema_version!='analysis-v2':
            raise ValueError('Incompatible taxonomy/schema')
        if (run.status=='succeeded')!=(run.result is not None):raise ValueError('Invalid run outcome')
        if run.result and (not run.attempts or run.attempts[-1].contract_status!='passed' or run.attempts[-1].error):
            raise ValueError('Successful run lacks accepted attempt')
    # Reject malformed reviews before a missing kind can cause them to disappear.
    if any(r.get('kind') not in ('summary','reply') for r in reviews):raise ValueError('Review kind required')
    fields={};mismatches=[]
    for field in FIELDS:
        pairs=[];excluded=Counter()
        for sample in samples:
            expected=getattr(sample.expected,field)
            if 'seven_fields' not in sample.applicable_checks:excluded['check_not_applicable']+=1;continue
            if expected is None:excluded['human_reference_pending']+=1;continue
            run=by_id.get(sample.sample_id)
            predicted=(getattr(run.result,field) if run and run.result else '<missing>' if not run else '<uncertain>' if run.status in ('running','interrupted_or_unknown') else '<failed>')
            if run and run.metadata.get('fallback'):predicted='<fallback>'
            pairs.append((expected,predicted))
            if predicted!=expected:mismatches.append(dict(sample_id=sample.sample_id,run_id=run.run_id if run else None,field=field,expected=expected,predicted=predicted))
        fields[field]=dict(score_pairs(pairs),eligible=len(samples),excluded=dict(excluded))
    complete=[s for s in samples if 'seven_fields' in s.applicable_checks and all(v is not None for v in s.expected.model_dump().values())]
    all_correct=sum(bool(by_id.get(s.sample_id) and by_id[s.sample_id].result and not by_id[s.sample_id].metadata.get('fallback') and all(getattr(by_id[s.sample_id].result,f)==getattr(s.expected,f) for f in FIELDS)) for s in complete)
    attempts=[a for r in runs for a in r.attempts]
    succeeded=[r for r in runs if r.status=='succeeded' and not r.metadata.get('fallback')]
    counts=dict(eligible=len(samples),attempted=sum(bool(r.attempts) for r in runs),succeeded=len(succeeded),
                failed=sum(r.status=='failed' for r in runs),uncertain=sum(r.status in ('running','interrupted_or_unknown') for r in runs),
                fallback=sum(r.status=='succeeded' and bool(r.metadata.get('fallback')) for r in runs),
                missing=len(samples)-len(runs),evaluated=len(complete),pending=len(samples)-len(complete))
    # Reuse real product deterministic aggregation in a disposable new store.
    aggregates={};checks=[]
    with tempfile.TemporaryDirectory(prefix='complaint_eval_') as directory:
        repo=Repository(Path(directory)/'evaluation.sqlite3');service=AnalysisService(repo,OfflineFake())
        for run in succeeded:repo.save(run)
        for dimension in ('store_location','product_category'):
            groups=service.aggregate(runs[0].cohort_id,dimension) if runs else []
            aggregates[dimension]=groups
            for group in groups:
                expected_members={r.run_id for r in succeeded if getattr(r.result,dimension)==group['group']}
                negative={r.run_id for r in succeeded if r.run_id in expected_members and r.result.sentiment=='negative'}
                checks.append(set(group['member_run_ids'])==expected_members and set(group['negative_member_run_ids'])==negative
                    and group['denominator']==len(expected_members) and group['numerator']==len(negative)
                    and group['negative_rate']==len(negative)/len(expected_members)
                    and all(repo.get(rid).email==next(r.email for r in runs if r.run_id==rid) for rid in expected_members))
    token_keys=('input_tokens','output_tokens','total_tokens')
    usage={k:dict(known_attempts=sum(a.metadata.get(k)is not None for a in attempts),total_attempts=len(attempts),
        known_subtotal=sum(a.metadata.get(k) or 0 for a in attempts),total=sum(a.metadata[k] for a in attempts) if attempts and all(a.metadata.get(k)is not None for a in attempts) else None) for k in token_keys}
    timings=[a.elapsed_ms for a in attempts if a.elapsed_ms is not None]
    costs=[a.metadata.get('cost_cny') for a in attempts]
    independent=False
    if freeze_manifest is not None:
        from src.evaluation.gold import verify_freeze
        frozen=verify_freeze(freeze_manifest)
        if dataset_hash(frozen)!=dataset_hash(samples):raise ValueError('Evaluation differs from frozen dataset')
        independent=(freeze_manifest['independent_holdout'] and bool(runs) and all(r.config.backend=='deepseek_live' for r in runs))
    business_reference={}
    for dimension in ('store_location','product_category','source_attribution'):
        ready=[s for s in samples if 'aggregate' in s.applicable_checks and getattr(s.expected,dimension) is not None and s.expected.sentiment is not None]
        expected_groups={};predicted_groups={}
        for sample in ready:
            value=getattr(sample.expected,dimension)
            group=expected_groups.setdefault(value,dict(numerator=0,denominator=0,sample_ids=[]))
            group['denominator']+=1;group['numerator']+=sample.expected.sentiment=='negative';group['sample_ids'].append(sample.sample_id)
            run=by_id.get(sample.sample_id)
            if run in succeeded:
                value=getattr(run.result,dimension)
                pred=predicted_groups.setdefault(value,dict(numerator=0,denominator=0,sample_ids=[]))
                pred['denominator']+=1;pred['numerator']+=run.result.sentiment=='negative';pred['sample_ids'].append(sample.sample_id)
        for groups in (expected_groups,predicted_groups):
            for group in groups.values():group['negative_rate']=group['numerator']/group['denominator']
        business_reference[dimension]=dict(eligible=len(samples),reference_available=len(ready),pending_or_excluded=len(samples)-len(ready),
            expected=expected_groups,predicted=predicted_groups,
            deltas={key:dict(denominator=predicted_groups.get(key,{}).get('denominator',0)-expected_groups.get(key,{}).get('denominator',0),
                numerator=predicted_groups.get(key,{}).get('numerator',0)-expected_groups.get(key,{}).get('numerator',0)) for key in sorted(set(expected_groups)|set(predicted_groups))},
            source='evaluation_only_reference_comparison; product P3 evidence reported separately')
    from src.evaluation.p3_business import verify_business
    p3_business=verify_business(samples,runs) if runs else None
    return dict(protocol='e2e-evaluation-v1',mode=mode,dataset_id=samples[0].dataset_id,dataset_hash=dataset_hash(samples),
        provenance=samples[0].provenance.model_dump(),reference_statuses=dict(Counter(s.reference_status for s in samples)),
        config=runs[0].config.model_dump() if runs else None,cohort_id=runs[0].cohort_id if runs else None,
        counts=counts,structure=dict(accepted=ratio(len(succeeded),len(samples)),json=ratio(sum(a.parse_status=='passed' for a in attempts),len(attempts)),
            schema=ratio(sum(a.contract_status=='passed' for a in attempts),len(attempts)),attempt_records=len(attempts),
            provider_dispatch_records=sum(a.metadata.get('dispatch') in ('started_or_unknown','response_received') for a in attempts),
            retries=sum(max(0,len(r.attempts)-1) for r in runs),errors=dict(Counter(a.error.error_type for a in attempts if a.error)),
            fallback=sum(bool(r.metadata.get('fallback')) for r in runs),warnings=sum(any(a.warnings for a in r.attempts) for r in runs)),
        fields=fields,overall_fields=ratio(sum(m['correct'] for m in fields.values()),sum(m['denominator'] for m in fields.values())),
        all_seven=ratio(all_correct,len(complete)),mismatches=mismatches,
        independent_accuracy=ratio(all_correct,len(complete)) if independent else None,
        independent_certification='DECLARED_HUMAN_FREEZE_VALIDATED' if independent else 'INDEPENDENT_HOLDOUT_PENDING',
        summary=content_scores('summary',samples,by_id,reviews),reply=content_scores('reply',samples,by_id,reviews),
        aggregates=aggregates,business_reference_comparison=business_reference,aggregate_verification=dict(passed=bool(checks) and all(checks),groups_checked=len(checks),
            scope='Product arithmetic and members against saved predictions; not semantic attribution correctness',
            failed_excluded=counts['failed'],uncertain_excluded=counts['uncertain'],missing_excluded=counts['missing'],
            fallback_excluded=sum(bool(r.metadata.get('fallback')) for r in runs),
            unknown_product=sum(r.result.product_category=='unknown' for r in succeeded),unknown_store=sum(r.result.store_location=='unknown' for r in succeeded),
            source_attribution_query='P3_READONLY_ATTRIBUTION_SERVICE'),
        p3_business=p3_business,
        traceability=[dict(sample_id=s.sample_id,input_hash=s.input_hash,reference_hash=digest(s.model_dump()),
            run_id=by_id[s.sample_id].run_id if s.sample_id in by_id else None,output_hash=output_hash(by_id[s.sample_id]) if s.sample_id in by_id else None,
            run_record_hash=digest(by_id[s.sample_id].model_dump()) if s.sample_id in by_id else None) for s in samples],
        usage=usage,cost=dict(known_attempts=sum(c is not None for c in costs),total_attempts=len(costs),estimated_cny=sum(costs) if costs and all(c is not None for c in costs) else None,actual_cny=None),
        latency_ms=dict(n=len(timings),p50=percentile(timings,.5),p95=percentile(timings,.95)),
        browser_e2e_verified=False,ui_status='Separate AppTest evidence required; this evaluator does not exercise a browser',
        system_quality='Persistence/idempotency/version/failure/UI covered by separate named engineering tests; no composite quality score')
