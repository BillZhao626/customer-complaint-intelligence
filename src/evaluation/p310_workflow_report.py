"""Explicit initial-versus-correction accounting; no historical status rewrite."""
from hashlib import sha256
from src.domain.contracts import digest
from src.evaluation.p310_report import evaluate


def combine(initial_plan,initial_runs,correction_plan,correction_runs,budget=None):
    first=evaluate(initial_plan,initial_runs,budget)
    extra=evaluate(correction_plan,correction_runs,budget) if correction_plan else None
    initial={m['run_id']:m for m in first['members'] if m['run_id']}
    run_hashes={r.run_id:digest(r.model_dump()) for r in initial_runs}
    corrected={r.email.email_id:r for r in correction_runs}
    contexts={r['email']['email_id']:r['repair_context'] for r in correction_plan['inputs']} if correction_plan else {}
    by_parent={}
    for sample,context in contexts.items():
        parent=initial.get(context['parent_run_id'])
        if not parent or parent['arm']!='challenger' or parent['formal_accepted'] or parent['input_hash']!=context['input_hash'] or parent['raw_sha256']!=context['prior_raw_sha256'] or run_hashes[parent['run_id']]!=context['parent_run_hash']:
            raise ValueError('Correction must bind exact rejected Challenger first-pass raw')
        result=corrected.get(sample)
        if result and result.metadata.get('correction_parent_run_id') not in (None,context['parent_run_id']):raise ValueError('Correction lineage drift')
        by_parent[context['parent_run_id']]=result
    members=[]
    for m in first['members']:
        repair=by_parent.get(m['run_id']);ok=bool(m['formal_accepted'] or repair and repair.result)
        members.append(dict(sample_id=m['sample_id'],pair=m['pair'],arm=m['arm'],first_pass_run_id=m['run_id'],
            first_pass_accepted=m['formal_accepted'],correction_run_id=repair.run_id if repair else None,
            correction_attempted=repair is not None,workflow_accepted=ok,
            selected_run_id=repair.run_id if repair and repair.result else m['run_id'],
            original_status_unchanged=m['original_status'],human_semantic_score=None,
            correction_parent_preserved=True,reply_status='unreviewed_unsent'))
    arms={}
    for arm in first['arms']:
        chosen=[m for m in members if m['arm']==arm];prior=first['arms'][arm]
        n=sum(m['workflow_accepted'] for m in chosen)
        arms[arm]=dict(denominator=len(chosen),first_pass_accepted=prior['accepted'],first_pass_rate=prior['acceptance_rate'],
            final_accepted=n,final_acceptance_rate=n/len(chosen),rejected_or_missing=len(chosen)-n,
            additional_calls=sum(m['correction_attempted'] for m in chosen),
            base_tokens=prior['total_tokens'],base_cost_peak_upper_cny=prior['cost_peak_miss_upper_cny'],
            correction_tokens=extra['arms']['correction']['total_tokens'] if arm=='challenger' and extra else 0,
            correction_cost_peak_upper_cny=extra['arms']['correction']['cost_peak_miss_upper_cny'] if arm=='challenger' and extra else 0,
            human_content_quality=None)
    pairs=[]
    for n in range(1,len(initial_plan['inputs'])+1):
        selected={m['arm']:m for m in members if m['pair']==n}
        paired=set(selected)=={'champion','challenger'}
        pairs.append(dict(pair=n,sample_id=next(iter(selected.values()))['sample_id'],
            first_pass_delta=int(selected['challenger']['first_pass_accepted'])-int(selected['champion']['first_pass_accepted']) if paired else None,
            workflow_delta=int(selected['challenger']['workflow_accepted'])-int(selected['champion']['workflow_accepted']) if paired else None,
            members=selected,human_semantic_winner=None))
    body=dict(version='p310-explicit-workflow-report-v1',initial_plan_hash=initial_plan['plan_hash'],
        correction_plan_hash=correction_plan['plan_hash'] if correction_plan else None,arms=arms,members=members,pairs=pairs,
        workflow_improvements=sum(p['workflow_delta']==1 for p in pairs),workflow_regressions=sum(p['workflow_delta']==-1 for p in pairs),
        first_pass_improvements=sum(p['first_pass_delta']==1 for p in pairs),first_pass_regressions=sum(p['first_pass_delta']==-1 for p in pairs),
        first_pass_reuse=initial_plan['phase']=='development',initial_report=first,correction_report=extra,
        budget=budget,actual_invoice_cny=None,human_semantics='pending',independent_gold='pending',
        correction_budget_policy='one per rejected initial Challenger, fixed input order, within remaining canonical budget; no second correction',
        model_single_call_improvement_proven=False,quality_promotion_recommended=False)
    return dict(body,report_hash=digest(body))
