# Customer Complaint Intelligence

**当前版本：P4 Final / P5 Preflight 产品候选版。** 已实现邮件/历史真实run → Issue与Evidence → 未审草稿 → 编辑版本/diff → 本地人工批准、退回或拒绝 → 模拟发送 → SQLite历史重读及分版本Dashboard。五项研究者政策有独立诊断层，严重分析错误不可用批准绕过。UI强制禁用付费API，真实SMTP/CRM没有接入。

最新 [最终研究者审核包](docs/p4/FINAL_READINESS.md) 包含离线真实 SDK 接线、浏览器验收、历史成绩单和 P5 独立质量认证提案。新付费调用未启用，独立质量认证仍 pending。

从 [P4交付入口](docs/p4/DELIVERY.md)、[演示说明](docs/p4/DEMO.md)、[系统设计](docs/p4/ARCHITECTURE.md) 开始。旧实验和下文阶段描述作为历史保留；“没有批准流程”等旧结论已由P4工作流更新。模型独立质量认证仍pending，P3.10失败Challenger未晋升，旧400封始终是确定性模板生成。

P3.5已新增向后兼容的Analysis-v3多问题契约、明确有损的v2投影、问题/邮件分母分离及离线评测。Single Analysis中的P3.5工作区可运行公开双问题fixture；本地候选审核入口读取`COMPLAINT_V3_CANDIDATES`。完整验证和限制见[本轮交接](docs/p35/VERIFICATION.md)：本机154/154、portable67/67；真实v3模型质量仍pending。24条最终开发裁决及172条候选记录（160适用、12隔离）保存在本地，不随仓库公开。

客户投诉分析研究原型，使用 Streamlit + Python Application Service + SQLite。提供显式 Offline Fake / Legacy Mock / DeepSeek 分析、七字段分类、摘要、未审核回复草稿、版本化保存、来源归属 Dashboard 和原文追溯。

**研究边界：** P2 的 12 条是开发者合成案例，83/84 = **98.81% 字段参考匹配率**（12封 × 7字段），11/12 邮件七字段全对；不是独立人工泛化准确率。旧 400 条由固定模板程序生成，不能支持真实市场或门店排名。Human Gold 仍为 **HUMAN_GOLD_PENDING**，摘要/回复人工审核未完成；没有批准或发送流程。服务类别新 Prompt 只有离线规则证据，**REAL_MODEL_FIX_PENDING**。

P3 已实现来源/模型/Prompt/schema/taxonomy 隔离、时间和门店/产品/情绪/运行状态筛选、投诉/负面/归属分布、门店×产品交叉统计、unknown/unclear/none/unavailable/failed/fallback 区分，以及统计成员→原文/分析详情下钻。业务来源归属不是已证实因果或法律责任；原因描述投诉内容，渠道描述联系途径，三者不能互换。v2 未保存联系渠道，显示 unavailable。

## 安装与安全离线 Demo

