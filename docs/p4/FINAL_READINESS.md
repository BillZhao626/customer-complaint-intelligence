# P4 Final / P5 Preflight — 研究者审核包

2026-10-27，Asia/Shanghai。结论：可供研究者验收的单机、有人审核、仅模拟发送的毕业设计候选；工程接线已有离线证据，独立业务质量认证尚未取得。不是任意新邮件实时 DeepSeek 已上线，也不是 P3.10 Challenger 晋升。

## 最短阅读路径

1. 本文：产品变化、体验方式、验证边界与集成。
2. [历史可信成绩单](../p5/preflight/HISTORICAL_SCORECARD.md)：400封来源、80封494/560、P2/P3.6/P3.9/P3.10复算及不可比较处；[脱敏机器汇总](../p5/preflight/historical-metrics.json)。
3. [方法与要求对应](../p5/preflight/RESEARCH_AND_REQUIREMENTS.md)：LangChain真实职责、模块/时序图、原始论文和导师要求追踪。导师原始三封邮件尚未找到，当前用户任务与旧总结分别标识。
4. [P5可执行提案](../p5/preflight/PROTOCOL.md)：独立双人标注/仲裁、族级泄漏检查、盲评、分母、同等纠错预算、晋升门槛和6项真人决策。全部未批准项保持pending。

## 本轮交付

保留并整合上轮未提交的CSV P1修复：三处上传入口统一解析，空文件/仅表头/损坏/错误编码只在本区域提示；不会泄露原文或堆栈。工作台优先呈现原始邮件、情绪/投诉/紧急度、Issue及Evidence、风险和处理顺序，技术身份/raw/JSON移入Developer Details。主要工作台标签中文化，历史工具保留旧名称和来源提示。

P4看板仍按不可变完整cohort隔离，单列accepted、failed、analysis/reply blocked、unknown及fallback；未知情绪保留在业务分母。可选统计组及成员，展开原文和证据，再进入同一案例审核。P3读分析库，P4读产品库，历史400统计及80封参考比较另列；494/560=88.21%不是独立Gold准确率。

新增 [ProductAnalysis](../../src/application/product_analysis.py) 协调原 [AnalysisService](../../src/application/analysis_service.py) 和 [ProductStore](../../src/application/product_workflow.py)。[设计依据与兼容](FINAL_INTEGRATION_DESIGN.md) 在实现前记录：不改SQLite v1、不迁移原库；新增来源从不可变配置和source_ref派生。真实 [ChatOpenAI.ainvoke适配器](../../src/infrastructure/deepseek.py) 接受显式MockTransport，测试经过真实SDK序列化/响应解析、持久化attempt、严格契约/Evidence、质量门禁、草稿审核及模拟回执。RunnableLambda fixture与历史兼容链不是这条SDK路径，LangChain不承担语义正确性认证。

新真实请求必须显式构造服务，使用独立ProductAuthorization绑定config hash、输入白名单、期限、新产品预算路径和账本身份，同时服务端开启；默认关闭。旧实验剩余次数不符合授权。已落库分析到产品快照失败返回run_id；`recover(run_id)`只读原终态run，不重发、不要求重新授权；running/uncertain不转为业务草稿。失败或分析风险阻断不能发送。

批量UI仍为明确标识的legacy_mock；可执行统一应用接口为`ProductAnalysis.submit_many(emails)`，逐行返回case/run/state，内部复用submit。验证失败与快照待恢复保留行号，不静默宣称全部成功。此API不会自动创建预算或把上传转换为付费任务。完整构造及故障恢复示例见 [离线集成测试](../../tests/test_product_analysis.py)；测试中的显式fixture/profile不能当成获准正式产品配置。

## 直接体验与复核

本机当前服务：`http://127.0.0.1:8526/`。专用本轮库为`.local/p4/final-20261026/browser-product.sqlite3`，旧实验库只读。目录从10月26日开始，续验日期为27日。

新检出可用下列命令启动独立演示，`NEW_FINAL_DEMO`必须是尚不存在的目录；勿覆盖任何旧演示：

```powershell
.\.venv\Scripts\python.exe -B scripts/p4_demo.py --out .local/p4/NEW_FINAL_DEMO
$env:COMPLAINT_PRODUCT_DB = (Resolve-Path .local/p4/NEW_FINAL_DEMO/product.sqlite3).Path
$env:COMPLAINT_DB_PATH = Join-Path (Resolve-Path .local/p4/NEW_FINAL_DEMO).Path 'legacy-ui.sqlite3'
$env:LLM_ENABLE_API = 'false'
$env:COMPLAINT_ENABLE_LIVE = 'false'
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.address 127.0.0.1 --server.port 8527 --browser.gatherUsageStats false
```

脚本同时生成START.md和7场景服务层验收收据。普通咨询：分析→核对原文/Evidence→填写审核原因和三项检查→批准→模拟→刷新/重开；自定义邮件只生成unknown占位。严重风险须额外安全核对；分析级阻断不能靠改回复消除。全部代理验收使用demo_test，不记作真人独立评分。

