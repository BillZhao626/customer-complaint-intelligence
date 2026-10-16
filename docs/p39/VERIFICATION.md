# P3.9 预检与真实冒烟停止回执

2026-10-16（Asia/Shanghai）。起点HEAD为`a590fd754bec9f8df8429c7d98657695b8dd0368`。本轮已收到独立72次/10元授权；计划64次，8次复验余量不能自动消费。全部仍为已开发暴露的虚构邮件，不是独立Holdout。

|状态|证据与限制|
|---|---|
|CONTENT_POLICY_OWNER_APPROVED|附件六项政策保留用户请求及hash|
|CONTENT_DEV_EXPERT_ADJUDICATED|22成功×18维=396判断、2失败不适用；run/input/output、原文/摘要/回复逐一匹配；来源是研究者批准政策+助手专家应用，非独立真人Gold|
|AB_PREFLIGHT_VERIFIED|P3.8 final-v4固定32输入/64步骤；新P3.9身份；同v3.1契约/配置/链路，A逐字保留迁移基线，B增加六项通用规则；模型payload无参考/裁决|
|AB_SMOKE_STOPPED_BEFORE_GATE|真实第1次A收到响应但跨字段契约失败，账本halted=failure_requires_review；未调用B，没有冒烟通过收据|
|AB_SMOKE_RESEARCHER_REVIEW_PENDING|4对冒烟未完成，尚未达到可批准remaining的人工闸口；AI没有创建真实researcher_approved文件|
|AB_REMAINING_PENDING|剩余63个原计划请求未尝试，其中7个冒烟及56个remaining；复验0次|
|NEW_SEMANTIC_HUMAN_JUDGMENT_PENDING|失败raw有新18维AI可见范围意见，不计为成功内容分数；没有Issue级Gold或A/B语义胜负|
|INDEPENDENT_HOLDOUT_PENDING|全部开发暴露，保持pending|

官网人民币价格与模型页面本机实时下载留存：deepseek-flash对应DeepSeek-V4.1-Flash，高峰缓存未命中输入¥2/百万token、输出¥8/百万token。保存官方v4 tokenizer，tokenizers==0.22.2仅装入本轮本地工具目录，未改项目venv/requirements。取完整JSON payload与官方chat template较大token估计+1024余量；字节上限独立检查。64次预留规划¥2.704864、72次最坏样本上界¥3.159792、最大payload20,535字节。实际API输入3427超过chat估计3403，但低于4747预留，说明不能把tokenizer估计当精确计费证明。

真实首请求通过AnalysisService→DeepSeek LangChain→原契约/gate→独立SQLite→新连接重读。JSON可解析、JSON Schema形状通过、三处证据跨度精确；模型同时给出low与general_help（后者强制medium），原跨字段检查拒绝，属于模型输出契约不一致。仅在内存诊断副本改basis=other后所有原检查通过；未保存为预测、未改原run、未放宽gate、未改冻结Prompt、未真实复验。

真实用量3427输入+649输出=4076 tokens，缓存hit=0/miss=3427。高峰未命中估算¥0.012046，持久保守预留¥0.041494，实际账单null。provider延迟6873.773毫秒、service 7120.809毫秒，各n=1；不能据此宣称生产p95或稳定性。接口收到内容1/1，契约接受0/1，失败1/1；32对计划尚未形成可比较A/B结果。

本机`.local/p39/REPORT.md`为总入口；`runtime-v1/review-v2/SMOKE_REVIEW.html`与Markdown包含原邮件、全部raw、摘要回复、Issue字段、证据、用量和未尝试B；`AI_FAILURE_REVIEW_v1.md/json`为18维新AI意见；`stop-receipt-v1.json`是停止回执，不能替代smoke receipt。源附件/授权/账本/原始响应仅本机，不公开。

离线完整回归259/259，加新增真实失败模式的脱敏fixture回归1/1；portable165/165加该新增回归1/1。包含mock HTTP实际SDK发送体核验、缓存字段、请求/费用上限、重启/租约、未知发送、失败即停、第9次闸口、假批准hash拒绝、64次fake完整路径和分母/人类空值。测试fake批准仅在临时目录，明确标注fixture；真实目录没有批准文件。旧247项完整、153项portable均保留。

原2853文件基线，最终仅离线测试入口及HANDOFF两项授权文件修改，其余2851逐字保持；P3.6全部40请求/JSON/SQLite/Prompt/输入/配置/输出/旧24题裁决及锁账保持，143/168、17/24、29/32不变。.env仍旧API启用但未修改；没有邮件发送、自动复验或复用旧预算。

后续若保持当前口径，需要研究者明确决定复验范围，并实现保留原失败分母、独立复验身份及同一总预算约束。若修改Prompt，须新实验身份及共享本轮72/10总上限；不能重建新账本来重置额度。具体提案在本机失败归因包，不自动执行。
