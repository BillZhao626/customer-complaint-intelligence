"""Consolidate observed status, reproducibility and the 74-row delta; no APIs."""
import json,csv,sys,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.infrastructure.p5b8r3_execution import read
from src.evaluation.p5b8r3_judge import validate_slot
from src.domain.contracts import EmailInput
DOC=ROOT/'docs/p5b8r3';LOCAL=ROOT/'.local/p5b8r3'
def dump(name,v):(DOC/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def md(name,t):(DOC/name).write_text(t.strip()+'\n','utf-8')
def main():
    first=read(DOC/'RESULTS.json');final=read(DOC/'FINAL_QUALITY_RESULTS.json');budget=read(DOC/'COMPLETE_BUDGET.json')
    data=[]
    for directory in [LOCAL/'live-v4',LOCAL/'quality-final-v1']:
        for path in (directory/'results').glob('*.json'):
            r=read(path);validate_slot(r['slot'],EmailInput.model_validate(r['customer']));data.append(dict(path=path.relative_to(ROOT).as_posix(),r=r))
    errors=[dict(identity=x['r']['identity'],error=x['r']['parse']['error'],run_id=x['r']['call']['run_id']) for x in data if not x['r']['parse']['semantic_eligible']]
    dump('FIRST_REPLY_DENOMINATORS.json',dict(attempted_replies=len(data),structured_valid=sum(x['r']['parse']['semantic_eligible'] for x in data),structured_failures=errors,unit='First reply generation only; excludes analysis, planner, synthesis and Judge calls',not_semantic_accuracy=True))
    token_rows=[]
    for root in [LOCAL/f'live-v{i}' for i in (1,2,3,4)]+[LOCAL/'quality-final-v1']:
        for path in (root/'calls').glob('*/response.json'):
            r=read(path);m=r['metadata'];token_rows.append(dict(identity=r['identity'],run_id=r['run_id'],input_tokens=m.get('input_tokens'),output_tokens=m.get('output_tokens'),total_tokens=m.get('total_tokens'),elapsed_ms=r['elapsed_ms'],mode=r['mode']))
    dump('USAGE_AND_LATENCY.json',dict(provider_requests=budget['actual_requests'],responses_with_usage=len(token_rows),responses_without_usage=budget['actual_requests']-len(token_rows),input_tokens=sum(r['input_tokens'] or 0 for r in token_rows),output_tokens=sum(r['output_tokens'] or 0 for r in token_rows),total_tokens=sum(r['total_tokens'] or 0 for r in token_rows),elapsed_definition='Provider/SDK call plus first raw persistence timing from Dispatcher; sum is serial LLM time, not full UI end-to-end latency.',end_to_end_ms=None,rows=token_rows))
    with (ROOT/'docs/p5b8r2/ACCEPTANCE.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
    rows=[]
    for r in old:
        code=r['id'];status='R2_EVIDENCE_RETAINED';note='保持R2原证据范围，不能扩展为R3质量认证';evidence=r['evidence']
        if code.startswith('C') or code in ('B01','B02','B03','B04'):status='REAL_TESTED_NOT_CERTIFIED';note='真实重复/反转与已知漏判均保留；真人逐维n=0';evidence='JUDGE_ANALYSIS.md; JUDGE_OBSERVED_COUNTEREXAMPLES.json'
        if code in ('E01','E02','E03','E04'):status='VERIFIED_REAL_RUN' if code=='E04' else 'VERIFIED_PROTOCOL';note='48/48首次回复已运行，24配对仅18自动评分，6预选未知';evidence='A_48_FIRST_REPLY_SLOTS.json; PAIRED_RESULTS.csv; prepared-v4/PLAN.json'
        if code=='E05':status='OBSERVED_NO_STABLE_GAIN';note='WITH胜1、NO胜1、持平16、未知6；独立持平7、未知5';evidence='ORDINAL_ANALYSIS.json; FINAL_QUALITY_RESULTS.json'
        if code in ('F01','F02','F03','F04'):status='VERIFIED_REAL_RUN';note='DEV12对实际结果，11可语义评；独立12对，8可评。工具本地且两臂隔离';evidence='B_12_ACTUAL_PAIR_SLOTS.json; INDEPENDENT_ACTUAL_RESULTS.json'
        if code.startswith('G') and code in ('G01','G02','G03'):status='REAL_TESTED_WITH_LIMITS';note='6族12封冻结后生成的合成迁移测试，无后续调优；非独立真人Gold';evidence='INDEPENDENT_DATA_IDENTITY.md; FINAL_CASEBOOK.md'
        if code in ('G04','G06'):status='VERIFIED_ACCOUNTING';note='两独立授权，298/310请求，上界3.989208元，实扣未知；旧账本不变';evidence='COMPLETE_BUDGET.json; USAGE_AND_LATENCY.json; PROTECTION_FINAL.json'
        if code in ('A01','D01','D02','D03','D04','D06','D07','H08'):status='IMPROVEMENT_NOT_CERTIFIED';note='共享修订有6份真实新回复，但Judge全持平且B7-084动作错配未解决；不晋升';evidence='TARGETED_ACTUAL_RESULTS.json; JUDGE_OBSERVED_COUNTEREXAMPLES.json'
        if code in ('H06','I07'):status='VERIFIED_RESULTS_AND_LIMITATIONS';note='RQ1/2/3按实际负结果、未知和限制更新';evidence='FINAL_THESIS_RESULTS.md'
        if code in ('H07','I08'):status='VERIFIED_ARTIFACT' if (DOC/'PDF_QA.json').exists() else 'ARTIFACT_PENDING_QA';note='8页更新作品集，已渲染目视检查；质量认证未通过';evidence='STAGE_PORTFOLIO.pdf; PDF_QA.json'
        if code=='I12':status='HUMAN_PENDING';note='集中3对实际新输出盲评；不重签旧16Gold';evidence='HUMAN_REVIEW_FINAL.md'
        if code=='J_ALL':status='VERIFIED_NO_FALSE_COMPLETION';note='真实运行与缺测分开，Judge上升不作回复改善，独立失败不隐去，真人一致率不计算';evidence='FINAL_DELIVERY.md; FINAL_THESIS_RESULTS.md'
        rows.append(dict(id=code,requirement=r['requirement'],R2_status=r['status'],R3_status=status,actual_measurement=note,evidence=evidence))
    assert len(rows)==74 and {r['id'] for r in rows}=={r['id'] for r in old}
    with (DOC/'ACCEPTANCE_FINAL_74.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    md('ACCEPTANCE_FINAL_74.md','# 74项原验收与本轮新增实测\n\n逐字需求及原编号见ACCEPTANCE_FINAL_74.csv；74行不是74项通过。\n\n|编号|R2|R3|实测与局限|\n|---|---|---|---|\n'+'\n'.join('|'+r['id']+'|'+r['R2_status']+'|'+r['R3_status']+'|'+r['actual_measurement']+'|' for r in rows))
    md('ITERATIONS.md','''# 真实迭代、假设与退步

1. 身份入口：R2空事件不验证源槽位，盲化可重新标记错案；R3对所有槽位验证case/input、原始事件身份及重复ID，事件ID改为opaque并保留解盲key。离线16项首轮发现事件ID泄露臂名、SQLite连接未关闭；修复后通过，最后17项含背景引用回归通过。历史结果不回写。
2. 初次真实Judge：1次HTTP400（缺JSON字样），保存HTTP/body，账本保守UNKNOWN预留0.095386元，旧身份不重发；新评分器版本独立执行。保留v1-v4计划、授权链与源码快照，不挑最好重试。
3. 首轮真实47次：34合法、13证据引用失败。根因是缺证据的断言用查询作背景引用；将背景与支持回执分开，仍拒绝外臂/外案/外event。新10次定向都合法、3政策正确，但AB/BA22/30未过.85，停发DEV。
4. 五维锚点：无道歉不能凭措辞专业得态度2；危险动作分别落在正确维度，不在密度维重复扣分。分值/硬错/.85门槛不变。最后6次重复19/20、ABBA17/20，仅两个DEV配对窄范围过门槛；非Judge认证。
5. 实际DEV：48情绪回复和12对链全部首次运行；情绪1胜/1负/16平/6未知，链Direct1胜/10平/1未知。原始动作虚构、未来回访承诺、JSON失败保留。Judge校准消耗超预期，6个A配对在派发前分层选为未知，主研究覆盖受限。
6. 共享候选2：基于实际虚构任务/回访家族，明确composer不能创建动作，无匹配回执仅条件性建议，无安排不承诺回访；不按Case ID写回复。6份新首次实测Judge全部持平；B7-035/065部分回访承诺减少，B7-084仍明确虚构转达请求，Judge还给满分。高分持平不能证明修好；不晋升正式Champion。
7. 同文Guard：扩展已在本地登记等任务名词范围，任务创建证据不放松，独立已转达仍拦截，错类型物流单不能支持表扬转达。4项专项通过。统一新旧重筛和模型输出改善分开。
8. 冻结后一次性独立迁移：12新邮件/6语义意图家族，执行完整链与情绪单变量，未再调优。1次分析证据失败、10份回复结构失败，保留首次、不自动修复或补样。完整链1 Direct胜/7平/4未知；情绪7平/5未知。模型质量与Judge均未最终认证。
''')
    md('DELIVERY.md','# 最终入口\n\n本轮完整交付见 [FINAL_DELIVERY.md](FINAL_DELIVERY.md)。第一授权与第二授权、开发与独立测试分开保存，旧阶段缺测状态不代表最终仍未运行。')
    md('THESIS_RESULTS.md','# 最终论文结果入口\n\n完整RQ1/2/3实测及局限见 [FINAL_THESIS_RESULTS.md](FINAL_THESIS_RESULTS.md)。DEV与独立测试各自保留分母，无真人准确率认证。')
    md('ACCEPTANCE.md','# 最终验收入口\n\n[74项最终差异](ACCEPTANCE_FINAL_74.md)及 [CSV](ACCEPTANCE_FINAL_74.csv)。74行不是74项质量通过。')
    md('FINAL_DELIVERY.md',f'''# P5-B8-R3 最终研究交付

所有已授权阶段已执行到可观察结果；**最终产品质量验收未通过**，没有自动晋升候选。结论由实际首次输出支持，不以测试数量替代质量。

|阶段|真实状态|主要结果/失败|
|---|---|---|
|I 工程|已实施并Mock/离线验证|身份、事件、预算、原始响应、UNKNOWN停发；保留首轮错误|
|II Judge|真实63次校准；未认证|首47仅34合法；后10顺序不稳；最后6窄范围门槛通过，实际仍漏判|
|III 配对|48首次情绪回复、12对实际业务链均已运行|情绪1胜1负16平6未知；链Direct1胜10平1未知|
|IV 收敛/独立|6份新修订回复＋6配对；冻结后12新邮件双实验|修订6平但存在硬错；独立情绪7平5未知，链Direct1胜7平4未知；10条结构失败|
|V 交付|全文、账本、论文结果、盲评包、8页作品集与74行差异|真人逐维0；导师最终质量验收仍未完成|

回答五个问题：新版总体更自然/专业/积极/可靠尚未证实，存在部分回访承诺减少和未解决动作错配；显式情绪未见稳定可测增益；Guided完整链未见稳定优势；Judge尚不能稳定识别实际硬错/改进；数据足以支撑诚实的毕业论文结果与局限、导师作品集展示，但不能宣称系统质量或导师终审已通过。

两次明确授权合计¥35/310请求，实际{budget['actual_requests']}次，保守费用上界¥{budget['reserved_and_settled_upper_cny']:.6f}，实际独占扣费UNKNOWN。第一笔189次、第二笔109次；12个未使用请求位均保持关闭（由预定范围调整及结构失败按协议跳过），不因余额自动继续。HTTP400留有原始响应、预留与UNKNOWN记录，无旧身份重派。旧历史账本不变。

主要文件：CASEBOOK.md（DEV邮件/历史/全部新首次回复）；FINAL_CASEBOOK.md（6案修订与12新场景四臂全文）；A_48_FIRST_REPLY_SLOTS.json；B_12_ACTUAL_PAIR_SLOTS.json；FINAL_QUALITY_RESULTS.json；JUDGE_ANALYSIS.md；JUDGE_OBSERVED_COUNTEREXAMPLES.json；COMPLETE_BUDGET.json；FINAL_THESIS_RESULTS.md；ACCEPTANCE_FINAL_74.csv；HUMAN_REVIEW_FINAL.md；STAGE_PORTFOLIO.pdf。

自然度与真人满意度HUMAN_PENDING，Kappa/人机一致率均不可计算。独立集为冻结后新生成的合成语义家族迁移测试：家族生成意图预注册，并非隐藏意图的第三方盲测或人类Gold。没有用测试结果继续调优；将来若调优须转DEV身份并换新集。

## 无费用复算

```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -B tests/run_offline.py 'test_p5b8r3*.py'
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r3_deliver.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r3_final_report.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r3_close.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r3_verify.py
```

禁止重新运行已关闭的live身份。源码/计划版本变化会拒绝旧实验派发；需要重现旧实现时查看.local/p5b8r3/frozen-source-v2/v3/v4快照，勿覆盖当前源码或资产。provider raw、wire、LangChain响应与新SQLite随完整ZIP提供；只读聚合脚本不调用Provider。工程完整回归727通过对应早期v2快照；最终17项+4专项通过，不能混写成所有最新源码的完整727认证。
''')
    print(json.dumps(dict(acceptance_rows=len(rows),first_replies=len(data),structured_valid=sum(x['r']['parse']['semantic_eligible'] for x in data),total_tokens=sum(r['total_tokens'] or 0 for r in token_rows)),ensure_ascii=False))
if __name__=='__main__':main()
