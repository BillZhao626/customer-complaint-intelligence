# P3.9 执行边界

本轮研究者授权72次/10元；64次固定配对计划，8次余量不能自动使用。先4对冒烟，研究者对绑定收据的内容安全批准之前禁止remaining。来源是本轮用户请求及本机附件，不是程序或AI签署。

保留P3.8 final-v4的32个输入及64步骤；原manifest、Prompt与零授权记录不修改。P3.9建立新身份：A逐字使用P3.8迁移基线，B在P3.8业务版上追加本轮六项通用规则，不嵌入题号、答案、裁决或参考。两组仍用原Analysis-v3.1、正式AnalysisService、DeepSeek LangChain adapter、相同gate、投影和SQLite格式。新adapter仅补充发送前payload核对与缓存用量观测，双方共用。无契约/Taxonomy/数据库迁移。

独立排他账本绑定授权、源码、配置、依赖、白名单和固定顺序。预写attempt及保守费用后才发送；SDK/应用重试均为0。官方tokenizer估计完整序列化payload和chat template，取较大者再加1024 token；50,000 UTF-8字节是独立请求大小限制，不能当作精确token证明。实际usage超过预留token、缺失/异常、模型身份变化、失败或未知发送立即锁止。费用按核实的高峰未命中费率保守预留，实际账单保留null。

验收：来源完整性22×18/2失败/6政策；旧P3.6锁账及所有旧文件hash不变；离线fixture验证预算并发/重启/人工闸口/失败/身份/用量；真实每步service→SQLite→新连接重读；冒烟可读包含原文、完整A/B分析、证据、摘要回复和18维候选。不得以Schema接受率证明内容正确。全部为开发暴露合成邮件，INDEPENDENT_HOLDOUT_PENDING。

真实raw、裁决、授权、邮箱原文与内账仅在.local/p39；公开只留源码、测试和脱敏说明。本阶段不发送邮件。
