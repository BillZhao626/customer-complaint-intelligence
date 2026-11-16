"""Read-only views of persisted experiment evidence, keyed by existing Case ID."""
import json,statistics,math
from pathlib import Path
from collections import Counter,defaultdict
from src.application.p5b8_pipeline import check_reply
from src.evaluation.p5b8_lexicon import predict
from src.domain.contracts import EmailInput
ROOT=Path(__file__).resolve().parents[2];LOCAL=ROOT/'.local/p5b8'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def maybe(p):return read(p) if Path(p).exists() else None
def readable_reply(row):
    """Display a complete JSON string value even if the object delimiter failed.

    This never changes the original parse outcome, draft eligibility or Judge input.
    """
    if row['reply']:return row['reply']
    import re
    raw=row['call']['raw'];m=re.search(r'"reply"\s*:\s*',raw)
    if m:
        try:
            value,_=json.JSONDecoder().raw_decode(raw[m.end():])
            if isinstance(value,str):return value
        except ValueError:pass
    return raw
def cases():
    plan=read(LOCAL/'plan.json');rows=[]
    for eid in plan['A_ids']+[s['id'] for s in plan['independent_scenarios']]:
        p=ROOT/'.local/p5b7/dataset'/(eid+'.json') if eid.startswith('B7') else LOCAL/'new-dataset'/(eid+'.json')
        if not p.exists():continue
        d=read(p);e=EmailInput(email_id=eid,subject=d['subject'],body=d['body']);a=maybe(LOCAL/'analysis'/(eid+'.json'))
        replies={v:r for v in ('A_DIRECT','A_GUIDED','B_DIRECT','B_GUIDED','NO_SENTIMENT') if (r:=maybe(LOCAL/'replies'/v/(eid+'.json'))) is not None}
        judges=[read(p) for p in sorted((LOCAL/'judgments').glob('*'+eid+'*.json'))]
        old={v:r for v in ('B2','R3','C1') if (r:=maybe(ROOT/'.local/p5b7'/v/eid/'run.json')) is not None}
        flags=[]
        if eid in e.body or re_search_generation_artifact(e.body):flags.append(dict(variant='GENERATION',family='SYNTHETIC_NATURALNESS_CANDIDATE',detail='Case identifier or synthetic marker occurs in customer prose; retain in denominator, review naturalness.'))
        for v,r in replies.items():
            r['display_reply']=readable_reply(r)
            from src.application.p5b8_guard import inspect
            r['supplemental_checks']=inspect(e,r['reply'],r['runtime'])
            if r['error']:flags.append(dict(variant=v,family='REPLY_PARSE',detail=r['error']))
            flags.extend(dict(variant=v,family='PARSE_BLOCKED_LANGUAGE_NOT_EVALUATED' if r['error'] and f['code']=='LANGUAGE' else f['code'],detail=f) for f in r['checks']['hard_findings'])
            flags.extend(dict(variant=v,family='GUARD_V2_'+f['code'],detail=f) for f in r['supplemental_checks']['hard_findings'] if f not in r['checks']['hard_findings'])
        if a and a['error']:flags.append(dict(variant='ANALYSIS',family='ANALYSIS_CONTRACT',detail=a['error']))
        baseline=predict(e.subject+'\n'+e.body)
        if a and a['data'] and baseline['expressed_sentiment']!=a['data']['expressed_sentiment']:flags.append(dict(variant='BASELINE_VS_LLM',family='PREDICTION_DISAGREEMENT_NOT_GOLD',detail=dict(rule=baseline['expressed_sentiment'],llm=a['data']['expressed_sentiment'])))
        for j in judges:
            if j['error']:flags.append(dict(variant=j['experiment'],family='JUDGE_PARSE',detail=j['error']))
            for answer in (j['parsed'] or {}).get('answers',[]):
                v=j['order'][['A','B'].index(answer['slot'])]
                flags.extend(dict(variant=v,family='JUDGE_'+f['code'],detail=f) for f in answer['hard_errors'])
        repair=maybe(LOCAL/'repairs'/(eid+'.json'));repair_judge=maybe(LOCAL/'repair-judgments'/(eid+'.json'))
        if repair:
            if repair['analysis_error'] or repair['reply_error']:flags.append(dict(variant='GUIDED_R2',family='REPAIR_STILL_FAILED',detail=repair['analysis_error'] or repair['reply_error']))
        rows.append(dict(case_id=eid,email=e.model_dump(),input_hash=e.input_hash,language='zh' if any('\u4e00'<=c<='\u9fff' for c in e.body) else 'en',source='LLM_SYNTHETIC',family=d['family'],dataset_role='DEV_REGRESSION_EXPOSED_B7' if eid.startswith('B7') else 'INDEPENDENT_SYNTHETIC_FAMILY_TRANSFER_NOT_HUMAN_GOLD',annotation_status='MODEL_PROVISIONAL_NO_HUMAN_GOLD',analysis=a,baseline=baseline,replies=replies,judges=judges,repair=repair,repair_judge=repair_judge,historical_runs=old,findings=flags))
    from src.application.p5b8_product import make_run,stored,quality
    for row in rows:
        if 'A_GUIDED' not in row['replies']:continue
        run=make_run(row);gate=quality(run,stored(run) if run.status=='succeeded' else None,row['replies']['A_GUIDED']['reply'],run.status=='succeeded')
        row['workspace_quality']=gate
        row['findings'].extend(dict(variant='SAVED_GUIDED_WORKSPACE',family='WORKSPACE_'+f['code'],detail=f) for f in gate['findings'] if f['severity']=='block')
    return rows
