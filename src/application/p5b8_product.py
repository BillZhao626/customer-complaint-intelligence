"""Trace-bound adapter into the existing inbox, never a new provider response."""
import json
from src.domain.contracts import AnalysisRun,AnalysisResult,AnalysisAttempt,RunConfig,EmailInput,ErrorDTO,digest,idempotency_key
from src.application.p5b8_guard import inspect as check_reply
from src.application.p5b5_pipeline import now

def make_run(case):
    email=EmailInput.model_validate(case['email']);a=(case['analysis'] or {}).get('data');r=case['replies'].get('A_GUIDED')
    if not r:raise ValueError('Reply not yet dispatched')
    if not a or not r['reply']:
        config=RunConfig(backend='deepseek_live',model_id='deepseek-flash',schema_version='p5b8-calibration-1',prompt_version='p5b8-integrated-1',parameters=dict(experiment='p5b8',arm='分析增强回复',projection='explicit-display-v1-not-provider-prediction'))
        at=r['call']['metadata']['dispatch_at'];reason=(case['analysis'] or {}).get('error') or r['error'] or 'Analysis unavailable'
        attempt=AnalysisAttempt(attempt_no=1,started_at=at,finished_at=None,parse_status='passed' if r['reply'] else 'failed',contract_status='failed',normalization_status='failed',business_status='not_run',warnings=['Failed analysis/reply retained; no reviewable draft'],raw_output=r['call']['raw'],parsed_output=None,error=ErrorDTO(error_type='validation_error',message=reason,occurred_at=at),elapsed_ms=r['call']['elapsed_ms'],metadata=r['call']['metadata'])
        return AnalysisRun(run_id=r['call']['run_id'],idempotency_key=idempotency_key(email,config),email=email,input_hash=email.input_hash,config=config,cohort_id=config.cohort_id,status='failed',created_at=at,result=None,attempts=[attempt],metadata=dict(runtime=r['runtime'],evidence_identity='FAILED_REAL_CHAIN_NO_DRAFT',dataset_role=case['dataset_role'],annotation_status=case['annotation_status']))
    i=next((i for i in a['issues'] if i['object_type']=='product'),a['issues'][0]);sent=a['expressed_sentiment'];proc=i['business_process']
    result=AnalysisResult(store_location=a['mentioned_store'] or 'unknown',product_name=i['object_name'],product_category=i['category'],sentiment=sent if sent!='mixed' else 'unknown',urgency=a['urgency'],is_complaint=a['complaint_intent']=='yes',complaint_reason='other' if a['complaint_intent']=='yes' else 'none',source_attribution=proc if proc not in ('billing/invoice issue','none') else 'unclear' if a['complaint_intent']=='yes' else 'none',key_information=[q for i in a['issues'] for q in i['evidence']],summary='；'.join(i['object_name']+'：'+'；'.join(i['customer_requests']) for i in a['issues']),suggested_reply=r['reply'],confidence=0.0)
    config=RunConfig(backend='deepseek_live',model_id='deepseek-flash',schema_version='p5b8-calibration-1',prompt_version='p5b8-integrated-1',parameters=dict(experiment='p5b8',arm='分析增强回复',projection='explicit-display-v1-not-provider-prediction'))
    attempt=AnalysisAttempt(attempt_no=1,started_at=r['call']['metadata']['dispatch_at'],finished_at=None,parse_status='passed',contract_status='passed',normalization_status='mapped',business_status='warning',warnings=['Display projection from separately retained analysis and reply; not historical v3.2 acceptance'],raw_output=r['call']['raw'],parsed_output=json.loads(r['call']['raw']),error=None,elapsed_ms=r['call']['elapsed_ms'],metadata=r['call']['metadata'])
    return AnalysisRun(run_id=r['call']['run_id'],idempotency_key=idempotency_key(email,config),email=email,input_hash=email.input_hash,config=config,cohort_id=config.cohort_id,status='succeeded',created_at=r['call']['metadata']['dispatch_at'],result=result,attempts=[attempt],metadata=dict(p5b8=a,analysis_hash=digest(a),projection_hash=digest(result.model_dump()),runtime=r['runtime'],analysis_run_id=case['analysis']['call']['run_id'],reply_run_id=r['call']['run_id'],evidence_identity='REAL_CHAIN_DISPLAY_PROJECTION_NOT_RAW_ANALYSIS',dataset_role=case['dataset_role'],annotation_status=case['annotation_status']))
def stored(run):
    if not run.result or run.metadata['projection_hash']!=digest(run.result.model_dump()) or run.metadata['analysis_hash']!=digest(run.metadata['p5b8']):raise ValueError('B8 projection binding mismatch')
    raw=json.loads(run.attempts[0].raw_output)
    if raw!={'reply':run.result.suggested_reply}:raise ValueError('Reply raw binding mismatch')
    from src.application.p5b8_pipeline import validate_analysis
    validate_analysis(json.dumps(run.metadata['p5b8'],ensure_ascii=False),run.email)
    def align(q):
        for field in ('body','subject'):
            text=getattr(run.email,field);start=text.find(q)
            if start>=0:return dict(field=field,start=start,end=start+len(q),quote=q)
        return dict(field='body',start=0,end=len(q),quote=q)  # mismatch remains a block
    issues=[]
    for i in run.metadata['p5b8']['issues']:
        evidence=[align(q) for q in i['evidence']]
        issues.append(dict(i,evidence=evidence,risk_evidence=evidence if i['risk'] in ('minor','severe') else [],risk_level=i['risk']))
    return dict(run.result.model_dump(),issues=issues,complaint_status={'yes':'current_unresolved','no':'no_complaint','uncertain':'unknown'}[run.metadata['p5b8']['complaint_intent']])
def quality(run,data,reply,accepted):
    checks=check_reply(run.email,reply or '',run.metadata['runtime']);findings=[dict(f,scope='reply',severity='block',finding_id=digest(f)) for f in checks['hard_findings']]
    findings += [dict(f,scope='reply',severity='review',finding_id=digest(f)) for f in checks['review_findings']]
    from src.application.p5b5r2_guard import inspect as inherited, matching_stop
    from src.application.product_quality import dangerous_instruction
    prior=inherited(run.email,data,reply or '',accepted=accepted,events=run.metadata['runtime']['events'])
    for f in prior['findings']:
        if f['code']=='dangerous_reproduction' and not dangerous_instruction(reply or ''):continue
        if f['code']=='missing_stop_use_advice' and matching_stop(run.email,reply or ''):continue
        if f not in findings:findings.append(f)
    if not accepted:findings.append(dict(code='analysis_rejected',quote='',reason='Original chain rejected; no draft approval permitted',scope='analysis',severity='block',finding_id=digest('analysis_rejected')))
    return dict(version='p5b8-workspace-guard-3-inherited-safety',policy_version='p5b8-local-only',policy_hash=digest('p5b8-local-only'),status='blocked' if any(f['severity']=='block' for f in findings) else 'review_required',findings=findings,safety_review_required=prior.get('safety_review_required',False) or any(i['risk']=='severe' for i in run.metadata.get('p5b8',{}).get('issues',[])),human_approved=False,semantic_status='SEMANTIC_PROVISIONAL',reply_hash=digest(reply))
