# v3.1兼容边界

旧 `analysis_v3.py`、旧三版Prompt、P3.5 Schema和P3.6原始运行均未修改。旧v3仍拒绝medium安全投诉。`RunConfigV31`单独扩展配置类型，原`RunConfig`枚举和旧`EmailAnalysis`导出Schema保持一致；运行包按配置版本精确解析，v2/v3/v3.1不能互相冒充。Pydantic验证器补充JSON Schema不能表达的原文、跨字段和来源约束。

新契约保留旧字段，增加风险`severe/minor/none/unknown`、风险证据和解释、urgency_basis及证据、policy_version、reply_language、billing/invoice reason/process。severe强制high；minor安全问题允许medium。有限明确危险表达还会检查严重风险是否被遗漏或降级；该词面检查不是完整危险语义识别器。风险证据/紧急度证据同样验证原文位置。完全相同的Issue证据列表拒绝；不同跨度是否真正支持独立事件仍需语义审核。

客户重要性和建议业务顺序继续独立。客户equal需明确equal/同等重要证据；一起跟进不够。关系继续要求原文证据，不从业务顺序生成reported_dependency。客户primary未确定时，不用处理顺序挑主问题。

发票使用`billing/invoice issue`，团队`customer_support`仅为协调建议。新`customer-primary-v31-safe-1`投影将发票有损映射为other/unclear，附诊断，绝不虚构refund或客服过错。size/fit仍other；mixed仍unknown；未知投诉状态投false有显式损失说明；confidence=0是兼容哨兵。

SQLite继续user_version=2，无DDL迁移。完整预测保存为analysis_v31及其hash，原始响应在attempt，投影有独立kind/hash/diagnostics，回复unreviewed_unsent。读取同时验证输入、配置、cohort、幂等身份、原始响应与完整预测一致、输出hash和投影；不能只改metadata把派生结果写成原始预测。旧v3的analysis_v3键和验证路径保留。

统计按单配置cohort和dataset_id隔离。邮件和Issue分母分别显示；failed/fallback保留邮件分母，unknown/unclear不隐去。原P3.6七字段143/168、邮件17/24、最终契约29/32只是旧开发背景，新政策不回写旧参考，不做跨Schema Prompt提升声明。