```powershell
.\.venv\Scripts\python.exe -B tests/run_offline.py
.\.venv\Scripts\python.exe -B scripts/run_portable.py
.\.venv\Scripts\python.exe -B tests/run_offline.py test_product_analysis.py
.\.venv\Scripts\python.exe -B scripts/audit_readiness.py --out .local/p4/NEW_METRICS.json
```

历史审计缺少私有原资产时明确unavailable；不能伪造复算成功。P5空白材料生成与校验命令见PROTOCOL。生成器只生成空白签名/标注，校验绑定和基础完整性，不验证真人身份、独立性或语义，不自动冻结Gold。

## 验收证据及限制

本机完整证据在`.local/p4/final-20261026/`，不上传SQLite、预算、raw、客户文本或原研究资料。before-workspace截图是本轮视觉整理前的工作台，不能称为全部代码均未改的RC1。

- 实际浏览器：批准前缺检查项拦截、普通咨询批准/模拟发送、终态按钮禁用、刷新及链接新标签页恢复、已核对PID的本轮服务重启；P4分组→成员原文/Issue/Evidence→返回审核；自定义中文邮件unknown占位、业务分母1且unknown=1；P3空库来源提示及历史494/560说明；CSV空/仅表头/损坏/编码/合法1行恢复，评测预测/参考标签两入口空文件隔离。截图与DOM以`browser-*`存档。
- 多Issue、严重风险额外审核、退回编辑/新版本/diff、契约与分析器失败、风险低估拒绝等继续由实际app.py AppTest覆盖；此前全浏览器矩阵保留于[RC1独立工程验收](INDEPENDENT_ACCEPTANCE_20261019.md)，不冒充本轮每条都重新人工操作。
- SDK离线集成专门覆盖快照恢复不重发、错模型/契约/Evidence、过期/错误授权、旧账本拒绝、默认关停、安全分析阻断及批量逐行结果。工程测试不能证明真实模型质量。
- 完整离线409/409通过；干净导出Portable共315项，308通过、7跳过；pip check无依赖问题。7项分别需要3份旧causal raw、historical64、研究者政策附件、真实风险重放及其UI测试，公开检出有意不含这些资料，本机完整回归均执行。最终记录、旧测试ID覆盖和文件保护在本机`FINAL_VERIFICATION.json`冻结；最终Git SHA与CI收据另存，避免自引用commit hash。

资产检查还发现并修复一项旧测试隔离遗漏：若干早于P4的AppTest（含`tests/test_streamlit.py`）原来只指定临时分析库，初始化默认空产品库使SQLite文件头的change-counter及version-valid-for变化。五张业务表均为空；仅恢复这两个计数字段可精确匹配本轮开始时的SHA256，已保留变化后副本与恢复收据并恢复原字节。测试入口现为全部测试强制指定临时分析库/产品库，各测试可覆盖为自身fixture；旧Streamlit测试也显式指定临时产品库。局部修复后仍有其他旧UI测试触及默认库，已再次按相同精确hash恢复，随后按统一隔离入口重新全量回归。此处不隐瞒中间发生过的文件变化，也不把其当作业务数据修改。

## Git集成及回滚

本轮基于P4 `7d5b8df34b8ce1f451183695c35c3627b974c697`，分支`codex/p4-final-p5-preflight`；main基线`f0a5eb71e7a46c036700f1d406cc3b34b680ff07`。main目标Draft PR包含既有P3.9/P3.10/P4累计改动和本轮修复，因此审查必须区分累计范围与本轮增量。原PR #1/#2保留，不自动关闭、改基线、合并或发Release。仅白名单源码/测试/脱敏文档提交，既存其他未跟踪成果不加入。

失败Challenger仅作为显式选择的研究profile及审计资产存在；产品默认仍离线，未晋升。回滚使用新revert提交或另检出旧SHA并指向独立演示库；不要reset/清理现有工作区，不回滚预算、原分析、产品事件或经济账本。没有数据库迁移，已保存原run/草稿/事件可以按版本复核。

## 真人验收结论分类

|类别|事项|
|--|--|
|已实现且工程验证|CSV边界、工作台/审核/模拟、来源与统计下钻、真实SDK离线接线/恢复、历史复算和P5空白准备工具|
|已实现但需真人确认|工作台易用性与实际回复内容、既有政策适用性、导师原始要求核对、P5协议/阈值/人员/预算提案|
|未实现且为可信毕设结论必要|独立双人Gold/仲裁、未暴露holdout、v3.1正式Gold适配验收、公平有预算的真实配对评测、摘要/回复独立真人质量结论|
|非必要可延后|RAG、LangGraph、多Agent、前后端重写、真实SMTP/CRM、多租户和生产负载|

新付费调用0、真实邮件发送0；旧P3.9保留1次，P3.10仍180/180停发。上述独立质量缺口需要真实人员/新预算，不能用更多fixture测试或旧开发题改名填补。
