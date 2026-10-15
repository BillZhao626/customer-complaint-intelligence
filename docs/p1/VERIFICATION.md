# P1 验证记录

日期：2026-10-15（Asia/Shanghai）。状态：**P1_ENGINEERING_VERIFIED**，仅表示本轮授权的离线工程门槛通过。

## 执行证据

修改前已读取 P0 的 401 文件 manifest、验证 262 个受保护资产，并在 `D:\TEMP\complaint_p1_recovery_onjain1l` 保存可能修改的源码/文档快照（171 文件，排除密钥）。明细为 `evidence/baseline.json`。

首次 tests-first：`evidence/initial-red.txt`，10 项中 8 个断言失败、2 个错误。断言覆盖旧缺字段自比较、重复 ID、宽松 provider/bool、缺报告硬编码成绩及混后端验收；两个错误分别为新 coverage 字段尚不存在、新 canonical 模块尚不存在。不是把这轮失败记为产品通过。修复后同组 10/10（`regressions-green.txt`）。

随后发现默认七字段对旧 smoke runner 的兼容影响，先补 `test_legacy_smoke_report_explicit_six_field_compatibility`，记录缺 source_attribution 的失败（`compatibility-red.txt`），再修为显式六字段并统一 mismatch 核心，未修改其参考标签。

最终运行：`.\.venv\Scripts\python.exe -B tests\run_offline.py`，**52/52 通过，0 failure、0 error、0 skipped**，约 19.21 秒。机器结果与完整测试 ID：`evidence/test-results.json`；控制台：`evidence/full-suite.txt`。数值为测试方法数，参数化 subTest 边界不另虚增计数。

| 分组 | 方法数 | 结果 |
|---|---:|---|
| F01–F06 初始回归 | 10 | 10/10 |
| 契约、taxonomy、input/hash | 10 | 10/10 |
| 评测边界单元 | 6 | 6/6 |
| 历史回归 | 5 | 5/5 |
| Service / Repository 集成 | 15 | 15/15 |
| Streamlit AppTest | 6 | 6/6 |

测试套件同时关闭 API/tracing，阻断 socket 连接，对冻结目录写入设置 audit hook。数据库均在 TemporaryDirectory；报告缺失用读函数注入，不改名/移动真实历史文件。AppTest 的 bare-context warning 是框架提示，最终 exception 列表均为空。

其他验证：93 个 Python 文件内存 compile 无语法错误；pip check 无依赖冲突；单独 CLI `run_offline_demo.py` 保存并由新连接读出 4 succeeded / 1 failed，A=1/2=0.5，记录在 `evidence/demo-run.json`。这些不解释为真实模型质量通过。

## 六项缺陷与实现

| 缺陷 | 实际修复 | 验收断言 |
|---|---|---|
| F01 | core.index_rows 在比较前验证每侧字段、空白/None/NaN/pandas NA/非法非标量 | 缺 Gold、缺预测、双方都缺值均不能得分 |
| F02 | 唯一 ID 校验；missing/extra/expected/matched/coverage；invalid 无指标；I4E2 使用共享核心 | 2×2 重复被拒；Gold80/Pred79 输出 expected80/matched79/coverage79/80 且无分数；extra 拒绝 |
| F03 | LegacyProviderResult 先于 `_prepare_llm_payload` 默认值；v2 严格模型；服务保存分阶段状态 | 空对象、数组、字段缺失、非法 bool/enum/type 失败；原 JSON 与 normalized 分开；业务矛盾 warning |
| F04 | research-products-v2 实际八类 + unknown；精确同名旧类别保留，歧义类别显式 unknown+warning | 完整标签集合核对；Other 与 Service/Other、unknown 区分；旧80 raw不变 |
| F05 | validate_summary 校验七字段定义/计数/精度/有限值/运行计数；UI 无硬编码成绩回退 | AppTest 缺文件、读权限异常、坏 JSON、坏结构均 unavailable；有效报告显示解析值 |
| F06 | 所有行逐一检查 backend/API/parse/schema/status/error；无失败、唯一且固定输入 ID 完全匹配才 accepted | 399 DeepSeek+1 fallback 不 accepted；各类坏 flags/status/error/ID 拒绝；真实留存400通过只读复核 |

