"""Read-only model evidence → R6 reports. Does not dispatch or alter historical assets."""
import sys,json,csv,statistics,hashlib,zipfile,shutil,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b8r6 import DOC,LOCAL,read,write,md,csvout,table,sha
from src.domain.contracts import EmailInput
from src.evaluation import p5b8r4_judge as judge
def block(d):return '\n```json\n'+json.dumps(d,ensure_ascii=False,indent=2)+'\n```\n'

OPINIONS={
36:dict(delta='IMPROVED_WITH_GAP',core=True,knowledge=True,action=False,hard=False,explanation='比旧版增加歉意、照片/订单收集并真实建售后；新v2分析漏物流Issue，最终Guided只有售后任务，O01物流推进未全满足。不是六案全过。'),
84:dict(delta='IMPROVED_WITH_SOFT_REGRESSION',core=True,knowledge=True,action=True,hard=False,explanation='专业安装/密封/裂纹/渗水部位+产品咨询/售后条件核实均保留，不再虚构已转达；v4没有适度歉意且部分重复已做检查，保留软退步。'),
35:dict(delta='IMPROVED_AFTER_FAILED_REVISION',core=True,knowledge=True,action=True,hard=False,explanation='v4真实退步：虚称reviewed photos；v5新身份显式承认仅客户报告，保留周六和库存/加急/替代核查。最终为修订候选，原失败不消失。'),
9:dict(delta='IMPROVED',core=True,knowledge=True,action=True,hard=False,explanation='真实创建转达请求、取消无关复发提醒、祝福；Guard对internal request片段有误拒，新同文规则复筛单列，不算模型提升。'),
10:dict(delta='IMPROVED',core=True,knowledge=True,action=True,hard=False,explanation='表扬转达created、真诚感谢、自然三段和使用祝福；相较旧复杂流程清楚。'),
85:dict(delta='IMPROVED_WITH_GAP',core=True,knowledge=True,action=True,hard=False,explanation='保留两方面好评，收费依据与告知核查有真任务，无退款免责；仍说未来pass appreciation但无转达任务，是待执行/服务范围软缺陷，不冒充已完成。')}

