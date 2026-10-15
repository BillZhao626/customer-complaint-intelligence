# P2 配置与复现

本轮仅允许已冻结的12封合成邮件，最多20次请求、20元人民币、串行执行。`.env` 未修改；旧 `LLM_ENABLE_API=true` 本身不会启用新入口。旧历史 CLI 入口保持原样，不用于本轮复现。

## 离线复验

```powershell
Set-Location D:\Projects\complaint_llm_system
.\.venv\Scripts\python.exe -B tests\run_offline.py
.\.venv\Scripts\python.exe -B -m pip check
```

runner 只发现 tests/test_*.py，显式禁用新旧API开关和 tracing，阻断外部同步/async连接。Windows仅允许标准库 socketpair 创建 asyncio 的本机唤醒通道。报告写 docs/p2/evidence/test-results.json；不会覆盖 P1 报告。`test_live.py` 是离线 fake/MockTransport 测试，真实调用仅在手工运行的 `scripts/p2_pilot.py` 中。

## 安全演示现有真实结果

```powershell
$env:COMPLAINT_ENABLE_LIVE = 'false'
$env:COMPLAINT_DB_PATH = 'D:\Projects\complaint_llm_system\.local\p2-pilot-v1\runs.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py
```

默认 offline_fake。用交接文档中的真实 run_id 执行 Load saved run，或选择已保存的 deepseek_live cohort，从统计成员读取原文。无需 API 开关即可重读真实结果。Suggested reply 始终是未审核、未发送草稿。

## 本轮授权内的真实入口

```powershell
$env:COMPLAINT_ENABLE_LIVE = 'true'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
$env:LANGCHAIN_TRACING = 'false'
$env:COMPLAINT_DB_PATH = 'D:\Projects\complaint_llm_system\.local\p2-pilot-v1\runs.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py
```

Single Analysis 选择 deepseek_live；填写 `tests/fixtures/p2_pilot_v1.json` 中完整、原样的 email_id/subject/body。服务端白名单按 subject/body hash 验证，非授权输入不会发往 API。已成功、失败或不确定的相同运行不自动重放。不要换 email_id 绕过复用来重复付费。

新入口仅接受官方 `https://api.deepseek.com/chat/completions`、`deepseek-flash`，非思考模式、temperature=0、JSON object、最多1800输出Token。客户端关闭重定向、环境代理和 SDK 重试；不更改用户全局环境/代理配置。

本轮执行命令（已经执行的阶段无需再发请求）：

```powershell
.\.venv\Scripts\python.exe -B scripts\p2_pilot.py prepare
.\.venv\Scripts\python.exe -B scripts\p2_pilot.py smoke
.\.venv\Scripts\python.exe -B scripts\p2_pilot.py semantic
.\.venv\Scripts\python.exe -B scripts\p2_pilot.py ui
.\.venv\Scripts\python.exe -B scripts\p2_pilot.py report
```

prepare 使用排他创建，已有预算账本会拒绝重建；不要删除或另建账本绕过20次总限额。report 只读运行记录，产生带时间版本的新报告目录。UI 阶段为实际 app.py 的 AppTest，不是浏览器E2E。全部阶段共享 `.local/p2-pilot-v1/budget.sqlite3`。

本轮已完成12封/12次调用，账本已标记pilot_completed，以上smoke/semantic/ui命令现在会报告已停止。既有结果重读和同配置同输入的幂等复用继续可用；新付费实验需要另行明确授权，不能通过删账本消耗剩余额度。

认证失败会永久暂停该试点；超时、断网或进程硬中断会保留 lease，禁止继续付费调用。当前没有自动解锁/重试命令；先人工核对提供方记录、已用预算和未知请求，再决定另一个明确授权的实验。仅退款/解锁本地计数不能证明服务端未计费。

## 计价与版本边界

2026-10-15核对[官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：Flash高峰输入缓存未命中2元/百万Token，输出8元/百万Token；成本统一按这个上界估算，实际扣费 unknown。预算预留使用消息 UTF-8 字节数加1024开销余量，以及最大输出Token；消息最大20000字节、输出最大2000。每次请求预留永不退款；缺usage不记0。

官方[非思考参数](https://api-docs.deepseek.com/guides/thinking_mode/)为 thinking.type=disabled。[JSON模式](https://api-docs.deepseek.com/guides/json_mode/)指定response_format和max_tokens。安装的langchain-openai 1.2.1会重命名max_tokens，适配器只在请求序列化处改回官方字段，已有HTTP MockTransport契约测试。升级SDK后必须复验该边界。

返回模型名只作resolved_model；权重快照 unavailable。冻结文件记录实际Prompt/hash、Schema/taxonomy、包版本、价格来源和预期。修复请求另记实际系统Prompt hash。后续价格变化或新实验需重新核查，不能把本轮预算视为长期付费授权。
