"""Replay real service records. Exact development agreement != human semantics."""
from collections import Counter
import json
from pathlib import Path
import statistics
from hashlib import sha256
from src.domain.contracts import digest
from src.domain.analysis_v3 import AnalysisV3, stored_analysis
from src.evaluation.e2e_v3 import SEVEN
from src.infrastructure.p36_budget import DevelopmentBudget
from src.infrastructure.dashboard_sources import ReadOnlyRepository


def percentile(values, q):
    if not values:return None
    values=sorted(values);pos=(len(values)-1)*q;lo=int(pos);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(pos-lo)


def development_comparison(inputs, runs):
    latest={r.email.email_id:r for r in sorted(runs,key=lambda r:(r.created_at,r.run_id))}
    rows=[]
    for item in inputs:
        if item['expected'] is None:continue
        run=latest.get(item['email']['email_id'])
        actual=run.result.model_dump() if run and run.status=='succeeded' and not run.metadata.get('fallback') else None
        checks={k:bool(actual is not None and actual[k]==item['expected'][k]) for k in SEVEN}
        rows.append(dict(sample_id=item['email']['email_id'],input_hash=item['input_hash'],reference_hash=item['reference_hash'],
            run_id=run.run_id if run else None,status=run.status if run else 'missing',expected=item['expected'],
            actual={k:actual[k] for k in SEVEN} if actual else None,checks=checks,all_correct=all(checks.values()),
            exclude_clean=item['exclude_clean']))
    def metrics(selected):
        n=len(selected)
        return dict(samples=n,field_denominator=n*7,field_correct=sum(sum(r['checks'].values()) for r in selected),
            per_field={k:dict(correct=sum(r['checks'][k] for r in selected),denominator=n) for k in SEVEN},
            all_correct=sum(r['all_correct'] for r in selected),all_denominator=n,
            missing_prediction=sum(r['actual'] is None for r in selected))
    return dict(rows=rows,all24=metrics(rows),clean23=metrics([r for r in rows if not r['exclude_clean']]),
                basis='Frozen research-owner development adjudication v1.1; exposed calibration, not independent Gold')


def diagnose_attempt(attempt, email):
    result=dict(json=attempt.parse_status,schema=False,exact_spans=None,reply_gate=None,errors=[])
    if attempt.parsed_output is None:return result
    try:value=AnalysisV3.model_validate(attempt.parsed_output)
    except ValueError as exc:
        result['errors']=[dict(type=e['type'],loc=list(e['loc']),message=e['msg']) for e in exc.errors()] if hasattr(exc,'errors') else ['schema_invalid']
        return result
    result['schema']=True
    ev=[e for i in value.issues for e in i.evidence+i.importance_evidence]+[e for r in value.relations for e in r.evidence]
    checks=[dict(e.model_dump(),valid=getattr(email,e.field)[e.start:e.end]==e.quote,
                 unique_quote=getattr(email,e.field).count(e.quote)==1,
                 located_start=getattr(email,e.field).find(e.quote)) for e in ev]
    result['exact_spans']=dict(valid=sum(e['valid'] for e in checks),denominator=len(checks),spans=checks)
    from src.application.v3_safety import check_reply
    try:check_reply(value);result['reply_gate']='passed'
    except ValueError:result['reply_gate']='rejected_requires_semantic_review'
    return result