def all_reports():
 traces=[]
 for p in sorted((LOCAL/'traces').glob('*/*-reply.json')):
  r=read(p);r['_source']=p.relative_to(ROOT).as_posix();traces.append(r)
 judgments=[dict(read(p),source=p.relative_to(ROOT).as_posix()) for p in sorted((LOCAL/'judgments').glob('*.json'))]
 write(DOC/'evidence/all-new-replies.json',traces);write(DOC/'evidence/all-new-judgments.json',judgments)
 groups=Counter();structures=Counter();screen=[]
 for r in traces:
  group=r['_source'].split('/traces/')[1].split('/')[0].rsplit('-',2)[0] if False else r['_source'].split('/traces/')[1].split('/')[0]
  version=group.split('-')[1];cohort='UNSEEN' if group.startswith('UNSEEN') else 'DEV'
  k=cohort+'/'+version;groups[k]+=1;structures[k]+=r['parse']['status']=='accepted'
  s=r['slot'];new=judge.audit_slot(s,EmailInput.model_validate(r['email'])) if s['parse_ok'] else None
  screen.append(dict(source=r['_source'],run_id=s['run_id'],arm=s['arm'],case_id=s['case_id'],first_parse=s['parse_ok'],original_guard=r['guard'],current_same_text_screen=new,identity='POST_RUN_RULE_RESCREEN_NOT_MODEL_QUALITY_GAIN'))
 write(DOC/'evidence/guard-rescreen.json',screen)
 rows=[dict(cohort=k,first_valid=structures[k],attempts=n,rate=structures[k]/n) for k,n in groups.items()];csvout('FIRST_STRUCTURE_RESULTS.csv',rows)
 final=[]
 for n in (36,84,35,9,10,85):
  rev='v5' if n==35 else 'v4';r=next(t for t in traces if f'DEV-{rev}-B7-{n:03}/GUIDED' in t['_source']);final.append(dict(r,opinion=OPINIONS[n]))
 write(DOC/'evidence/final-six.json',final)
 # Every historical source and every new first preserved as full text; invalid raw is shown intact.
 old=read(ROOT/'docs/p5b8r5/evidence/six-cases-historical-firsts.json');sections=[]
 for r in final:
  eid=r['slot']['case_id'];n=int(eid[-3:]);historical=next(x for x in old if x['case_id']==eid)
  t='## '+eid+'\n\n### 原客户邮件（固定LLM合成）\n\n'+r['email']['subject']+'\n\n'+r['email']['body']+'\n\n输入hash '+r['slot']['input_hash']+'\n\n### Codex独立于模型Judge的AI复核意见（非真人/非独立ChatGPT）\n\n'+OPINIONS[n]['explanation']+'\n'
  t+='\n### 历史完整首次回复与同臂回执\n'
  for x in historical['actual_r3_replies']:
   a=x['row'];t+='\n#### '+a['identity']+'\n\n来源 '+x['path']+'\n\n'+(a['slot']['reply'] or '结构失败，无合法回复；原raw：\n'+a['call']['raw'])+'\n\n实际回执/Guard：'+block(dict(run_id=a['slot']['run_id'],arm=a['slot']['arm'],events=a['slot']['events'],guard=a.get('action_screen')))
  t+='\n### R6所有版本完整首次回复（不挑优删除）\n'
  for a in traces:
   if a['slot']['case_id']!=eid:continue
   t+='\n#### '+a['_source']+'\n\n'+(a['slot']['reply'] or '首次结构失败，完整raw：\n'+a['call']['raw'])+'\n\n'+block(dict(run_id=a['slot']['run_id'],arm=a['slot']['arm'],model=a['call']['metadata'].get('resolved_model'),composer=a['composer'],parse=a['parse'],events=a['slot']['events'],guard=a['guard'],elapsed_ms=a['call']['elapsed_ms'],usage=a['call']['metadata'].get('usage'),upstream_reuse=a.get('upstream_reuse')))
  t+='\n### 实际Judge原始判断与绑定\n'
  for j in judgments:
   if eid in j.get('logical','') or (n==35 and 'REVERIFY' in j.get('logical','')):t+=j['source']+block({k:j.get(k) for k in ('status','parsed','error','key')})
  sections.append(t)
 md('FIRST_PASS_E2E_CASEBOOK.md','# 六案完整首答、全部修订和同臂动作\n\n55份R6首次回复生成，54合法；43份严格工具输出全部合法。六案初始新端到端v1每案分析+Direct Plan+两臂首答，v2同样全新；v3/v4/v5明确复用v2分析，重新独立执行任务并生成新首答，不能称每版重跑分析。旧文、首次失败与退步均保留。最终六份为v4五份+v5礼盒一份，不隐瞒中间失败。人类逐维分0，独立ChatGPT意见未提供；Owner政策方向不是数字Gold。\n\n'+'\n'.join(sections))
 unseen=[r for r in traces if r['dataset_role']=='UNSEEN'];us=[]
 for r in unseen:us.append('## '+r['slot']['case_id']+' '+r['slot']['arm']+'\n\n'+r['email']['subject']+'\n\n'+r['email']['body']+'\n\n'+r['slot']['reply']+'\n\n'+block(dict(source=r['_source'],events=r['slot']['events'],guard=r['guard'])))
 md('TRANSFER_CASEBOOK.md','# 新合成迁移全量；严格独立验收未通过\n\n原UNSEEN命名留痕，不追认独立。002与R3N-007/008无障碍说明家族重叠；冻结后源码漂移，实际wire证明输入。6封12首答一次运行，无补样/调优。5封新目标候选可作探索迁移，不能宣称正式独立质量认证。\n\n'+'\n'.join(us))
 # Judge controls with exact sentence attribution, not all flaws in a whole answer.
 metric=dict(control_calls=15,parsed=0,hard_expected=12,hard_detected=0,hard_unknown=0,normal_expected=3,normal_false_positive=0,normal_unknown=0,preference_direction_match=0,preference_direction_n=12,preference_unknown=0,ab_ba_key_match=0,ab_ba_pairs=5,repeat_key_match=0,repeat_pairs=5,preference_abba_match=0,preference_repeat_match=0)
 normalized={}
 for n in (36,35,9,85,10):
  spec=read(LOCAL/f'controls/{n}.json');sentence=spec['expectation']['sentence'];hard=spec['expectation']['hard']
  for order in ('AB','BA','REPEAT'):
   j=next(x for x in judgments if x.get('logical')==f'CAL-{n}-{order}');p=j.get('parsed')
   if not p:
    if hard:metric['hard_unknown']+=1;metric['preference_unknown']+=1
    else:metric['normal_unknown']+=1
    normalized[(n,order)]=None;continue
   metric['parsed']+=1;mutslot='X' if order=='BA' else 'Y';base='Y' if order=='BA' else 'X'
   answer=next(a for a in p['answers'] if a['slot']==mutslot)
   detected=any(f['category']=='HARD_ERROR' and (f['quote'] in sentence or sentence in f['quote']) for f in answer['findings'])
   if hard:
    metric['hard_detected']+=detected;metric['preference_direction_match']+=p['preference']==base
   else:metric['normal_false_positive']+=detected
   by={('mutated' if a['slot']==mutslot else 'base'):dict(scores=a['scores'],hard=any(f['category']=='HARD_ERROR' for f in a['findings'])) for a in p['answers']}
   pref='base' if p['preference']==base else 'mutated' if p['preference']==mutslot else p['preference'];normalized[(n,order)]=dict(scores=by,preference=pref,hard=detected)
  for target,prefix in [('BA','ab_ba'),('REPEAT','repeat')]:
   x,y=normalized[(n,'AB')],normalized[(n,target)]
   metric[prefix+'_key_match']+=bool(x and y and x['hard']==y['hard'])
   metric['preference_abba_match' if target=='BA' else 'preference_repeat_match']+=bool(x and y and x['preference']==y['preference'])
 write(DOC/'evidence/judge-metrics.json',metric)
 md('JUDGE_CALIBRATION.md','# Judge的有限可信范围\n\n'+block(metric)+'\n硬错召回按注入原句计：检出/12全部派发，1份协议失败作为UNKNOWN，不静默排除。正常FP按3次相同正常补充句计，不表示开放域误拒率。五个不同控制，AB/BA/重复各一次；同题key=硬错是否存在，不能称五维完全稳定。\n\nOwner方向只是“安全/真实执行/不虚构政策更好”的定性要求，不存在虚构五维人工分。四类硬错方向按12次全分母计算，正常可TIE不预设赢家。程序事实门禁不等于Judge；实际009创建请求被截断误拒、085过去转达词形漏判都另列，不能把程序的判断塞给Judge后称独立准确率。\n\n已确认真实缺陷：v4礼盒`reviewed photos`为硬错，最后两个Judge均判新v5更好；009实际有转达created，Judge却沿确定性误拒判新差，属于已知FP一例，不计算开放域率。085 v3未经核实“无需额外付款”被本轮Codex判硬风险，后续不选该版。无盲人类逐维评审，Kappa/Macro-F1=N/A。所有原分保留，修门禁后不回写旧Judge。')
 # Primary report carefully distinguishes imperfect candidates from certification.
 summary=dict(total_provider_requests=120,analysis=18,plans=18,replies=len(traces),reply_first_valid=sum(r['slot']['parse_ok'] for r in traces),judges=len(judgments),strict_reply_attempts=sum(r['call']['metadata'].get('contract')=='STRICT_TOOL_ARGUMENTS_NOT_CONTENT_JSON' for r in traces),first_by_version=rows,final_core_coverage_ai=sum(r['opinion']['core'] for r in final),final_bounded_help_ai=sum(r['opinion']['knowledge'] for r in final),final_complete_action_goal_ai=sum(r['opinion']['action'] for r in final),final_hard_errors_observed_ai=0,human_gold_n=0,final_status='PARTIAL_NOT_PROMOTED',freeze_integrity='FAIL',transfer_families_strictly_independent='NOT_CERTIFIED',budget=read(DOC/'evidence/budget-final.json'))
 write(DOC/'evidence/quality-summary.json',summary)
 md('QUALITY_RESULTS.md','# 真实质量差异与限度\n\n已完成真实生成与逐案对照，候选不晋升全自动生产。120次底层请求全部有响应用量，费用高峰未命中上界¥1.310508/¥15，实际账单UNKNOWN；旧账本不重开。\n\n'+table([['指标','实际分母与结论'],['首次结构','54/55；v1 11/12，严格输出43/43；样本小且多版本重复DEV，不能宣称总体≥98%'],['六案最终核心诉求覆盖','Codex AI审阅6/6；非真人质量准确率'],['有边界专业帮助/有用答复','Codex AI审阅6/6；专业知识与动作分别看'],['完整动作目标推进','5/6；036新分析漏物流，最终Guided只有售后任务'],['最终六案已观察事实硬错','0/6（AI非穷尽审阅），不等于错误率为零'],['真实退步','v4礼盒虚称看过照片；v3收费未经核实免付义务；009早期重提故障；084终版无歉意'],['旧→v4模型Judge','原偏好新4/6、旧2/6；009包含程序误拒，035真实硬错；不能当可靠净增益'],['礼盒v4→v5','2/2 Judge偏好新；同一DEV修订并非独立泛化'],['Codex旧新复核','六案均有实质改善点；036物流缺口、084态度退步、085未执行的未来转达保留'],['迁移测试','6封12首答一次；1家族与R3重叠、冻结漂移；不能认定独立测试PASS'],['新轴人工真值','0；不计算新轴Macro-F1、准确率或Kappa']])+'\n\n'+table([['案例','AI差异','限制']]+[[f'B7-{n:03}',d['delta'],d['explanation']] for n,d in OPINIONS.items()])+'\n\n新合成迁移：Direct/Guided原Judge为Guided胜2、Direct胜1、持平3（6对），受Guard误拒与冻结问题影响，不能宣称Guided稳定优越。退款/地址/续费政策仍需核验，不能用样本泛化解决所有业务。R3显式情绪/Guided历史负结果原样保留。\n\n完整邮件、新旧首答、Raw、同臂回执、Judge分与延迟在FIRST_PASS_E2E_CASEBOOK、TRANSFER_CASEBOOK和evidence。最后六份为已公开修订路径，不把筛选出的最好一份冒充最初六案端到端成功率。后续真正独立人类审核与新预算才能认证剩余语义缺口。')
 # Policy and tiers: source verbatim plus current reviewer identities.
 source=(DOC/'P5-B8-R6_Codex_完整执行Prompt.md').read_text('utf-8-sig');policy=source.split('## 1.')[1].split('## 2.')[0]
 cs=read(DOC/'evidence/semantic-cases.json');tiers=[]
 for c in cs:tiers.append(dict(case_id=c['case_id'],input_hash=c['input_hash'],family=c['family'],data_quality_tier=c['data_quality_tier'],scenario_complexity=c['scenario_complexity'],business_risk=c['business_risk'],dataset_role=c['dataset_role'],language=c['language'],reason=c['quality_reason']))
 csvout('EMAIL_DATA_TIERS.csv',tiers)
 md('OWNER_POLICY_AND_DATA_TIERS.md','# Owner源与四个独立分层轴\n\n来源：2026-11-04用户明确要求执行附件；以下为其采纳的Owner定性政策，不是五维分数或新分类Gold。\n\n'+policy+'\n\n逐封成员及理由见EMAIL_DATA_TIERS.csv；输入hash去重、同family均DEV。质量A70/B18/C2/隔离0，长度不是分级条件，020为A/SINGLE/NORMAL/DEV。失败分析34/56/67输入仍A，不因模型失败降输入等级。新轴人类签署0。\n\n'+block(read(DOC/'evidence/semantic-summary.json'))+'\n\n历史3逐字认可/13原则代拟、旧80/24分类标签维持各自来源。Codex逐封审阅与独立ChatGPT空表分开，后者未收到；不要把有完整原文的空表称完成独立复核。R6U002与历史无障碍家族重叠，原manifest保留并在freeze-deviation纠正身份；其它五封也因源码漂移仅探索迁移。')
 write(DOC/'evidence/report-freeze.json',dict(quality_summary_sha256=sha(DOC/'evidence/quality-summary.json'),all_replies_sha256=sha(DOC/'evidence/all-new-replies.json'),judgments_sha256=sha(DOC/'evidence/all-new-judgments.json'),meaning='Research claims frozen before PDF authoring; later changes only verification/status references'))
 print('REPORTS',summary)

if __name__=='__main__':all_reports()
