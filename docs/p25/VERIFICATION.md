# P2.5 验证与研究状态

2026-10-15。完整离线套件 **108/108通过，0失败、0错误、0跳过**，59.720秒；原77项保留，2项portable smoke及29项P2.5新增。测试ID及机器结果见[evidence/test-results.json](evidence/test-results.json)。本机完整日志`.local/p25/full-suite-v1.txt`；测试runner阻断网络及冻结资产写入，默认报告已改到新建P2.5目录，不覆盖P2。

基线阶段79/79通过。测试先行的初始red阶段、后续新预算fixture配置错误（manifest应包含config键）均保留本机日志；修正fixture后真实配置隔离断言和最终全套通过，没有把失败阶段算通过。

新增覆盖：400完整性/确定性生成证据、模板与近重复/场景族分组、泄漏、标注Schema、假Gold拒绝、reviewer独立声明/原文证据、分歧与仲裁、冻结防覆盖/篡改、Service边界正反例、新Prompt服务链及预算版本、失败/缺预测/fallback/unknown分母、Macro-F1和混淆矩阵、摘要人工参考/输出hash/关键错误、聚合/成员原文、source/version隔离、浏览器与发送状态不误报、Git资产排除分类。

真实旧P2重放12条仍83/84、11/12，无新调用。portable显式fixture 5条含1次预期故障，28/35、4/5，仅用于检验分母。summary/reply审核均pending；独立准确率null。报告与追溯hash见evidence，完整run引用在本机`.local/p25/p2-replay-v2/`、`.local/p25/portable-evaluation-v1/`。

冻结资产：原262项与本轮额外保护的342项全部hash不变，包含原数据、outputs、论文、P1/P2证据、真实.env、P2运行库与预算库、P2 Prompt及fixture。本机完整保护台账`.local/p25/frozen-assets-v1.json`，公开摘要[evidence/frozen-assets-summary.json](evidence/frozen-assets-summary.json)。本轮起始522个文件的完整恢复副本（含Git index和本机敏感材料，绝不上传）位置在`.local/p25/recovery.json`；旧备份保留。

| 验收域 | 状态 |
|---|---|
| 本地Git工程基线 | LOCAL_GIT_BASELINE_VERIFIED；SHA见GIT_AND_GITHUB_REPORT |
| 数据审计/能力矩阵 | DATASET_AUDIT_VERIFIED / COVERAGE_MATRIX_VERIFIED |
| 统一评价框架 | E2E_EVALUATION_FRAMEWORK_VERIFIED（离线框架与记录重放） |
| 工程回归 | OFFLINE_REGRESSION_VERIFIED |
| 人工协议 | HUMAN_GOLD_PROTOCOL_READY / HUMAN_GOLD_PENDING |
| 独立泛化评价 | INDEPENDENT_HOLDOUT_PENDING |
| 服务分类修复 | BADCASE_CAUSE_VERIFIED（规则冲突） / BADCASE_RULE_REGRESSION_VERIFIED |
| 新Prompt真实模型 | REAL_MODEL_FIX_PENDING |
| 摘要/回复人工质量 | PENDING；无直接发送资格 |
| 浏览器完整E2E | PENDING；AppTest不能替代 |

后续真实独立评价最小输入：真人审核的冻结数据及完整Gold manifest、未暴露holdout与访问记录、审定taxonomy/服务对象优先级、已冻结Prompt/config、单独新预算目录、明确模型/数据范围/最大请求数/费用授权。先做新开发集小规模验证，再按预注册方案只运行封存holdout；本轮没有消耗剩余P2预算或增加付费Judge。