def re_search_generation_artifact(text):
    import re
    return bool(re.search(r'synthetic customer case|合成客户案例',text,re.I))
def wilson(k,n):
    if not n:return None
    z=1.95996398454;center=(k/n+z*z/(2*n))/(1+z*z/n);half=z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [center-half,center+half]
def primary(answer):return not answer['hard_errors'] and answer['scores']['B1']==2 and answer['scores']['B2']==2
def comparison(rows,experiment,independent=False):
    selected=[r for r in rows if r['case_id'].startswith('B8N')==independent and experiment+'_DIRECT' in r['replies'] and experiment+'_GUIDED' in r['replies']];out=[]
    for r in selected:
        j=next((j for j in r['judges'] if j['experiment']==experiment and not j['swap']),None);a=b=None
        if j and j['parsed']:
            mapped={j['order'][['A','B'].index(ans['slot'])]:ans for ans in j['parsed']['answers']};a=mapped[experiment+'_DIRECT'];b=mapped[experiment+'_GUIDED']
        ap,bp=primary(a) if a else None,primary(b) if b else None
        out.append(dict(case_id=r['case_id'],direct_primary=ap,guided_primary=bp,delta='UNKNOWN' if ap is None or bp is None else 'IMPROVED' if bp and not ap else 'REGRESSED' if ap and not bp else 'TIED',direct_judge=a,guided_judge=b,judge_preference=(j['order'][0] if j['parsed']['preference']=='A' else j['order'][1] if j['parsed']['preference']=='B' else j['parsed']['preference']) if j and j['parsed'] else 'UNKNOWN'))
    scored=[x for x in out if x['delta']!='UNKNOWN'];n=len(selected);counts=Counter(x['delta'] for x in out)
    return dict(n_dispatched_pairs=n,n_judged=len(scored),changes=dict(counts),direct_primary_pass=sum(x['direct_primary'] is True for x in out),guided_primary_pass=sum(x['guided_primary'] is True for x in out),
        direct_wilson_judged=wilson(sum(x['direct_primary'] is True for x in scored),len(scored)),guided_wilson_judged=wilson(sum(x['guided_primary'] is True for x in scored),len(scored)),
        evidence_status='AUTOMATED_PROVISIONAL_NOT_HUMAN_CERTIFIED',rows=out)