Python 3.12；直接依赖固定为验收版本。建议新建虚拟环境。安装依赖需要访问包仓库，测试与 demo 不请求模型。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -B scripts/run_portable.py
# --out 必须不存在，不覆盖任何旧运行
.\.venv\Scripts\python.exe -B scripts/p3_demo.py --out .local/p3-demo-v1
$env:LLM_ENABLE_API = 'false'
$env:COMPLAINT_ENABLE_LIVE = 'false'
$env:LANGSMITH_TRACING = 'false'
$env:LANGCHAIN_TRACING_V2 = 'false'
$env:LANGCHAIN_TRACING = 'false'
$env:COMPLAINT_DB_PATH = '.local/p3-demo-v1/runs.sqlite3'
$env:COMPLAINT_DATASET_MANIFEST = '.local/p3-demo-v1/dataset.json'
.\.venv\Scripts\python.exe -m streamlit run app.py --browser.gatherUsageStats false
```

打开 **Dashboard → P3 versioned attribution → Configured SQLite runs**。选择模型/实验版本，再选门店、产品、情绪和时间。选择 Breakdown 查看类别或交叉表；在 Statistic to inspect 选择统计项、Numerator/Denominator 成员，再点 Open original and analysis。Download statistics and member IDs 导出绑定版本、分母和成员ID的 JSON。原三个历史模式仍在 Historical dashboards。

10条公开 demo 是 `src/evaluation/p3_fixture.py` 的显式合成验收表：7成功、1失败、1fallback、1不确定；含一个故意设置的归属差异，用于验证比较器。它不是模型质量实验或人工 Gold。原文、P2.5 Sample manifest、input hash、run ID、版本和输出 hash 写入新目录。CLI 无付费模式。普通 Single Analysis 的 Offline Fake 只识别演示 token，不是自然语言模型。绑定 demo manifest 时只接受其样本；分析其他邮件请使用另一个新数据库并取消该 manifest 设置。

本机拥有 P2 结果时可选 **P2 saved synthetic DeepSeek results**；该入口只读 `.local/p2-pilot-v1/run-*.json`，不打开旧 SQLite、重跑模型或重建账本。远程干净检出没有这些研究资产，会显示不可用。不要为了查看 P2 把可写 Single Analysis 数据库指向历史库。

## 统计解释

计数单位是同一 cohort、时间区间内每个 `email_id + input_hash` 的最新运行，即邮件修订版。重试不会重复计入；修改正文会形成不同修订版，不等同于独立消费者数。

|分母|适用指标|
|---|---|
|全部所选邮件修订版|邮件数量、成功数、投诉/负面全邮件比例、失败与fallback状态|
|成功且无fallback|投诉/负面成功比例、门店/产品/交叉分布、unknown桶|
|投诉邮件|主要原因、来源归属分布、有效归属覆盖|
|有效业务归属|投诉中五个具体业务类别的分布，不含unknown/unclear/none|

每项携带分子、分母名称、过滤条件和双方成员ID。零分母为 null / unavailable。业务字段筛选会排除没有结果的邮件；界面同时展示筛选前状态和排除数量。没有 manifest 的数据库明确标记 unregistered，不能被当成已核实研究数据集。门店按保存值精确分组，无未经审定的别名合并。

## 代码与验证

|目录/入口|用途|
|---|---|
|app.py、src/app/|四tab界面、P3过滤与下钻|
|src/application/|分析服务、确定性 AttributionService|
|src/domain/contracts.py|冻结 analysis-v2 / research-products-v2|
|src/infrastructure/|provider、SQLite、只读数据适配器|
|src/evaluation/|统一分层评价、P3参考差异、人工协议|
|scripts/p3_demo.py|新目录离线fixture与评价|
|scripts/p3_calibration.py|本机24条双人独立校准包|
|tests/、.github/workflows/offline.yml|阻断外部socket的便携工程CI|

完整本机回归包含历史资产复算；公开检出只运行自包含 portable 套件，不伪称拥有原始研究数据。P3 浏览器范围为离线 Dashboard 筛选、失败/空分母、下钻和保存结果读取/下载；完整上传→模型→审批→发送链路未验证，AppTest 不替代浏览器。

```powershell
# 仅原本机具有完整历史资产时
python -B tests/run_offline.py
```

`data/`、`outputs/`、`.local/`、论文/学校材料、原始模型返回、预算库、真实 `.env` 不上传。旧历史 API runner 可能付费且使用固定输出位置，不能当测试运行。新付费调用需单独授权。

自有源码采用 [MIT](LICENSE)，第三方依赖保留其各自许可；[许可范围](docs/p3/LICENSING.md)。工程及研究状态见 [P3 验证](docs/p3/VERIFICATION.md)、[公开审计](docs/p3/PUBLIC_RELEASE.md)、[语义与分母](docs/p3/DESIGN.md)、[P2.5 人工指南](docs/p25/ANNOTATION_GUIDE.md)；下一轮从 [HANDOFF](HANDOFF.md) 恢复。
