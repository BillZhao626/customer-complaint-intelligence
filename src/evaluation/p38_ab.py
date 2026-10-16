"""Executable paired experiment preparation and evaluation. Zero authorization by default."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import random
import math
from src.domain.contracts import EmailInput,RunConfigV31,digest
from src.domain.analysis_v31 import AnalysisV31,SCHEMA,TAXONOMY,POLICY,PROJECTION
from src.application.reply_review import VERSION as GATE
from src.application.v31_prompt import messages,prompt_hash,PARENT_PROMPT_HASH
from src.dataset.adoption_v3 import validate as validate_dataset

VERSION='p38-controlled-ab-v1'
SELECTED=('P35-021','P35-031','P35-100','P35-111','P35-122','P35-128','P35-147','P35-171')


def chain_hash():
    root=Path(__file__).resolve().parents[2]
    paths=('src/application/v3_pilot_prompt.py','src/application/v31_prompt.py','src/application/research_policy_v2.py',
        'src/application/reply_review.py','src/domain/analysis_v31.py','src/application/analysis_service.py',
        'src/application/live_execution.py','src/infrastructure/deepseek.py','src/infrastructure/p38_budget.py',
        'src/evaluation/p38_ab.py','src/application/p38_execution.py','src/infrastructure/repository.py',
        'src/domain/contracts.py','src/domain/versioned_analysis.py')
    return digest({p:sha256((root/p).read_bytes()).hexdigest() for p in paths})


def configuration(arm,dataset_hash):
    return RunConfigV31(backend='deepseek_live',model_id='deepseek-flash',prompt_version='complaint-v31-'+arm+'-1',
        prompt_hash=prompt_hash(arm),schema_version=SCHEMA,taxonomy_version=TAXONOMY,
        parameters=dict(temperature=0,thinking='disabled',response_format='json_object',max_tokens=4000,sdk_max_retries=0,
            max_attempts=1,http_timeout=45.0,deadline=90.0,endpoint='https://api.deepseek.com/chat/completions',
            policy_version=POLICY,projection_policy=PROJECTION,reply_gate_version=GATE,dataset_id=VERSION,dataset_hash=dataset_hash,
            arm=arm,processing_chain_hash=chain_hash()))


def build_manifest(dataset,frozen):
    validate_dataset(dataset)
    if len(frozen)!=24 or len({r['input_hash'] for r in frozen})!=24:raise ValueError('Expected frozen 24 development inputs')
    inputs=[]
    for f in frozen:
        email=EmailInput.model_validate(f['email'])
        if email.input_hash!=f['input_hash'] or not f.get('fictional_provenance'):raise ValueError('Frozen provenance mismatch')
        inputs.append(dict(email=email.model_dump(),input_hash=email.input_hash,group='frozen24',source_hash=digest(f),
            provenance='frozen fictional development; old reference kept outside provider input',owner_quality_approved=False))
    current={r['logical_id']:r for r in dataset['records'] if r['state']=='current'}
    for id in SELECTED:
        r=current[id];c=r['source_record']
        if r['queue']!='natural' or r['quality_status']!='owner_adopted' or c['generation_source']!='codex_authored_synthetic':
            raise ValueError('New A/B candidate not approved fictional natural input')
        email=EmailInput(email_id=r['record_id'],subject=c['subject'],body=c['body'])
        inputs.append(dict(email=email.model_dump(),input_hash=email.input_hash,group='adopted8',source_hash=r['source_record_hash'],
            provenance='owner-approved synthetic text/adoption; content Gold pending',owner_quality_approved=True))
    bound=digest(inputs);configs={a:configuration(a,bound).model_dump() for a in ('A','B')}
    rng=random.Random(3801);order=list(range(len(inputs)));rng.shuffle(order);schedule=[]
    for pair,index in enumerate(order):
        arms=['A','B'];rng.shuffle(arms)
        for arm in arms:schedule.append(dict(pair=pair+1,arm=arm,input_index=index,phase='smoke' if pair<4 else 'remaining'))
    packet=dict(version=VERSION,design='same-v31-migration-baseline-A-vs-business-optimized-B',
        baseline_is_p36_frozen_prompt=False,dataset_manifest_hash=dataset['manifest_hash'],inputs=inputs,inputs_hash=bound,
        prompt_migration=dict(parent_p36_prompt_hash=PARENT_PROMPT_HASH,method='Replace schema once, replace safety/medium invariants, append mandatory v2 migration; B appends business quality checklist'),
        schema_hash=digest(AnalysisV31.model_json_schema()),processing_chain_hash=chain_hash(),configs=configs,schedule=schedule,
        authorization=dict(requests=0,cny=0,status='REAL_MODEL_AB_PENDING'),future_proposal=dict(pairs=len(inputs),base_requests=len(schedule),
            max_failure_retests=8,max_requests=72,max_cny=10,smoke_pairs=4),
        input_byte_cap=50000,planning_prices=dict(input_cny_per_million=2,output_cny_per_million=8,status='HISTORICAL_PLANNING_ONLY_RECHECK_REQUIRED'),
        evaluation=dict(old_seven_reference='Separate frozen-v1.1 development consistency; not policy-v2 accuracy',
            new_policy_reference='PENDING',issue_and_content='PENDING_HUMAN',failure_denominator='all 32 pairs per arm'),
        sending='No customer email sending; only future authorized provider requests')
    packet['manifest_hash']=digest(packet)
    return packet


def preflight(manifest,authorization=None):
    copy=dict(manifest);claim=copy.pop('manifest_hash')
    if digest(copy)!=claim or manifest['version']!=VERSION or manifest['schema_hash']!=digest(AnalysisV31.model_json_schema()) or manifest['processing_chain_hash']!=chain_hash():
        raise ValueError('Experiment identity/schema/processing drift')
    inputs=manifest['inputs']
    if len(inputs)!=32 or len({x['input_hash'] for x in inputs})!=32 or digest(inputs)!=manifest['inputs_hash']:
        raise ValueError('A/B whitelist identity mismatch')
    for arm in ('A','B'):
        if manifest['configs'][arm]!=configuration(arm,manifest['inputs_hash']).model_dump():raise ValueError('Arm configuration drift')
    schedule=manifest['schedule']
    if len(schedule)!=64 or Counter((s['input_index'],s['arm']) for s in schedule)!=Counter((i,a) for i in range(32) for a in ('A','B')):
        raise ValueError('Unpaired schedule')
    if any(schedule[j]['pair']!=j//2+1 or schedule[j]['phase']!=('smoke' if j<8 else 'remaining') for j in range(64)) or any(schedule[j]['input_index']!=schedule[j+1]['input_index'] for j in range(0,64,2)):
        raise ValueError('Invalid smoke/pair ordering')
    sizes=[]
    for row in inputs:
        email=EmailInput.model_validate(row['email'])
        if email.input_hash!=row['input_hash']:raise ValueError('Input hash mismatch')
        for arm in ('A','B'):
            size=len(json.dumps(messages(email,arm),ensure_ascii=False).encode('utf8'))+1024
            if size>manifest['input_byte_cap']:raise ValueError('Input exceeds conservative byte cap')
            sizes.append(size)
    allowed=False
    if authorization is not None:
        if authorization.get('status')!='researcher_explicitly_authorized' or not authorization.get('researcher') or not authorization.get('authorization_evidence'):
            raise ValueError('Explicit researcher authorization required')
        if (authorization.get('experiment_hash')!=claim or type(authorization.get('requests')) is not int
            or type(authorization.get('cny')) not in (int,float) or not 1<=authorization.get('requests',0)<=72 or not 0<authorization.get('cny',0)<=10):
            raise ValueError('Authorization scope or hard cap mismatch')
        checked=datetime.fromisoformat(authorization.get('prices_verified_at',''))
        if checked.tzinfo is None or not 0<=(datetime.now(timezone.utc)-checked).total_seconds()<=86400:
            raise ValueError('Official price/model verification must be within 24 hours')
        if authorization.get('price_source')!='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/' or authorization.get('model')!='deepseek-flash' or not authorization.get('model_availability_verified'):
            raise ValueError('Official price/model evidence required')
        prices=authorization.get('prices',{})
        if set(prices)!={'input_cny_per_million','output_cny_per_million'} or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<=0 for v in prices.values()):
            raise ValueError('Verified positive prices required')
        allowed=True
    return dict(manifest_hash=claim,inputs=len(inputs),scheduled_requests=len(schedule),max_input_bytes=max(sizes),
        authorized_requests=authorization['requests'] if allowed else 0,authorized_cny=authorization['cny'] if allowed else 0,
        paid_dispatch_allowed=allowed,price_verification='future_required' if not allowed else 'explicit_external_receipt',
        new_requests=0,content_score=None)


def evaluate(manifest,runs,old_references=None):
    preflight(manifest);by={};members=[]
    from src.domain.analysis_v31 import stored_analysis
    from src.evaluation.e2e_v3 import SEVEN
    from src.evaluation.p2_report import percentile
    from src.application.reply_review import inspect_reply
    from src.application.research_policy_v2 import assess,requested_language,language
    inputs={r['email']['email_id']:r for r in manifest['inputs']}
    if old_references is not None:
        if set(old_references)!={id for id,item in inputs.items() if item['group']=='frozen24'}:
            raise ValueError('Old-reference coverage must be exactly frozen24')
        for id,ref in old_references.items():
            if digest(ref)!=inputs[id]['source_hash'] or ref.get('input_hash')!=inputs[id]['input_hash'] or ref.get('email')!=inputs[id]['email'] or set(ref.get('expected',{}))!=set(SEVEN):
                raise ValueError('Frozen old-reference version/input/hash mismatch')
    for run in runs:
        arm=(run.config.parameters or {}).get('arm');id=run.email.email_id
        if arm not in ('A','B') or id not in inputs or run.email.model_dump()!=inputs[id]['email'] or run.config.model_dump()!=manifest['configs'][arm]:
            raise ValueError('Evaluation input/arm/config mismatch')
        if (id,arm) in by:raise ValueError('Duplicate arm result; select an explicit retest cohort')
        if (run.status=='succeeded') != (run.result is not None):raise ValueError('Run status/result mismatch')
        if run.result:stored_analysis(run)
        by[id,arm]=run
    report={}
    for arm in ('A','B'):
        accepted=0;received=0;tokens=0;token_unknown=0;cost=0;cost_unknown=0;latencies=[];states=Counter();fields=0;ref_den=0;all_correct=0
        for id,item in inputs.items():
            run=by.get((id,arm));state=run.status if run else 'missing';states[state]+=1
            actual=stored_analysis(run) if run and run.result and not run.metadata.get('fallback') else None
            accepted+=bool(actual)
            attempts=run.attempts if run else []
            received+=bool(attempts and attempts[-1].raw_output is not None)
            for a in attempts:
                if a.elapsed_ms is not None:latencies.append(a.elapsed_ms)
                t=a.metadata.get('total_tokens');tokens+=t or 0;token_unknown+=t is None
                c=a.metadata.get('cost_cny');cost+=c or 0;cost_unknown+=c is None
            reference=(old_references or {}).get(id);ref=reference['expected'] if reference else None
            if item['group']=='frozen24' and ref:
                ref_den+=len(SEVEN)
                checks=[bool(actual and getattr(run.result,k)==ref[k]) for k in SEVEN];fields+=sum(checks);all_correct+=all(checks)
            members.append(dict(sample_id=id,arm=arm,state=state,input_hash=item['input_hash'],run_id=run.run_id if run else None,
                output_hash=run.metadata.get('analysis_v31_hash') if run else None,issue_count=len(actual.issues) if actual else None,
                config_hash=digest(run.config.model_dump()) if run else None,schema=SCHEMA,prompt_hash=manifest['configs'][arm]['prompt_hash'],
                raw_hashes=[digest(a.raw_output) for a in attempts],errors=[a.error.model_dump() for a in attempts if a.error],
                deterministic_review=dict(reply_gate=inspect_reply(actual.suggested_reply),policy_candidate=assess(run.email.body),
                    expected_reply_language_candidate=requested_language(run.email.body),actual_reply_language_candidate=language(actual.suggested_reply),
                    evidence_spans='passed') if actual else None,
                seven_reference_applicability='historical_v1.1_consistency_only' if ref else 'pending',
                issues_pending=actual.model_dump()['issues'] if actual else None,summary_pending=actual.summary if actual else None,
                reply_pending=actual.suggested_reply if actual else None,content_human_score=None,critical_errors_human=None))
        report[arm]=dict(input_denominator=len(inputs),response_received=received,accepted=accepted,states=dict(states),
            old_seven_consistency=dict(correct=fields,denominator=ref_den,emails_all_correct=all_correct,email_denominator=ref_den//len(SEVEN),
                caveat='Frozen development reference, not new-policy accuracy; urgency/routing policy may differ'),
            issue_evidence_summary_reply='PENDING_HUMAN',p50_ms=percentile(latencies,.5),p95_ms=percentile(latencies,.95),
            latency_n=len(latencies),observed_tokens=tokens,token_unknown_attempts=token_unknown,
            estimated_cost_cny=None if cost_unknown else cost,known_cost_subtotal_cny=cost,cost_unknown_attempts=cost_unknown,actual_invoice_cost=None)
    def pair_values(id,arm):
        r=by.get((id,arm));v=stored_analysis(r) if r and r.result and not r.metadata.get('fallback') else None
        return dict(state=r.status if r else 'missing',urgency=v.urgency if v else None,issue_count=len(v.issues) if v else None,
                    output_hash=r.metadata.get('analysis_v31_hash') if r else None,human_content_score=None)
    return dict(version='p38-paired-evaluation-1',manifest_hash=manifest['manifest_hash'],arms=report,members=members,
        pairs=[dict(sample_id=id,A=pair_values(id,'A'),B=pair_values(id,'B')) for id in inputs],
        seven_version_applicability=dict(sentiment='old_development_consistency_only',urgency='policy_v2_changed_do_not_claim_accuracy',
            is_complaint='old_development_consistency_only_unknown_projection_loss',store_location='new_safe_projection_may_differ',
            product_category='new_customer_primary_projection_may_differ',complaint_reason='billing_has_no_v2_equivalent',
            source_attribution='routing_is_not_liability_new_safe_projection_may_differ'),
        human_content_review='PENDING',real_model_ab='PENDING' if not runs else 'OBSERVED_RUNS_ONLY',independent_holdout='PENDING',
        historical_background='P3.6 v3: 143/168,17/24,29/32; different schema cannot establish prompt improvement')
