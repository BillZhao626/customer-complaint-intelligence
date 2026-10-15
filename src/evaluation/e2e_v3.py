"""Service-run evaluation. Missing outputs never shrink the semantic denominator."""
from collections import Counter
from typing import Literal
from pydantic import Field,model_validator
from src.domain.contracts import StrictModel,EmailInput,digest,idempotency_key
from src.domain.analysis_v3 import AnalysisV3,stored_analysis,to_v2
from src.application.v3_statistics import snapshot

SEVEN=('sentiment','urgency','is_complaint','store_location','product_category','complaint_reason','source_attribution')
ISSUE_FIELDS=('object_type','object_name','category','issue_kind','reason','sentiment','urgency','resolution',
              'business_process','routing_team','attribution_certainty','customer_requests','customer_importance','handling_priority')


class Candidate(StrictModel):
    dataset_id: str
    sample_id: str
    subject: str
    body: str
    input_hash: str
    generation_source: Literal['codex_authored_synthetic','explicit_test_fixture']
    generation_method: str
    generation_version: str
    scenarios: list[str] = Field(min_length=1)
    language: Literal['zh','en','mixed']
    template_family: str
    semantic_family: str
    split: Literal['development','regression','quarantine']
    exposure: Literal['development_exposed'] = 'development_exposed'
    review_status: Literal['pending','owner_calibration','test_fixture'] = 'pending'
    reference_basis: str | None = None
    reference: AnalysisV3 | None = None
    quality_flags: list[str] = Field(default_factory=list)
    exclusion_reason: str | None = None

    def email(self): return EmailInput(email_id=self.sample_id,subject=self.subject,body=self.body)

    @model_validator(mode='after')
    def binding(self):
        if self.email().input_hash!=self.input_hash: raise ValueError('Candidate input hash mismatch')
        if self.reference is not None:
            if self.review_status=='pending' or not self.reference_basis: raise ValueError('Reference needs explicit basis')
            self.reference.validate_input(self.email())
        if self.split=='quarantine' and not self.exclusion_reason: raise ValueError('Quarantine needs reason')
        return self


def validate_candidates(rows):
    rows=[Candidate.model_validate(r.model_dump() if isinstance(r,Candidate) else r) for r in rows]
    if not rows: raise ValueError('Empty dataset')
    if len({r.dataset_id for r in rows})!=1 or len({r.generation_source for r in rows})!=1:
        raise ValueError('Mixed datasets/sources')
    if len({r.sample_id for r in rows})!=len(rows): raise ValueError('Duplicate sample ID')
    for attr in ('input_hash','template_family','semantic_family'):
        groups={}
        for r in rows:
            if r.split=='quarantine': continue
            groups.setdefault(getattr(r,attr),set()).add(r.split)
        if any(len(s)>1 for s in groups.values()): raise ValueError('Cross-split family leakage')
    return rows


def dataset_hash(rows): return digest([r.model_dump() for r in rows])


def issue_signature(issue):
    # Exact grounding + object identity avoids arbitrary provider issue-ID/order dependence.
    return (issue.object_name,tuple(sorted((e.field,e.start,e.end,e.quote) for e in issue.evidence)))


def compare_issues(expected,actual):
    e={issue_signature(i):i for i in expected.issues};a={issue_signature(i):i for i in actual.issues}
    if len(e)!=len(expected.issues) or len(a)!=len(actual.issues): return False
    def content(i): return i.model_dump(exclude={'issue_id','priority_rationale'})
    if set(e)!=set(a) or any(content(e[k])!=content(a[k]) for k in e): return False
    def relations(v):
        ids={i.issue_id:issue_signature(i) for i in v.issues}
        result=[]
        for r in v.relations:
            pair=(ids[r.from_issue],ids[r.to_issue])
            if r.kind=='equal_importance': pair=tuple(sorted(pair))
            result.append((r.kind,pair))
        return sorted(result)
    return relations(expected)==relations(actual)


