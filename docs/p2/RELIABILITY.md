# P2 调用治理和存储边界

一次逻辑运行对应一个稳定输入及配置。最多两次应用层尝试，SDK重试为0；网络退避与JSON修复共用两次额度。本轮全局20次预留、12个输入、20元、一个lease。开始attempt及预算预留在请求前分别提交；两个SQLite文件没有跨库原子事务，任何缝隙失败均保守占用预算、保留claim，不自动重发。

服务路径：AnalysisService.analyze → live_execution → Repository.claim_live → PilotBudget lease → attempts(prepared/started_or_unknown) → DeepSeekAnalyzer.request → LangChain ChatOpenAI.ainvoke → OpenAI SDK Chat Completions → strict_json → AnalysisResult → identity normalization → business_warnings → attempts终态 → results/runs终态事务 → 新连接重读 → UI。

| 分类 | 行为 |
|---|---|
| configuration_error | 开关、Key、端点、模型、参数、tracing、白名单、预算或版本不匹配；不发请求 |
| authentication_error | 401/403，不重试，暂停整个pilot |
| rate_limited / provider_5xx | 显式429/5xx响应，有额度时退避0.5秒后再尝试一次 |
| timeout / network_error | 客户端无法确认服务端处理情况；interrupted_or_unknown，保留lease，不重放 |
| empty_response / invalid_json / raw_schema_invalid | 至多一次格式修复，与网络重试共享总额度 |
| normalization_failed | 独立规范化阶段失败；无默认值补齐，无fallback |
| semantic_warning | 结构合法但字段关系值得复核，保持warning，不当作语义正确证明 |
| storage_error | 不显示成功凭据；已写入的claim/attempt保留，不能写回时保留running与lease |
| interrupted_or_unknown | 重启后超过120秒的running标记不确定，保留attempt；不解锁、不自动调用 |

HTTP transport timeout为45秒；每次await同时受剩余逻辑deadline约束，逻辑预算90秒（包含provider准备、重试等待，不包含最初SQLite claim和最后终态落盘的阻塞时间）。超时取消客户端await不表示撤销服务端处理。普通调用异常只保存固定错误类型，不保存异常正文/Key。原邮件和模型原文是本机运行数据，不是脱敏后的通用日志。

P1 AnalysisResult不变；v2表迁移前使用SQLite backup创建旁路备份，新增execution_state/metadata_json和live唯一claim索引，不修改历史CSV。原status列保留原CHECK，非终态内部以failed占位；读取必须使用Repository或execution_state，不能对旧status列直接统计。所有正式统计使用DTO的succeeded并按cohort隔离。

相同email_id+input_hash+完整配置的live记录覆盖成功、失败和不确定状态，任何重复点击复用它。不同输入/版本是新请求，仍受全局预算限制。没有外部API exactly-once保证；即使服务端已计费、本机未收到或未落盘，也不会自动再次请求。单机同步试点，不提供多机调度、分布式锁或后台恢复。

raw_output、parsed_output、规范结果、各阶段状态独立留存。原始JSON拒绝额外文本、重复键、NaN、空对象/数组/缺字段、错误bool/enum/type。规范化不填缺失字段。usage、request_id、resolved model、成本缺失为null/unavailable；历史P1记录新增字段保持默认缺失，不伪造过去调用元数据。
