# P1 离线复现

工作目录：`D:\Projects\complaint_llm_system`。复用现有 Python 3.12 虚拟环境；本轮未升级依赖。包版本见 `evidence/environment.json`。全部命令无需 API key。

## 回归与保护

```powershell
Set-Location D:\Projects\complaint_llm_system
.\.venv\Scripts\python.exe -B tests\run_offline.py
.\.venv\Scripts\python.exe -B scripts\verify_p1_assets.py
.\.venv\Scripts\python.exe -B -m pip check
```

测试 runner 仅发现 tests/test_*.py，强制关闭 API/tracing、阻断 socket 连接、拒绝冻结目录的写入。请勿全仓库收集旧 test/validate 脚本；其中有真实 API 入口或历史报告写入。测试重跑会更新本轮 `test-results.json`，随后重跑资产检查以刷新本轮新增文件摘要。

## 实际 Single Analysis 页面

```powershell
$env:COMPLAINT_DB_PATH = 'D:\Projects\complaint_llm_system\.local\runs.sqlite3'
$env:LLM_ENABLE_API = 'false'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGSMITH_TRACING = 'false'
.\.venv\Scripts\python.exe -B -m streamlit run app.py
```

1. 在 Single Analysis，Analyzer 显示并选中 offline_fake；页面显示 Offline Fake / Demo。填写稳定 Email ID、synthetic subject/body，点击 Analyze email。
2. 分别输入下表四封邮件。fake 只识别展示用 token，不做自然语言语义分析。
3. 页面显示 run_id、backend、状态、原文、hash、版本、结果及验证阶段。重复相同提交复用同一成功 run。
4. 普通 rerun 保留结果；刷新浏览器保留 URL run_id。关闭后重新打开时可保留带参数 URL，或在 Run ID to reopen 输入 ID 并 Load saved run。
5. Saved runs 选择单一 Run source / version。Store filter 选 A：numerator=1、denominator=2、negative_rate=0.5。Statistic dimension 可选产品；unknown 门店独立显示。
6. Members 选 negative numerator members，再 Open member original，读取该 run 对应的原邮件与版本。Run status=failed 只看失败记录，不显示成功统计。

| Email ID | Subject | Customer email | 独立预期 |
|---|---|---|---|
| demo-A-negative | Synthetic A complaint | [store:A] [negative] Synthetic: headphones broke. | A / negative / complaint |
| demo-A-positive | Synthetic A thanks | [store:A] [positive] Synthetic: thank you. | A / positive / non-complaint |
| demo-B-neutral | Synthetic B inquiry | [store:B] [neutral] Synthetic: opening hours? | B / neutral / non-complaint |
| demo-unknown | Synthetic unknown | [neutral] Synthetic: store unspecified. | unknown / neutral / non-complaint |
| demo-failed | Synthetic failure | [fail] | failed，保存错误，不计入成功统计 |

空正文点击分析应报 Invalid input，且不创建运行。存储不可用或事务失败应报 Storage unavailable / Save failed，不显示新成功。使用全新专用数据库获得恰好四个成功样本的 50% 演示；已有库如含其他成功输入会按实际成员改变分母。

## CLI 重现同一服务

```powershell
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --db .local\repro-demo.sqlite3
```

输出配置、run IDs 和聚合。相同成功输入幂等，失败输入每次产生新的可追踪失败尝试。该命令只构造 OfflineFake，不读取 `.env` 或导入模型配置。实跑凭据见 `evidence/demo-run.json`；其临时 SQLite 路径保留以便当前机器复查，不属于可移植研究资产。

## 兼容范围

保留四个 tab 和三个历史 Dashboard 模式。历史报告缺失、不可读、JSON 错误或校验不通过显示 unavailable；I4E3 摘要不会被用作缺失正式报告的替代成绩。旧批量 mock 的新 CSV 导出保存到 `.local/exports/<UUID>-...csv`，示例生成保存到 `.local/samples/<UUID>/`；不会写旧 outputs/batch_results.csv 或旧 Gold。生成的示例标签由 mock 产生，只能作为自一致性演示。

AppTest 已验证实际 app.py 入口、交互、持久化与下钻，但不属于真实浏览器 E2E；上传/下载完整交互、生产并发、真实 DeepSeek 语义/延迟/成本均未验证。不要运行历史 API runner main 来“补验收”。