def generate(space, name):
    space=Path(space);out=space/name;manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    data=json.loads((space/'inputs-v1.json').read_text(encoding='utf8'))
    assert digest(data)==manifest['inputs_hash']
    runs=ReadOnlyRepository(out/'runs.sqlite3').list_runs()
    assert all(r.config.model_dump()==manifest['config'] for r in runs)
    allowed={x['email']['email_id']:x for x in data['inputs']}
    assert all(r.email.model_dump()==allowed[r.email.email_id]['email'] and r.input_hash==allowed[r.email.email_id]['input_hash'] for r in runs)
    by_id={r.email.email_id:r for r in runs}
    attempts=[(r,a) for r in runs for a in r.attempts if a.metadata.get('dispatch') in ('response_received','started_or_unknown')]
    successes=[r for r in runs if r.status=='succeeded']
    comparison=development_comparison(data['inputs'],runs)
    diagnostics=[dict(sample_id=r.email.email_id,run_id=r.run_id,attempt=a.attempt_no,
        service_error=a.error.error_type if a.error else None,**diagnose_attempt(a,r.email)) for r,a in attempts]
    usage={k:dict(known_sum=sum(a.metadata.get(k) or 0 for _,a in attempts),known_requests=sum(a.metadata.get(k) is not None for _,a in attempts),denominator=len(attempts)) for k in ('input_tokens','output_tokens','total_tokens')}
    costs=[a.metadata.get('cost_cny') for _,a in attempts]
    span_diags=[d['exact_spans'] for d in diagnostics if d['exact_spans'] is not None]
    metrics=dict(planned=36,logical_attempted=len(runs),succeeded=len(successes),failed=sum(r.status=='failed' for r in runs),
        interrupted=sum(r.status=='interrupted_or_unknown' for r in runs),missing=36-len(runs),http_requests=len(attempts),
        response_received=sum(a.metadata.get('dispatch')=='response_received' for _,a in attempts),
        json_legal=sum(a.parse_status=='passed' for _,a in attempts),schema_legal=sum(d['schema'] for d in diagnostics),
        contract_accepted=sum(a.contract_status=='passed' for _,a in attempts),request_denominator=len(attempts),
        logical_denominator=len(runs),retries=sum(max(0,len(r.attempts)-1) for r in runs),fallback=sum(bool(r.metadata.get('fallback')) for r in runs),
        provider_latency_ms=dict(n=len(attempts),p50=percentile([a.elapsed_ms for _,a in attempts if a.elapsed_ms is not None],.5),p95=percentile([a.elapsed_ms for _,a in attempts if a.elapsed_ms is not None],.95)),
        orchestration_latency_ms=dict(p50=percentile([r.metadata['elapsed_ms'] for r in runs if 'elapsed_ms' in r.metadata],.5),p95=percentile([r.metadata['elapsed_ms'] for r in runs if 'elapsed_ms' in r.metadata],.95)),
        usage=usage,estimated_peak_cache_miss_cny=sum(c for c in costs if c is not None),cost_known_requests=sum(c is not None for c in costs),actual_billed_cny=None,
        resolved_models=dict(Counter(a.metadata.get('resolved_model') or 'unknown' for _,a in attempts)),
        exact_span_valid=sum(d['valid'] for d in span_diags),exact_span_denominator=sum(d['denominator'] for d in span_diags),
        span_evaluable_requests=len(span_diags),evidence_semantic_support='HUMAN_CONTENT_REVIEW_PENDING')
    metrics.update(success_rate=len(successes)/len(runs) if runs else None,
        failure_rate=sum(r.status=='failed' for r in runs)/len(runs) if runs else None,
        schema_legal_rate=sum(d['schema'] for d in diagnostics)/len(attempts) if attempts else None)
    packet=[]
    for item in data['inputs']:
        r=by_id.get(item['email']['email_id']);v=stored_analysis(r) if r and r.result else None
        packet.append(dict(sample_id=item['email']['email_id'],input=item['email'],input_hash=item['input_hash'],
            run_id=r.run_id if r else None,cohort_id=r.cohort_id if r else None,output_hash=r.metadata.get('analysis_v3_hash') if r else None,
            reference_hash=item['reference_hash'],seven_field_reference=item['expected'],reference_kind='owner_development' if item['expected'] else 'none',
            prediction=v.model_dump() if v else None,status='pending',reviewer=None,human_declaration=False,
            unaccepted_parsed_outputs=[a.parsed_output for a in r.attempts] if r and not v else [],
            rubric_version='p36-semantic-content-v1',issue_reference_status='PENDING_NOT_GOLD',
            scores={k:None for k in ('issue_count','omission','duplication','object_reason','emotion','resolution','handling_order','attribution_uncertainty','evidence_support','summary_coverage','summary_invention','reply_requests','reply_safety','refund_compensation_commitment')},
            critical_errors=[],evidence_notes=[],ai_candidate_notes=[]))
    result=dict(experiment=name,cohort_id=next(iter(runs)).cohort_id if runs else None,metrics=metrics,comparison=comparison,
        diagnostic_gate_sha256=sha256((Path(__file__).resolve().parents[1]/'application/v3_safety.py').read_bytes()).hexdigest(),
        diagnostic_note='Posthoc gate diagnosis uses the hash above; accepted/failed metrics always use original persisted attempts.',
        diagnostics=diagnostics,budget=DevelopmentBudget(space/'budget.sqlite3').summary(),
        issue_semantic_metrics=dict(reference_approved=0,denominator=36,missing_predictions=36-len(successes),quality_rate=None),
        content=dict(summary_pending=36,reply_pending=36,evidence_support_pending=36),
        status=dict(REAL_MODEL_PILOT_VERIFIED=bool(attempts),DEVELOPMENT_SEMANTIC_EVALUATED=bool(comparison['rows']),
                    HUMAN_CONTENT_REVIEW_PENDING=True,INDEPENDENT_HOLDOUT_PENDING=True),
        caveat='A failed/missing prediction counts as incorrect. No reference on candidate12; no v3 issue Gold or signed content score.')
    # Reports are versioned; never overwrite earlier replay or review edits.
    version=1
    while (out/f'report-v{version}.json').exists():version+=1
    for file,value in ((f'report-v{version}.json',result),(f'human-review-v{version}.json',packet),(f'comparison24-v{version}.json',comparison)):
        with (out/file).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
    lines=[f'# {name} 真实模型开发试点', '仅开发校准，不是独立Holdout。摘要、回复和问题级语义待真人审核。',
           '```json',json.dumps(metrics,ensure_ascii=False,indent=2),'```',
           '## 冻结24题逐题比较', '|ID|状态|一致字段/7|不一致字段|', '|---|---|---:|---|']
    lines += [f'|{r["sample_id"]}|{r["status"]}|{sum(r["checks"].values())}|{", ".join(k for k,v in r["checks"].items() if not v)}|' for r in comparison['rows']]
    lines += ['\n24题全部与排除F176后的23题分别统计：','```json',json.dumps({k:v for k,v in comparison.items() if k!='rows'},ensure_ascii=False,indent=2),'```']
    (out/f'REPORT-v{version}.md').write_text('\n\n'.join(lines),encoding='utf8')
    return str(out/f'REPORT-v{version}.md')
