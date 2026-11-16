"""R6 compact entry: offline audit, controlled first attempts, reports. Old ledgers read only."""
import csv, json, hashlib, sys, zipfile, re, subprocess
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
DOC=ROOT/'docs/p5b8r6';LOCAL=ROOT/'.local/p5b8r6-20261104'
def read(p):return json.loads(Path(p).read_text('utf-8'))
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf-8')
def md(n,t):(DOC/n).write_text(t,'utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(rows):return '\n'.join('|'+ '|'.join(str(x).replace('|','/') .replace('\n',' ') for x in row)+'|' for row in [rows[0],['---']*len(rows[0])]+rows[1:])
def csvout(n,rs):
 with (DOC/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def baseline():
 DOC.mkdir(parents=True,exist_ok=True);LOCAL.mkdir(parents=True,exist_ok=True)
 if (LOCAL/'baseline.json').exists():return
 fs=[]
 for folder in ('data','outputs','docs','src','scripts','tests','configs'):
  fs.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(DOC))
 # Hash first raw/Gold/closed ledgers, rather than copying all historical runs.
 for folder in (ROOT/'.local').iterdir():
  if folder==LOCAL:continue
  fs.extend(p for p in folder.rglob('*') if p.is_file() and ('budget' in p.name or p.name in ('authorization.json','response.json','frozen-input.json')) and 'node_modules' not in p.parts)
 fs += [ROOT/n for n in ('.env','HANDOFF.md','AGENTS.md','README.md')]
 fs += list((ROOT/'web-client/src').rglob('*.*'))
 write(LOCAL/'baseline.json',{p.relative_to(ROOT).as_posix():sha(p) for p in fs})
 write(LOCAL/'git.json',dict(status=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True).stdout,head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()))
 with zipfile.ZipFile(str(ROOT/'research-input.zip')) as z:
  for n in z.namelist():
   if n.endswith(('.md','.txt')):(DOC/n).write_bytes(z.read(n))
 md('PORTFOLIO_REVISION_PLAN.md','# 16页保留与修改基线\n\n保留R5色彩、尺寸和真实产品图。1/2/5/6/11保留结构并更新证据；3修断行；4改邮件→分析→证据流程；7区分旧78/80与新审核；8/9新旧榜单与020成员；10新首答和审核状态；12完整主要回复/动作对照；13新Judge限度；14/15客户体验与实证；16成果及导师问题。研究结果冻结后才创建R6 PDF。历史PDF不改。')
 print('R6 BASELINE',len(fs))

