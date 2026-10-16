# P3.8离线复验与人工入口

使用已有venv；默认不调用模型、不发送邮件。不要直接运行历史API脚本。完整研究原文/参考/SQLite/账本仍仅保留本机。

```powershell
.\.venv\Scripts\python.exe -B tests/run_offline.py
.\.venv\Scripts\python.exe -B scripts/run_portable.py
# 每次选择一个未存在的新目录，不能覆盖冻结包
.\.venv\Scripts\python.exe -B scripts/p38.py prepare --out .local/p38/NEW_PREPARATION
.\.venv\Scripts\python.exe -B scripts/p38.py preflight --manifest .local/p38/NEW_PREPARATION/ab-manifest.json
.\.venv\Scripts\python.exe -B scripts/p38.py rehearse --manifest .local/p38/NEW_PREPARATION/ab-manifest.json --out .local/p38/NEW_OFFLINE_REHEARSAL
.\.venv\Scripts\python.exe -B scripts/p38.py demo --out .local/p38/NEW_DEMO
```

prepare创建政策、183版本历史快照、159自然导入视图、32回执、泄漏组件、24内容审核、历史审计、32输入白名单、两个Prompt、配置、64步骤和零授权预检；所有输出排他创建。rehearse通过正式service和新SQLite执行64个明确fake占位结果，只证明接线；不报告模型准确率，不创建真实预算。evaluate对实际未来运行保留32/arm分母；旧参考通过完整源记录hash绑定，七字段仅旧开发一致性，新政策/内容评分pending。

本机最终包为`.local/p38/prepared-final-v4`。UI启动前显式关闭API与追踪，并使用新数据库：

```powershell
$env:LLM_ENABLE_API='false'
$env:COMPLAINT_ENABLE_LIVE='false'
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:COMPLAINT_P38_PREPARED='D:\Projects\complaint_llm_system\.local\p38\prepared-final-v4'
$env:COMPLAINT_V31_DB_PATH='D:\Projects\complaint_llm_system\.local\p38\NEW_UI\runs.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Single Analysis → P3.8：可存三Issue明确fixture、按run_id/刷新重读、查看1封/3问题分母、四个数据队列和父版本；24内容审核区显示旧v3原文/原始或独立派生视图、18维候选意见和证据，下载unsigned审核草稿。AI不能签署人类评分。

实际`.env`原有LLM_ENABLE_API=true未改。离线CLI及测试显式禁网/禁API；不依赖.env默认值。旧P3.6数据库只读审核，已锁预算不复用。

未来真实执行条件见[AB_PLAN](AB_PLAN.md)。现在没有任何新真实调用授权。
