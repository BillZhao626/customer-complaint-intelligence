# P3.8 验证与交接

2026-10-16（Asia/Shanghai），起点HEAD `a280b3cda1e4ba6f62a94fcd271bfbcd9239f132`。本轮新增真实模型调用0次、费用0元，没有真实客户邮件或发送。完整本机报告为`.local/p38/REPORT.md`，研究原文不进入公共Git。

|状态|证据与边界|
|---|---|
|POLICY_V2_OWNER_APPROVED|[八项政策台账](research-owner-policy-v2.json)，来源是本轮研究者明确指令；不是内容Gold签署|
|SCHEMA_EVOLUTION_VERIFIED|[新Schema](analysis-v3.1.schema.json)、[兼容说明](COMPATIBILITY.md)，旧v3安全严格规则及Schema保留|
|DATASET_ADOPTION_VERIFIED|实际183历史版本/172当前；159自然、1对抗、12质量隔离、11被替代；32处理回执，128自然候选质量待审|
|E2E_OFFLINE_VERIFIED|正式service/新SQLite/重读/分母、64 fake演练、AppTest和本机浏览器保存/刷新/查看；不代表真实模型质量|
|HUMAN_CONTENT_REVIEW_PENDING|22成功×18维AI候选意见，2失败不可评分；人工分数与关键错误确认均null；159自然候选尚未逐项人工语义审核|
|REAL_MODEL_AB_PENDING|[同v3.1方案](AB_PLAN.md)、32白名单/64步骤/预检可执行；当前授权0/0，真实预算未创建|
|INDEPENDENT_HOLDOUT_PENDING|全部开发暴露；无新的独立Gold或Holdout|

自然/对抗/隔离是用途队列，语义族是另一个字段。已批准P35-157新版保留转发恶意页脚，P35-159保留反讽；不因原semantic_family=adversarial就暗中扩大自然子集排除范围。P35-073明确单列对抗。旧原文和原12隔离记录全可追溯，新正文不继承旧预测或人工参考。

泄漏检查涵盖183版本+24冻结输入的207节点。精确/归一化重复0、阈值0.86近重复0，冻结24题与候选之间直接来源匹配0；已知重写/叙事/语义族/保守主题关系形成5个连通分量。冻结题与候选有448个保守主题重合边，这不是448个已证实同源污染；禁止据词面未命中宣称独立。24题原template/semantic组和来源hash已读入；未登记翻译同源仍需人工检查。

原P3.6全部40次JSON/SQLite/Prompt/输入/配置/输出/白名单/预算只读复核，锁止authorization_limit；143/168、17/24、29/32不变。没有修改24题v1.1参考或用新政策覆盖旧low。

测试从200本机/110 portable开始，最终247/247本机、153/153 portable；原有测试ID和expected保留。首次基线出现一次旧AppTest冷启动超时，23项live单独复验通过；中间暴露共享枚举改变旧Schema和新fixture混合来源/血缘错误，已通过独立配置子类型及修正fixture解决，失败日志保留。另对费用未知保持null而非0增加断言。完整日志、连续性、资产保护和Git收据详见本机报告。

有限词面风险、否定范围、语言检查是工程门禁，不能证明所有自由文本语义正确。摘要有用性、证据蕴含、独立事件及全面安全/隐私审核仍需真实人类过程。后续只需内容审核/新版问题参考、128待审质量项、独立Holdout及另行付费授权，不重问已批准八项政策或冻结24题。

复验命令及UI入口见[REPRODUCE](REPRODUCE.md)。
