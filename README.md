# Customer Complaint Intelligence

Streamlit 客户投诉分析研究原型。当前为 P2 + P2.5 评价基础版本：单封邮件校验、显式 fake/mock/DeepSeek 分析、结构化结果、摘要与未审核回复草稿、SQLite 运行保存及重读、按版本隔离的门店/产品统计与原文下钻。历史批量和三类 Dashboard 页面保留。

P2 真实试点是 12 条开发者合成案例：83/84 字段匹配、11/12 邮件七字段全对；不是独立人工准确率或泛化证明。摘要与回复未获独立人工认证。AppTest 不是浏览器 E2E。P3 完整归因 Dashboard、P4 审核和模拟发送尚未实施。

## 离线运行

使用 Python 3.12（本机验证 3.12.8）及 requirements.txt。依赖未锁定，干净检出验证使用本机现有依赖，不代表全新依赖安装验证。

```powershell
python -m pip install -r requirements.txt
python -B scripts/run_portable.py
$env:COMPLAINT_ENABLE_LIVE = 'false'
$env:LLM_ENABLE_API = 'false'
python -m streamlit run app.py
```

默认 Offline Fake 使用显式演示 token，不是自然语言模型。回复是草稿，未发送。历史 API runner 有固定路径及付费副作用，不要当普通测试运行。新模型调用需要独立预算授权。

## 本机历史资产与测试

Git 只保存经过审核的工程文件及安全 fixture。data/raw、data/synthetic、data/golden、outputs、docs/dissertation、.local、原始模型返回和预算数据库保留本机，不随仓库上传。没有确认对历史研究材料的外部披露权属，Private 不替代审核。

完整历史回归需要原始 400 邮件、18 条 smoke、旧 80 参考/预测、14 张 Dashboard 表，以及本机 docs/p1/evidence 和 docs/p2/evidence。完整资产范围由本机冻结 hash 清单定义。缺资产时不宣称完整历史测试通过；可移植 smoke 仅用 tests 内自带合成 fixture。

```powershell
# 显式 pattern 避免旧 runner 重写历史 P2 报告
python -B tests/run_offline.py "test_*.py"
```

历史累计 README 的本机副本保存在 .local/p25/README.pre-p25.md 及修改前恢复快照。工程契约见 docs/p1/CONTRACT_SPEC.md，P2 调用边界见 docs/p2/RELIABILITY.md；后续工作从 HANDOFF.md 开始。没有发布许可声明；第三方依赖遵循各自许可。

## P2.5 评价基础

已完成400条模板合成数据审计、统一端到端评价Schema、离线Application Service/历史run重放、七字段与生成内容/业务统计分层指标、130条人工标注候选、双评审/仲裁/冻结工具，以及独立版本的服务类别Prompt候选。完整108项离线测试通过；可移植套件包含28项，无需历史资产。人工Gold、摘要/回复人工评价、新Prompt真实模型验证、独立holdout和浏览器E2E仍pending。

```powershell
python -B tests/run_offline.py
python -B scripts/p25.py offline --dataset tests/fixtures/p25_portable_v1.json --out .local/my-new-evaluation
```

详见[本轮验证](docs/p25/VERIFICATION.md)、[400条数据审计](docs/p25/DATASET_QUALITY_AUDIT.md)、[端到端能力矩阵](docs/p25/E2E_COVERAGE_MATRIX.md)、[评价协议](docs/p25/EVALUATION_PROTOCOL.md)、[人工标注指南](docs/p25/ANNOTATION_GUIDE.md)和[Git/GitHub审核](docs/p25/GIT_AND_GITHUB_REPORT.md)。所有新报告写新目录；旧P2原始证据保留本机。
