# 人工标注操作指南 v1

当前状态 HUMAN_GOLD_PENDING。队列在`.local/p25/annotations-v2/`，legacy和complex分别提供candidates、reviewer-a、reviewer-b、adjudication JSON。真实评审可直接开始；reviewer均为空，没有代理伪签名。先复制自己的空白文件到新版本，勿覆盖原队列。

每位评审只看subject/email_body，不看模型预测和另一位的文件。明确填写真实reviewer标识、human_declaration和independent_of_predictions；这些是人的声明，不能由工具自动勾选。旧400候选不预填expected，避免模板答案锚定。

逐字段记录value、原文连续证据片段evidence数组、certainty(high/medium/low)、rationale。status完成后写reviewed；证据必须逐字出现在主题或正文，不能编造摘要作为证据。缺失对象可引用整段邮件并在rationale说明“全文未出现对象”。unknown与none不同：非投诉reason/source为none；真正缺依据为unknown；业务来源不清但确有多方问题为unclear。歧义保留低确定度和理由，交仲裁。

情绪按当前主要未解决问题；混合称赞不自动消除投诉。紧急度以明确安全风险、紧迫表述或严重影响为依据，不按案例序号决定。以邮件为单位，只选一个主要问题；无法确定主次必须说明，不隐含增加多标签能力。

产品类别规则见BADCASE_REVIEW.md。Service/Other表示明确服务对象，不是兜底垃圾桶；只有商品缺失不能自动决定unknown，也不能自动决定Service/Other。商品与服务同时出现先找主要对象；无法唯一判断则unknown并记录。来源归因是业务归属，不能写成已证实因果或法律责任。

summary_reference、reply_reference、attribution_reference逐个填写facts（事实要点）、forbidden（不能编造的内容）、constraints（约束）、alternatives（可接受表达）。审核后status=approved、reviewer=本人的标识。摘要不要求唯一标准句；回复必须是未发送草稿，不假设订单、政策、批准退款、赔偿、送达日期或已执行动作。未知政策应请求必要信息或提出核查。详见EVALUATION_PROTOCOL.md的Rubric和关键错误门禁。

建议先从每类5条小批次校准标注规范，但这些已讨论样本只属于开发集。正式holdout需另行隔离，不能拿本次讨论的例子反复调Prompt后又声称独立。
