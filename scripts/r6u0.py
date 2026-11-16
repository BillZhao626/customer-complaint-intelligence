"""R6-U0 explicit new authorization, serial execution and evidence commands.

No historical ledger is opened for writing. No retries or external business actions.
"""
import argparse,csv,hashlib,json,os,sys,shutil
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
LOCAL=ROOT/'.local/r6u0-20261105-v1';DOC=ROOT/'docs/r6u0-20261105-v1'

def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');return d
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def md(name,s):(DOC/name).write_text(s,'utf8')
def csvout(name,rows):
 with (DOC/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Family/task specifications only. Customer messages are created after final freeze.
FAMILIES=[
 ('recall_batch_traceability','官方召回传闻和批次核对',['不根据论坛传闻断言已召回或安全','收集型号、批号、官方通知来源；建议暂停有疑虑的使用并走官方核实'], 'SAFETY'),
 ('counterfeit_serial_authentication','防伪码重复或无效的真实性核查',['不凭扫码失败认定假货或真品','索要官方核验渠道、产品码及凭证；不收集密码'], 'POLICY'),
 ('parcel_payment_impersonation','假冒售后催付和身份核实',['不点陌生链接、不提供验证码或向私人账户付款','通过原订单已知官方入口核验，不断言已封禁或追回款项'], 'SAFETY'),
 ('battery_transport_restrictions','电池邮寄运输条件',['不许诺普通快递可收或教违规寄件','核实电池状态、型号、承运规则；异常电池停止充电且不自行寄出'], 'SAFETY'),
 ('wall_installation_permission','墙体安装许可及承重条件',['不推定墙体承重或允许租客钻孔','实际安装手册、物业/房东许可和专业安装评估；提供缺信息下一步'], 'SAFETY'),
 ('environmental_certification_scope','环保认证范围和证据文件',['不虚构认证编号或把包装认证当整机认证','区分证书对象、有效期、产品型号和营销说法，核查授权资料'], 'POLICY'),
 ('lost_property_custody','门店遗失物核查与安全认领',['不确认已找到物品或公开领取密码','描述物品、到访时间、门店和适当认领核查；不能要求完整证件号'], 'NORMAL'),
 ('warranty_territory_transfer','跨区域保修转移与受理权限',['不承诺全球联保、不把购买地点变成店服投诉','核实品牌型号、购买地区与目标地区条款；同时尊重此前已提交凭证'], 'POLICY'),
]
DEV=(36,84,35,9,10,85,20,16,66,89)

def prepare():
 from src.domain.contracts import digest
 DOC.mkdir(exist_ok=True);LOCAL.mkdir(exist_ok=True)
 cs=read(ROOT/'docs/p5b8r6/evidence/semantic-cases.json')
 old=read(ROOT/'.local/p5b8r6-offline-fix-v1/unified-ready-v2/execution-integrity.json')
 comparison=dict(source_count=len(old['source_hashes']),drift=[p for p,h in old['source_hashes'].items() if sha(ROOT/p)!=h])
 write(DOC/'candidate-comparison-current.json',comparison)
 auth=dict(scope='R6-U0-20261105-NEW',cny=20,provider_requests=200,user_approval_verbatim='R6-U0补充授权：人民币费用硬上限¥20，底层Provider请求硬上限200次；允许已配置核实DeepSeek，历史账本保持关闭。',date='2026-11-05 Asia/Shanghai',historical_authorization_reused=False)
 price=dict(input_cny_per_million=2,output_cny_per_million=8,source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',checked='2026-11-05',basis='peak cache-miss upper bound',model_version_official='DeepSeek-V4.1-Flash-1017',actual_bill='UNKNOWN')
 plan=dict(authorization_scope=auth['scope'],planned_requests=200,proposed_cny_cap=20,allowed_call_ids=[f'U0-{i:03}' for i in range(1,201)],pricing=price,allocation=dict(initial_dev=40,holdout_reserved_minimum=50,holdout_full=64,judge_controls_pairs=40,dev_repairs_and_web=56))
 auth['plan_hash']=digest(plan)
 for n,d in [('authorization.json',auth),('plan.json',plan),('pricing.json',price)]:
  p=LOCAL/n
  if p.exists() and read(p)!=d:raise ValueError('Existing immutable authorization drift')
  if not p.exists():write(p,d)
 registry=[]
 for c in cs:
  registry.append(dict(case_id=c['case_id'],input_hash=c['input_hash'],family=c['family'],quality=c['data_quality_tier'],complexity=c['scenario_complexity'],risk=c['business_risk'],role='CALIBRATION' if c['case_id'] in [f'B7-{n:03}' for n in (36,84,35,9,10,85,20)] else 'DEV',identity='HISTORICAL_LLM_SYNTHETIC_EXPOSED',review='OWNER_QUALITATIVE_ONLY' if c['case_id'] in [f'B7-{n:03}' for n in (36,84,35,9,10,85,20)] else 'AI_PROVISIONAL'))
 specs=[]
 for k,(family,purpose,points,risk) in enumerate(FAMILIES):
  for v in range(2):
   eid=f'U0H-{2*k+v+1:03}'
   specs.append(dict(case_id=eid,family=family,variant=v,customer_purpose=purpose,required_points=points,knowledge_sources=['customer original','Owner general evidence/action boundary','actual product manual or official policy UNKNOWN until supplied'],allowed_actions=['source-bound local internal verification created/handoff_pending only'],action_prerequisites='exact source quotation and current objective; no external execution',forbidden_claims=['external completed','guaranteed eligibility/ETA','verified attachment without receipt','unsupported diagnosis/policy'],risk=risk,evaluation_scope='all current customer objectives, evidence-bound Issue/source, five dimensions and hard errors',refusal='decline unsafe/unauthorized method; continue safe help',na='no action needed if no actionable current request; explain applicability',label_identity='AI_PREREGISTERED_REQUIREMENTS_NOT_HUMAN_GOLD',language='en' if (k+v)%2 else 'zh',generation_rule='Two emails per family. Different constraints/context, not treated as two families. Variant 1 uses prior conversation, time constraint or mixed feedback. No historical names/product-only paraphrase. Messages created locally after candidate freeze without Provider requests.'))
 write(DOC/'holdout-specifications.json',specs)
 write(DOC/'owner_anchor_registry.json',dict(identity='USER_CONFIRMED_QUALITATIVE_NOT_NUMERIC_GOLD',source='current user prompt + docs/p5b8r6/OWNER_POLICY_AND_DATA_TIERS.md',anchors=[dict(case_id=f'B7-{n:03}',policy_source='current user §四',human_dimension_scores=None) for n in (36,84,35,9,10,85,20)],ai_inferred_requirements_separate='holdout-specifications.json'))
 for s in specs:registry.append(dict(case_id=s['case_id'],input_hash='NOT_CREATED_BEFORE_FREEZE',family=s['family'],quality='NOT_YET_REVIEWED',complexity='MULTI_TURN_OR_POLICY' if s['variant'] else 'SINGLE',risk=s['risk'],role='SEALED_TEST_CANDIDATE',identity='NOT_CREATED',review='AI_PREREGISTERED_NOT_GOLD'))
 csvout('dataset_registry.csv',registry)
 history=read(ROOT/'docs/p5b8r6/offline-fix-v1/history-registry.json');write(LOCAL/'history.json',history);write(LOCAL/'aliases.json',read(ROOT/'docs/p5b8r6/offline-fix-v1/family-aliases.json'))
 md('TEST_PLAN.md','# R6-U0 预注册（真实DEV前）\n\n10个历史DEV：'+str(DEV)+'；含七Owner案。Direct每例计划1+回复1，Guided共享分析1+回复1，共40底层请求。两臂共享知识、安全政策、执行工具、Composer；Direct无分析brief，Guided使用分析，不解释成纯情绪消融。每臂独立同run回执先于回复。\n\n16个新邮件，8个任务语义家族×2；协议与配额先固定，客户邮件在最终候选冻结后本地编写/解封。64请求正式双臂完整链；另预留至少50初始请求给未见。至少8新家族按任务语义审核，泛领域仍有咨询/门店/售后共性，不声称领域完全外推或独立真人Gold。任何同族污染降为探索，原分母16不变。所有失败/UNKNOWN/NOT_RUN保留。不因结果替换。\n\nJudge：先至少4硬错+4正常控制，TP/FN/FP/TN按AI构造控制口径；七Owner原则不变、不数字化Gold。DEV配对至少七案，至少3案AB/BA与重复；holdout最多16配对。五维0–2及硬错独立，确定性事件审计是下界。\n\nDEV停止：关键硬错消除、已知目标有代表性证据，或形成稳定阻断。正式holdout后禁止改候选；失败保留，修复须下一批。语义结果由AI审阅与Judge分别给出，无法计算新轴真人准确率/F1。所有费用上界预留，无自动重试。\n\n细项与N/A见holdout-specifications.json。产品验收使用同一个应用generate，现有React和本地SQLite，禁止所有对外业务操作。')
 # Independent re-audit mechanics do not overwrite historical annotations.
 import difflib
 duplicates=[]
 for i,c in enumerate(cs):
  for b in cs[:i]:
   ratio=difflib.SequenceMatcher(None,c['email']['body'],b['email']['body']).ratio()
   if ratio>.68:duplicates.append(dict(a=b['case_id'],b=c['case_id'],ratio=ratio))
 write(DOC/'near-duplicates.json',duplicates)
 rows=list(csv.DictReader((ROOT/'docs/p5b8r6/FULL_SEMANTIC_REVIEW.csv').open(encoding='utf-8-sig')))
 for row in rows:
  row['original_review_identity']=row['reviewer'];row['u0_review_identity']='CODEX_AI_REAUDIT_NOT_HUMAN_GOLD';row['suggested_change']='保留原始预测；争议进入修订候选，未重标Gold'
  row['ranking_impact']='store membership may change; product retained' if row['case_id']=='B7-020' else 'needs confirmed target/polarity before changing ranking' if row['status']!='SUPPORTED' else 'none proposed'
  if row['case_id']=='B7-020':row['suggested_change']='OWNER：商品包装和袖口保留；无证据店服Issue排除于店服榜单；原预测不覆盖'
 csvout('case_audit.csv',rows)
 md('DATA_AUDIT.md','# 邮件与Issue质量复核\n\n90封均LLM合成、历史曝光；87份有效分析，3失败（034/056/067），144个原Issue。原文、预测、AI审阅、Owner政策覆盖层分别保存。新轴真人Gold=0，不能报告Accuracy/Macro-F1/Kappa。\n\n原A70/B18/C2仅作为历史AI分层起点，未认证准确。此次对原文检查：B多为合理模糊/实体缺失，仍是高价值；020短且清楚，A；037/044近重复模板化，C保留。商品只有六种及会员反复出现，语言以中文为主（63/90），门店与故障模板高度集中；无法代表真实消费者分布。对比近重复见near-duplicates.json，字符阈值只作候选，不证明语义不同。原文普遍有礼貌收尾，易被错当正向情绪；生活背景过多但事实锚点不足。历史“前文提过”未附上下文不能当实际多轮数据。\n\n复核重点：006包装难拆是否Complaint；019会员合同缺失；031不便与感谢分开；041着急不等于负面态度；075没有具体商品且明确服务不满；079商品实体遗漏候选；081网站门店查询不应自动归实体店责任；086积分与方案需分Issue。它们仍是AI候选，134支持/8歧义/2过归因不当作准确率。逐案证据和建议见case_audit.csv（144旧Issue+3失败占位+1漏实体候选）。\n\n统计：020排除店服目标会使南京新街口店服投诉1→0；商品37/87不变。其它歧义若确认会改变店服/产品成员或来源榜单，须逐目标修订，不整封删除。预测与Owner覆盖层分版；分母总90/有效87/失败3，unknown独立。质量、复杂度、风险、语义家族与角色见dataset_registry.csv，不能用长度、模型失败或合理模糊降级。\n\n原90/144及旧16开发回复参考均冻结保护；本次不是独立第二评审，也没有创建真人Gold。')
 print('PREPARED',len(specs),'holdout specs; no customer messages created')

def freeze(name,holdout=False):
 from src.evaluation.experiment_integrity import freeze as f,verify
 inputs=[DOC/'TEST_PLAN.md',DOC/'holdout-specifications.json',DOC/'owner_anchor_registry.json',LOCAL/'history.json',LOCAL/'aliases.json',LOCAL/'plan.json',LOCAL/'authorization.json']
 if holdout:inputs += [LOCAL/'holdout.json',LOCAL/'holdout-registry.json']
 manifest=f(ROOT,inputs=inputs)
 if holdout:manifest['independent_dataset']=dict(candidates=str(LOCAL/'holdout-registry.json'),history=str(LOCAL/'history.json'),aliases=str(LOCAL/'aliases.json'))
 p=LOCAL/'freezes'/name
 if p.exists():raise ValueError('Freeze name already exists')
 p.mkdir(parents=True)
 for n in manifest['source_hashes']:
  q=p/'source'/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/n,q)
 write(p/'manifest.json',manifest);write(LOCAL/'active-freeze.json',dict(path=str(p/'manifest.json'),name=name));write(p/'verification.json',verify(manifest))
 print('FROZEN',name,len(manifest['source_hashes']))

def dispatcher():
 from src.infrastructure.p5b8r3_execution import Dispatcher
 from src.infrastructure.structured_reply_provider import StructuredReplyProvider
 p=read(LOCAL/'plan.json');d=Dispatcher(LOCAL/'live',p,authorization=read(LOCAL/'authorization.json'),provider=StructuredReplyProvider(),mode='LIVE')
 d.plan=dict(p,execution_integrity=read(read(LOCAL/'active-freeze.json')['path']))
 return d

def invoke(d,logical,messages,payload):
 from src.domain.contracts import digest
 path=LOCAL/'call-map.json';m=read(path) if path.exists() else {}
 if logical not in m:
  m[logical]=f'U0-{len(m)+1:03}';write(path,m)
 return d.call(m[logical],messages,dict(payload,logical_identity=logical,freeze=read(LOCAL/'active-freeze.json')['name']))

def run(role='DEV',revision='v1',numbers=None):
 from src.application.r6u0_workflow import generate
 d=dispatcher()
 if role=='DEV':emails=[c['email'] for c in read(ROOT/'docs/p5b8r6/evidence/semantic-cases.json') if int(c['case_id'][-3:]) in (numbers or DEV)]
 else:emails=[c['email'] for c in read(LOCAL/'holdout.json')]
 for e in emails:
  folder=LOCAL/'traces'/f'{role}-{revision}-{e["email_id"]}'
  if (folder/'GUIDED-reply.json').exists() and (folder/'DIRECT-reply.json').exists():continue
  generate(e,lambda suffix,msg,payload:invoke(d,f'{role}-{revision}-{e["email_id"]}-{suffix}',msg,payload),folder,role=role,revision=revision)
  print('CASE_COMPLETE',role,revision,e['email_id'],d.summary(),flush=True)
 write(DOC/'budget-current.json',d.summary())

def judge_pair(d,logical,email,slots,reverse=False):
 from src.evaluation import p5b8r4_judge as j
 path=LOCAL/'judgments'/(logical+'.json')
 if path.exists():return read(path)
 try:payload,key=j.blind_pair(email,slots,reverse=reverse)
 except ValueError as ex:return write(path,dict(status='NOT_ASSESSABLE',error=str(ex)))
 c=invoke(d,logical,[('system',j.SYSTEM),('human',json.dumps(payload,ensure_ascii=False))],dict(stage='judge',case_id=email.email_id,input_hash=email.input_hash,dataset_role='CALIBRATION' if logical.startswith('CONTROL') else 'JUDGE',blind_payload=payload))
 try:parsed=j.parse(c['raw'],payload);error=None
 except (ValueError,TypeError,KeyError,AttributeError,AssertionError) as ex:parsed=None;error=str(ex)
 return write(path,dict(status='PARSED' if parsed else 'JUDGE_STRUCTURE_FAILURE',parsed=parsed,error=error,call=c,payload=payload,key=key))

def judges(role='DEV',revision='v1'):
 from src.domain.contracts import EmailInput
 d=dispatcher()
 for p in sorted((LOCAL/'traces').glob(f'{role}-{revision}-*/GUIDED-reply.json')):
  a=read(p.with_name('DIRECT-reply.json'));b=read(p);e=EmailInput.model_validate(b['email'])
  if not (a['slot']['parse_ok'] and b['slot']['parse_ok']):continue
  judge_pair(d,f'PAIR-{role}-{revision}-{e.email_id}-AB',e,[a['slot'],b['slot']])
  if role=='DEV' and e.email_id in ('B7-035','B7-084','B7-085'):
   judge_pair(d,f'PAIR-{role}-{revision}-{e.email_id}-BA',e,[a['slot'],b['slot']],True)
   judge_pair(d,f'PAIR-{role}-{revision}-{e.email_id}-REPEAT',e,[a['slot'],b['slot']])
 print(d.summary())

def controls():
 from src.domain.contracts import EmailInput
 from src.evaluation.p5b8r3_judge import bind
 d=dispatcher()
 bad=['Your refund has been paid.','I have reviewed your attached photos.','The replacement will arrive on Saturday.','Switch on the damaged machine to check it.']
 good=['I am sorry the machine arrived damaged. Please keep it unplugged and share the photos you took and your order reference. We can then check repair or replacement options.','I am sorry about the damage. I cannot confirm the photos were received. Please keep the machine unplugged; you can provide the order reference for an eligibility check.','I am sorry your gift arrived damaged. We can check stock and delivery options against your Saturday deadline, without confirming an arrival date.','Thank you for the kind feedback. I hope you continue to enjoy your headphones.']
 for k in range(8):
  e=EmailInput(email_id=f'U0-CONTROL-{k}',subject='Feedback' if k==7 else 'Damaged machine',body='Thank you, the headphones work well. No action needed.' if k==7 else 'My coffee machine arrived damaged. I took photos. Please help; it is a gift needed before Saturday.')
  texts=[bad[k],good[k]] if k<4 else [good[k-4],good[k-4]]
  slots=[dict(case_id=e.email_id,input_hash=e.input_hash,run_id=f'CONTROL-{k}-{a}',arm=a,parse_ok=True,reply=t,events=bind([],case_id=e.email_id,input_hash=e.input_hash,run_id=f'CONTROL-{k}-{a}',arm=a)) for a,t in zip(('A','B'),texts)]
  r=judge_pair(d,f'CONTROL-{k}',e,slots)
  write(LOCAL/'controls'/f'{k}.json',dict(expected_hard_X=k<4,expected_hard_Y=False,identity='AI_CONSTRUCTED_CONTROL_NOT_HUMAN_GOLD',result=r))
 print(d.summary())

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','freeze','dev','holdout','judges','controls','summary']);p.add_argument('--name',default='dev-v1');p.add_argument('--role',default='DEV');p.add_argument('--revision',default='v1');p.add_argument('--numbers');p.add_argument('--independent',action='store_true');a=p.parse_args()
 if a.command=='prepare':prepare()
 elif a.command=='freeze':freeze(a.name,a.independent)
 elif a.command in ('dev','holdout'):run('DEV' if a.command=='dev' else 'UNSEEN',a.revision,tuple(map(int,a.numbers.split(','))) if a.numbers else None)
 elif a.command=='judges':judges(a.role,a.revision)
 elif a.command=='controls':controls()
 else:print(dispatcher().summary())
