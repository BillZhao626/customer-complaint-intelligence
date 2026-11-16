"""Explicit 56-item cross acceptance and local ZIP, with bounded claims."""
import csv,json,re,shutil,subprocess,sys,zipfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b8r4 import DOC,LOCAL,ROOT,read,sha,rel,dump,block

def build():
    # Each value: status, actual observation/denominator, evidence, remaining gap.
    rows={
1:('PASS','原HEAD保留；3个既有共享源码小改，新增R4覆盖层','source-changes.json; workspace.json','无新平台'),
2:('PASS','历史资产逐文件hash核对，见保护记录分母','protection-final.json','不以Git diff代替未跟踪文件保护'),
3:('PASS','真实外部业务操作0；本地任务与Mock标明fixture','local-action-smoke.json; budget-and-permissions.json','不提供生产执行认证'),
4:('PASS','六个B8/R3旧账本只读核查；R4新live账本0','budget-and-permissions.json; tests-targeted-final.txt','无新付费授权'),
5:('PASS','超时/计费未知/重启/存储失败注入保留UNKNOWN、不再派发','tests-targeted-final.txt','真实故障恢复不自动重试'),
6:('PASS','B7-084实际全文复现：先FAIL；修复后转达断言unsupported+H04','observed-084-before-after.json; test-before.txt','仅确定性缺陷修复，非新回复'),
7:('PASS','25控制含同kind错goal、human_input与store_service正反例','fact-controls.json','开放域隐含目标仍有规则覆盖边界'),
8:('PASS','case/run/arm/input/payload/空事件臂及盲化正反回归','tests-targeted-final.txt','旧原生身份缺失不能追认'),
9:('PASS','7状态矩阵；内部存在与外部完成分别验权','tests-targeted-final.txt; fact-controls.json','assigned不等于外部完成'),
10:('PASS','已拍/已发不推断接收；received不可支持viewed','tests-targeted-final.txt','非真实附件处理流程测试'),
11:('PASS','物流查询/created退款不能支持到货/退款完成','fact-controls.json; tests-targeted-final.txt','未接入真实物流或退款接口'),
12:('PASS','B7-084不再同时supported及同断言block；一致性断言启用','observed-084-before-after.json','开放域识别边界保留'),
13:('PASS','另一臂事件ID拒绝，先验原始绑定再盲化','tests-targeted-final.txt','B7-009历史分数不覆盖，新Judge未派发'),
14:('PASS','原满分保留，解析器输出JUDGE_INTERNAL_CONTRADICTION/硬错遗漏','tests-targeted-final.txt; observed-084-before-after.json','新LLM是否主动学会识别尚未验证'),
15:('PARTIAL','历史124/124请求已查；5额外字段、5缺括号、1尾随；补强Schema提示','structure-audit.json','新模型首次结构修复复验0，未认证'),
16:('PASS','124/124实际wire为json_object；官方文档核查2026-11-02','structure-audit.json','json模式不保证字段Schema'),
17:('PASS','首次113/124不变；5/11可本地恢复但仍列首答失败','structure-audit.json; tests-targeted-final.txt','本地可读不等于语义正确'),
18:('PASS','16逐案对账；3逐字与历史原文逐字一致，13助手代拟','annotation-overlay.json','全部为DEV，无新逐维人分'),
19:('PASS','6/6 Owner定性政策写入overlay；084 COMBINE','annotation-overlay.json','不再要求重签'),
20:('PASS','24/24研究者辅助分类裁决单列分类任务','annotation-overlay.json','非回复Gold'),
21:('PASS','80/80项目分类参考单列','annotation-overlay.json','非独立人类回复评分'),
22:('PASS','B4 28候选轮次、24线程，身份未升级','annotation-overlay.json','reviewer仍未签署'),
23:('PASS','检索旧16/6/24/80/B4及历史Judge输入；未找到独立近30签署集','annotation-overlay.json; owner-search.json','“近30”真实回复集合仍UNKNOWN，不凑数'),
24:('PASS','所有Owner文字政策numeric=false；COMBINE及未知保留','annotation-overlay.json','人类数值n=0'),
25:('PASS','五维原0/1/2及N/A定义、正反锚点与引用协议','../R4_OWNER_JUDGE_CALIBRATION.md; freeze.json','锚点是开发协议，不是人类数值'),
26:('PARTIAL','客户目标/Issue覆盖/评分span强制解析，72位Mock流程验证','prepared-plan.json; tests-targeted-final.txt','新真实Judge协议输出0'),
27:('PASS','逐断言含类型/业务物件/目标/状态/span及证据ID','observed-084-before-after.json; fact-controls.json','有限中英规则，不覆盖所有暗示'),
28:('PASS','四类语义发现与结构失败分别保留；不把坏JSON评0','historical-judge-revalidation.json; structure-audit.json','分类可执行，主观严重性未认证'),
29:('PARTIAL','25控制FN0/12、FP0/13含合理条件句与否定','fact-controls.json','真实LLM误拒/漏判新校准0'),
30:('AUTHORIZATION_BLOCKED','长短条件句均不触发事实硬错；新长度评分实验0','fact-controls.json; prepared-plan.json','不能据程序同结果声称模型无长度偏好'),
31:('AUTHORIZATION_BLOCKED','历史AB/BA和重复逐维结果留存；新真实次数0','historical-judge-revalidation.json','模型稳定性尚待新付费校准'),
32:('AUTHORIZATION_BLOCKED','6案定性方向已迁移；新Judge与Owner方向一致率N/A n=0','annotation-overlay.json; prepared-plan.json','COMBINE不强制赢家'),
33:('PASS','HUMAN_NUMERIC_UNAVAILABLE；Kappa/相关/逐维人机一致N/A','summary.json','没有人类数值真值'),
34:('PASS','保持独立安全/隐私/政策门禁；硬错否决不能被高分覆盖','tests-targeted-final.txt; source-changes.json','不是开放域安全认证'),
35:('PARTIAL','25开发控制、不同动作/语法族；没有用2例或6轮认证','fact-controls.json','未见集0，Judge未获认证'),
36:('PASS','共享Composer对两臂相同；仅可选输入不同；有源码hash','source-changes.json; freeze.json; prepared-plan.json','尚未晋升Champion'),
37:('AUTHORIZATION_BLOCKED','中性损坏致歉规则已共享；旧036全文保留','full-reply-comparison.json','R4新首次回复0，不宣称措辞改善'),
38:('AUTHORIZATION_BLOCKED','084知识保留及咨询/转达回执严格分开','full-reply-comparison.json; local-action-smoke.json','真实新知识+主动售后回复未生成'),
39:('AUTHORIZATION_BLOCKED','035保留周六期限、已有high-priority事实','full-reply-comparison.json','新真实处理/回复0'),
40:('PARTIAL','显式转达请求跨resolved/praise保留；本地fixture真建任务且幂等','local-action-smoke.json; tests-targeted-final.txt','009/010新真实首答0，未发生外部转达'),
41:('AUTHORIZATION_BLOCKED','085收费依据优先规则和旧两链全文已保留','full-reply-comparison.json','新首答0，不以Prompt本身算改善'),
42:('AUTHORIZATION_BLOCKED','084不着急仍推进规则已共享，无安排回访被拦','full-reply-comparison.json','无新实际模型输出'),
43:('PASS','生产R4模块无Case ID分支；相似fixture换ID行为不变','source-changes.json; tests-targeted-final.txt','报告和预注册案例清单有ID，非业务分支'),
44:('PARTIAL','6案原邮件/Issue/历史两链/所有R3回复全文与回执、旧Judge齐全','../R4_REAL_REPLY_COMPARISON.md; full-reply-comparison.json','新两链明确AUTHORIZATION_BLOCKED空槽'),
45:('PASS','结构113/124、次级恢复5与语义新n=0分栏','summary.json; ../R4_REAL_REPLY_COMPARISON.md','无合并单分'),
46:('PASS','旧24及R3N12均为R4已曝光DEV；原历史身份不变','prepared-plan.json','不可改名为新holdout'),
47:('NOT_RUN','候选/Judge已freeze；R4独立正文未创建 n=0','freeze.json; prepared-plan.json','需另定隔离家族和采集授权，不能用DEV替代'),
48:('PASS','R4真实Provider派发0、费用0；无授权在Provider构造前拒绝','budget-and-permissions.json; tests-targeted-final.txt','新真实实验AUTHORIZATION_BLOCKED'),
49:('PASS','124首次raw保留；5次恢复另列；UNKNOWN不重派','structure-audit.json; protection-final.json','无择优补样'),
50:('PARTIAL','程序TP12/FN0/FP0/TN13；历史未知及N/A保留；新Judge n=0','fact-controls.json; historical-judge-revalidation.json','不把程序混淆矩阵当LLM准确率'),
51:('PARTIAL','导师五要求与历史功能/证据逐项映射','../R4_FINAL_ACCEPTANCE.md','本轮未重新实测浏览器或独立语义'),
52:('PASS','论文补充明确R3未证实情绪/Guided稳定增益；R4仅工程证据','../R4_FINAL_ACCEPTANCE.md','无新语义提升结论'),
53:('PASS','保留旧真实8页PDF，引用原来源；未重包装或伪造新截图','../R4_FINAL_ACCEPTANCE.md','不将R4当新产品认证'),
54:('PASS','四核心MD、一个可校验ZIP，原始数据集中evidence','../R4_FINAL_ACCEPTANCE.md; package-manifest.json','不重做Harness/UI/PDF'),
55:('PASS','原74行逐行保留R3状态，新增R4差异/限制/证据','old-74-delta.json','不将全部旧行升为通过'),
56:('PASS','R3持平/退步/失败原值保留；R4语义UNKNOWN、不预设Guided获胜','../R4_REAL_REPLY_COMPARISON.md','真实负结果仍可用于论文'),
    }
    source=(LOCAL/'attachment-1.txt').read_text('utf-8-sig');accept=[]
    for line in source.splitlines():
        if re.match(r'^\d\d \|',line):
            parts=[x.strip() for x in line.split('|')];number=int(parts[0]);status,measurement,evidence,gap=rows[number]
            accept.append(dict(id=parts[0],requirement=parts[1],prompt=parts[2],status=status,actual=measurement,evidence=evidence,remaining=gap,
                               version_hash='evidence/freeze.json; each source artifact includes hash/input identity',unit='per-item explicit denominators above; no combined quality accuracy'))
    assert len(accept)==56 and len({r['id'] for r in accept})==56
    dump(DOC/'evidence/acceptance-56.json',accept)
    with (DOC/'evidence/acceptance-56.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(accept[0]));writer.writeheader();writer.writerows(accept)
    s=read(DOC/'evidence/summary.json');protection=read(DOC/'evidence/protection-final.json');freeze=read(DOC/'evidence/freeze.json')
    table='|编号|要求|结果|实测/分母|证据（evidence/下，另注者除外）|剩余问题|\n|---|---|---|---|---|---|\n'
    for r in accept:table+='|'+'|'.join(str(r[k]).replace('|','/') for k in ('id','requirement','status','actual','evidence','remaining'))+'|\n'
    text='''# R4 最终逐项验收

本轮按S0→S5推进了全部不依赖付费的工程工作；真实Judge校准、真实新首次回复和未见家族质量验证仍受新增付费授权限制。没有重建Harness/审批UI，没有提交、推送、外部联系或真实发信。已完成不等于56项全通过。

本轮真实请求0，新增费用¥0。旧R3 298次/310授权、历史保守上界¥3.989208和UNKNOWN预留保持原记录，剩余位不续用。旧16参考无需重签。本轮不需要Owner重复做政策确认；目前明确依赖仅为新的CNY金额和底层请求上限授权，以及未来如需人类数值认证所需的新增真实评分。

S0：先保存实际失败，再修复创建支持的空集合漏洞、Guard一致性与Judge事实否决；结构问题按wire/raw归因。S1：完成16/6/24/80/B4全来源轻量overlay；S2：五维协议与25事实控制、历史原始Judge复核；S3：共享Composer和必要显式转达Planner可选版本及退步回归；S4：72请求位计划和假Provider全链运行，付费0/新独立0；S5：四核心文件、56行与74行差异、完整历史邮件和审核ZIP。每阶段状态不掩盖未认证部分。

导师五项主线：

|要求|既有证据|R4实际贡献与限制|
|---|---|---|
|LLM生成邮件|docs/p5b7/review_bundle/CASEBOOK.md及R3完整历史册；400程序模板与90模型合成分开|不新增/重写历史邮件；非真实消费者数据|
|LangChain情绪及来源分析|src/application/p5b8_pipeline.py；docs/p5b8r3/CASEBOOK.md、124实际wire索引|共享协议尊重原文，坏结构不当语义分|
|产品/门店负面统计|docs/p5b8r3/FINAL_THESIS_RESULTS.md及历史产品统计下钻记录|业务类别是来源关联，非因果/法律责任；无新分母拼接|
|情绪/知识/动作→客服回复|R4_REAL_REPLY_COMPARISON.md六案全文、实际回执、旧分和同文重筛|确定性动作支持修复，不冒充新生成质量提升|
|Web产品演示与评测|docs/p5b8r2/UI_ACCEPTANCE.md；docs/p5b8r3/STAGE_PORTFOLIO.pdf及PORTFOLIO_SOURCES.json|沿用真实历史UI/8页作品集，本轮未再包装、未声称新浏览器认证|

可供论文直接引用的补充结果：R3没有证明显式情绪或Guided稳定增益。R4在25个开发事实控制上TP=12、FN=0、FP=0、TN=13；这是程序事实校验，非LLM Judge或人类满意度准确率。124历史首答113合法，5额外字段、5缺括号、1尾随；5可本地语法恢复，不提高首答113/124。Owner逐维人类数值n=0，Kappa及相关不可计算。R4新模型语义改善、真实顺序/重复稳定性及泛化均未测，不能声称提升。

重要完整错误前后例子、原Judge证据及事件在R4_DETERMINISTIC_AUDIT.md：实际B7-084整封回复/满分Judge/Guard冲突→新断言拒绝；匹配表扬任务正例；本地退款请求冒充完成；正常条件式；照片阅读缺证。不能用这五个例子认证开放域Judge。

预备付费工作是72请求位：6案×2独立新规划/分析＋6案×2新首答＋6案×3 AB/BA/重复Judge＋10个开发事实配对×3Judge。最多72并不等于必须消耗，结构失败的配对不再派Judge；UNKNOWN立即停整个账本。仅用已有合成DEV原邮件，每臂新空本地库独立规划和执行，禁止复制历史或另一臂回执，不执行新外部业务。此计划不是授权。独立未见家族验证须另定方案和范围。pricing文档2026-11-02为USD计价，计划3/12 CNY每百万是保守预留边界（假设≤10 CNY/USD），非实际汇率或实扣费用；未来授权须认可该预留口径。新同文事实重筛绝不计新质量。

复现命令：
```powershell
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r4.py
.\\.venv\\Scripts\\python.exe -X utf8 -B tests/run_offline.py 'test_p5b8r*.py'
.\\.venv\\Scripts\\python.exe -X utf8 -B tests/run_offline.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r4_deliver.py
.\\.venv\\Scripts\\python.exe -X utf8 -B scripts/p5b8r4_acceptance.py
# --live 无新增授权时，在Provider构造前明确拒绝。
```

精确版本和输入Hash：evidence/freeze.json；每个控制、原始请求与annotation记录另含自身hash。脚本默认只写R4派生文档；任何重做实验应另建版本，不能覆盖本轮freeze或结果。

逐项状态：
'''+block(dict(counts=dict(Counter(r['status'] for r in accept)),summary=s,protection=protection,freeze=freeze))+table
    old=read(DOC/'evidence/old-74-delta.json')
    observed=read(DOC/'evidence/observed-084-before-after.json')
    text+='\n## 三个完整错误前后例子及Judge证据\n\n### 实际B7-084：咨询回执冒充转达\n\n'+observed['original']['reply']+'\n\n原Judge逐维与证据（原字句保留）：\n'+block(observed['original']['judge'])+'\n修复前后：\n'+block(dict(before=observed['rerun_before']['actual'],after=observed['after']))
    failures=[r for r in read(DOC/'evidence/structure-audit.json')['rows'] if r['defect']!='NONE']
    for category,title in [('SCHEMA_EXTRA_FIELD','额外type字段不放宽白名单'),('JSON_SYNTAX','缺括号恢复不改首次失败')]:
        item=next(r for r in failures if r['defect']==category)
        text+='\n### '+title+'\n\n实际历史原始返回全文：\n\n```text\n'+item['raw']+'\n```\n'+block({k:item[k] for k in ('identity','run_id','source','raw_hash','metadata','parsed','wire_source','response_format','max_tokens')})+'\nJudge语义评分：ENGINEERING_FAILURE，不能把空串评成0分；本地恢复另列且不提供新模型质量证据。\n'
    text+='\n## 旧74项逐行差异\n\n原始细节完整保留在evidence/old-74-delta.json；此表只描述本轮增量，不覆盖原状态。\n\n|编号|原R3状态|R4状态|差异及限制|\n|---|---|---|---|\n'
    text+='\n'.join('|'+ '|'.join(str(r[k]).replace('|','/') for k in ('id','R3_status','R4_status','R4_delta'))+'|' for r in old)
    (DOC/'R4_FINAL_ACCEPTANCE.md').write_text(text+'\n','utf-8')
    return accept

def package():
    paths=[p for p in DOC.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name!='package-manifest.json']
    paths += [p for folder in ('src/application','src/evaluation','scripts','tests') for p in (ROOT/folder).glob('*p5b8r4*.py')]
    paths += [ROOT/n for n in ('src/application/p5b8r1_guard.py','src/application/p5b8r3_final_guard.py','src/evaluation/p5b8r3_judge.py')]
    paths += [ROOT/'docs/p5b8r3'/n for n in ('FIRST_REPLY_DENOMINATORS.json','JUDGE_OBSERVED_COUNTEREXAMPLES.json','FINAL_THESIS_RESULTS.md','ACCEPTANCE_FINAL_74.csv')]
    paths += [ROOT/n for n in ('docs/p5b8r3/prepared-v4/GOLD16_READONLY_COPY.json','docs/p5q/owner_accepted_references_v1.json','docs/p5b8r2/OWNER_POLICY_v2.md','docs/p5b4/GOLD_CANDIDATE.jsonl','.local/p35/calibration-decision-v1.1/snapshot.json','data/golden/golden_labels_review_sample_v1_reviewed.csv','HANDOFF.md')]
    for row in read(DOC/'evidence/structure-audit.json')['rows']:
        if row['defect']=='NONE' or not row['wire_source']:continue
        folder=(ROOT/row['wire_source']).parent
        paths += [folder/n for n in ('wire-request.json','provider-response.txt','provider-http.json','frozen-input.json','response.json') if (folder/n).is_file()]
    paths=list(dict.fromkeys(paths))
    manifest={rel(p):sha(p) for p in paths};dump(DOC/'evidence/package-manifest.json',manifest)
    out=DOC/'P5-B8-R4_COMPLETE_REVIEW.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths+[DOC/'evidence/package-manifest.json']:z.write(p,rel(p))
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for n,h in manifest.items():
            import hashlib
            assert hashlib.sha256(z.read(n)).hexdigest()==h,n
    print(json.dumps(dict(archive=str(out),files=len(manifest)+1,bytes=out.stat().st_size,sha256=sha(out))))

if __name__=='__main__':build();package()
