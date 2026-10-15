# P3.5 实施决定（2026-10-15）

用户本轮已授权多问题契约、兼容、候选重建、离线评测及安全提交。基线 HEAD 38e79ec；既存未跟踪成果保留，恢复副本与保护清单位于 `.local/p35/`。实现前记录如下决定。

|真实问题|层次与字段|必要性/代价|未采用的替代|
|一封邮件同时夸赞和投诉|邮件 overall sentiment（增加 mixed）；Issue sentiment|高/中；整体不能覆盖方面情绪|不扩张七字段为无限组合枚举|
|夹克破损和预约取消同等重要|Issue customer_importance + importance evidence；handling_priority/rationale|高/中；策略不改写客户事实|不推断不存在的依赖关系|
|流程分派被误作责任|business_process、routing_team、attribution_certainty、missing_evidence；responsibility 始终 unverified|高/低；当前无核实责任的外部证据接口|不增加法律责任分类器|
|问题已解决仍算投诉|Issue resolution 与邮件 complaint_status|高/低；描述客户报告状态|不实现 P4 工单审批状态机|
|wrong size 被混作 wrong item|Issue reason 新增 size/fit issue|高/低；v2 投影 other 并诊断|不重标历史参考|
|证据无法定位|subject/body 零基字符跨度、逐字 quote|高/中；校验位置不等于校验语义|不把摘要自动当事实证据|
|渠道与门店混淆|独立 contact_channel / purchase_channel、mentioned_store / store_verification|中/低；unknown 与未核实显式|不从热线购买推断本次联系渠道|
|新旧结果必须共存|RunConfig schema/taxonomy/prompt hash + metadata.analysis_v3；result 保存明确 v2 投影|高/中；沿用 SQLite v2 的 metadata_json，事务保存/重读并严格验证绑定，无需迁移旧库|不重建库，不追溯重算旧分数|
|统计分母变形|新 v3 快照分别列 email revisions / issues 及成员|高/中；拒绝混来源/版本|不改 P3 和历史 Dashboard 的口径|

AnalysisService 保留统一 EmailInput 与 AnalysisRun。v3 provider 只输出 AnalysisV3；服务校验原文证据及安全草稿规则，再保存完整 v3 与有损兼容投影。v2→v3 保留完整原始 v2 供无损回程，但缺失的多问题/证据/渠道标 unavailable，不能制造提取能力。v3→v2 不确定主问题时返回 unknown/other 并列诊断，绝不以业务优先级替代客户主次。

验收：严格未知字段/枚举/hash/跨度/重复ID/关系约束；历史往返；同服务 fake 与模拟 HTTP；SQLite重读/幂等/错误/版本；24条决策快照校验；数据精确/近似/语义族审计；失败不缩分母；实际 app.py AppTest 与条件允许的浏览器测试。真实 v3 模型质量、人工 Gold、独立 holdout 继续 pending。新候选正文及裁决只保存在 .local，不公开。

## 一手资料与取舍依据

- [SemEval-2016 ABSA](https://aclanthology.org/S16-1002/)（研究，已读论文）：方面/实体属性与情绪分别处理，支持问题层情绪；不直接照搬餐饮/笔记本 taxonomy。
- [ACOS 2021](https://aclanthology.org/2021.acl-long.29/)（研究）：方面、类别、观点、情绪及隐含信息说明仅靠显式对象不充分。本项目以 unknown/missing evidence 表示未提及信息，不建立完整四元组训练系统。
- [ISO 10002:2018](https://www.iso.org/standard/71580.html)（规范公开摘要）：投诉处理及持续改进支持流程追溯；未取得全文，不宣称条款级合规或认证。
- [Zendesk ticket fields](https://support.zendesk.com/hc/en-us/articles/4408886739098-About-ticket-fields)（成熟产品实践）：status、priority、assignment分开；本项目借鉴分离，不复制完整工单生命周期。
- [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)（厂商工程指导）：场景化评测、人工校准、边界案例；采用逐层指标和关键错误门禁，不用生成者自评证明准确率。
- [NIST AI RMF Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)（风险框架）：记录测试条件、限制及独立评估；以显式 pending 防止工程通过替代语义证据。
- [GPT-6 Astra Codex 指南](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)（2026-09-11 厂商工作流经验）：按任务相关性加载说明、明确完成边界。仅用于本轮工程工作组织，不作为 DeepSeek 提示词效果的证据。

以上链接于2026-10-15核实。具体字段与实现是本项目工程取舍，不是来源强制规定；未采用社区经验作为规范依据。