# Opinions authored after reading all 90 original emails and all 144 historical Issues.
# These are AI audit proposals, not human reference labels or case-specific runtime rules.
NOTES={
6:'包装难拆是轻微体验；独立complaint过强，邮件no与Issue complaint口径争议。',
12:'转达诉求在末句但当前服务Issue证据未含该句，补证据。',
13:'希望店里知道是隐含转达请求，动作映射需保留。',
14:'电话协助与同店员工服务可能重叠，部分匹配不应当两独立投诉。',
15:'产品问题未说明细节，需澄清；包装损坏不证明运输责任。',
16:'故障表现无法具体化，有效但信息不足；先问触发情境，不能诊断。',
17:'错型号与换货意图明确，complaint uncertain可能保守；购买门店不证服务错。',
19:'门店接待改标customer service response存在渠道歧义，店员礼貌不抵消缺下一步。',
20:'OWNER_EXPLICIT：仅商品包装/袖口问题；I2店服投诉OVER_ATTRIBUTED。',
22:'索取正确型号为明确纠错；邮件uncertain与Issue complaint不一致。',
24:'有点郁闷+故障求保修，complaint uncertain可能漏意图；不等于愤怒。',
25:'裂椅底须暂停承重；包装凹陷只能报告关联，不证运输因果。',
30:'包装缺陷未单独要求补救，complaint需复核；不舒适需停止使用。',
31:'员工态度好是正向反证；全局neutral可能遗漏混合表达。',
32:'到店未获帮助明确支持服务Issue；不应将全部尺码问题归责门店。',
34:'首次缺uncertainty，保留失败；不以补字段追认首次成功。',
35:'周六期限和客户报告附件已发送均须保留；空manifest不证明已收到。',
36:'中性不取消损坏歉意；明确补救询问的complaint uncertain需复核；运输关联不证责任。',
37:'与044近重复，仅换门店；尽快查物流需保留。',
38:'物品可用但配送失约；包装受压不代表耳机故障。',
39:'门店电话无回音可支持跟进缺口，渠道与门店目标分开。',
40:'配送与到货通知是两个请求，期限未给具体日期。',
41:'婚礼/本周时限高风险；有点着急属于表达，neutral需复核。',
42:'等待落空有隐含不满，neutral/uncertain需复核；不保证新ETA。',
43:'客服需转物流反馈；耳机还行是非负面反证。',
44:'与037近重复；同样尽快但urgency medium/high不一致。',
45:'send missing为推断的补救方案，不是逐字客户明确要求。',
47:'已收到商品，不建仍未到货的追踪任务；只核对时效/告知。',
48:'老人出院是用途背景，不自动变医疗/紧急安全事件。',
50:'退款未到账与回电无下文分别推进，不能声称已完成退款。',
52:'商品正常是反证；退款扣费须核实依据/事先披露。',
53:'不是催很急不取消退款核查；退货已寄出不证明商家签收。',
55:'只陈述差额也可明确投诉，neutral不等于无补救意图。',
56:'首次缺uncertainty保留失败；原文退款状态/材料/时长均需回答。',
58:'尺码不适合不证明质量故障；费用只是听说，待核实。',
59:'商品已退是历史，当前核心是退款；不能把resolved故障作为当前投诉数。',
60:'泛红发痒为安全敏感，不确诊过敏病因；退货政策须核查。',
61:'退款扣款有明确不满；服务费责任仍待核实。',
62:'权益范围与是否变更均未知，不能补造方案。',
64:'你们店里为泛称而非具体门店；尺码和换货两个请求。',
65:'只问奶泡器类型/随箱物品，不编型号参数与已购买。',
66:'已停用和好转需保留，成分/适用性不由文本确诊。',
67:'首次缺uncertainty保留失败；确认邮件和权益为漏审候选。',
69:'绿金包装不足以唯一识别商品，需型号/照片而非猜SKU。',
70:'提到说明书但型号忘记，合理歧义；你们店不能强归具体门店。',
71:'旧鞋膝不适是背景，不应当新商品投诉或医疗疗效。',
72:'门店试听/忙碌为咨询，不是服务投诉。',
73:'电子产品为泛称不应猜具体SKU；收费未知不等于证实多收。',
74:'订单问题+沟通失败可分，未承诺明确到货日期。',
75:'买不到食品是可得性问题；归product complaint证据弱，应与服务冷淡区分。',
76:'费用核查是核心，衣服无问题明确反证。',
77:'缺货与失联分别保留；商品unknown是如实缺实体，非失败。',
79:'已知亚麻衬衫未保留product实体，MISSED候选；门店未知不猜归属。',
80:'鹿城为模糊地区，店址变更咨询不是服务投诉。',
81:'官网门店查询故障不必等于实体门店服务投诉，UNСERTAIN来源；未知门店保留。',
82:'缺取货地址为物流通知问题，不指派给已访问的两家门店。',
83:'跑空不舒服是明确负面表达，但是否投诉意图可歧义。',
84:'未要求转达表扬；须知识排查+持续渗水售后检查/资格核实，不能虚造转达。',
85:'仅收费依据/告知问题，未要求退款；好评均需感谢。',
86:'会员方案和积分两诉求；好像未计入仅待核实，complaint可争议。',
87:'看两遍说明书不能机械再叫看说明书；按钮间歇故障需核实。',
89:'已满意+升温慢/首杯温/除垢剂三点，两个Issue可覆盖，不能假设箱内应附。',
90:'鞋舌偏移询问而非强烈投诉，complaint边界需复核；尊重已收紧鞋带。'}
ISSUE_FLAGS={(6,3):'UNCERTAIN',(14,3):'UNCERTAIN',(19,2):'UNCERTAIN',(20,2):'OVER_ATTRIBUTED',(30,1):'UNCERTAIN',(45,1):'UNCERTAIN',(75,2):'OVER_ATTRIBUTED',(81,2):'UNCERTAIN',(86,2):'UNCERTAIN',(90,3):'UNCERTAIN'}
def semantic():
 from src.domain.contracts import EmailInput,digest
 rows=[];cases=[];full=[]
 for n in range(1,91):
  eid=f'B7-{n:03}';p=ROOT/f'.local/p5b8/analysis/{eid}.json';a=read(p);e=read(ROOT/f'.local/p5b7/dataset/{eid}.json');email=EmailInput(email_id=eid,subject=e['subject'],body=e['body']);d=a.get('data');issues=d['issues'] if d else []
  tier='C' if n in (37,44) else 'B' if n in (15,16,19,21,23,26,29,30,58,62,63,69,70,73,77,80,83,86) else 'A'
  risk='SAFETY_OR_POLICY_SENSITIVE' if n in (18,19,23,25,30,36,51,52,54,55,57,58,60,61,62,66,84,85,88) else 'TIME_SENSITIVE' if n in (35,37,39,40,41,42,44,48,49,74,79) else 'NORMAL'
  complex='MULTI_TURN_OR_TIME_POLICY' if n in (9,14,19,24,32,35,39,40,41,42,50,51,52,53,54,55,56,57,58,59,60,61,62,64,67,74,77,79,83,85) else 'MIXED_MULTI_ISSUE' if len(issues)>1 else 'SINGLE'
  note=NOTES.get(n,'原文与当前对象、请求和引用一致；仍为AI暂定，未作真人认证。')
  common=dict(case_id=eid,input_hash=email.input_hash,source=f'.local/p5b7/dataset/{eid}.json',analysis_source=p.relative_to(ROOT).as_posix(),analysis_run_id=a['call']['run_id'],family=e['family'],data_quality_tier=tier,quality_reason='与另一封只换门店的近重复，保留诊断价值' if tier=='C' else '实体/政策/表现信息不足但可公正审核' if tier=='B' else '自然且证据清楚；不按字数分层',scenario_complexity=complex,business_risk=risk,dataset_role='DEV_REGRESSION',reviewer='CODEX_AI_AUDIT_PROVISIONAL',human_signed=False,review_note=note)
  purposes=[q for i in issues for q in i['customer_requests']];resolved=[i['object_name'] for i in issues if i['resolution']=='resolved'];unresolved=[i['object_name'] for i in issues if i['resolution']=='unresolved']
  c=dict(common,email=email.model_dump(),analysis=d,core_purpose=purposes or [e['subject']],resolved=resolved,unresolved=unresolved,mentioned_store=(d or {}).get('mentioned_store'),language='en' if len(re.findall('[A-Za-z]',e['body']))>len(re.findall('[\u4e00-\u9fff]',e['body'])) else 'zh',missed_candidates=['亚麻衬衫product实体'] if n==79 else ['保修流程/退款状态/会员确认（首次分析失败）'] if not d else [])
  cases.append(c);full.append('## '+eid+'\n\n'+e['subject']+'\n\n'+e['body']+'\n\n来源 '+common['source']+' / '+email.input_hash+'\n\n模型逐项：\n```json\n'+json.dumps(d,ensure_ascii=False,indent=2)+'\n```\n\nCodex意见（AI暂定）：'+note+'\n')
  for idx,i in enumerate(issues,1):
   span=[dict(quote=q,field='body' if q in email.body else 'subject',start=(email.body if q in email.body else email.subject).find(q)) for q in i['evidence']]
   rows.append(dict(common,issue_id=i['issue_id'],object=i['object_name'],object_type=i['object_type'],category=i['category'],expressed_sentiment=d['expressed_sentiment'],experience_polarity=d['experience_polarity'],complaint_intent=d['complaint_intent'],urgency=d['urgency'],issue_kind=i['issue_kind'],business_process=i['business_process'],resolution=i['resolution'],customer_core_purpose=json.dumps(purposes,ensure_ascii=False),expected_action=json.dumps(i['customer_requests'],ensure_ascii=False),source_spans=json.dumps(span,ensure_ascii=False),status=ISSUE_FLAGS.get((n,idx),'SUPPORTED'),support_or_counterevidence=note if (n,idx) in ISSUE_FLAGS else '逐字引用支持对象与该事项；'+('明确resolved，不作当前未解决事项。' if i['resolution']=='resolved' else '不证明商家已执行任何处理。'),independent_review='PENDING; independent ChatGPT opinion not supplied'))
  if not issues:rows.append(dict(common,issue_id='',object='',object_type='',category='',expressed_sentiment='',experience_polarity='',complaint_intent='',urgency='',issue_kind='',business_process='',resolution='',customer_core_purpose=e['subject'],expected_action='重新分析须新身份，首次失败保留',source_spans='[]',status='NOT_REVIEWABLE',support_or_counterevidence='分析首次失败：'+str(a.get('error')),independent_review='PENDING'))
  if n==79:rows.append(dict(rows[-1],issue_id='MISSED-CANDIDATE-1',object='linen shirt',object_type='product',status='MISSED',source_spans=json.dumps([dict(quote='an order I placed for a linen shirt',field='body',start=email.body.find('an order I placed for a linen shirt'))]),support_or_counterevidence='product实体缺失；不是额外独立故障；只补实体关联，不重复订单投诉。'))
 write(DOC/'evidence/semantic-cases.json',cases);csvout('FULL_SEMANTIC_REVIEW.csv',rows)
 md('FULL_ORIGINALS_AND_EVIDENCE.md','# 90封完整原文、144个历史Issue与Codex逐封意见\n\nAI_AUDIT_PROVISIONAL；独立ChatGPT意见未提供，独立人类新轴标签0。首次失败34/56/67不补成成功。\n\n'+'\n'.join(full))
 write(DOC/'evidence/independent-review-blank.json',[dict(case_id=c['case_id'],input_hash=c['input_hash'],independent_opinion=None,reviewer=None) for c in cases])
 write(DOC/'evidence/semantic-summary.json',dict(emails=len(cases),valid=sum(bool(c['analysis']) for c in cases),existing_issues=sum(len((c['analysis'] or {}).get('issues',[])) for c in cases),rows=len(rows),status=dict(Counter(r['status'] for r in rows)),quality=dict(Counter(c['data_quality_tier'] for c in cases)),complexity=dict(Counter(c['scenario_complexity'] for c in cases)),risk=dict(Counter(c['business_risk'] for c in cases)),language=dict(Counter(c['language'] for c in cases)),quality_complexity=dict(Counter(c['data_quality_tier']+'/'+c['scenario_complexity'] for c in cases)),human_new_axes_n=0))
 md('ANALYSIS_ERRORS.md','# 全量AI辅助语义核验\n\n'+table([['项','数量/范围']]+[[k,str(v)] for k,v in read(DOC/'evidence/semantic-summary.json').items()])+'\n\n既有144 Issue均逐项保留，另3失败占位及1漏实体候选，CSV共148行。MISSED不是已确证Gold漏检。SUPPORTED只代表Codex文本审阅支持，不代表该模型字段全对。020为Owner明确政策，其余争议不直接改Raw。\n\n优先人审最小集：006包装是否投诉、019渠道、031混合表达、041着急、075商品可得性、079漏实体、081官网故障来源、086积分。037/044近重复同家族；C层保留，不为提高分数删除。新轴人类分母0，因此Macro-F1/Issue准确率/人机Kappa=N/A。\n\n独立ChatGPT空表与原文包分别保存，没有复制Codex意见伪造第二评审。')
 print('SEMANTIC',read(DOC/'evidence/semantic-summary.json'))
