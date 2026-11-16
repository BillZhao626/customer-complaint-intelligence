"""Deterministic aggregation of real first outputs. No historical relabel/write."""
import csv,json,sqlite3,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r8_evidence import L,D,O,read,write,table

def label(record,answer=None):
 if not record['analysis_parse']['semantic_eligible'] or not record['slot']['parse_ok']:return 'FAIL','Upstream analysis/reply contract rejected'
 if any(f['severity']=='block' for f in record['guard']['findings']):return 'FAIL','Deterministic fact guard blocks; semantic review cannot overrule'
 if not answer:return 'UNKNOWN','No certified paired semantic score'
 if any(f['category'] in ('HARD_ERROR','MAJOR_SERVICE_GAP') for f in answer['findings']):return 'FAIL','Judge located hard error/core service gap; AI provisional'
 if answer['scores']['reliability']==0 or answer['scores']['helpfulness']==0:return 'FAIL','Reliability/helpfulness zero; AI provisional'
 if any(f['category']=='UNKNOWN' for f in answer['findings']):return 'UNKNOWN','Semantic uncertainty retained'
 return 'PASS','No identified material defect; same frozen criteria; AI provisional, human pending'

def controls():
 from src.evaluation.p5b8r4_judge import DIMENSIONS
 allstats=Counter();first=Counter();protocol=certified=0;slots=[];groups=[]
 for p in sorted((L/'controls').glob('*.json')):
  c=read(p);num=p.stem;group=[]
  for order in ['AB','BA','REPEAT']:
   jp=L/'judgments'/f'CONTROL-{num}-{order}.json'
   if not jp.exists():continue
   r=read(jp);parsed=r['parsed'];protocol+=bool(parsed);ok=bool(parsed and parsed['validation']['status']=='AUTOMATED_PROVISIONAL');certified+=ok
   g=dict(order=order,valid=ok,scores={},preference=None)
   for arm,expected in zip(['A','B'],c['expected_hard']):
    slot=next((s for s,k in r['key'].items() if k['arm']==arm),None)
    a=next((a for a in parsed['answers'] if a['slot']==slot),None) if parsed else None
    hard=any(f['category']=='HARD_ERROR' for f in a['findings']) if a else None
    state='UNKNOWN' if not ok else ('TP' if expected and hard else 'FN' if expected else 'FP' if hard else 'TN')
    allstats[state]+=1
    if order=='AB':first[state]+=1
    g['scores'][arm]=a['scores'] if a else None
    slots.append(dict(family=c['family'],order=order,arm=arm,expected_hard=expected,observed_hard=hard,state=state,error=r['error']))
   if ok:
    pref=parsed['validation']['validated_preference'];g['preference']=r['key'][pref]['arm'] if pref in r['key'] else pref
   group.append(g)
  if len(group)==3:
   ab,ba,repeat=group;groups.append(dict(family=c['family'],all_certified=all(x['valid'] for x in group),position_agreement=ab['preference']==ba['preference'] if ab['valid'] and ba['valid'] else None,repeat_preference_agreement=ab['preference']==repeat['preference'] if ab['valid'] and repeat['valid'] else None,repeat_numeric_agreement=ab['scores']==repeat['scores'] if ab['valid'] and repeat['valid'] else None,expected_preference=c['expected_preference'],observed=[g['preference'] for g in group]))
 m=dict(identity='AI_CONSTRUCTED_CONTROLS_NOT_HUMAN_GOLD',families=len(groups),hard_families=sum(any(read(p)['expected_hard']) for p in (L/'controls').glob('*.json')),requests=sum(1 for _ in (L/'judgments').glob('CONTROL-*.json')),protocol_valid=protocol,certified=certified,repeat_slots=dict(allstats),first_AB_independent_content_slots=dict(first),group_agreement={k:dict(agree=sum(g[k] is True for g in groups),eligible=sum(g[k] is not None for g in groups),total=len(groups)) for k in ['position_agreement','repeat_preference_agreement','repeat_numeric_agreement']},human_agreement=None,cohen_kappa=None,groups=groups,slots=slots)
 write('judge-metrics.json',m)
 write('R8_JUDGE_CALIBRATION.md','# Judge校准与稳定性\n\n'+table(['项目','结果'],[[k,json.dumps(v,ensure_ascii=False)] for k,v in m.items() if k not in ['groups','slots']])+ '\n\n'+table(['家族','AB/BA偏好同向','重复偏好','重复数值','观察偏好'],[[g['family'],g['position_agreement'],g['repeat_preference_agreement'],g['repeat_numeric_agreement'],g['observed']] for g in groups])+ '\n\n每个家族只有1对独立内容，AB/BA/REPEAT是相关重复；唯一硬错家族另列，不能把重复TP当独立错误数。FP/FN保留，协议拒绝和内部矛盾为UNKNOWN不混进TN。控制期望由Codex构造，源于明确事实、安全边界及Owner定性政策；没有真人数值Gold，Agreement/κ=NOT_MEASURED。\n\n保留原0–2五维尺度，未改阈值。R7 soft_overcollection的FP源于把多余普通凭证升为硬错，本版明确软缺陷与索密钥/取件码/完整证件的实质隐私风险分开。每一输出完整原wire和五维解释在新账本与judgments。\n\n方法参考：Shi et al. (2025), Judging the Judges, https://aclanthology.org/2025.ijcnlp-long.18/；Guerdan et al. (2025), Validating LLM-as-a-Judge Systems under Rating Indeterminacy, https://www.microsoft.com/en-us/research/publication/validating-llm-as-a-judge-systems-under-rating-indeterminacy/ 。位置/重复稳定性与多合理答案动机，不是本项目人类效度证明。\n')
 print('CONTROL_METRICS',{k:v for k,v in m.items() if k not in ['groups','slots']});return m