## 纵切片与存储

实际入口 `app.py` 的 Single Analysis 调用 service，不是仅测试 service 函数。AppTest 输入独立 synthetic fixture，提交、重复提交、普通 rerun、新 AppTest session 输入 run_id、URL run_id 恢复、门店/产品/状态过滤、统计分子分母、unknown、成员下钻原文均通过；四 tab 与三种历史 Dashboard 模式保留。

SQLite 四表：emails/runs/results/attempts。事务覆盖原文、运行、结果、attempt；在 attempt 插入时触发故障后四表全部为零。FK、attempt 主键、成功幂等部分唯一索引、四线程竞争、配置/输入绑定拒绝篡改、不同输入/Prompt产生不同run、跨配置聚合隔离、失败重试保存不同run均有断言。

统计来源仅选定 cohort 的 succeeded run；A 门店四样本中的两条为 1 negative / 2 total，B 为 0/1，unknown 为 0/1。返回全部/负面成员 run_id 并读取完整原文。失败样本不进入成功统计。不同 input 内容版本是不同运行成员，UI/Spec 明示，未悄悄当成最新邮件去重。

## 历史与数据保护

- 旧80：七字段正确 494/560=88.2142857%，66 mismatch，邮件七字段全对 32/80。各字段 weighted P/R/F1、support、mismatch 与原报告在 1e-10 内一致。
- 旧400：输入 ID 与历史预测完整一致，逐行历史 DeepSeek/API/parse/schema 标记可复核，失败文件0行；没有重建过去的请求或 usage。
- 原14张 Dashboard 表计数、比率和百分比一致。
- 原18条 mock smoke 保持 31 mismatch（77/108），未调整标签或口径消除差异。
- 262 个受保护资产原 SHA-256 全部不变；还检查其余 P0 原始文件，仅允许明确列出的源码/配置/文档变更。完整结果、修改前后 hash、新增文件见 `evidence/change-ledger.json`。台账自身不作递归自摘要。
- 源码备份未上传；没有 commit/push/reset/clean/tag/release。Git 仍 main、0 commits、无可解析 HEAD。实际 `.env` 未修改，未打印 key。

## 变更范围与限制

修改旧文件：app.py、.gitignore、langchain_complaint_chain.py、evaluate_results.py、run_i4e2_reviewed_80_eval_v1.py、run_i4g_full_pool_deepseek_batch_v1.py、run_smoke_test_v1.py、HANDOFF.md、原审计/架构/路线三份文档。完整相对路径与摘要以台账为准。

新增业务：domain/contracts.py、application/analyzers.py、application/analysis_service.py、infrastructure/repository.py、app/offline_slice.py、evaluation/core.py；新增 tests、两个离线脚本、P1 Spec/存储/复现/验证文档及证据。未增加第三方依赖、HTTP服务、审核/发送表或后续阶段空骨架。

真实浏览器 E2E、上传下载全流程、真实模型结构化成功率/语义/延迟/Token/费用、独立人工盲标仍未验证。SQLite仅单机试点，异常捕获后有失败记录，但进程硬中断前尚未提交的尝试不具备持久恢复。legacy CLI 的固定输出 main 仍作为历史入口保留，本轮没有运行；新运行应使用 service/新demo脚本。CI与依赖锁未实施。

## P2 明确输入

使用本轮严格契约、Analyzer Protocol、Repository、独立阶段状态和版本键作为起点；旧80仅作固定回归。下一步先离线验证 provider deadline、重试预算、429/5xx/timeout、request_id/usage 缺失与错误分类，再提出真实调用模型/样本/最大调用数/费用/数据范围供授权。新 holdout 的分组划分、近重复/模板隔离、独立标注和冻结 hash 需单独建立；不能借 taxonomy 变化宣称模型改善。