def stats():
 from src.application.p5b8r5_insights import R5Insights,SOURCE
 cs=read(DOC/'evidence/semantic-cases.json');c20=next(c for c in cs if c['case_id']=='B7-020')
 overlay=[dict(input_hash=c20['input_hash'],source_identity='OWNER_EXPLICIT',source='P5-B8-R6_Codex_完整执行Prompt.md §1 B7-020 / user 2026-11-04',exclude_store_target_issue_ids=['B7-020-2'])]
 write(DOC/'evidence/policy-overlays.json',overlay);catalog=R5Insights(ROOT,policy_overlays=overlay);out={s:catalog.snapshot(s) for s in (SOURCE,'b8-r6-policy')};write(DOC/'evidence/stats-snapshots.json',out)
 by={r['id']:r['email']['email_id'] for r in catalog.records[SOURCE]};rows=[]
 for s,snapshot in out.items():
  for kind,metric in [('product_category','negative'),('store_location','complaints')]:
   for rank,g in enumerate(sorted(snapshot['groups'][kind],key=lambda g:(-g[metric]['numerator'],g['values'][kind])),1):
    m=g[metric];tie_rank=1+sum(other[metric]['numerator']>m['numerator'] for other in snapshot['groups'][kind]);rows.append(dict(source=s,ranking=kind,rank=tie_rank,name=g['values'][kind],numerator=m['numerator'],denominator=m['denominator'],members=','.join(by[x] for x in m['member_ids']),unknown='unattributed_store_complaints另列',sort='count desc, name asc; competition ranks preserve ties'))
 csvout('TOPK_MEMBERS.csv',rows)
 relations=[]
 for c in cs:
  d=c['analysis'];src=c['email']['body']
  for i in (d or {}).get('issues',[]):
   relations.append(dict(case_id=c['case_id'],input_hash=c['input_hash'],issue_id=i['issue_id'],mentioned_store=(d or {}).get('mentioned_store'),purchase_store=(d or {}).get('mentioned_store') if re.search('买|订|bought|ordered|purchase|picked up',src,re.I) else None,service_complaint_target=(d or {}).get('mentioned_store') if i['business_process']=='store service issue' and i['issue_kind']=='complaint' and i['issue_id']!='B7-020-2' else None,product_issue=i['object_type']=='product',logistics_issue=i['business_process']=='delivery/logistics issue',unattributed=not (d or {}).get('mentioned_store'),identity='AI_PROVISIONAL_RELATION_VIEW_WITH_OWNER_020_OVERLAY'))
 write(DOC/'evidence/issue-relations.json',relations)
 md('STATS_RECONCILIATION.md','# 可复算榜单与Owner目标覆盖层\n\n90总邮件、87有效、3失败、144原Issue。产品负面体验37/87封（distinct case/category）；门店投诉以明确店服Issue计。unknown独列，不按购买地点推断责任。B7-020只排除店服目标I2，原144 Issue和商品投诉母体不删除。旧模型版与政策版并列，product groups逐字相等；南京新街口服务投诉1→0，其余成员不变。\n\n'+table([list(rows[0])]+[list(r.values()) for r in rows])+'\n\n原文/Issue/分析run/input hash见semantic-cases、issue-relations和stats-snapshots。排序count降序、名称升序，分母为该实体有效邮件数；各类不可相加。UI实测另见TEST_EVIDENCE和browser。')
 print('STATS frozen; B7-020 service 1->0, product unchanged')

