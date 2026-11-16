"""Read-only research aggregation of the second authorized first-attempt scope."""
import json,csv,sys,sqlite3,hashlib,shutil
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.infrastructure.p5b8r3_execution import read
from src.application.p5b8r3_experiment import unblind
from src.application.p5b8r3_final_guard import assess
DOC=ROOT/'docs/p5b8r3';RUN=ROOT/'.local/p5b8r3/quality-final-v1'
PLAN=read(DOC/'followup-prepared/PLAN.json')
DIMENSIONS=('attitude','helpfulness','action_accuracy','reliability','information_density')
def maybe(p):return read(p) if Path(p).exists() else None
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,v):(DOC/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def md(name,t):(DOC/name).write_text(t.strip()+'\n','utf-8')
def block(v):return '\n```json\n'+json.dumps(v,ensure_ascii=False,indent=2)+'\n```\n'
def csvout(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (DOC/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def effect(j,arms):
    values=unblind(j) if j else None
    preference=j['key'].get(j['parsed']['preference'],{}).get('arm',j['parsed']['preference']) if values else 'UNKNOWN'
    return dict(preference=preference,semantic_graded=bool(values),difference={d:values[arms[1]]['scores'][d]-values[arms[0]]['scores'][d] if values and all(type(values[a]['scores'][d])is int for a in arms) else None for d in DIMENSIONS},
        hard_error_by_arm={a:sum(f['category']=='HARD_ERROR' for f in values[a]['findings']) if values else None for a in arms})
def aggregate(rows):
    return dict(n_planned_pairs=len(rows),n_semantic_pairs=sum(r['effect']['semantic_graded'] for r in rows),preferences=dict(Counter(r['effect']['preference'] for r in rows)),dimensions={d:dict(n=sum(r['effect']['difference'][d] is not None for r in rows),positive=sum((r['effect']['difference'][d] or 0)>0 for r in rows),zero=sum(r['effect']['difference'][d]==0 for r in rows),negative=sum((r['effect']['difference'][d] or 0)<0 for r in rows),unknown=sum(r['effect']['difference'][d] is None for r in rows)) for d in DIMENSIONS},human_numeric_n=0,identity='AUTOMATED_PROVISIONAL_NOT_HUMAN_SATISFACTION')
def budget():
    path=RUN/'budget.sqlite3'
    if not path.exists():return dict(status='NOT_RUN',requests=0,upper_cny=0)
    c=sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)
    try:
        calls=c.execute('SELECT identity,run_id,state,reserved_micro,settled_micro,metadata FROM calls').fetchall()
        return dict(authorized_cny=15,authorized_requests=120,requests=len(calls),states=dict(Counter(r[2] for r in calls)),upper_cny=sum(r[4] if r[4] is not None else r[3] for r in calls)/1e6,actual_bill_cny=None,halted=c.execute('SELECT halted FROM policy').fetchone()[0],sha256=sha(path),calls=[dict(identity=r[0],run_id=r[1],state=r[2],reserved_cny=r[3]/1e6,settled_upper_cny=r[4]/1e6 if r[4] is not None else None,metadata=json.loads(r[5]) if r[5] else None) for r in calls])
    finally:c.close()
def report():
    targeted=[];rescreen=[];book=['# 定向收敛与独立测试全文\n','R3首次结果不覆盖；所有样本为研究合成邮件。候选2为预先声明的实验版本，不自动晋升正式产品。旧16 Gold无需重签；五维人类标签0。\n']
    for s in PLAN['target']:
        eid=s['case_id'];baseline=s['baseline'];new=maybe(RUN/'results'/('T_REPLY-'+eid+'.json'));j=maybe(RUN/'judgments'/('T_JUDGE-'+eid+'.json'))
        row=dict(case_id=eid,baseline_identity=baseline['identity'],baseline_run=baseline['call']['run_id'],candidate_first_run=new['call']['run_id'] if new else None,baseline=baseline,candidate=new,judgment=j,effect=effect(j,[baseline['slot']['arm'],'CANDIDATE_V2']))
        for label,r in (('BASELINE',baseline),('CANDIDATE',new)):
            if r:
                h=r['slot']['input_hash'];screen=assess(r['slot']['reply'],r['runtime'],h);rescreen.append(dict(case_id=eid,version=label,first_run=r['call']['run_id'],original_screen=r['action_screen'],new_screen=screen,identity='SAME_REPLY_GUARD_RESCREEN_NOT_MODEL_IMPROVEMENT'))
        targeted.append(row);book+=['\n## DEV收敛 '+eid+'\n','### 客户全文\n\n'+baseline['customer']['subject']+'\n\n'+baseline['customer']['body'],'\n### R3首次基线全文\n\n'+baseline['slot']['reply'],block(dict(call=baseline['call'],runtime=baseline['runtime'])),'\n### 修订实际首次回复\n\n'+(new['slot']['reply'] if new else 'NOT_RUN'),block(new),'\n### 同评分器配对\n',block(j)]
    independent=[];identity=maybe(RUN/'DATA_IDENTITY.json');freeze=maybe(RUN/'FINAL_CANDIDATE_AND_JUDGE_FREEZE.json')
    for n in range(1,13):
        eid=f'R3N-{n:03}';source=maybe(RUN/'dataset'/(eid+'.json'));b={arm:maybe(RUN/'results'/(arm+'_REPLY-'+eid+'.json')) for arm in ('DIRECT','GUIDED')};a={arm:maybe(RUN/'results'/(stage+'-'+eid+'.json')) for arm,stage in (('ISSUES_NO_SENTIMENT','NO_EMOTION'),('ISSUES_WITH_SENTIMENT','WITH_EMOTION'))}
        jb=maybe(RUN/'judgments'/('JUDGE_CHAIN-'+eid+'.json'));ja=maybe(RUN/'judgments'/('JUDGE_EMOTION-'+eid+'.json'))
        row=dict(case_id=eid,source=source,B_replies=b,A_replies=a,B_judgment=jb,A_judgment=ja,B_effect=effect(jb,['DIRECT','GUIDED']),A_effect=effect(ja,['ISSUES_NO_SENTIMENT','ISSUES_WITH_SENTIMENT']),plans={arm:maybe(RUN/'plans'/(eid+'-'+arm+'.json')) for arm in ('DIRECT','GUIDED')})
        independent.append(row);book+=['\n## 独立新场景 '+eid+'\n',block(source)]
        for arm,r in dict(b,**a).items():book+=['\n### '+arm+' 完整首次回复\n\n'+(r['slot']['reply'] if r else 'NOT_RUN_OR_FAILED_DEPENDENCY'),block(r)]
        book+=['\n### 新分析/独立规划与两个Judge\n',block(dict(plans=row['plans'],chain_judge=jb,emotion_judge=ja))]
    summary=dict(targeted=aggregate(targeted),independent_chain=aggregate([dict(effect=r['B_effect']) for r in independent]),independent_emotion=aggregate([dict(effect=r['A_effect']) for r in independent]),
                 independent_generation=dict(planned=12,generated=sum(bool(r['source'] and r['source'].get('email')) for r in independent),valid_frozen=sum(bool(r['source'] and r['source'].get('status')=='FROZEN_TEST_SAMPLE') for r in independent),family_count=6),
                 identity=identity,freeze=freeze,budget=budget(),human_numeric_n=0,human_agreement=None,judging_model_independent_of_generator=False,automatic_production_promotion=False)
    dump('FINAL_QUALITY_RESULTS.json',summary);dump('TARGETED_ACTUAL_RESULTS.json',targeted);dump('INDEPENDENT_ACTUAL_RESULTS.json',independent);dump('GUARD_SAME_REPLY_RESCREEN.json',rescreen)
    # Preserve this concrete contradiction instead of treating identical perfect
    # scores as proof of improvement or correctness.
    counterexamples=[]
    for r in targeted:
        if not r['candidate'] or not r['judgment'] or not r['judgment'].get('parsed'):continue
        screen=assess(r['candidate']['slot']['reply'],r['candidate']['runtime'],r['candidate']['slot']['input_hash'])
        answer=unblind(r['judgment'])['CANDIDATE_V2']
        if any(f['code']=='H04' for f in screen['findings']) and answer['scores']['action_accuracy']==2 and answer['scores']['reliability']==2:
            counterexamples.append(dict(case_id=r['case_id'],reply=r['candidate']['slot']['reply'],actual_events=r['candidate']['runtime']['events'],deterministic_screen=screen,judge=answer,identity='OBSERVED_ACTION_KIND_MISMATCH_AND_JUDGE_FALSE_NEGATIVE_NOT_HUMAN_ACCURACY_ESTIMATE'))
    dump('JUDGE_OBSERVED_COUNTEREXAMPLES.json',counterexamples)
    md('FINAL_CASEBOOK.md','\n'.join(book))
    csvout('TARGETED_PAIRS.csv',[dict(case_id=r['case_id'],baseline_run=r['baseline_run'],candidate_run=r['candidate_first_run'],**r['effect']) for r in targeted])
    csvout('INDEPENDENT_PAIRS.csv',[dict(case_id=r['case_id'],family=r['source']['spec']['family'] if r['source'] else None,source_role=r['source'].get('role') if r['source'] else None,B=r['B_effect'],A=r['A_effect'],not_human_gold=True) for r in independent])
    md('INDEPENDENT_DATA_IDENTITY.md','# 独立测试的数据身份\n\n'+block(dict(identity=identity,freeze=freeze))+'\n6个家族的生成意图已在执行源码中预注册；邮件正文在候选/评分器冻结后才由Provider首次生成，冻结后不改Prompt。不是对作者隐藏家族意图的第三方盲测，也不是独立真人Gold。营销退订、账户数据导出、回收设备数据擦除、可访问电子说明、礼物收据隐私、软件授权转移，与既有商品故障/物流/退款/表扬等问题家族作迁移检验。词法Jaccard筛查不等于语义独立认证，源级语义家族核验单独列出。12条、6族、中英各6，小样本/相同Provider生成评分的偏差均保留。\n\n本轮used_for_tuning=false；不得使用这些实际结果继续调候选。后续如用于调优，须写明转DEV的曝光overlay并换新未见集，原首次结果仍保留。')
    first=read(DOC/'RESULTS.json');combined=dict(grants=[dict(cny_cap=20,request_cap=190,actual_requests=first['budget']['requests'],upper_cny=first['budget']['reserved_and_settled_upper_cny']),dict(cny_cap=15,request_cap=120,actual_requests=summary['budget']['requests'],upper_cny=summary['budget']['upper_cny'])],total_cny_cap=35,total_provider_request_cap=310,actual_requests=first['budget']['requests']+summary['budget']['requests'],reserved_and_settled_upper_cny=first['budget']['reserved_and_settled_upper_cny']+summary['budget']['upper_cny'],actual_bill_cny=None,old_historical_ledgers_reopened=False)
    dump('COMPLETE_BUDGET.json',combined)
    # Numerical deltas are observations, not proof of human preference.
    md('FINAL_THESIS_RESULTS.md','# 毕业研究最终实测结果与局限\n\n## 数据与方法\n\n历史90封Provider合成邮件、400封程序模板与真实消费者数据分开。RQ1旧80参考78/80不是独立准确率；90份中87有效/3失败，表达负面23/87、产品负面体验37/87、投诉意图24/87，来源关联不解释为因果或法律责任。新维度无人类独立数值Gold。\n\n## RQ2：显式情绪增量\n\nDEV新首次48/48回复，24配对中18有实际自动评分：WITH胜1、NO胜1、持平16、未知6（预算在派发前分层预选，不以结果挑选）。相同事实/Issue/回执/知识/模型，仅explicit_emotion不同。独立新家族的实际结果：\n'+block(summary['independent_emotion'])+'\n没有将JSON/任务变化归因于情绪字段，差异均按五维序数和独立硬错分列；模型偏好不是人类满意度。\n\n## RQ3：完整LangChain链\n\nDEV12对独立Direct/Guided：Direct胜1、持平10、未知1；缺失来自一条回复JSON失败，不能记为语义退步或持平。各自真实本地查询/任务、分析/规划、全文和时延/Token已保存。独立新家族：\n'+block(summary['independent_chain'])+'\ncreated只代表本地待办，不表示外部联系或客户问题解决。Guided既可能补全步骤，也可能引入结构化分析误差，不预设优越性。\n\n## 通用回复修订的真实结果\n\n基于首败的两类根因：回复器将规范性任务要求误当执行许可；无回访安排却承诺后续回复。共享规范明确仅负责写信、缺回执则条件性提议、无执行安排不承诺。6个目标案例使用同一冻结输入/事实/回执，仅替换共享系统提示，既有基线不重生成。结果：\n'+block(summary['targeted'])+'\nGuard广义任务名词范围修复对新旧同文统一重筛，和模型改进分开。不得将相同旧文重筛少报硬错当作回复改善。B7-035/065的无安排回访承诺在新回复中减少，但这不是已经改善自然度或全体安全的证明。B7-084新文明确声称提交转达请求，实际仅产品咨询human_input_request；属于未解决的动作类型错配。6案多数基线为R3独立Guided且已有任务，不能用这些高分持平证明缺回执条件下的虚构建单问题已修好。所有候选退步与失败都见全文，不以最好重试覆盖首次。\n\n## Judge可信度\n\n首轮47次34合法、13证据引用失败；修订10次全合法但AB/BA22/30未达.85；最后6次定向重复19/20、AB/BA17/20。仅两个曝光DEV配对的门槛通过，不是稳定准确率认证。实际B7-084 Judge一面承认无专门转达回执，一面给动作准确性和可靠性2分，未报告硬错（见JUDGE_OBSERVED_COUNTEREXAMPLES）。B7-065对无安排回访承诺的去除也未形成分差；不能说Judge已稳定识别真实改善或硬错。预测与评分同Provider；无真人逐维标签，Kappa、相关和人机一致率不计算。\n\n## 独立测试与结论范围\n\n新测试邮件在候选与Judge冻结后生成，未用于调优。'+block(summary['independent_generation'])+'\n六族/12条，仅支持研究合成场景中的迁移观察；生成意图不是Gold、词法去重不证明语义独立。自然度、专业性和积极性需要少量真实盲评，不能用更高Judge分替代。现有实测足以形成包含负结果和局限的毕业论文研究章节与可复核导师作品集；系统稳定优于基线、真实客户满意度与最终导师认证仍不能宣称。')
    # Genuine new subjective pairs, not a re-signature request for the old Gold.
    review=['# 最小新增盲评材料\n','仅3对实际新修订输出；无需重签16旧Gold。未给机器分数和候选名，请判断哪份更自然、积极、专业、事实/动作可靠。可选X/Y/相近/各有优劣/无法判，并指出关键一句。数值评分可留空。\n'];key=[]
    usable=[next(r for r in targeted if r['case_id']==eid) for eid in ('B7-009','B7-084','B7-065') if any(r['case_id']==eid and r['candidate'] for r in targeted)]
    for n,r in enumerate(usable[:3],1):
        review+=['\n## 对 '+str(n)+'\n',r['baseline']['customer']['subject']+'\n\n'+r['baseline']['customer']['body']]
        ordered=[r['baseline'],r['candidate']] if n%2 else [r['candidate'],r['baseline']]
        for label,item in zip(('X','Y'),ordered):review+=['\n### '+label+'\n\n'+item['slot']['reply'],block(dict(events=item['runtime']['events'],facts=item['runtime']['facts'],attachment_manifest=[]))]
        key.append(dict(pair=n,case_id=r['case_id'],X=ordered[0]['identity'],Y=ordered[1]['identity']))
    md('HUMAN_REVIEW_FINAL.md','\n'.join(review));dump('HUMAN_REVIEW_FINAL_KEY_KEEP_SEPARATE.json',key)
    for name in ('final-quality-live.txt','followup-mock-summary.json','tests-final-candidate.txt','tests-scope-adapter.txt'):
        p=ROOT/'.local/p5b8r3'/name
        if p.exists():shutil.copyfile(p,DOC/name)
    print(json.dumps(dict(targeted=summary['targeted']['preferences'],independent_chain=summary['independent_chain']['preferences'],independent_emotion=summary['independent_emotion']['preferences'],budget=combined),ensure_ascii=False))
if __name__=='__main__':report()