def align_issues(expected,actual):
    """Greedy evidence-overlap alignment, deterministic; human matching may differ."""
    def spans(issue):return {(e.field,e.start,e.end,e.quote) for e in issue.evidence}
    edges=[]
    for n,e in enumerate(expected):
        for m,a in enumerate(actual):
            shared=len(spans(e)&spans(a))
            score=10*shared+int(e.object_name.casefold()==a.object_name.casefold())
            if score:edges.append((-score,n,m))
    pairs={};used=set()
    for score,n,m in sorted(edges):
        if n not in pairs and m not in used:pairs[n]=m;used.add(m)
    return pairs


def evaluate(candidates,runs,reviews=None):
    rows=validate_candidates(candidates);by_id={r.sample_id:r for r in rows};bound_hash=dataset_hash(rows)
    runs=list(runs);seen=set();cohorts=set()
    for r in runs:
        if r.run_id in seen: raise ValueError('Duplicate run ID')
        seen.add(r.run_id);cohorts.add(r.cohort_id)
        if r.email.email_id not in by_id or r.email!=by_id[r.email.email_id].email(): raise ValueError('Input mismatch')
        if r.input_hash!=r.email.input_hash or r.cohort_id!=r.config.cohort_id or r.idempotency_key!=idempotency_key(r.email,r.config): raise ValueError('Run binding mismatch')
        params=r.config.parameters or {}
        if params.get('dataset_id')!=rows[0].dataset_id or params.get('dataset_hash')!=bound_hash: raise ValueError('Dataset version mismatch')
        if r.config.schema_version!='analysis-v3': raise ValueError('Expected v3')
        if (r.status=='succeeded')!=(r.result is not None): raise ValueError('Status/result mismatch')
        if r.result and (not r.attempts or r.attempts[-1].contract_status!='passed' or r.attempts[-1].error):
            raise ValueError('Successful result lacks accepted attempt')
        if r.result: stored_analysis(r)
    if len(cohorts)>1: raise ValueError('Mixed model/prompt/config cohorts')
    latest={}
    for r in sorted(runs,key=lambda r:(r.created_at,r.run_id)): latest[r.email.email_id]=r
    eligible=[r for r in rows if not r.exclusion_reason];excluded=[r for r in rows if r.exclusion_reason]
    states=Counter();metrics={key:dict(correct=0,denominator=0) for key in (*SEVEN,'seven_fields_all_correct','email_semantics','issue_count','issue_details',
        *('issue_'+k for k in ISSUE_FIELDS),'issue_evidence')}
    issue_alignment=dict(reference_issues=0,predicted_issues_on_referenced_samples=0,matched=0,unmatched_predictions=0)
    mismatches=[];members=[];reference_pending=0
    for sample in eligible:
        run=latest.get(sample.sample_id);state='missing' if run is None else 'fallback' if run.metadata.get('fallback') else run.status
        states[state]+=1
        actual=stored_analysis(run) if run and state=='succeeded' else None
        ref=sample.reference
        if ref is None: reference_pending+=1
        else:
            policy=(run.config.parameters or {}).get('projection_policy','customer-primary-v1') if run else 'customer-primary-v1'
            ev2=to_v2(ref,policy)[0];av2=to_v2(actual,policy)[0] if actual else None
            checks={key:bool(av2 and getattr(ev2,key)==getattr(av2,key)) for key in SEVEN}
            checks['seven_fields_all_correct']=all(checks.values())
            checks.update(email_semantics=bool(actual and all(getattr(ref,k)==getattr(actual,k) for k in ('sentiment','urgency','request_types','complaint_status'))),
                issue_count=bool(actual and len(ref.issues)==len(actual.issues)),issue_details=bool(actual and compare_issues(ref,actual)))
            for field,ok in checks.items():
                metrics[field]['denominator']+=1;metrics[field]['correct']+=int(ok)
                if not ok:mismatches.append(dict(sample_id=sample.sample_id,field=field,state=state))
            predicted=actual.issues if actual else [];pairs=align_issues(ref.issues,predicted)
            issue_alignment['reference_issues']+=len(ref.issues)
            issue_alignment['predicted_issues_on_referenced_samples']+=len(predicted)
            issue_alignment['matched']+=len(pairs);issue_alignment['unmatched_predictions']+=len(predicted)-len(pairs)
            for n,issue in enumerate(ref.issues):
                got=predicted[pairs[n]] if n in pairs else None
                issue_checks={k:bool(got and getattr(issue,k)==getattr(got,k)) for k in ISSUE_FIELDS}
                issue_checks['evidence']=bool(got and {digest(e.model_dump()) for e in issue.evidence}=={digest(e.model_dump()) for e in got.evidence})
                for k,ok in issue_checks.items():
                    field='issue_'+k;metrics[field]['denominator']+=1;metrics[field]['correct']+=int(ok)
                    if not ok:mismatches.append(dict(sample_id=sample.sample_id,issue_id=issue.issue_id,field=field,state=state))
        members.append(dict(sample_id=sample.sample_id,input_hash=sample.input_hash,run_id=run.run_id if run else None,
                            output_hash=run.metadata.get('analysis_v3_hash') if run else None,state=state,reference_hash=digest(ref.model_dump()) if ref else None))
    content={kind:dict(eligible=len(eligible),reviewed=0,pending=len(eligible),critical_errors=[],scores=[],status='PENDING') for kind in ('summary','reply')}
    reviewed=set()
    for review in reviews or []:
        key=(review['sample_id'],review['kind'])
        if key in reviewed or review['kind'] not in content: raise ValueError('Duplicate/invalid content review')
        reviewed.add(key);run=latest.get(review['sample_id'])
        if not run or review['sample_id'] not in {s.sample_id for s in eligible} or run.status!='succeeded' or run.metadata.get('fallback'): raise ValueError('No eligible successful output to review')
        for field,want in dict(run_id=run.run_id,input_hash=run.input_hash,cohort_id=run.cohort_id,output_hash=run.metadata['analysis_v3_hash']).items():
            if review.get(field)!=want: raise ValueError('Review binding mismatch')
        if review.get('status')!='approved' or not review.get('reviewer') or not review.get('evidence') or review.get('rubric_version')!='p35-content-rubric-v1': raise ValueError('Unapproved review')
        expected={'facts','requests','all_important_issues','no_invention','safety'}
        if set(review['scores'])!=expected or any(type(v) is not int or v not in (0,1,2) for v in review['scores'].values()): raise ValueError('Invalid rubric')
        c=content[review['kind']];c['reviewed']+=1;c['pending']-=1;c['scores'].append(review['scores']);c['critical_errors'].extend(review['critical_errors'])
    for c in content.values():
        c['status']='BLOCKED' if c['critical_errors'] else 'PENDING' if c['pending'] else 'REVIEWED'
    for m in metrics.values(): m['rate']=m['correct']/m['denominator'] if m['denominator'] else None
    selected=[r for r in latest.values() if r.email.email_id in {s.sample_id for s in eligible}]
    attempts=[a for r in runs if r.email.email_id in {s.sample_id for s in eligible} for a in r.attempts]
    structure=dict(attempts=len(attempts),parse_passed=sum(a.parse_status=='passed' for a in attempts),
        contract_passed=sum(a.contract_status=='passed' for a in attempts),
        retries=sum(max(0,len(r.attempts)-1) for r in runs if r.email.email_id in {s.sample_id for s in eligible}),
        dispatch_started=sum(a.metadata.get('dispatch') in ('started_or_unknown','response_received') for a in attempts),
        api_availability=None,evidence_matching='exact original substring validation only; not semantic entailment')
    return dict(protocol='e2e-v3-1',dataset_id=rows[0].dataset_id,dataset_hash=bound_hash,cohort_id=next(iter(cohorts),None),
        eligible=len(eligible),excluded=len(excluded),excluded_ids=[r.sample_id for r in excluded],attempted=sum(bool(latest.get(s.sample_id) and latest[s.sample_id].attempts) for s in eligible),
        succeeded=states['succeeded'],failed=states['failed'],pending=states['missing']+states['running']+states['interrupted_or_unknown'],states=dict(states),
        reference_pending=reference_pending,metrics=metrics,mismatches=mismatches,members=members,content=content,structure=structure,issue_alignment=issue_alignment,
        statistics=snapshot(selected,next(iter(cohorts)),rows[0].dataset_id) if selected else None,
        independent_accuracy=None,real_model_quality='PENDING',human_gold='PENDING',holdout='PENDING',
        caveat='Exact development/fixture reference agreement only. Issue matching uses exact evidence and object; paraphrases need human review.')