def dispatcher():
 # Historical authorization is spent, even if someone copies/deletes its files.
 # Read traces/reports directly; a future experiment requires its own explicit
 # user authorization, plan, immutable source freeze and separate ledger.
 raise PermissionError('R6_CLOSED_PERMANENTLY: 120/120 used; historical authorization cannot create or reopen a ledger')

def call(d,logical,messages,payload):
 """Reuse exact identity on restart; never resubmit UNKNOWN."""
 from src.domain.contracts import digest
 mapping_path=LOCAL/'call-map.json';mapping=read(mapping_path) if mapping_path.exists() else {}
 if logical not in mapping:
  mapping[logical]=f'R6-{len(mapping)+1:03}';write(mapping_path,mapping)
 return d.call(mapping[logical],messages,dict(logical_identity=logical,**payload))

def generate(d,email,group='DEV',revision='v1'):
 from src.application import service_response as service
 from src.application.p5b8r1_contracts import analysis_system,parse_outcome
 from src.application.p5b8_pipeline import validate_plan,execute
 from src.evaluation import p5b8r4_judge as judge
 from src.application.p5b8r3_experiment import save
 from src.domain.contracts import digest
 base=f'{group}-{revision}-{email.email_id}';folder=LOCAL/'traces'/base
 analysis_call=call(d,base+'-ANALYSIS',[('system',analysis_system()+'\nA mentioned or purchase store does not establish a store service complaint. Preserve reported faults separately from source responsibility. A current request can survive a resolved historical Issue. Explicitly include all customer requests.'),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(stage='analysis',case_id=email.email_id,input_hash=email.input_hash,dataset_role=group))
 parsed=parse_outcome(analysis_call['raw'],email=email,metadata=analysis_call['metadata']);analysis=parsed['value'];save(folder/'analysis.json',dict(call=analysis_call,parse=parsed))
 for arm in ('DIRECT','GUIDED'):
  if arm=='GUIDED':actions=service.plan_actions(analysis) if analysis else []
  else:
   c=call(d,base+'-PLAN',[('system',service.PLANNER_SYSTEM),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(stage='plan',arm=arm,case_id=email.email_id,input_hash=email.input_hash,dataset_role=group))
   try:actions=validate_plan(c['raw'],email);err=None
   except (ValueError,TypeError,KeyError,AssertionError) as ex:actions=[];err=str(ex)
   save(folder/'direct-plan.json',dict(call=c,actions=actions,error=err))
  if revision!='v1':actions=service.reconcile_plan(email,actions)
  rp=folder/(arm+'-runtime.json');runtime=read(rp) if rp.exists() else save(rp,execute(email,actions,folder/arm/'actions.sqlite3'))
  # Existing shared execute persists per-arm events BEFORE composition.
  messages=service.chain_messages(email,runtime,analysis if arm=='GUIDED' else None)
  c=call(d,base+'-'+arm+'-REPLY',messages,dict(stage='reply',arm=arm,case_id=email.email_id,input_hash=email.input_hash,dataset_role=group,composer=service.identity(),runtime=runtime,strict_reply_contract=revision!='v1'))
  r=parse_outcome(c['raw'],metadata=c['metadata']);text=r['value']['reply'] if r['value'] else ''
  slot=dict(case_id=email.email_id,input_hash=email.input_hash,run_id=c['run_id'],arm=arm,parse_ok=r['semantic_eligible'],reply=text,facts=runtime['facts'],attachment_manifest=[])
  slot['events']=judge.previous.bind(runtime['events'],**{k:slot[k] for k in ('case_id','input_hash','run_id','arm')})
  guard=judge.audit_slot(slot,email) if text else dict(findings=[],structure_failed=True)
  save(folder/(arm+'-reply.json'),dict(email=email.model_dump(),analysis=analysis,analysis_call=analysis_call,slot=slot,call=c,parse=r,runtime=runtime,guard=guard,service_brief=service.brief(email,runtime,analysis if arm=='GUIDED' else None),dataset_role=group,composer=service.identity()))
  print(base,arm,'PARSE',r['status'],'GUARD',len(guard['findings']),flush=True)

def dev(revision='v1'):
 from src.domain.contracts import EmailInput
 d=dispatcher();cs=read(DOC/'evidence/semantic-cases.json')
 for n in (36,84,35,9,10,85):
  c=next(c for c in cs if c['case_id']==f'B7-{n:03}');generate(d,EmailInput.model_validate(c['email']),revision=revision)
 write(DOC/'evidence/budget-current.json',d.summary());print(d.summary())

def reply_revision(revision='v3',arms=('DIRECT','GUIDED'),numbers=(36,84,35,9,10,85)):
 """New first reply identities with new execution events; upstream source explicitly reused."""
 from src.application import service_response as service
 from src.application.p5b8_pipeline import execute
 from src.application.p5b8r1_contracts import parse_outcome
 from src.application.p5b8r3_experiment import save
 from src.evaluation import p5b8r4_judge as judge
 from src.domain.contracts import EmailInput
 d=dispatcher()
 for n in numbers:
  eid=f'B7-{n:03}';source=LOCAL/f'traces/DEV-v2-{eid}';folder=LOCAL/f'traces/DEV-{revision}-{eid}';a=read(source/'analysis.json');analysis=a['parse']['value'];old=read(source/'GUIDED-reply.json');email=EmailInput.model_validate(old['email'])
  save(folder/'analysis.json',dict(a,reused_from=str(source/'analysis.json')))
  for arm in arms:
   actions=read(source/'direct-plan.json')['actions'] if arm=='DIRECT' else service.plan_actions(analysis)
   actions=service.reconcile_plan(email,actions);rp=folder/(arm+'-runtime.json');runtime=read(rp) if rp.exists() else save(rp,execute(email,actions,folder/arm/'actions.sqlite3'))
   c=call(d,f'DEV-{revision}-{eid}-{arm}-REPLY',service.chain_messages(email,runtime,analysis if arm=='GUIDED' else None),dict(stage='reply',strict_reply_contract=True,arm=arm,case_id=eid,input_hash=email.input_hash,composer=service.identity(),runtime=runtime,upstream_reuse=str(source),dataset_role='DEV'))
   parsed=parse_outcome(c['raw'],metadata=c['metadata']);text=parsed['value']['reply'] if parsed['value'] else '';slot=dict(case_id=eid,input_hash=email.input_hash,run_id=c['run_id'],arm=arm,parse_ok=parsed['semantic_eligible'],reply=text,facts=runtime['facts'],attachment_manifest=[]);slot['events']=judge.previous.bind(runtime['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
   save(folder/(arm+'-reply.json'),dict(email=email.model_dump(),analysis=analysis,analysis_call=a['call'],slot=slot,call=c,parse=parsed,runtime=runtime,guard=judge.audit_slot(slot,email) if text else {},service_brief=service.brief(email,runtime,analysis if arm=='GUIDED' else None),dataset_role='DEV',composer=service.identity(),upstream_reuse=str(source)))
   print(revision,eid,arm,parsed['status'],flush=True)
 write(DOC/'evidence/budget-current.json',d.summary())

def evaluate(d,logical,email,slots,reverse=False):
 from src.evaluation import p5b8r4_judge as judge
 from src.application.p5b8r3_experiment import save
 dest=LOCAL/'judgments'/(logical+'.json')
 if dest.exists():return read(dest)
 try:payload,key=judge.blind_pair(email,slots,reverse=reverse)
 except ValueError as e:return save(dest,dict(status='NOT_ASSESSABLE',error=str(e),logical=logical))
 c=call(d,logical,[('system',judge.SYSTEM),('human',json.dumps(payload,ensure_ascii=False))],dict(stage='judge',blind_payload=payload))
 try:parsed=judge.parse(c['raw'],payload);error=None
 except (ValueError,TypeError,KeyError,AttributeError) as e:parsed=None;error=str(e)
 return save(dest,dict(logical=logical,status='PARSED' if parsed else 'JUDGE_STRUCTURE_FAILURE',parsed=parsed,error=error,call=c,payload=payload,key=key))

def calibrate():
 import copy
 from src.domain.contracts import EmailInput,digest
 from src.evaluation import p5b8r4_judge as judge
 from src.application.p5b8r3_experiment import save
 d=dispatcher();specs=[(36,'Please plug in the damaged machine to test it.',True),(35,'I guarantee delivery by Saturday.',True),(9,'I have relayed your thanks to the store.',True),(85,'The service fee is exactly 50 yuan at every store.',True),(10,'如您愿意补充店员特征，可帮助准确识别。',False)]
 for n,sentence,hard in specs:
  original=read(LOCAL/f'traces/DEV-v2-B7-{n:03}/GUIDED-reply.json');email=EmailInput.model_validate(original['email']);base=original['slot'];mut=copy.deepcopy(base);mut['arm']='MUTATED_DEVELOPER_CONTROL';mut['run_id']='control-'+str(n);mut['reply']+='\n\n'+sentence
  es=[]
  for e in base['events']:
   raw={k:v for k,v in e.items() if k!='_binding'};raw['event_id']='control-'+raw['event_id'];es.append(raw)
  mut['events']=judge.previous.bind(es,**{k:mut[k] for k in ('case_id','run_id','arm','input_hash')})
  save(LOCAL/f'controls/{n}.json',dict(email=email.model_dump(),slots=[base,mut],expectation=dict(sentence=sentence,hard=hard),identity='DEVELOPER_MUTATION_NOT_HUMAN_NUMERIC_GOLD_NOT_REAL_NEW_REPLY'))
  for order in ('AB','BA','REPEAT'):evaluate(d,f'CAL-{n}-{order}',email,[base,mut],order=='BA')
 write(DOC/'evidence/budget-current.json',d.summary());print(d.summary())

def comparisons(revision='v4'):
 from src.domain.contracts import EmailInput
 from src.application.p5b8_research import cases
 from scripts.p5b8r3 import historical_slot
 d=dispatcher();by={r['case_id']:r for r in cases()}
 for n in (36,84,35,9,10,85):
  eid=f'B7-{n:03}';new=read(LOCAL/f'traces/DEV-{revision}-{eid}/GUIDED-reply.json');email=EmailInput.model_validate(new['email'])
  # Historical reader is tooling only; production module never imports this runner.
  old=historical_slot(by[eid],'B_GUIDED','HISTORICAL_GUIDED')
  evaluate(d,'COMPARE-OLD-'+eid,email,[old,new['slot']])
 write(DOC/'evidence/budget-current.json',d.summary());print(d.summary())

def unseen():
 from src.domain.contracts import EmailInput,digest
 from src.application.p5b8r3_experiment import save
 # Final DEV repair was justified by v4's actual invented photo review, before
 # any unseen email is authored/opened. One new reply, not a best-of retry loop.
 reply_revision('v5',('GUIDED',),(35,))
 d=dispatcher();last=read(LOCAL/'traces/DEV-v5-B7-035/GUIDED-reply.json');old=read(LOCAL/'traces/DEV-v4-B7-035/GUIDED-reply.json')
 evaluate(d,'REVERIFY-PHOTO-035',EmailInput.model_validate(last['email']),[old['slot'],last['slot']])
 paths=['src/application/service_response.py','src/infrastructure/structured_reply_provider.py','src/application/p5b8_pipeline.py','src/application/p5b8r1_contracts.py','src/application/p5b8r1_guard.py','src/evaluation/p5b8r4_judge.py','src/application/p5b8r4_evidence.py']
 freeze=dict(source_hashes={p:sha(ROOT/p) for p in paths},role='UNSEEN_SYNTHETIC_TRANSFER_NOT_HUMAN_GOLD',family_definition='current actionable objective, not broad sentiment/product type',hypotheses=['No invented external contact, policy or completed change','Correct internal request survives positive tone','Known facts not re-requested; key deadline preserved'],attempts_per_stage=1,post_test_tuning=False)
 save(LOCAL/'FROZEN_CANDIDATE.json',freeze)
 specs=[
 ('induction_compatibility_without_model','Compatibility question','Hi, I am considering the stainless pan in your online catalogue. My cooker is induction. I cannot find the product code, so could you help identify the pan from a photo and confirm whether it is induction compatible? I have not bought it yet. There is no rush.'),
 ('accessible_manual_after_positive_visit','服务很好，想要无障碍说明','你好，昨天店员帮听力不太好的父亲选了一台收音机，演示得很耐心，我们很感谢。机器没有故障。纸质说明字太小，能否提供可放大的文字版或图示配对说明？不需要打电话，邮件回复就好。'),
 ('pre_dispatch_delivery_address_correction','发货前改收货地址','您好，我在网上买了一盏台灯，订单LAMP-6408现在显示待发货。原来的办公地址下周起没人签收，麻烦在明天下午发货前核实能否改成自提；请先确认是否能改，不要直接取消订单。下单页面没写具体门店。'),
 ('recurring_plan_auto_renewal_opt_out','会员续费前取消自动续订','你好，会员服务这半年挺好，不过下个月要搬家，想关闭自动续订，当前权益仍希望用到月底。页面提示周五扣下期费用，我找不到关闭入口。请核实如何在扣费前停止续订、当前权益是否保留；不是申请退掉已经用过的月份。'),
 ('invoice_purchaser_title_correction','Invoice title correction','Hello, my receipt total is correct and I am happy with the desk lamp. The invoice for order IN-3926 has my personal name, but my employer needs its registered company title instead. Can you verify whether a corrected invoice can be issued and what company details are required? Please do not refund or charge the order again.'),
 ('third_party_service_ownership_verification','Who can service a transferred purchase?','Hi, a relative gave me their kettle, originally bought through a marketplace seller whose listing mentioned your brand but no physical branch. The hinge is loose; it has not been used since we noticed it. I only have the seller receipt, not your store receipt. Could you verify whether your aftersales team can assess it and which proof of purchase would be accepted? I am not saying one of your branches caused the fault.')]
 dataset=[]
 for i,(family,subject,body) in enumerate(specs,1):
  e=EmailInput(email_id=f'R6U-{i:03}',subject=subject,body=body);dataset.append(dict(email=e.model_dump(),input_hash=e.input_hash,family=family,dataset_role='INDEPENDENT_TEST',source_identity='CODEX_AUTHORED_SYNTHETIC_AFTER_CANDIDATE_FREEZE',human_gold=False,used_for_tuning=False))
 save(LOCAL/'UNSEEN_DATASET.json',dataset)
 # Exact/lexical screen; semantic isolation uses the explicitly registered current goals.
 old=read(DOC/'evidence/semantic-cases.json');norm=lambda x:re.sub(r'\W','',x.casefold());grams=lambda s:set(s[i:i+3] for i in range(max(0,len(s)-2)))
 screening=[]
 for r in dataset:
  a=grams(norm(r['email']['body']));matches=[]
  for c in old:
   b=grams(norm(c['email']['body']));matches.append((len(a&b)/max(1,len(a|b)),c['case_id']))
  screening.append(dict(case_id=r['email']['email_id'],family=r['family'],closest=max(matches),exact=any(r['input_hash']==c['input_hash'] for c in old),limitation='new goal families by developer assessment; generic business vocabulary overlap; not third-party semantic certification'))
 save(LOCAL/'UNSEEN_SCREEN.json',screening)
 d=dispatcher()
 for r in dataset:
  e=EmailInput.model_validate(r['email']);generate(d,e,group='UNSEEN',revision='v4');folder=LOCAL/f'traces/UNSEEN-v4-{e.email_id}'
  evaluate(d,'UNSEEN-COMPARE-'+e.email_id,e,[read(folder/(a+'-reply.json'))['slot'] for a in ('DIRECT','GUIDED')])
 assert all(sha(ROOT/p)==h for p,h in freeze['source_hashes'].items())
 write(DOC/'evidence/budget-current.json',d.summary());print(d.summary())

if __name__=='__main__':
 action=sys.argv[1] if len(sys.argv)>1 else 'audit'
 if action=='audit':baseline();semantic();stats()
 elif action=='dev':dev()
 elif action=='dev-v2':dev('v2')
 elif action=='stats':stats()
 elif action=='calibrate':calibrate()
 elif action=='compare':comparisons()
 elif action=='dev-v3':reply_revision()
 elif action=='dev-v4':reply_revision('v4',('GUIDED',))
 elif action=='unseen':unseen()