def insight(rows):
    valid=[r for r in rows if r['analysis'] and r['analysis']['data']];den=[r['case_id'] for r in valid];products=defaultdict(lambda:defaultdict(set));stores=defaultdict(lambda:defaultdict(set))
    memberships={name:[] for name in ('expressed_negative','negative_experience','negative_product_experience','complaint','mixed','unknown')}
    for r in valid:
        a=r['analysis']['data'];eid=r['case_id']
        if a['expressed_sentiment']=='negative':memberships['expressed_negative'].append(eid)
        if a['experience_polarity']=='negative':memberships['negative_experience'].append(eid)
        if any(i['object_type']=='product' and i['experience_polarity']=='negative' for i in a['issues']):memberships['negative_product_experience'].append(eid)
        if a['complaint_intent']=='yes':memberships['complaint'].append(eid)
        if a['expressed_sentiment']=='mixed':memberships['mixed'].append(eid)
        if a['expressed_sentiment']=='unknown':memberships['unknown'].append(eid)
        from src.application.p5b7_research import canonical_store
        store=canonical_store(a['mentioned_store'] or 'unknown');stores[store]['all'].add(eid)
        if a['complaint_intent']=='yes':stores[store]['complaints'].add(eid)
        for i in a['issues']:
            if i['object_type']!='product':continue
            p=products[i['category']];p['all'].add(eid)
            if i['experience_polarity']=='negative':p['negative_experience'].add(eid)
            if i['sentiment']=='negative':p['negative_issue_sentiment'].add(eid)
            if a['expressed_sentiment']=='negative':p['expressed_negative'].add(eid)
            if i['issue_kind']=='complaint':p['complaints'].add(eid)
    def pack(groups):return {k:{name:dict(n=len(ids),case_ids=sorted(ids)) for name,ids in v.items()} for k,v in groups.items()}
    issues=[dict(case_id=r['case_id'],**i) for r in valid for i in r['analysis']['data']['issues']]
    return dict(n_dispatched=len(rows),valid=len(valid),failed_or_not_run=len(rows)-len(valid),denominator_case_ids=den,memberships=memberships,products=pack(products),stores=pack(stores),global_experience_counts=dict(Counter(r['analysis']['data']['experience_polarity'] for r in valid)),issue_counts=dict(total=len(issues),sentiment=dict(Counter(i['sentiment'] for i in issues)),experience=dict(Counter(i['experience_polarity'] for i in issues)),kind=dict(Counter(i['issue_kind'] for i in issues))),issue_rows=issues,source='P5B8_MODEL_CALIBRATION_NOT_GOLD',unit='email-category deduplicated; negative is strict five-way label, mixed reported separately; issue sentiment separate from experience and expression',unknown_store=len(stores['unknown']['all']))
def summary(rows=None):
    rows=cases() if rows is None else rows
    from scripts.p5b8_live import status
    arms={}
    for v in ('A_DIRECT','A_GUIDED','B_DIRECT','B_GUIDED','NO_SENTIMENT'):
        rs=[r['replies'][v] for r in rows if v in r['replies']];times=[x['call']['elapsed_ms'] for x in rs]
        arms[v]=dict(n=len(rs),nonempty=sum(bool(x['reply']) for x in rs),rule_reviewable=sum(x['checks']['reviewable'] for x in rs),rule_hard=sum(bool(x['checks']['hard_findings']) for x in rs),language_matches=sum(x['checks']['language']['matches'] for x in rs),tokens=sum(x['call']['metadata']['total_tokens'] for x in rs),cost_upper=sum(x['call']['cost_upper'] for x in rs),latency_ms_p50=statistics.median(times) if times else None)
    analysis=[r['analysis'] for r in rows if r['analysis']];controls=[read(p) for p in sorted((LOCAL/'controls').glob('*.json'))];control_counts=Counter()
    for c in controls:
        if not c['parsed']:control_counts['UNKNOWN']+=1;continue
        exp=set(c['control']['expected_hard_codes']);actual={x['code'] for a in c['parsed']['answers'] for x in a['hard_errors']}
        control_counts['EXACT' if exp==actual else 'DISAGREED']+=1
    swaps=[]
    for r in rows:
        orig=next((j for j in r['judges'] if j['experiment']=='A' and not j['swap']),None);swap=next((j for j in r['judges'] if j['swap']),None)
        if orig and swap:
            def mapping(j):return {j['order'][['A','B'].index(a['slot'])]:dict(scores=a['scores'],hard_codes=sorted(x['code'] for x in a['hard_errors'])) for a in (j['parsed'] or {}).get('answers',[])}
            swaps.append(dict(case_id=r['case_id'],valid=bool(orig['parsed'] and swap['parsed']),same_scores_and_codes=mapping(orig)==mapping(swap),first=mapping(orig),swap=mapping(swap)))
    return dict(version='p5b8-results-1',status='IMPROVED_NOT_CERTIFIED',historical_B7=dict(dispatched=90,first_accepted=72,first_failed=18,identity='IMMUTABLE_HISTORICAL_B2'),budget=status(),arms=arms,
        analysis=dict(n=len(analysis),accepted=sum(x['data'] is not None for x in analysis),failed=sum(x['error'] is not None for x in analysis),cost_upper=sum(x['call']['cost_upper'] for x in analysis),tokens=sum(x['call']['metadata']['total_tokens'] for x in analysis),latency_ms_p50=statistics.median([x['call']['elapsed_ms'] for x in analysis]) if analysis else None),
        A=comparison(rows,'A'),B=comparison(rows,'B'),independent=comparison(rows,'A',True),controls=dict(control_counts),swaps=swaps,insights=insight([r for r in rows if r['case_id'].startswith('B7')]),human_gold_new=0,human_double_annotations=0,kappa=None)