def dev():
 from src.domain.contracts import EmailInput
 from src.evaluation.p5b8r4_judge import audit_slot
 rows=[]
 for c in read(L/'cases.json'):
  cid=c['case_id'];a=read(c['record_path']);bp=L/'traces'/('DEV-v2-'+cid)/'GUIDED-reply.json'
  if not bp.exists():continue
  b=read(bp);jp=L/'judgments'/('DEVPAIR-'+cid+'.json');j=read(jp) if jp.exists() else None
  old,new=None,None
  if j and j['parsed'] and j['parsed']['validation']['status']=='AUTOMATED_PROVISIONAL':
   for answer in j['parsed']['answers']:
    key=j['key'][answer['slot']]
    if key['run_id']==a['slot']['run_id']:old=answer
    if key['run_id']==b['slot']['run_id']:new=answer
  # Recalculate guards for both with exactly the same implementation, alongside
  # original saved guard. Never write back into either saved first output.
  a=dict(a,guard=audit_slot(a['slot'],EmailInput.model_validate(a['email'])));b=dict(b,guard=audit_slot(b['slot'],EmailInput.model_validate(b['email'])))
  ov,oreason=label(a,old);nv,nreason=label(b,new)
  rows.append(dict(case_id=cid,cohort='DEV',family=c['scenario']['family'],email=c['email'],input_hash=b['slot']['input_hash'],run_id=b['slot']['run_id'],old_verdict=c['old']['ai_full_chain'],rescored_old=ov,new_verdict=nv,reason=nreason,old_reason=oreason,old_reply=a['slot']['reply'],new_reply=b['slot']['reply'],events=b['slot']['events'],guard=b['guard'],analysis=b['analysis'],judge=j,analysis_ok=b['analysis_parse']['semantic_eligible'],reply_ok=b['slot']['parse_ok'],source=str(bp)))
 counts={k:dict(Counter(r[k] for r in rows)) for k in ['old_verdict','rescored_old','new_verdict']}
 write('dev-results.json',dict(n=54,observed=len(rows),counts=counts,cases=rows))
 write('R8_DEV_BEFORE_AFTER.md','# 固定54封同题新旧首答\n\n'+json.dumps(counts,ensure_ascii=False,indent=2)+'\n\n评价为同一校准后Judge与事实门槛的AI暂定结果，无真人Gold。历史33/14/7不回写。新链独立重新分析及执行，任务可能因抽取修复而改变；不是纯Composer消融。先前v1全保留，最终统一取v2，不选最好一次。\n\n'+table(['邮件','历史R7','统一复判旧','v2新首答','原因'],[[r['case_id'],r['old_verdict'],r['rescored_old'],r['new_verdict'],r['reason']] for r in rows])+ '\n\n完整原文、两版逐封首答、同臂事件及五维引用见dev-results.json与网页。判决规则：上游或结构失败/事实阻断为FAIL；认证Judge硬错、核心缺口或可靠/帮助0为FAIL；无认证评分或明确UNKNOWN保留UNKNOWN；其余仍需人工校准。分数相同不证明等效；软缺陷保持原分。\n')
 return rows
def ui():
 rows=read(D/'dev-results.json')['cases'] if (D/'dev-results.json').exists() else []
 if (D/'holdout-results.json').exists():rows+=read(D/'holdout-results.json')['cases']
 jm=read(D/'judge-metrics.json') if (D/'judge-metrics.json').exists() else {}
 summary={s:dict(N=sum(r['cohort']==s for r in rows),**dict(Counter(r['new_verdict'] for r in rows if r['cohort']==s))) for s in ['DEV','HOLDOUT']}
 write('quality-ui.json',dict(cases=rows,summary=summary,judge_metrics=jm,judge_summary=f"{jm.get('families',0)}个独立内容家族，{jm.get('hard_families',0)}种硬错家族；{jm.get('protocol_valid',0)}/{jm.get('requests',0)}协议有效。重复槽结果{jm.get('repeat_slots',{})}。独立人工效度待测。"))
def ledger():
 db=L/'live/budget.sqlite3'
 with sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True) as conn:
  calls=[dict(zip(['identity','request_hash','run_id','state','reserved_micro','settled_micro','metadata'],row)) for row in conn.execute('SELECT * FROM calls')]
 tokens=Counter();stages=Counter()
 for p in (L/'live/calls').glob('*/response.json'):
  r=read(p)
  for k in ['input_tokens','output_tokens','total_tokens']:tokens[k]+=r['metadata'][k]
  stages[read(p.with_name('frozen-input.json'))['payload']['stage']]+=1
 result=dict(requests=len(calls),states=dict(Counter(c['state'] for c in calls)),tokens=dict(tokens),stages=dict(stages),estimated_upper_cny=sum(c['settled_micro'] if c['settled_micro'] is not None else c['reserved_micro'] for c in calls)/1e6,actual_bill='UNKNOWN',request_cap=600,cny_cap=30,auto_retry=0)
 write('R8_TRACE_AND_LEDGER/LEDGER_AUDIT.json',result)
 with (D/'R8_TRACE_AND_LEDGER/request-ledger.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=[k for k in calls[0] if k!='metadata']);w.writeheader();w.writerows({k:v for k,v in c.items() if k!='metadata'} for c in calls)
 print(result)
if __name__=='__main__':
 for name in sys.argv[1:] or ['controls','dev','ui','ledger']:globals()[name]()
