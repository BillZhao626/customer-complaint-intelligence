"""Read-only reanalysis and compact research delivery. Never constructs a Provider.

All generated artifacts are new R5 derivatives; no labels or first calls change.
"""
import csv,json,sys,hashlib,re,itertools
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b8r5_insights import R5Insights,SOURCE,VERSION
from src.application.p5b8r4_contracts import parse_reply
from src.evaluation.classification_research import build_report
from src.domain.contracts import digest
DOC=ROOT/'docs/p5b8r5';EV=DOC/'evidence'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf-8')
def md(n,s):(DOC/n).write_text(s+'\n','utf-8')
def block(x):return '\n```json\n'+json.dumps(x,ensure_ascii=False,indent=2)+'\n```\n'
def table(rows):
 rows=[[str(x).replace('|','/').replace('\n',' ') for x in row] for row in rows]
 return '\n'.join(['|'+'|'.join(rows[0])+'|','|'+'|'.join(['---']*len(rows[0]))+'|']+['|'+'|'.join(row)+'|' for row in rows[1:]])
def csvwrite(n,rows):
 with (DOC/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def main():
 EV.mkdir(parents=True,exist_ok=True);c=R5Insights(ROOT);s=c.snapshot(SOURCE);records=c.records[SOURCE];byid={r['id']:r for r in records}
 dump(EV/'dashboard-snapshot.json',s);dump(EV/'analysis-records.json',records)
 # Every chart member resolves to original email, output, Issue and literal span.
 audit=[]
 for dimension in ['product_category','store_location']:
  for g in s['groups'][dimension]:
   entity=g['values'][dimension]
   for measure in ['count','negative','complaints']:
    m=g[measure]
    if not m['member_ids']:audit.append(dict(dimension=dimension,entity=entity,measure=measure,numerator=0,denominator=m['denominator'],case_id='',run_id='',issue_ids=[],quotes=[],input_hash='',status='ZERO_MEMBERS'))
    for rid in m['member_ids']:
     r=byid[rid]
     issues=[i for i in r['issues'] if (dimension=='store_location' or (i['object_type']=='product' and i['category']==entity))]
     audit.append(dict(dimension=dimension,entity=entity,measure=measure,numerator=m['numerator'],denominator=m['denominator'],case_id=r['email']['email_id'],run_id=rid,issue_ids=[i['issue_id'] for i in issues],quotes=[e['quote'] for i in issues for e in i['evidence']],input_hash=r['input_hash'],status='MODEL_OUTPUT_DESCRIPTIVE'))
 for rid in s['unattributed_store_complaints']['member_ids']:
  r=byid[rid];issues=[i for i in r['issues'] if i['issue_kind']=='complaint' and i['business_process']=='store service issue']
  m=s['unattributed_store_complaints']
  audit.append(dict(dimension='unattributed_store_service',entity='unknown',measure='complaints',numerator=m['numerator'],denominator=m['denominator'],case_id=r['email']['email_id'],run_id=rid,issue_ids=[i['issue_id'] for i in issues],quotes=[e['quote'] for i in issues for e in i['evidence']],input_hash=r['input_hash'],status='MODEL_OUTPUT_DESCRIPTIVE'))
 csvwrite('AGGREGATION_RECONCILIATION.csv',audit)
 oldstores=Counter(r['prediction']['store_location'] for r in records if r['prediction'] and r['prediction']['is_complaint'])
 changes=[]
 for g in s['groups']['store_location']:
  k=g['values']['store_location'];m=g['complaints'];changes.append(dict(store=k,old_mentioned_in_complaint_email=oldstores[k],new_store_service_complaint=m['numerator'],members=[byid[x]['email']['email_id'] for x in m['member_ids']]))
 dump(EV/'store-definition-before-after.json',changes)
 product=sorted(s['groups']['product_category'],key=lambda x:(-x['negative']['numerator'],x['values']['product_category']))
 stores=sorted(s['groups']['store_location'],key=lambda x:(-x['complaints']['numerator'],x['values']['store_location']))
 axes={f:{k:v['numerator'] for k,v in d.items()} for f,d in s['axes'].items()}
 unique_product=set(x for g in product for x in g['negative']['member_ids']);issue_n=sum(len(r['issues']) for r in records)
 ranking='# 合成客户邮件中的产品与门店反馈\n\n版本 '+VERSION+'。模型输出的描述统计，来源 `.local/p5b8/analysis/B7-*.json`；每条输入见 evidence/analysis-records.json。\n\n90封派发，87有效，3失败；失败保留总分母。负面表达23/87，负面体验55/87，明确投诉24/87；不确定投诉38/87。产品负面体验涉及'+str(len(unique_product))+'/87封；Issue共'+str(issue_n)+'条。\n\n'+block(axes)
 ranking+='\n产品按邮件/类别去重；负面体验与投诉Issue分别统计。分母是提及该类产品Issue的有效邮件；一封可涉及多类，不可把各类人数相加作为总人数。\n\n'+table([['类别','负面体验/该类','投诉Issue关联/该类','负面体验成员']]+[[g['values']['product_category'],f"{g['negative']['numerator']}/{g['negative']['denominator']}",f"{g['complaints']['numerator']}/{g['complaints']['denominator']}",', '.join(byid[x]['email']['email_id'] for x in g['negative']['member_ids'])] for g in product])
 ranking+='\n\n门店口径：必须有 complaint Issue 且对象为store或业务过程为store service issue。单纯购买门店、产品损坏和物流问题不自动归到门店。下列是模型识别的关联，尚需语义裁决。unknown单列；“你们店”“鹿城”未强行归并，保留别称歧义。\n\n'+table([['门店','提及数','旧：含明确投诉的相关邮件','新：门店服务投诉/提及','成员']]+[[g['values']['store_location'],g['count']['numerator'],oldstores[g['values']['store_location']],f"{g['complaints']['numerator']}/{g['complaints']['denominator']}",', '.join(byid[x]['email']['email_id'] for x in g['complaints']['member_ids'])] for g in stores])
 ranking+='\n\n关键歧义：B7-020原文只描述商品损坏并请求处理，模型却添加门店服务投诉Issue，证据只有“麻烦帮我处理一下”。这一行列为 AI_PROVISIONAL_DISPUTED，不伪造人工修正。若真人判为非门店投诉，南京新街口由1降至0；温州鹿城2仍为本合成样本首位。B7-085收费依据咨询当前标签为inquiry，不因负面体验改成已确认投诉。B7-079/081为2/8封未知门店邮件中的服务投诉，独立显示，不分派给具体门店。产品Service/Other及unknown共3个产品Issue邮件，保留且待复核；不能偷偷移除改善排名。\n\n浏览器与API一致性、点击路径见 UI_ACCEPTANCE.md / evidence/browser-verification.json。复算：`.venv/Scripts/python.exe -X utf8 -B scripts/p5b8r5_research.py`。'
 md('CATEGORY_STORE_RANKING.md',ranking)
 # Legacy classification scores are recomputed with their original reference identity.
 legacy=build_report(ROOT,c);dump(EV/'legacy-classification.json',legacy)
 legacyrows=[]
 for r in legacy['reports']:
  fields=r.get('fields',r.get('metrics',{}))
  for field,m in fields.items():
   if isinstance(m,dict) and 'correct' in m:legacyrows.append(dict(version=r['id'],field=field,correct=m['correct'],n=m['n'],macro_f1=m.get('macro_f1'),identity='DEVELOPMENT_REFERENCE_NOT_NEW_AXES_GOLD'))
 if legacyrows:csvwrite('LEGACY_FIELD_METRICS.csv',legacyrows)
 # Compact human review: preserve source exposure, do not fabricate an independent holdout.
 review=[]
 for p in sorted((ROOT/'.local/p5b8r3/quality-final-v1/dataset').glob('*.json')):
  d=read(p);review.append(dict(case_id=d['email']['email_id'],email=d['email'],input_hash=d['input_hash'],family=d['spec']['family'],source=str(p.relative_to(ROOT)).replace('\\','/'),historical_role=d['role'],current_role='EXPOSED_DEV_HUMAN_REVIEW_PENDING',human_labels=None))
 for eid in ['B7-036','B7-009','B7-084','B7-020']:
  r=next(r for r in records if r['email']['email_id']==eid);review.append(dict(case_id=eid,email=r['email'],input_hash=r['input_hash'],family=r['template'],source='.local/p5b7/dataset/'+eid+'.json',historical_role='EXPOSED_DEV',current_role='EXPOSED_DEV_HUMAN_REVIEW_PENDING',human_labels=None))
 # Exact/near lexical duplication is a screen, not proof of semantic independence.
 norm=lambda t:re.sub(r'\W+','',t.casefold())
 grams=lambda t:set(t[i:i+3] for i in range(max(0,len(t)-2)))
 alltexts=[(r['email']['email_id'],norm(r['email']['subject']+r['email']['body'])) for r in records]
 leakage=[]
 for r in review:
  t=norm(r['email']['subject']+r['email']['body']);a=grams(t);scores=[]
  for eid,v in alltexts:
   b=grams(v);scores.append((len(a&b)/max(1,len(a|b)),eid,t==v))
  best=max(scores);leakage.append(dict(case_id=r['case_id'],closest_b7=best[1],jaccard=best[0],exact=best[2],independent=False,reason='All current cases exposed; lexical novelty does not establish semantic independence'))
 dump(EV/'human-review-inputs.json',review);dump(EV/'leakage-screen.json',leakage)
 csvwrite('HUMAN_LABELS_PENDING.csv',[dict(case_id=r['case_id'],input_hash=r['input_hash'],family=r['family'],expressed_sentiment='',experience_polarity='',complaint_intent='',issues_json='',reviewer='',signed_at='',status='HUMAN_PENDING') for r in review])
 md('HUMAN_REVIEW_PACK.md','# 16封精简盲审材料\n\n仅需填写新的多轴标签，不重复签署旧政策。当前16封均已曝光；用于开发裁决，不作为未见独立测试。请先在不展示预测的本材料标注，再对照机器输出。新多轴独立认证需要另选未见语义家族并独立签署至少12–20封；本轮没有新未见邮件。\n\n'+ '\n'.join('## '+r['case_id']+' · '+r['family']+'\n\n'+r['email']['subject']+'\n\n'+r['email']['body']+'\n\n待填：表达/体验/投诉意图；逐Issue对象、类别、诉求、证据；reviewer与日期。\n' for r in review))
 md('ANNOTATION_MANUAL.md','''# 多轴语义标注手册 v1

标注单位为邮件修订(input_hash)及其中的独立Issue。先读全文，再分轴，不按礼貌词推断体验。

|字段|定义|值及反例|
|---|---|---|
|expressed_sentiment|话语中表达的态度|positive/negative/neutral/mixed/unknown；“谢谢，请问磕碰如何处理”可neutral|
|experience_polarity|所述体验|同五类；产品损坏即负面体验，礼貌不改变它|
|complaint_intent|是否针对当前不满寻求回应/补救|yes/no/uncertain；收费依据咨询不自动等于退款投诉|
|Issue|一个对象、体验和诉求的组合|产品与物流可分两个；同一问题多句证据不拆多项|
|issue_level_sentiment|对该方面的表达态度|可以与全局不同；好喝与渗水同存|
|产品/门店|明确对象与实体|只提购买门店不等于投诉门店；“你们店”保留未知|
|source_evidence|支持这一判断的原文|必须逐字且能支持该语义；合法offset不等于语义支持|
|urgency|当前处理时间约束|周六前礼物需保留期限；历史“昨天”不是紧急依据|
|unknown|证据缺失或无法判定|不填默认积极，不排出分母|

多Issue按对象类型+规范实体+业务过程+诉求做一对一匹配，先实体后诉求，冲突留人工裁决；错配不得用相同数量抵消漏检。Issue召回=匹配Gold Issue/Gold总Issue，精确率=匹配/预测Issue；实体标准化与证据支持分开。无人工签署时不计算新轴Accuracy、F1、Issue召回。

旧80/24 sentiment是单轴邮件总体/主要问题标签，不可直接映射expressed与experience；is_complaint仅映射其原协议的布尔口径，不能认证新版uncertain。旧单产品/门店只能作兼容投影，无法认证多Issue覆盖。16回复参考及6案政策仅支持回复偏好，B4候选仅开发材料，均不是新分类Gold。

反例：赞扬店员+产品漏水→mixed表达、混合体验、分别Issue；感谢解决旧故障→正向，旧故障resolved不再算当前投诉；购买门店+物流受损→门店提及，来源为产品/物流关联，不推断法律责任。
''')
 reps=['B7-036','B7-009','B7-084','B7-035','B7-085','B7-020']
 examples=[]
 for eid in reps:
  r=next(r for r in records if r['email']['email_id']==eid)
  examples.append('## '+eid+'\n\n'+r['email']['subject']+'\n\n'+r['email']['body']+'\n\n原始模型JSON：'+block(r['raw']['data'])+'\n裁决身份：AI_PROVISIONAL / HUMAN_PENDING。已有Owner政策仅约束回复，不签署本JSON语义。\n')
 md('SEMANTIC_CASES.md','# 六个完整语义审查案例\n\n'+'\n'.join(examples)+'\nB7-020为明确的AI待裁争议；B7-036的complaint_intent=uncertain也需按新版手册裁决。不得以字段完整而判全对。')
 md('RQ1_SEMANTIC_VALIDATION.md','# 情绪、Issue与来源归因语义验证\n\n状态 HUMAN_GOLD_PENDING。新轴人工Gold 0；有效模型暂定输出87/90，3失败；独立人工混淆矩阵、Macro-F1、逐类P/R、Issue漏检和实体准确率均N/A，未伪造零错误矩阵。\n\n'+block(axes)+'\n完整六案 SEMANTIC_CASES.md；16封人审材料 HUMAN_REVIEW_PACK.md 与 HUMAN_LABELS_PENDING.csv；原预测 evidence/analysis-records.json。现有90与R3N12均已曝光，R3N历史独立身份保留，但R5不再称未见测试。12新族之间原意图家族成对，后续划分须按家族/模板/整封邮件分组。词法筛查见 evidence/leakage-screen.json，仅筛近重复，不证明语义独立。\n\n旧80/24可在原协议内复算：evidence/legacy-classification.json含混淆矩阵与逐类P/R/F1，原参考身份保留；旧80的78/80为历史情绪参考一致性，不是新轴准确率。映射与不兼容项见 ANNOTATION_MANUAL.md。\n\n发现的实质问题：B7-020店员服务缺乏原文支持；B7-036中性表达与负面体验可并存；B7-085收费解释需求不能自动变退款。最小缺口是有身份签署的新轴语义标签，以及未见家族样本。没有付费请求或独立签署，本轮不认证泛化。')
 # All historical FIRST strings reparsed, original bytes and wire hashes bound.
 hist=read(ROOT/'docs/p5b8r4/evidence/structure-audit.json');first=[]
 for r in hist['rows']:
  now=parse_reply(r['raw'],r['metadata']);wire=read(ROOT/r['wire_source']);first.append(dict(r,r5_first=now['first']['status'],r5_recovery=now['recovery'],actual_model=wire.get('model')))
 dump(EV/'first-124-reaudit.json',first)
 bad=[r for r in first if r['r5_first']=='rejected'];csvwrite('FIRST_FAILURES.csv',[{k:r[k] for k in ['identity','run_id','source','defect','wire_source','wire_sha256','raw_hash','actual_model','response_format','max_tokens']} for r in bad])
 failuretext=[]
 for r in bad:
  original=read(ROOT/r['source']);failuretext.append('## '+r['identity']+'\n\n来源 '+r['source']+'\n\n'+block(original['customer'])+'\n首次原文（保持失败）：'+block(dict(raw=r['raw'],defect=r['defect'],finish_reason=r['metadata'].get('finish_reason'),wire=r['wire_source'],response_format=r['response_format'],max_tokens=r['max_tokens'])))
 md('FIRST_FAILURES_FULL.md','# 11份原始首次失败全文\n\n'+'\n'.join(failuretext))
 md('STRUCTURE_FIRST_PASS.md','# 首次结构输出验证\n\n历史124份真实首答逐条重解析：113/124 = 91.13%；11失败：extra type 5、缺末尾括号5、尾随1，全部finish_reason=stop。wire 124/124可用；逐请求模型与参数见 evidence/first-124-reaudit.json。5/11可在本地附加对象括号恢复，但首次113/124不变，不丢弃额外字段。\n\nR5真实新首答0，首次通过率N/A；因此没有证据说明高于历史基线。目标≥98%仍是预注册工程目标。R4共享Composer已包含唯一reply字段Schema、完整JSON例与结束约束，真实调用入口 scripts/p5b8r4.py::run_plan → Dispatcher → LangChainProvider → Analyzer.request；本轮保留该候选而不另起协议。严格解析 src/application/p5b8r1_contracts.py 拒绝重复键、非字符串、空白、额外字段和length。13项R5回归含长文/多语种协议及统计，详细日志另存，不能当模型首次稳定率。\n\n官方DeepSeek JSON模式仅指定json_object、提示含json、示例与合理max_tokens，未提供reply字段白名单保证；stop甚至可能空白。2026-11-02核对 [官方JSON输出](https://api-docs.deepseek.com/guides/json_mode/)；未确认当前alias支持Schema级输出，不擅自发送不支持参数。工具strict模式与文本response_format不是同一契约。\n\n11完整邮件/raw/wire/根因见 FIRST_FAILURES_FULL.md / FIRST_FAILURES.csv；修复输出不回写历史。新增真实实验依赖新的金额与底层请求次数授权，UNKNOWN停机，不自动重试。')
 # Provenance flattened, preserving exact sources and participation.
 gold=read(ROOT/'docs/p5b8r4/evidence/annotation-overlay.json')
 fields=sorted(set(k for r in gold['records'] for k in r));csvwrite('GOLD_PROVENANCE_LEDGER.csv',[{k:r.get(k) for k in fields}|dict(r5_new_calibration_calls=0) for r in gold['records']])
 judge=read(ROOT/'docs/p5b8r4/evidence/historical-judge-revalidation.json');dump(EV/'historical-judge-revalidation.json',judge)
 md('JUDGE_OWNER_CALIBRATION.md','# Judge与Owner偏好：有限证据\n\n状态 AUTHORIZATION_BLOCKED；本轮新LLM Judge 0，费用0，人类逐维数字0，Kappa与人机相关N/A。\n\n'+block(gold['summary'])+'\n逐条来源/版本/实际参与次数见 GOLD_PROVENANCE_LEDGER.csv。3条逐字认可与13条代拟不混同；6案定性方向继续沿用，无须重签；24分类辅助、80旧分类与28个B4候选/24线程分开。\n\n事实门禁已有25开发控制：TP12/FN0/FP0/TN13；R5专项回归继续验证引用和契约，非LLM Judge准确率。历史64派发/63响应，重筛53/63否决指评分输出与证据冲突，不等于53封客户邮件错误。旧分完整保留 evidence/historical-judge-revalidation.json。B7-084产品咨询回执支持表扬转达、旧Judge仍给满分，是已确证漏判；开放域FP/FN无法从非穷尽审核推算，记N/A。\n\n历史v2反转逐维22/30；后续窄锚点重复19/20、反转17/20，不足以代表开放域稳定。各批次对数、缺失与硬错集合变化见所附stability，不能合并挑优。\n\n五维协议与中英正反边界例见 JUDGE_RUBRIC.md。新流程先各自逐维评分，再AB/BA盲比较；事实门禁不接受文风总分覆盖。未来阈值：Owner方向≥85%、顺序≥90%、重复关键判定≥90%，只作预注册目标。')
 md('JUDGE_RUBRIC.md','''# 五维0/1/2/N/A开发锚点（非真人评分）

0=严重不符，1=部分满足，2=满足。N/A只在业务动作确实不适用时使用并解释，汇总不当2。先引用客户诉求与回复原句，再独立评分，最后比较；长短都可高分。

|维度|正例（中/英）|反例（中/英）|边界|
|---|---|---|---|
|态度|很抱歉收到受损商品 / Sorry it arrived damaged|只说请按流程 / Follow the procedure|客户neutral仍可歉意；不为普通咨询过度道歉|
|专业与覆盖|先暂停使用，请发送已拍照片 / Pause use; send the photos you took|重复客户已做的检查 / Repeat the checks already done|有范围的一般知识建议，未知型号不假定|
|业务推进|已创建待核实转达任务 / An internal relay request is pending|门店已收到 / The store has received it（仅created）|无动作需要可N/A；没建单是服务缺口，虚称已建是硬错|
|事实可靠|收费依据待查 / We can check the basis of the charge|已退款 / Refunded（无回执）|条件式提议不是完成；物流query不是到货|
|自然与有效|感谢肯定并直接回答收费问题 / Thank you; here is how to check the charge|未问退款却长篇免责 / Long refund disclaimer without a refund request|恰当长文可2，短而漏答可0|

覆盖：表扬、混合、多Issue、周六时限、产品安全、收费咨询、无需动作、条件意向及新意图家族。输入必须绑定case/run/arm/input/event/hash；缺执行证据即UNKNOWN，不借用另一臂事件。所有示例是开发锚点，不伪造Owner逐维分。
''')
 # Full real six-case comparison is reused as a derivative, never rewritten at source.
 raw=read(ROOT/'docs/p5b8r4/evidence/full-reply-comparison.json');dump(EV/'six-cases-historical-firsts.json',raw)
 old=(ROOT/'docs/p5b8r4/R4_REAL_REPLY_COMPARISON.md').read_text('utf-8')
 md('REPLY_QUALITY_CASEBOOK.md','# 六案客服质量与原始首答\n\nR5新生成0，NEW_GENERATION_NOT_RUN；新旧比较未知6/6，不把同文重筛或规划测试当质量提升。以下完整保留R4历史对照正文及其历史身份。已确认局部证据：035/065无据回访承诺减少；084仍虚构表扬转达。六案不按ID编写回复。\n\n'+old)
 badrows=[]
 for r in raw:
  eid=r['case_id']
  for x in r['actual_r3_replies']:
   a=x['row'];screen=a.get('action_screen',{})
   badrows.append(dict(case_id=eid,identity=a['identity'],run_id=a['call']['run_id'],input_hash=a['slot']['input_hash'],source=x['path'],parse_ok=a['slot']['parse_ok'],action_findings=screen,classification='ENGINEERING_FAILURE' if not a['slot']['parse_ok'] else 'REQUIRES_POLICY_AND_EVENT_REVIEW',r5_new_generation='NOT_RUN',r5_quality_delta='UNKNOWN'))
 csvwrite('BAD_CASE_REGRESSION.csv',badrows)
 md('REPLY_REPAIR_REVIEW.md','''# 现有共享修复复核

沿用R4 Composer和Planner，不再无证重复改写：损坏适度致歉、尊重已拍照片与已完成排查、保留礼盒期限、表扬转达须有匹配任务、收费问题先解释依据，Direct/Guided同规则。源码 p5b8r4_reply.py、p5b8r4_actions.py。R4实际修复不是新模型质量实测。

HARD_ERROR：084产品咨询冒充表扬转达、无安排声称回访；MAJOR_SERVICE_GAP：表扬未建需要的转达任务、漏主要诉求；SOFT_QUALITY：无关退款免责、重复已解决故障；ENGINEERING_FAILURE：首次JSON非法。不得互相替代。

035/065历史修订局部去除承诺可逐字验证，但6案配对Judge均持平；084退步/硬错仍保留。R5新回复改善0份可认证、持平0份可认证、退步0份可认证、未知6/6；这是缺新增生成，不能填6持平。完整首答/回执见 REPLY_QUALITY_CASEBOOK.md。新规划事实控制通过也不升级模型回复质量。
''')
 md('ABLATION_DECISION.md','''# NO_NEW_ABLATION

本轮不追加情绪或完整链消融。历史已经显示未见稳定优势；优先修语义真值、统计口径、客服残留硬错和首次结构，而不是重刷显著增益。

|历史数据身份|增强胜|对照胜|持平|未知|完整分母|
|---|---|---|---|---|---|
|DEV显式情绪 WITH/NO|1|1|16|6|24对|
|DEV完整链 Guided/Direct|0|1|10|1|12对|
|R3新族情绪|0|0|7|5|12对|
|R3新族完整链|0|1|7|4|12对|

来源 docs/p5b8r3/RESULTS.json、FINAL_QUALITY_RESULTS.json；原始首次保留。未知不是持平。旧Judge事实漏判、结构失败及两臂动作不同削弱因果解释；两种对照回答不同问题，不能混为情绪效应。R3N当时冻结后生成12封/6家族，R5已曝光不再是未来独立集。

可证伪后续假设：只加入显式情绪字段是否提升对负面体验的恰当回应且不增加虚构动作？固定Issue/事实/知识/工具/Prompt/模型，只改变情绪字段；主要终点由独立盲人审逐对判定，完整保留结构与未知失败。完整链需两臂独立空库及匹配动作能力。先完成独立多轴Gold与Judge有限校准，再冻结样本/版本、金额和底层请求上限；未满足条件不启动。本轮真实请求0，无预算库。

论文可写：本合成场景内没有观察到显式情绪或Guided稳定优势；不能据此证明情绪无用或所有链路等效。
''')
 results=[['S1','HUMAN_GOLD_PENDING','87/90模型暂定；新轴真人0；16封待审','RQ1_SEMANTIC_VALIDATION.md','否'],['S2','VERIFIED_EVIDENCE','90→87；产品负面体验37封；门店目标口径修复，含可疑020','CATEGORY_STORE_RANKING.md','模型描述统计'],['A1','IMPROVED_NOT_CERTIFIED','6案历史全文与残留错；R5新生成0/6','REPLY_QUALITY_CASEBOOK.md','未证实新语义增益'],['A2','AUTHORIZATION_BLOCKED','113/124首次；11失败；5可本地恢复；新0','STRUCTURE_FIRST_PASS.md','首次提升未知'],['A3','AUTHORIZATION_BLOCKED','25事实控制12/12+13/13；新Judge0，真人逐维0','JUDGE_OWNER_CALIBRATION.md','非开放域认证'],['B1','VERIFIED_EVIDENCE','NO_NEW_ABLATION；四组24/12/12/12对历史负结果','ABLATION_DECISION.md','无稳定优势']]
 dump(EV/'six-results.json',results)
 md('SIX_PRIORITY_RESULTS.md','# 六项研究与质量结果\n\n2026-11-02。六项已形成有证据的阶段结果，并非六项质量全通过。新增付费模型请求0、费用¥0；不续用旧额度，不执行外部联系。\n\n'+table([['任务','状态','实际结果/完整分母','证据','语义认证']]+results)+'\n\nS2统计数字和成员可复算，语义仍依赖模型标签；真实浏览器验收完成后另见UI_ACCEPTANCE。新多轴人工真值和新Provider质量复验是唯一无法离线补齐的缺口；其它工程及作品集继续完成。主张冻结见 CLAIM_EVIDENCE_MATRIX.md。')
 dump(EV/'research-freeze.json',dict(stage='SIX_RESULTS_BEFORE_SCREENSHOTS_AND_AUTHORING',statistics=VERSION,paid_requests=0,human_new_axis_labels=0,
    files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DOC.glob('*.md')}))
 print(json.dumps(dict(selected=s['selected'],valid=87,axes=axes,product_negative_unique=len(unique_product),issues=issue_n,human_review=len(review),historical_first=len(first),first_valid=sum(r['r5_first']=='accepted' for r in first)),ensure_ascii=False))
if __name__=='__main__':main()
