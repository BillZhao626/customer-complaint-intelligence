"""Deterministic recomputation over saved B7 evidence. No provider calls."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset.research_generation import audit
from src.application.research_insights import read_csv,file_hash
from src.application.p5b7_research import B7Insights
from src.domain.contracts import EmailInput
from src.domain.analysis_v32 import validate
from src.evaluation.p5b5r2_judge import controls,parse_judgment
from scripts.p5b7_live import status

LOCAL=ROOT/'.local/p5b7';DOC=ROOT/'docs/p5b7'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def quantile(v,q):
    v=sorted(v);return v[min(len(v)-1,int((len(v)-1)*q))] if v else None
def body_audit(ds):
    output={}
    for lang in ('zh','en'):
        rows=[d['body'] for d in ds if ('zh' if any('\u4e00'<=c<='\u9fff' for c in d['body']) else 'en')==lang]
        output[lang]=audit(rows)
    return output
def analyze_runs(arm):
    records=[];fail=[]
    for path in sorted((LOCAL/arm).glob('B7-*/run.json')):
        r=read(path);attempt=r['attempts'][0];data=attempt.get('parsed_output') or {};e=read(path.with_name('evaluation.json'))
        reason=None
        if r['status']!='succeeded':
            try:validate(data,EmailInput.model_validate(r['email']),context_check_profile=r['config']['parameters'].get('context_check_profile'))
            except (ValueError,TypeError,KeyError) as exc:reason=str(exc)
            fail.append(dict(email_id=r['email']['email_id'],run_id=r['run_id'],error=attempt.get('error'),root_validation=reason))
        records.append(dict(email_id=r['email']['email_id'],run=r,evaluation=e,data=data,validation_reason=reason))
    meta=[r['run']['attempts'][0]['metadata'] for r in records]
    ms=[r['run']['attempts'][0]['elapsed_ms'] for r in records]
    from src.application.research_policy_v2 import language,requested_language
    from src.application.reply_review import inspect_reply
    from src.application.p5b7_context_checks import reply_review
    reply_metrics=dict(n=len(records),nonblank=sum(bool(r['evaluation']['reply'].strip()) for r in records),
        language_matches=sum(language(r['evaluation']['reply'])==requested_language(r['run']['email']['body']) for r in records),
        lexical_no_signal=sum(not (reply_review(r['evaluation']['reply'],r['run']['email']['body']) if r['run']['config']['parameters'].get('context_check_profile') else inspect_reply(r['evaluation']['reply']))['findings'] for r in records),
        semantic_success=None,identity='PRESENCE_LANGUAGE_AND_LEXICAL_CHECKS_NOT_QUALITY_ACCURACY',
        resource_accounting='Analysis and reply share one model completion. Tokens, fee and latency cannot be split without double counting. Local tasks have zero model tokens/fees; first task latency was not instrumented.')
    return records,dict(n=len(records),provider_received=sum(m.get('dispatch')=='response_received' for m in meta),accepted=sum(r['run']['status']=='succeeded' for r in records),
        json_valid=sum(r['run']['attempts'][0]['parse_status']=='passed' for r in records),failed=fail,
        first_success_rate=sum(r['run']['status']=='succeeded' for r in records)/len(records) if records else None,
        latency_ms=dict(p50=quantile(ms,.5),p95=quantile(ms,.95),max=max(ms) if ms else None),
        tokens={k:sum(m.get(k) or 0 for m in meta) for k in ('input_tokens','output_tokens','total_tokens')},cost_peak_miss_upper_cny=sum(m.get('cost_cny') or 0 for m in meta),
        semantics='NO_INDEPENDENT_HUMAN_GOLD',first_only=True,reply_layer=reply_metrics,
        rule_findings=sum(bool(r['evaluation']['diagnostic'].get('hard_findings')) for r in records),
        local_events=Counter(e['status'] for r in records for e in r['evaluation']['runtime']['events']),
        external_business_actions=0)

def main():
    DOC.mkdir(parents=True,exist_ok=True)
    ds=[read(p) for p in sorted((LOCAL/'dataset').glob('*.json'))]
    old=read_csv(ROOT/'data/synthetic/customer_emails_full_v1.csv')
    rows={};arms={}
    for arm in ('B2','R3','C1'):
        records,summary=analyze_runs(arm)
        if records:rows[arm]=records;arms[arm]=summary
    plan=read(LOCAL/'generation-plan.json');byjob={j['id']:j for j in plan['jobs']}
    consistency=[]
    for rec in rows.get('B2',[]):
        j=byjob[rec['email_id']];expected=j['config']['intended_tone'];data=rec['data']
        consistency.append(dict(email_id=rec['email_id'],run_id=rec['run']['run_id'],subject=rec['run']['email']['subject'],family=j['family'],intent=expected,predicted=data.get('sentiment'),
            matches=None if expected=='mixed' else data.get('sentiment')==expected,accepted=rec['run']['status']=='succeeded',identity='GENERATOR_INTENT_DIAGNOSTIC_NOT_ACCURACY'))
    judge=[];ctrl={r['id']:r for r in controls()};controls_counts=Counter();preferences=Counter();hard_counts=Counter()
    for p in sorted((LOCAL/'JUDGE').glob('*/response.json')):
        response=read(p);frozen=read(p.with_name('frozen-input.json'));payload=frozen['payload'];identity=p.parent.name
        blind=payload.get('blind_payload',payload)
        try:parsed=parse_judgment(response['raw'],blind);error=None
        except (ValueError,TypeError,KeyError,AttributeError) as exc:parsed=None;error=str(exc)
        row=dict(id=identity,parsed=parsed,parse_error=error,payload=payload,raw=response['raw'],metadata=response['metadata'])
        if identity.startswith('control-'):
            c=ctrl[identity[8:]];expected=set(c['expected_hard_codes']);actual={h['code'] for a in (parsed or {}).get('answers',[]) for h in a['hard_errors']}
            row.update(control_reference_identity=c['identity'],expected_codes=list(expected),predicted_codes=list(actual))
            if parsed:
                for code in expected|actual:controls_counts['TP' if code in actual and code in expected else 'FN' if code in expected else 'FP']+=1
                if not actual and not expected:controls_counts['TN_clean_reply']+=1
                controls_counts['valid']+=1
            else:controls_counts['unknown']+=1
        elif parsed:
            order=payload['slot_order'];pref=parsed['preference'];preferences[order[0] if pref=='A' else order[1] if pref=='B' else pref]+=1
            for a in parsed['answers']:
                arm=order[['A','B'].index(a['slot'])];hard_counts[arm]+=len(a['hard_errors'])
        judge.append(row)
    paired=[]
    byarm={a:{r['email_id']:r for r in rs} for a,rs in rows.items()}
    for eid in plan['paired_ids']:
        if not all(eid in byarm.get(a,{}) for a in ('B2','R3')):continue
        a=byarm['B2'][eid];b=byarm['R3'][eid]
        paired.append(dict(email_id=eid,subject=a['run']['email']['subject'],body=a['run']['email']['body'],B2=a['evaluation'],R3=b['evaluation']))
    b=status();catalog=B7Insights(ROOT);snapshots={s:catalog.snapshot(s) for s in ('b7-B2','b7-R3') if s in catalog.sources}
    result=dict(version='p5b7-results-1',status='真实首次结果；语义与自然度待集中复核，B2保留、R3未晋升',
        generation=dict(planned_jobs=len(plan['jobs']),original_plan_count=plan['n'],metadata_correction='plan-count-amendment.json',accepted=len(ds),source='LLM_SYNTHETIC',models=['deepseek-flash'],
            model_documented='DeepSeek-V4.1-Flash-1017',weights_snapshot='unavailable',gold=0,exact_duplicate_baseline=sum(' '.join(d['body'].lower().split()) in {' '.join(o['email_body'].lower().split()) for o in old} for d in ds),
            audit=audit([d['body'] for d in ds]),by_language=body_audit(ds),template_audit=audit([d['email_body'] for d in old]),template_by_language=body_audit([dict(body=o['email_body']) for o in old]),
            families=Counter(d['family'] for d in ds),input_hashes={d['email_id']:d['input_hash'] for d in ds},
            naturalness='ASSISTANT_DIAGNOSTIC_PENDING_HUMAN_NO_SUPERIORITY_CLAIM'),
        arms=arms,budget=b,paired_ids=plan['paired_ids'],pairs=paired,
        intent_consistency=dict(identity='NOT_ACCURACY_NOT_GOLD',n_judgable=sum(r['matches'] is not None for r in consistency),matches=sum(r['matches'] is True for r in consistency),not_scored_mixed=sum(r['matches'] is None for r in consistency),rows=consistency),
        judge=dict(n=len(judge),valid=sum(r['parsed'] is not None for r in judge),controls=dict(controls_counts),paired_preference=dict(preferences),hard_errors_by_arm=dict(hard_counts),identity='SAME_PROVIDER_LLM_JUDGE_PROVISIONAL_NOT_HUMAN',human_scores=0,rows=judge),
        insights={k:dict(source=v['source'],metrics=v['metrics'],states=v['states'],product_ranking=v['product_ranking'],store_ranking=v['store_ranking'],groups=v['groups']) for k,v in snapshots.items()},
        sources=dict(freeze=file_hash(LOCAL/'freeze.json'),authorization=file_hash(LOCAL/'authorization.json'),generation_plan=file_hash(LOCAL/'generation-plan.json')),
        limitations=['生成模型与分析/Judge同Provider，错误可能相关','意图不是语义Gold；本轮独立人工分类/自然度/回复评分均0','失败raw不进入有效业务统计，但保留全部任务分母','本地动作不等于外部执行或客户问题解决','90任务元数据曾写100，追加更正保留原件','C1若有结果为开发修复回归，不是独立Holdout'])
    write(DOC/'RESULTS.json',result)
    # Shareable CSV and JSONL: all accepted new original emails, no keys/headers.
    with (DOC/'LLM_EMAILS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['email_id','subject','body','input_hash','source','family','gold_status']);w.writeheader();w.writerows({k:d[k] for k in w.fieldnames} for d in ds)
    with (DOC/'LLM_EMAILS.jsonl').open('w',encoding='utf-8') as f:
        for d in ds:f.write(json.dumps(d,ensure_ascii=False)+'\n')
    write(DOC/'GENERATION_AUDIT.json',result['generation']);write(DOC/'JUDGE_AUDIT.json',result['judge'])
    print(json.dumps(dict(generated=len(ds),arms={a:dict(n=s['n'],accepted=s['accepted']) for a,s in arms.items()},calls=b['reserved_attempts'],upper_cny=b['settled_and_pending_upper_cny'],judge_valid=result['judge']['valid']),ensure_ascii=False))

if __name__=='__main__':main()
