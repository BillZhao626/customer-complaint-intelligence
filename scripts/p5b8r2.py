"""Free R2 preparation and historical audit. Never constructs a provider or ledger.

Writes only docs/p5b8r2 and .local/p5b8r2. Reruns verify frozen inputs.
"""
import os,sys,json,csv,re,hashlib,shutil,argparse
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.domain.contracts import EmailInput,digest
from src.application.p5b8_research import cases,read,readable_reply,comparison,insight
from src.application.p5b8r2_reply import paired_messages,identity,SYSTEM,PLANNER_SYSTEM,KNOWLEDGE
from src.application.p5b8r1_experiment import pair_invariant,MODEL
from src.evaluation.p5b8r2_judge import VERSION as JUDGE_VERSION,SYSTEM as JUDGE_SYSTEM,RUBRIC,bind_events,deterministic
from src.application.p5b8r2_guard import assess,VERSION as GUARD_VERSION
from src.application.p5b8r1_guard import assess as previous_assess
DOC=ROOT/'docs/p5b8r2';LOCAL=ROOT/'.local/p5b8r2'
OWNER={
 'B7-036':('GUIDED','受损先适度致歉；暂不通电；请求提供已拍但未发送照片；真实售后/物流待办。','neutral表达不免除负体验致歉；不机械复述裂口，不虚构收到照片或外部已办。'),
 'B7-084':('COMBINE','保留Direct一般排查知识，融合Guided感谢和真实支持请求，直接回答是否需到店。','不强判赢家；尊重已装好水箱并清洗；未知品牌/门店不得诊断或保证检修。'),
 'B7-035':('DIRECT_WITH_WARMER_APOLOGY','保留Direct结构、周六期限和加急思路，增强诚恳致歉。','Guided已有high-priority，不能说完全没提加急；不保证周六补发；声称附件已发不等于收到。'),
 'B7-009':('DIRECT_ACTION','真诚感谢，实际创建本地转达请求，合理祝福。','不能虚构表彰/绩效；不加入产品缺陷提醒；Judge不得串用另一臂回执。'),
 'B7-010':('DIRECT_STYLE','简短自然致谢，记录并申请转达，合理祝福。','不解释冗长内部流程；没任务不称已登记；原AB/BA不稳仍保留。'),
 'B7-085':('GUIDED','先共情收费疑问，核小票及收费依据，给具体澄清下一步。','未请求退款时不强调退款未批准；A组结构失败与B组语义偏好分开。'),
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def frozen(p,v):
 if Path(p).exists():
  if read(p)!=json.loads(json.dumps(v,ensure_ascii=False)):raise ValueError('Frozen changed; use a new explicit version: '+str(p))
 else:dump(p,v)
def md(name,t):(DOC/name).write_text(t.strip()+'\n','utf-8')
def csvout(p,rows):
 rows=list(rows);fields=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def block(v):return '\n```json\n'+json.dumps(v,ensure_ascii=False,indent=2)+'\n```\n'

def prepare(rows):
 old=read(ROOT/'.local/p5b8r1/FROZEN_PROTOCOL_v2.json');by={r['case_id']:r for r in rows};specs=[]
 for c in old['cases']:
  r=by[c['case_id']];email=EmailInput.model_validate(r['email'])
  assert email.input_hash==c['input_hash']
  msgs=paired_messages(email,r['analysis']['data'],r['replies']['A_GUIDED']['runtime']);proof=pair_invariant(msgs)
  spec=dict(case_id=r['case_id'],input_hash=email.input_hash,stratum=c['stratum'],family=r['family'],language=r['language'],order=c['order'],messages=msgs,invariant=proof,role='EXPOSED_DEV_NOT_INDEPENDENT',source_analysis_run=r['analysis']['call']['run_id'],old_prepared_sha256=sha(ROOT/'.local/p5b8r1/prepared'/(r['case_id']+'.json')),status='AUTHORIZATION_BLOCKED')
  frozen(DOC/'prepared'/(r['case_id']+'.json'),spec);specs.append(spec)
 b_ids=list(OWNER)+['B7-002','B7-018','B7-050','B7-066','B7-075','B7-076']
 manifest=dict(version='p5b8r2-preregistered-1',date='2026-11-01 Asia/Shanghai',status='AUTHORIZATION_BLOCKED',live_dispatch_enabled=False,budget_ledger=None,authorization=None,new_paid_calls=0,new_cost_cny=0,reply=identity(),judge=dict(version=JUDGE_VERSION,hash=digest(JUDGE_SYSTEM)),guard=dict(version=GUARD_VERSION,source_sha256=sha(ROOT/'src/application/p5b8r2_guard.py')),model=MODEL,
  A=dict(n=24,planned_replies=48,attempted=0,not_run=48,semantic_graded=0,semantic_unknown=24,human_reviewed=0,endpoint='WITH minus NO: attitude and actual helpfulness, with reliability/action hard-error non-deterioration',strata=dict(Counter(s['stratum'] for s in specs)),cases=[{k:s[k] for k in ('case_id','input_hash','family','language','stratum','order','invariant')} for s in specs],r1_protocol_sha256=sha(ROOT/'.local/p5b8r1/FROZEN_PROTOCOL_v2.json'),common_change='R2 replaces both system prompts and adds identical scoped knowledge; R1 hashes remain unchanged. A uses same historical source actions, no new planning; only explicit_emotion differs.'),
  B=dict(n=12,case_ids=b_ids,role='DEV_EXPOSED',planned_calls=48,attempted=0,not_run=48,endpoint='Correct local action choice/receipt, actual helpfulness, escalation and truthful reply',initial_state='Both arms independently empty, same policy/knowledge/permissions',direct='Original mail -> independent planner -> local actions -> shared reply',guided='Original mail -> R1 strict LangChain analysis -> local Issue planner -> local actions -> same shared reply',storage_template='.local/p5b8r2/new-authorized-run/B/{case_id}/{arm}/actions.sqlite3',receipt_rule='Never copy A or other-arm actions. Bind server-owned case/run/arm/input/event/state/hash. Judge source slots blinded X/Y; internal identities random opaque values.'),
  judge_plan=dict(A=24,B=12,reversals=6,exact_repeats=4,total=46,attempted=0,rule='Preserve first raw; both structurally valid required for semantic pair. Label actual AB/BA inconsistencies separately. Old five B scores are not numerically interchangeable with new dimensions.'),
  requested_future_budget=dict(authorized=False,dev_request_limit=142,dev_cny_hard_cap=10,meaning='Proposed ceiling, not price estimate or authorization',breakdown='A48 + B48 + Judge46 = 142; no retry/repair allowance. Additional iteration must fit separately frozen approved scope.'),
  generalization=dict(status='NOT_RUN',candidate_count_target=24,opened_samples=0,independent_family_source=None,reason='DEV real quality not yet observed/stable; do not manufacture independence by renaming exposed cases or author new test content before freeze.',planned_future_calls=144,breakdown='24 new synthesis + 24*(Direct plan+reply + Guided analysis+reply) + 24 Judge = 144',authorization='Separate future scope required after DEV freeze',one_shot=True,if_repaired='Move seen failures to DEV and replace independent set; preserve first result'),
  denominators=['attempted','provider_ok','structured_valid','semantic_graded','semantic_unknown','human_reviewed','action_applicable','action_correct','action_unknown','hard_error','major_gap','soft_issue','not_run','N_A','infra_error'],failure_policy='First raw before parse; failure/UNKNOWN stays in denominator; no automatic redispatch or best-of selection; no semantic zero for invalid JSON.',statistics='All-pair win/tie/loss/unknown by family and stratum. Paired ordinal differences and paired bootstrap by conversation family only if observed; state small n and family dependence. No estimator for zero runs.',human_dimension_scores=None,kappa=None)
 frozen(DOC/'EXPERIMENT_MANIFEST.json',manifest)
 frozen(DOC/'REPLY_CONFIG.json',dict(identity=identity(),system=SYSTEM,planner=PLANNER_SYSTEM,knowledge=KNOWLEDGE,judge_system=JUDGE_SYSTEM))
 ab=[]
 for s in specs:
  ab.append(dict(experiment='R2_A',case_id=s['case_id'],family=s['family'],stratum=s['stratum'],input_hash=s['input_hash'],attempted=0,provider_ok=0,structured_valid=0,semantic_graded=0,semantic_unknown=1,human_reviewed=0,action_applicable=None,action_correct=None,action_unknown=None,hard_error=None,major_gap=None,soft_issue=None,not_run=2,N_A=None,infra_error=0,result='UNKNOWN',status='AUTHORIZATION_BLOCKED',direct_first_response=None,guided_first_response=None,elapsed_ms=None,tokens=None,cost_cny=None))
 for eid in b_ids:ab.append(dict(experiment='R2_B',case_id=eid,family=by[eid]['family'],attempted=0,not_run=4,result='UNKNOWN',status='AUTHORIZATION_BLOCKED'))
 for exp in ('A','B'):
  for c in comparison(rows,exp)['rows']:ab.append(dict(experiment='HISTORICAL_B8_'+exp,case_id=c['case_id'],result=c['delta'],status='UNKNOWN' if c['delta']=='UNKNOWN' else 'HUMAN_PENDING',old_judge_preference=c['judge_preference'],note='Legacy endpoint, NOT R2 results or emotion-only effect'))
 csvout(DOC/'AB_RESULTS.csv',ab);return manifest

def export(rows):
 by={r['case_id']:r for r in rows};src=DOC/'source_inputs/P5-B8-R2_Codex完整执行Prompt.md';prompt=src.read_text('utf-8-sig')
 table='\n'.join(line for line in prompt.splitlines() if line.startswith('| **B7-'))
 md('OWNER_POLICY_v2.md','# Owner定性政策 v2\n\n来源：用户要求执行的附件 §2，原件 SHA256 '+sha(src)+'。以下是附件记录的Owner反馈；本轮未取得更早对话的逐字原话，因此不伪称直接逐字访谈。用途为已曝光DEV的定性偏好与约束，不是6条逐维分、逐字Gold或Independent Test。旧16条客服Gold（3逐字历史、13授权代拟）、24分类研究者裁决和80项目参考各保留原身份。\n\n'+table+'\n\n通用执行：受损/安全、知识咨询、时间约束、明确表扬转达、混合Issue及收费澄清；源码不按B7 ID或客户姓名分支。正例为请求已创建本地单据后如实描述pending；反例为据此宣称门店已收到/退款已完成。中性损坏可致歉；普通礼貌询价不强制道歉。B7-084为COMBINE，不强判赢家。附件只支持定性方向，不支持任何数值Owner一致率。\n\n完整案例、事件与差异见 CASEBOOK；来源和逐项规则见 QUALITY_COMPARISON.csv。')
 book=['# R2关键案例全文与Owner政策\n','本册为真实保存的LLM_SYNTHETIC邮件及历史Provider首次回复，**不是真实消费者邮件**。R2新Direct/Guided未调用，不能伪造全文。后续本地UI动作不得追认历史回复。完整94案在 HISTORICAL_CASEBOOK_94.md，242个Registry对象原始来源在RAW_EVIDENCE.jsonl。\n'];quality=[];audits=[]
 for eid,(pref,rule,counter) in OWNER.items():
  r=by[eid];book.extend([f'\n## {eid} — {r["email"]["subject"]}\n','Owner定性：'+pref+'；'+rule+'\n\n边界：'+counter+'\n','### 原客户邮件全文\n\n'+r['email']['body']+'\n','### 情绪与Issue（历史模型预测，不是Gold）\n',block(r['analysis']['data'])])
  for arm,q in r['replies'].items():
   book.extend([f'### 历史 {arm} 全文\n',('工程失败，以下仅可读审计文本，非合法草稿。\n' if q['error'] else ''),readable_reply(q)+'\n',block(dict(run_id=q['call']['run_id'],response_id=q['call']['metadata'].get('provider_response_id'),input_hash=r['input_hash'],model=q['call']['metadata'].get('resolved_model'),model_snapshot=q['call']['metadata'].get('model_snapshot'),finish_reason=q['call']['metadata'].get('finish_reason'),structure_error=q['error'],actual_runtime=q['runtime']))])
   slot=dict(slot='X',case_id=eid,run_id=q['call']['run_id'],arm=arm,input_hash=r['input_hash'],reply=q['reply'],parse_ok=not bool(q['error']))
   slot['events']=bind_events(q['runtime']['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
   audits.append(dict(case_id=eid,arm=arm,raw_reply_sha256=digest(q['call']['raw']),old_assessment=previous_assess(q['reply'] or '',q['runtime'],r['input_hash']),r2=deterministic(slot,q['runtime']),new_numerical_scores=None))
  book.extend(['### 原Judge完整输出及顺序\n',block(r['judges']),'### R2新两链\n\nDIRECT: AUTHORIZATION_BLOCKED / NOT_RUN，无首次回复。\n\nGUIDED: AUTHORIZATION_BLOCKED / NOT_RUN，无首次回复。\n\nOwner定性要求已固化；新模型遵循程度UNKNOWN。自动筛查没有转换为Owner逐维分数。\n'])
  quality.append(dict(case_id=eid,owner_preference=pref,owner_rule=rule,counterexample=counter,historical_evidence='CASEBOOK.md#'+eid.lower(),r2_change='Shared reply v1 + scoped receipt intake + inherited explicit-praise local planner',actual_new_reply_pairs=0,model_quality_status='AUTHORIZATION_BLOCKED',old_scores='See CASEBOOK raw judges; unchanged',new_scores=None))
 md('CASEBOOK.md','\n'.join(book));csvout(DOC/'QUALITY_COMPARISON.csv',quality);dump(DOC/'OLD_VS_NEW_EVALUATOR.json',audits)
 for name,old in [('HISTORICAL_CASEBOOK_94.md','CASEBOOK.md'),('HISTORICAL_CASEBOOK_PRE_B8.md','HISTORICAL_CASEBOOK_P5B8.md'),('RAW_EVIDENCE.jsonl','RAW_EVIDENCE.jsonl'),('ALL_BAD_CASES.csv','ALL_BAD_CASES.csv'),('HISTORICAL_JUDGE_CALIBRATION.json','JUDGE_CALIBRATION.json')]:shutil.copyfile(ROOT/'docs/p5b8r1'/old,DOC/name)
 # Extend the inherited complete failure register; never narrow it to six examples.
 with (DOC/'ALL_BAD_CASES.csv').open(encoding='utf-8-sig',newline='') as f:bad=list(csv.DictReader(f))
 bad.append(dict(case_id='R2-CONTROL-RELAY-NOUN',error_families='INTERNAL_REQUEST_NOUN_FALSE_COMPLETION',original_findings='已创建内部转达请求 was misread as external completed relay',r1_findings='H04 false block',status='IMPROVED_NOT_HUMAN_CERTIFIED',repair='R2 masks task noun only when scanning completed predicates; separate 并已转达 still H04',evidence='test-r2-initial.txt; test-r2-round1.txt'))
 for eid,(_,rule,_) in OWNER.items():bad.append(dict(case_id=eid,error_families='OWNER_SERVICE_QUALITY',original_findings=rule,status='AUTHORIZATION_BLOCKED',repair='New shared prompt frozen; actual model retest 0',evidence='CASEBOOK.md; REPLY_CONFIG.json'))
 csvout(DOC/'ALL_BAD_CASES.csv',bad)
 for name in ('test-r2-initial.txt','test-r2-round1.txt','test-b-family.txt'):
  if (LOCAL/name).exists():shutil.copyfile(LOCAL/name,DOC/name)
 dump(DOC/'BUSINESS_STATISTICS.json',insight([r for r in rows if r['case_id'].startswith('B7')]))
 dump(DOC/'HISTORICAL_QUALITY.json',dict(A=comparison(rows,'A'),B=comparison(rows,'B')))
 dump(DOC/'SOURCE_INDEX.json',dict(new_paid_calls=0,sources=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in [ROOT/'AGENTS.md',ROOT/'docs/p5b8r1/DELIVERY.md',ROOT/'docs/p5b8/RESEARCH_AND_THESIS_RESULTS.md',ROOT/'docs/p5b7/RESEARCH_RESULTS.md',ROOT/'docs/p5b6/LANGCHAIN_CHAIN.md',ROOT/'docs/p5b5r2/RESULTS.md',ROOT/'docs/audit/2026-10-14-legacy-audit.md',ROOT/'docs/architecture/2026-10-14-architecture-options.md',ROOT/'docs/plans/PHASED_ROADMAP.md']],missing=['Earlier verbatim Owner conversation not supplied; attachment §2 is the actual recorded source'],historical_raw='RAW_EVIDENCE.jsonl; original paths and run IDs preserved; historical CASEBOOK copies byte-identical'))
 # Key-case actual wire inputs/first responses are reviewable without a backend.
 trace_index=[]
 for eid in OWNER:
  paths=[ROOT/'.local/p5b7/dataset'/(eid+'.json')]
  for stage in ('ANALYSIS','A_DIRECT','A_GUIDED','B_PLAN','B_DIRECT','B_GUIDED'):
   folder=ROOT/'.local/p5b8/calls'/stage/eid
   paths.extend(p for p in folder.glob('*') if p.is_file() and p.name in ('frozen-input.json','wire-request.json','provider-http.json','provider-response.txt','langchain-response.json','response.json'))
  for p in paths:
   rel=p.relative_to(ROOT/'.local');target=DOC/'traces'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
   trace_index.append(dict(case_id=eid,source=p.relative_to(ROOT).as_posix(),packaged=target.relative_to(DOC).as_posix(),sha256=sha(p),identity='IMMUTABLE_HISTORICAL_FIRST_CALL_NOT_R2'))
 for folder in (ROOT/'.local/p5b8/calls/JUDGE_PAIR').iterdir():
  if not any(eid in folder.name for eid in list(OWNER)+['B7-002']):continue
  for p in folder.glob('*'):
   if not p.is_file():continue
   target=DOC/'traces'/p.relative_to(ROOT/'.local');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
   trace_index.append(dict(source=p.relative_to(ROOT).as_posix(),packaged=target.relative_to(DOC).as_posix(),sha256=sha(p),identity='HISTORICAL_JUDGE_INPUT_RAW_AB_BA_NOT_R2'))
 for p in [ROOT/'.local/p5b8/freeze.json']+[p for p in (ROOT/'.local/p5b8/frozen-source').rglob('*') if p.is_file()]:
  target=DOC/'traces'/p.relative_to(ROOT/'.local');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
  trace_index.append(dict(source=p.relative_to(ROOT).as_posix(),packaged=target.relative_to(DOC).as_posix(),sha256=sha(p),identity='HISTORICAL_FROZEN_EXECUTION_SOURCE_READ_ONLY_DO_NOT_RUN_LIVE'))
 dump(DOC/'TRACE_INDEX.json',trace_index)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
 if args.live:raise PermissionError('AUTHORIZATION_BLOCKED: no R2 amount/request authorization; old ledgers stay closed. No Provider constructed.')
 DOC.mkdir(parents=True,exist_ok=True);rows=cases();manifest=prepare(rows);export(rows)
 print(json.dumps(dict(cases=len(rows),A_ready=manifest['A']['n'],paid_calls=0,status=manifest['status']),ensure_ascii=False))
if __name__=='__main__':main()
