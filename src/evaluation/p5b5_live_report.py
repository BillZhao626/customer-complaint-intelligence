"""Read-only live evidence aggregation. Missing/failed attempts stay in denominator."""
from pathlib import Path
from contextlib import closing
from collections import Counter
import json,sqlite3,statistics
from src.evaluation.p5b5 import ROOT,read,hashfile,DIMENSIONS

LOCAL=ROOT/'.local/p5b5-live-20261030-v1'

def summary():
    if not (LOCAL/'authorization.json').exists():return dict(status='NOT_AUTHORIZED',calls=0,arms={},pairs=[])
    with closing(sqlite3.connect((LOCAL/'budget.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        calls=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
        cost=c.execute('SELECT COALESCE(SUM(cost),0) FROM settlements').fetchone()[0]
        unresolved=c.execute('SELECT COUNT(*) FROM reservations r LEFT JOIN settlements s USING(run_id) WHERE s.run_id IS NULL').fetchone()[0]
        halted=c.execute('SELECT halted FROM policy').fetchone()[0]
    arms={};raws={}
    for arm in ('B2','E1','E2','E3','E4'):
        rows=[read(p) for p in sorted((LOCAL/arm).glob('*/evaluation.json'))]
        times=[];tokens=0;events=[];languages=Counter();families=Counter();raws[arm]=rows
        for row in rows:
            run=read(row['run_path']);a=run['attempts'][0]
            times.append(a['elapsed_ms']);tokens+=a['metadata'].get('total_tokens') or 0
            events.extend(row['runtime']['events'])
            if row['error']:families[row['error']]+=1
            from src.application.research_policy_v2 import language,requested_language
            current=run['email']['body'].rsplit('[customer · current message]\n',1)[-1]
            want=requested_language(current)
            if want in ('zh','en'):languages['applicable']+=1;languages['pass']+=language(row['reply'])==want
        quant=lambda p:statistics.quantiles(times,n=100,method='inclusive')[int(p)-1] if len(times)>1 else times[0] if times else None
        arms[arm]=dict(n_total=18,n_run=len(rows),n_not_run=18-len(rows),provider_received=sum(x['provider_received'] for x in rows),
            contract_first=sum(x['first_contract'] for x in rows),contract_fail=sum(not x['first_contract'] for x in rows),
            semantic_human_pass=None,semantic_human_unknown=18,language=dict(languages),
            p50_ms=statistics.median(times) if times else None,p95_ms=quant(95),tokens=tokens,
            event_status_counts=dict(Counter(e['status'] for e in events)),external_business_execution=0,
            query_result_counts=dict(Counter(e['payload']['result']['status'] for e in events if 'result' in e['payload'])),
            errors=dict(families),complete=(LOCAL/arm/'results.json').exists())
    gold={g['case_id']:g for g in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    candidate='E4' if (LOCAL/'E4/results.json').exists() else 'E3'
    pairs=[]
    for left in raws['B2']:
        right=next((r for r in raws[candidate] if (r['case_id'],r['turn'])==(left['case_id'],left['turn'])),None)
        if not right:continue
        g=gold[left['case_id']]
        def ui(r):
            run=read(r['run_path']);attempt=run['attempts'][0]
            findings=[]
            if r['error']:
                reason=r['error']
                try:
                    from src.domain.analysis_v32 import validate
                    from src.domain.contracts import EmailInput
                    validate(json.loads(attempt['raw_output']),EmailInput.model_validate(run['email']))
                except (ValueError,TypeError) as exc:reason=str(exc)
                findings.append(dict(code=r['error'],quote='',reason=reason))
            return dict(run_id=r['run_id'],reply=r['reply'],raw=attempt['raw_output'],path=r['run_path'],first_contract=r['first_contract'],
                elapsed_ms=attempt['elapsed_ms'],config=run['config'],diagnostic=r['diagnostic'],
                historical_guard=dict(product_gate_pass=None,contract_pass=r['first_contract'],findings=findings,receipts=r['runtime']['events'],
                    product_readiness='See actual ProductStore import; contract pass alone is not review readiness'))
        pairs.append(dict(case_id=f'{left["case_id"]}-T{left["turn"]}',thread_id=left['case_id'],family=g['scenario_family'],
            input=dict(subject=g['title'],body=[m['text'] for m in g['input_messages'] if m['role']=='customer'][left['turn']-1]),
            reference_status='OWNER_DEV_GOLD',gold=g,runs=dict(b2=ui(left),b3=ui(right)),actual_versions=dict(b2='B2',b3=candidate)))
    judges=[];stability=[];judge_errors=[]
    def judge_result(path,key,reverse=False):
        record=read(path);j=record['parsed'];answers={x['slot']:x for x in j['answers']}
        order=list(reversed(key['order'])) if reverse else key['order'];normalized={}
        for slot,arm in zip(('A','B'),order):
            item=answers[slot]
            if set(item['scores'])!=set(DIMENSIONS):raise ValueError('Judge missing dimensions')
            if not all(v is None or type(v)is int and v in (0,1,2) for v in item['scores'].values()):raise ValueError('Invalid judge score')
            source=next(r for r in raws[arm] if r['case_id']==key['case_id'] and r['turn']==key['turn'])
            for f in item['hard_errors']:
                if f['quote'] not in source['reply']:raise ValueError('Judge quote not in raw reply')
            normalized[arm]=item
        return normalized
    for p in sorted((LOCAL/'judge-keys').glob('*.json')):
        key=read(p);base=LOCAL/'judge'/p.stem/'judgment.json'
        if not base.exists():continue
        try:
            j=judge_result(base,key)
            judges.append(dict(case_id=key['case_id'],turn=key['turn'],scores=j,path=str(base),identity='LLM_JUDGE_PROVISIONAL'))
            for suffix in ('reverse','repeat'):
                other=base.parent.with_name(base.parent.name+'-'+suffix)/'judgment.json'
                if not other.exists():continue
                jj=judge_result(other,key,suffix=='reverse')
                equal=sum(j[a]['scores'][d]==jj[a]['scores'][d] for a in j for d in DIMENSIONS)
                hard_equal=all({f['code'] for f in j[a]['hard_errors']}=={f['code'] for f in jj[a]['hard_errors']} for a in j)
                stability.append(dict(case_id=key['case_id'],turn=key['turn'],kind=suffix,equal_dimensions=equal,total_dimensions=10,hard_set_agrees=hard_equal))
        except (KeyError,TypeError,ValueError) as exc:judge_errors.append(dict(path=str(base),error=str(exc)))
    semantic={}
    for arm in ('B2',candidate):
        valid=[j['scores'][arm] for j in judges if arm in j['scores']]
        vals=[sum(x['scores'].values()) for x in valid if all(v is not None for v in x['scores'].values())]
        semantic[arm]=dict(n_total=18,n_judged=len(valid),n_not_run=18-len(valid),n_unknown=len(valid)-len(vals),n_complete=len(vals),mean_total=sum(vals)/len(vals) if vals else None,
            strict_all2=sum(all(v==2 for v in x['scores'].values()) and not x['hard_errors'] for x in valid),
            sensitivity_8=sum(all(type(v)is int and v>=1 for v in x['scores'].values()) and sum(x['scores'].values())>=8 and not x['hard_errors'] for x in valid),
            hard_error_turns=sum(bool(x['hard_errors']) for x in valid),identity='PROVISIONAL_LLM_NOT_HUMAN',human_agreement=None)
    return dict(status='HALTED' if halted else 'AUTHORIZED_RUNNING',calls=calls,cost_upper_cny=cost,actual_bill_cny=None,
        unresolved_billing=unresolved,halted=halted,arms=arms,pairs=pairs,judge_rows=judges,judge_errors=judge_errors,
        judge_stability=stability,semantic=semantic,promotion='NOT_PROMOTED',human_numeric_labels=0,
        judge_audit=dict(status='UNRELIABLE_FOR_PROMOTION',human_numeric_labels=0,
            known_policy_false_hard_flags=['CAL-03 B2: 可以请... is proposal, not execution','CAL-05 B2: 可以请... is proposal, not execution'],
            unconfirmed_candidate_misses=['CAL-05 E4 asks if broken shade affects power use; risk wording needs human review','CAL-07 E4 event incorrectly selects exchange from alternatives; v3 offline state fix not live retested'],
            raw_scores_unchanged=True,independent_judge_model=False),
        authorization_sha256=hashfile(LOCAL/'authorization.json'),dataset_hash=read(LOCAL/'authorization.json')['dataset_hash'],candidate=candidate,
        source_kind='NEW_REAL_MODEL_FIRST_OUTPUTS_ON_EXPOSED_SYNTHETIC_DEV')
