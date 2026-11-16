"""Read-only computations; writes only new B3 review/report artifacts."""
from pathlib import Path
import sys,json,csv
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b_pilot import read,write_new,now
from src.application.p5b3_runtime import LOCAL,Budget
from src.application.live_execution import strict_json
from src.domain.analysis_v32 import validate
from src.domain.contracts import EmailInput,digest
from src.application.research_policy_v2 import requested_language,language
DOC=ROOT/'docs/p5b3'

def main():
    stages=['ui-initial','dev','dev-confirm','validation','test','paired-b2','regression','ui-final','ui-followup','ui-knowledge']
    metrics={}; ledger=[]; runs={}; reviews=[]; detail=[]
    for stage in stages:
        rs=[]
        for p in sorted((LOCAL/stage).glob('*/run.json')):
            r=read(p);rs.append(r);runs[r['run_id']]=r
            a=r['attempts'][-1] if r['attempts'] else {};meta=a.get('metadata',{});raw=a.get('raw_output')
            response=read(p.parent/'provider-response.txt') if (p.parent/'provider-response.txt').exists() else {}
            usage=response.get('usage',{});cache_hit=usage.get('prompt_cache_hit_tokens');cache_miss=usage.get('prompt_cache_miss_tokens')
            peak_usage=(cache_hit*.04+cache_miss*2+usage.get('completion_tokens',0)*8)/1e6 if cache_hit is not None and cache_miss is not None else None
            error=None
            try:validate(strict_json(raw),EmailInput.model_validate(r['email']))
            except Exception as exc:error=str(exc)
            try:reply=strict_json(raw).get('suggested_reply','')
            except (ValueError,TypeError):reply=''
            frozen=read(p.parent/'frozen-input.json')
            if raw and response.get('choices'):assert response['choices'][0]['message']['content']==raw
            assert digest(frozen['email'])==digest(r['email'])
            if frozen.get('trusted_runtime'):
                assert digest(frozen['trusted_runtime'])==r['config']['parameters']['runtime_context_hash']
            row=dict(stage=stage,email_id=r['email']['email_id'],run_id=r['run_id'],input_hash=r['input_hash'],status=r['status'],model=meta.get('resolved_model'),prompt=r['config']['prompt_version'],request_id=meta.get('provider_response_id'),input_tokens=meta.get('input_tokens'),output_tokens=meta.get('output_tokens'),total_tokens=meta.get('total_tokens'),peak_miss_upper_cny=meta.get('cost_cny'),peak_cache_usage_estimate_cny=peak_usage,elapsed_ms=a.get('elapsed_ms'),parse=a.get('parse_status'),contract=a.get('contract_status'),raw_sha256=sha256(raw.encode()).hexdigest() if raw else None,raw_path=str(p.parent/'provider-response.txt'),error=error)
            ledger.append(row)
            review=dict(stage=stage,email_id=row['email_id'],run_id=r['run_id'],input_hash=r['input_hash'],reply_hash=digest(reply),human_scores=dict(B1=None,B2=None,B3=None,B4=None,B5=None),hard_errors={f'H{i:02}':'NOT_ASSESSED' for i in range(1,8)},human_reviewer=None,human_signed_at=None,quality_identity='HUMAN_REVIEW_PENDING',contract=r['status'],failure=error)
            reviews.append(review)
            detail.append(f'## {stage} / {row["email_id"]}\n\nrun_id: `{r["run_id"]}` · {r["status"]}\n\n客户输入（含本版本真实历史）：\n\n{r["email"]["subject"]}\n\n{r["email"]["body"]}\n\n首次模型回复（失败时仅raw诊断，非可用草稿）：\n\n{reply}\n\n契约原因：{error or "PASS"}\n\n本地动作：\n\n```json\n{json.dumps(frozen.get("trusted_runtime",{}).get("action_results",[]),ensure_ascii=False,indent=2)}\n```\n\nB1/B2/B3/B4/B5：待真人评分；H01–H07待审。\n')
        if not rs:continue
        rows=[x for x in ledger if x['stage']==stage]
        ids={r['email']['email_id'].rsplit('-T',1)[0] for r in rs}
        complete=sum(all(r['status']=='succeeded' for r in rs if r['email']['email_id'].rsplit('-T',1)[0]==i) for i in ids)
        english=[]
        for r in rs:
            current=r['email']['body'].rsplit('[customer · current message]\n',1)[-1]
            if requested_language(current)=='en':
                try:english.append(language(strict_json(r['attempts'][-1]['raw_output'])['suggested_reply'])=='en')
                except Exception:english.append(False)
        metrics[stage]=dict(turns=len(rs),conversations=len(ids),provider_first_response=sum(r['attempts'][-1]['metadata'].get('dispatch')=='response_received' for r in rs),json_first=sum(r['attempts'][-1]['parse_status']=='passed' for r in rs),contract_first=sum(r['status']=='succeeded' for r in rs),conversation_all_turns_accepted=complete,failed=sum(r['status']=='failed' for r in rs),unknown=sum(r['status']=='interrupted_or_unknown' for r in rs),fallback=0,retries=0,english_reply_matches=sum(english),english_denominator=len(english),human_scored=0,RQPR=None)
    write_new(DOC/'METRICS.json',dict(at=now(),identity='SYNTHETIC_INTERNAL_SYSTEM_EXPERIMENT',stages=metrics,calls=len(ledger),total_tokens=sum(r['total_tokens'] or 0 for r in ledger),peak_miss_upper_cny=sum(r['peak_miss_upper_cny'] or 0 for r in ledger),peak_usage_estimate_cny=sum(r['peak_cache_usage_estimate_cny'] or 0 for r in ledger),actual_experiment_invoice=None,budget=Budget(LOCAL/'budget.sqlite3').summary()))
    write_new(DOC/'HUMAN_REVIEW_BLANK.json',reviews)
    write_new(DOC/'FULL_REVIEW_PACK.md','# 完整输入、首次模型回复与任务事件\n\n所有输出来自第一次对应版本生成；没有挑选替换。正式人工评价为空。\n\n'+'\n'.join(detail))
    with (DOC/'PROVIDER_LEDGER.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
    print(json.dumps(metrics,ensure_ascii=False,indent=2));print('calls',len(ledger))

if __name__=='__main__':main()
