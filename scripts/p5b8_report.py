"""Recompute new derived reports without API calls or changes to prior evidence."""
import csv,json,sys,statistics,random,math
from pathlib import Path
from collections import Counter
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b8_research import cases,summary,read,primary
from src.application.p5b7_research import B7Insights
from src.evaluation.classification_research import classification,build_report
from src.evaluation.p5b8_lexicon import predict
from src.domain.contracts import digest
DOC=ROOT/'docs/p5b8';LOCAL=ROOT/'.local/p5b8'
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def csvread(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def csvwrite(p,rows,fields=None):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def baseline():
    hist=csvread(ROOT/'docs/p5b7/forensics/HISTORICAL80_ALL.csv');rows=[]
    for h in hist:
        p=predict(h['subject']+'\n'+h['email_body']);rows.append(dict(case_id=h['email_id'],reference=h['sentiment_reference'],llm=h['sentiment_raw'],rule=p['legacy_three'],rule_detail=p,reference_status=h['reference_status'],source=h['reference_source']))
    old=build_report(ROOT,B7Insights(ROOT));write(DOC/'HISTORICAL_CLASSIFICATION.json',old)
    r=dict(version='p5b8-original-lexicon-2',n=80,identity='HISTORICAL_SYNTHETIC_ASSISTED_PROJECT_REFERENCE_NOT_INDEPENDENT_HUMAN_GOLD',definition='Legacy three-way reference; expression-v1 metrics NOT interchangeable. Mixed lexicon mapped by signed weighted sum only for this legacy comparison.',rule=classification([(r['reference'],r['rule']) for r in rows]),llm=classification([(r['reference'],r['llm']) for r in rows]),rows=rows,
        new_dimensions=dict(expressed_sentiment_accuracy=None,experience_accuracy=None,complaint_intent_accuracy=None,issue_sentiment_accuracy=None,source_attribution_accuracy_new=None,reason='No human Gold under new calibration definition'),kappa=None,double_human_annotations=0)
    write(DOC/'BASELINE.json',r);csvwrite(DOC/'BASELINE80.csv',rows);return r
def paired_stats(comp):
    rs=[r for r in comp['rows'] if r['delta']!='UNKNOWN'];n=len(rs);delta=[int(r['guided_primary'])-int(r['direct_primary']) for r in rs]
    improve=sum(x==1 for x in delta);regress=sum(x==-1 for x in delta);disc=improve+regress
    exact=min(1.,2*sum(math.comb(disc,i) for i in range(min(improve,regress)+1))/2**disc) if disc else 1.
    rng=random.Random(20261031);boots=sorted(sum(rng.choices(delta,k=n))/n for _ in range(5000)) if n else []
    return dict(n_judged=n,paired_difference=sum(delta)/n if n else None,paired_bootstrap_95=[boots[125],boots[4874]] if boots else None,exact_mcnemar_two_sided=exact,method='5000 paired bootstrap samples seed20261031; exact discordant binomial. Descriptive synthetic purposive cohort only; no general-population inference.')
def resources(rows):
    result=[]
    for c in rows:
        for variant,r in c['replies'].items():
            extra=[c['analysis']['call']] if 'GUIDED' in variant and c['analysis'] else []
            if variant=='B_DIRECT':
                p=LOCAL/'plans'/(c['case_id']+'.json')
                if p.exists():extra=[read(p)['call']]
            # An analysis in experiment A can be precomputed/shared; report marginal and charged path separately.
            result.append(dict(case_id=c['case_id'],variant=variant,reply_tokens=r['call']['metadata']['total_tokens'],reply_upper_cny=r['call']['cost_upper'],reply_ms=r['call']['elapsed_ms'],analysis_or_plan_tokens=sum(x['metadata']['total_tokens'] for x in extra),analysis_or_plan_upper_cny=sum(x['cost_upper'] for x in extra),analysis_or_plan_ms=sum(x['elapsed_ms'] for x in extra),path_tokens=r['call']['metadata']['total_tokens']+sum(x['metadata']['total_tokens'] for x in extra),path_upper_cny=r['call']['cost_upper']+sum(x['cost_upper'] for x in extra),path_ms=r['call']['elapsed_ms']+sum(x['elapsed_ms'] for x in extra)))
    return result
def main():
    rows=cases();r=summary(rows);b=baseline()
    for exp in ('A','B','independent'):r[exp]['paired_stats']=paired_stats(r[exp])
    cost=resources(rows)
    def path_summary(source):return {v:dict(n=len(rs),mean_tokens=statistics.mean(x['path_tokens'] for x in rs),mean_upper_cny=statistics.mean(x['path_upper_cny'] for x in rs),mean_serial_ms=statistics.mean(x['path_ms'] for x in rs)) for v in sorted({x['variant'] for x in source}) if (rs:=[x for x in source if x['variant']==v])}
    r['resource_paths']=path_summary([x for x in cost if x['case_id'].startswith('B7')]);r['independent_resource_paths']=path_summary([x for x in cost if x['case_id'].startswith('B8N')])
    # Independent audit of ALL original 18 failures; no retrospective rewrite of old contracts.
    failed=[]
    for p in sorted((ROOT/'.local/p5b7/B2').glob('*/run.json')):
        old=read(p)
        if old['status']=='succeeded':continue
        c=next(c for c in rows if c['case_id']==old['email']['email_id']);a=c['analysis'];replies=c['replies']
        failed.append(dict(case_id=c['case_id'],old_status=old['status'],old_error=old['attempts'][0]['error'],new_analysis_accepted=bool(a and a['data']),new_analysis_error=a['error'] if a else 'NOT_RUN',new_guided_reply_present=bool(replies.get('A_GUIDED',{}).get('reply')),new_guard_reviewable=replies.get('A_GUIDED',{}).get('checks',{}).get('reviewable'),semantic_certification='HUMAN_PENDING',comparability='NEW_SPLIT_CONTRACT_NOT_OLD_V32_REPAIR_RATE'))
    r['historical18_followup']=failed
    write(DOC/'RESULTS.json',r);write(DOC/'HISTORICAL18_FOLLOWUP.json',failed);csvwrite(DOC/'RESOURCE_PATHS.csv',cost)
    csvwrite(DOC/'AB_COMPARISON.csv',[dict(case_id=c['case_id'],dataset_role=c['dataset_role'],experiment=exp,input_hash=c['input_hash'],direct_full_first=c['replies'].get(exp+'_DIRECT',{}).get('display_reply','NOT_RUN'),guided_full_first=c['replies'].get(exp+'_GUIDED',{}).get('display_reply','NOT_RUN'),direct_parse_error=c['replies'].get(exp+'_DIRECT',{}).get('error'),guided_parse_error=c['replies'].get(exp+'_GUIDED',{}).get('error'),direct_run=c['replies'].get(exp+'_DIRECT',{}).get('call',{}).get('run_id'),guided_run=c['replies'].get(exp+'_GUIDED',{}).get('call',{}).get('run_id'),same_receipts=(c['replies'].get(exp+'_DIRECT',{}).get('runtime')==c['replies'].get(exp+'_GUIDED',{}).get('runtime')) if exp=='A' else False,paired_evaluation=next((x for x in r['independent' if c['case_id'].startswith('B8N') else exp]['rows'] if x['case_id']==c['case_id']),None)) for c in rows for exp in ('A','B') if exp+'_DIRECT' in c['replies'] or exp+'_GUIDED' in c['replies']])
    calls=[]
    for p in sorted((LOCAL/'calls').glob('*/*/response.json')):
        x=read(p);f=read(p.with_name('frozen-input.json'));calls.append(dict(stage=p.parent.parent.name,identity=p.parent.name,run_id=x['run_id'],input_tokens=x['metadata']['input_tokens'],output_tokens=x['metadata']['output_tokens'],total_tokens=x['metadata']['total_tokens'],upper_cny=x['cost_upper'],elapsed_ms=x['elapsed_ms'],response_id=x['metadata']['provider_response_id'],prompt_hash=f['config']['prompt_hash'],path=str(p.relative_to(ROOT)),raw_sha256=sha256(x['raw'].encode()).hexdigest()))
    csvwrite(DOC/'PROVIDER_CALLS.csv',calls)
    r['provider_totals']=dict(calls=len(calls),input_tokens=sum(x['input_tokens'] for x in calls),output_tokens=sum(x['output_tokens'] for x in calls),total_tokens=sum(x['total_tokens'] for x in calls),cost_peak_miss_upper=sum(x['upper_cny'] for x in calls),actual_bill='UNKNOWN')
    # Naturalness and new dimensions have no independent labels. Keep descriptive diagnostics only.
    r['new_dimension_distributions']={k:dict(Counter(c['analysis']['data'][k] for c in rows if c['case_id'].startswith('B7') and c['analysis'] and c['analysis']['data'])) for k in ('expressed_sentiment','experience_polarity','complaint_intent','urgency')}
    r['supplemental_guard_v2']={v:dict(n=len(rs),flagged=sum(bool(x['supplemental_checks']['hard_findings']) for x in rs),case_ids=[x['case_id'] for x in rs if x['supplemental_checks']['hard_findings']]) for v in r['arms'] if (rs:=[c['replies'][v] for c in rows if v in c['replies']])}
    r['judge_limitations']=['Same Provider as generation/analysis/reply; no human numerical truth','8 policy controls exact, but real H01-positive B8 calls absent; use inherited controls and deterministic safety tests only within their scopes','Score/code swap exact4/6; no independent annotator agreement','B7-009 future-intent vs completed-action H04 is disputed; frozen primary remains, human adjudication pending','Most judged replies at ceiling; 63/90 A unjudged; no total-population success claim','Ablation8 has praise-only coverage and no blinded preference scores; cannot isolate emotional contribution']
    r['final_workspace_guard']=dict(version='p5b8-workspace-guard-3-inherited-safety',n=len(rows),states=dict(Counter(c['workspace_quality']['status'] for c in rows)),blocked_case_ids=[c['case_id'] for c in rows if c['workspace_quality']['status']=='blocked'],identity='POSTHOC_PRODUCT_SAFETY_GATE_NOT_FROZEN_PRIMARY_ENDPOINT')
    write(DOC/'RESULTS.json',r)
    print(json.dumps(dict(A=r['A']['changes'],B=r['B']['changes'],independent=r['independent']['changes'],calls=r['budget']['reserved_attempts'],upper=r['budget']['settled_and_pending_upper_cny'],baseline=b['rule']['accuracy'],llm=b['llm']['accuracy']),ensure_ascii=False))
if __name__=='__main__':main()
