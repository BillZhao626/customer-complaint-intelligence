"""Failure-inclusive paired measures with separate validation-profile deltas."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from src.domain.contracts import EmailInput,digest
from src.evaluation.p310_audit import acceptance,diagnostics
from src.evaluation.p2_report import percentile
from src.evaluation.semantic_review_v2 import GUIDANCE


def evaluate(plan,runs,budget=None):
    body=dict(plan);claim=body.pop('plan_hash')
    if digest(body)!=claim:raise ValueError('Stored plan hash mismatch')
    by={}
    for r in runs:
        arm=r.config.parameters['arm'];key=(r.email.email_id,arm)
        if key in by or r.config.model_dump()!=plan['configs'].get(arm):raise ValueError('Duplicate or drifted run/config')
        expected=next((x for x in plan['inputs'] if x['email']['email_id']==r.email.email_id),None)
        if not expected or r.email.model_dump()!=expected['email'] or r.input_hash!=expected['input_hash']:raise ValueError('Input drift')
        by[key]=r
    members=[];arms={};pairs=[]
    for step in plan['schedule']:
        item=plan['inputs'][step['input_index']];email=EmailInput.model_validate(item['email'])
        r=by.get((email.email_id,step['arm']));raw=r.attempts[-1].raw_output if r and r.attempts else None
        old=acceptance(raw,email);new=acceptance(raw,email,'corrected')
        if r and (r.result is not None)!=old['accepted']:raise ValueError('Formal acceptance/raw replay drift')
        try:
            from src.application.live_execution import strict_json
            prediction=strict_json(raw)
        except (ValueError,TypeError):prediction=None
        scope='accepted_output' if r and r.result else 'failed_raw_diagnostic_only' if raw else 'no_prediction'
        members.append(dict(pair=step['pair'],sample_id=email.email_id,arm=step['arm'],run_id=r.run_id if r else None,
            input_hash=email.input_hash,config_hash=digest(plan['configs'][step['arm']]),original_email=email.model_dump(),
            original_status=r.status if r else 'unattempted',formal_accepted=bool(r and r.result),
            raw_sha256=sha256(raw.encode()).hexdigest() if isinstance(raw,str) else None,raw_prediction=prediction,
            original_profile=old,corrected_profile=new,findings=diagnostics(raw,email) if raw else [],
            attempts=[a.model_dump() for a in r.attempts] if r else [],
            semantic_dimensions={k:dict(state='unreviewed',severity_candidate=None,reason=v,evidence=None,
                scope=scope,human_score=None,human_critical_error=None) for k,v in GUIDANCE.items()},
            human_semantic_score=None,reply_status='unreviewed_unsent'))
    for arm in plan['configs']:
        subset=[x for x in members if x['arm']==arm];attempts=[a for m in subset for a in m['attempts']]
        vals=lambda k:[a['metadata'].get(k) for a in attempts]
        costs=vals('cost_cny');tokens=vals('total_tokens')
        arms[arm]=dict(planned=len(subset),accepted=sum(m['formal_accepted'] for m in subset),
            corrected_diagnostic_accepted=sum(m['corrected_profile']['accepted'] for m in subset),
            rejected_or_missing=sum(not m['formal_accepted'] for m in subset),unattempted=sum(m['original_status']=='unattempted' for m in subset),
            received=sum(a['metadata'].get('dispatch')=='response_received' for a in attempts),
            unknown_send=sum(a['metadata'].get('dispatch')=='started_or_unknown' for a in attempts),
            acceptance_denominator=len(subset),acceptance_rate=sum(m['formal_accepted'] for m in subset)/len(subset),
            input_tokens=sum(x or 0 for x in vals('input_tokens')),output_tokens=sum(x or 0 for x in vals('output_tokens')),
            total_tokens=sum(x or 0 for x in tokens),tokens_unknown=sum(x is None for x in tokens),
            cost_peak_miss_upper_cny=sum(x for x in costs if x is not None),cost_unknown=sum(x is None for x in costs),
            provider_p50_ms=percentile([a['elapsed_ms'] for a in attempts if a['elapsed_ms'] is not None],.5),
            provider_p95_ms=percentile([a['elapsed_ms'] for a in attempts if a['elapsed_ms'] is not None],.95),
            failure_stages=dict(Counter(m['original_profile']['stage'] for m in subset if not m['formal_accepted'])),
            human_content_quality=None,confirmed_critical_errors_human=None)
    for n,item in enumerate(plan['inputs'],1):
        pair=[m for m in members if m['pair']==n];status={m['arm']:m['formal_accepted'] for m in pair}
        delta=(int(status['challenger'])-int(status['champion'])) if set(status)=={'champion','challenger'} else None
        pairs.append(dict(pair=n,sample_id=item['email']['email_id'],acceptance=status,paired_acceptance_delta=delta,
                          run_ids={m['arm']:m['run_id'] for m in pair},human_semantic_winner=None))
    return dict(version='p310-paired-evaluation-v1',plan_hash=claim,phase=plan['phase'],arms=arms,pairs=pairs,members=members,
                paired_acceptance_improvements=sum(p['paired_acceptance_delta']==1 for p in pairs),
                paired_acceptance_regressions=sum(p['paired_acceptance_delta']==-1 for p in pairs),
                independent_gold='pending',independent_human_holdout='pending',human_content_review='pending',
                budget=budget,actual_invoice_cny=None,quality_promotion_recommended=False,
                comparison='Same original strict profile and reply gate; corrected-profile gains separate; human semantic scores null')


def export(report,out):
    from html import escape
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    summary={k:v for k,v in report.items() if k not in ('members','pairs')}
    (out/'REPORT.md').write_text('# P3.10 real-model measures\n\n```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf8')
    html=['<!doctype html><meta charset="utf-8"><style>body{font:16px system-ui;max-width:1100px;margin:30px auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #888}</style><h1>P3.10 paired evidence</h1><p>Unsent drafts. Contract acceptance is not semantic correctness. Human scores null.</p>']
    for m in report['members']:
        html+=['<article><h2>'+escape(f"{m['pair']} {m['arm']} {m['sample_id']} {m['original_status']}")+'</h2><pre>'+escape(json.dumps(m,ensure_ascii=False,indent=2))+'</pre></article>']
    (out/'REVIEW.html').write_text('\n'.join(html),encoding='utf8')
    return summary
