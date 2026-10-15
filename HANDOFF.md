# HANDOFF — P2真实DeepSeek集成与受控试点完成

2026-10-15（Asia/Shanghai）；状态：**P2_ENGINEERING_VERIFIED / REAL_MODEL_PILOT_VERIFIED**。

- 已实现：Single Analysis显式选择offline_fake/legacy_mock/deepseek_live；AnalysisService接LangChain ChatOpenAI，冻结v2 Prompt、严格校验、分阶段原始/解析/规范结果、SQLite v2运行claim及attempt预写、有限重试、共享持久预算、失败/不确定状态、重启重读。
- 离线最终77/77通过（P1原52保持，P2新增25）。历史80仍494/560、66 mismatch、32/80全对；14张Dashboard表、18条mock的31 mismatch保持。262冻结资产hash不变。
- 真实试点12封/12请求（1冒烟+10语义+1实际app.py AppTest），12首轮accepted，0重试/失败/fallback；七字段83/84，11/12封全对。唯一差异是服务咨询product_category预期Service/Other、实际unknown；未改expected或Prompt。
- Token输入13242+输出2209=15451；按官方高峰缓存未命中估算0.044156元，实际账单unknown。provider调用p50/p95为2.020/7.975秒；逻辑编排区间2.111/8.063秒（n=12，不含起止数据库提交）；UI提交到渲染9.209秒（n=1）。不是生产SLO或独立人工准确率。
- 真实UI运行：`790173b1-f0b7-4df2-a48f-5cb786160d6d`，`p2-delivery-ui`。实际UI→DeepSeek→SQLite成功，新AppTest会话重读，重复点击2次仍只有12次总请求。AppTest不是浏览器E2E。
- 本机原始证据/预算/运行库：`.local/p2-pilot-v1/`；已停止新付费调用（halted=pilot_completed），保留结果重读。Prompt/base hash及fixture冻结清单在manifest，SDK版本与源码hash在preflight。返回模型deepseek-flash仅为alias，权重快照unavailable；request_id未返回。

## 开始下一轮

先读 [P2验证与交接](docs/p2/VERIFICATION.md)、[真实实验报告](docs/p2/LIVE_REPORT.md)、[bad case审阅](docs/p2/LIVE_REVIEW.md)、[复现说明](docs/p2/REPRODUCE.md)、[设计](docs/p2/DESIGN.md)、[可靠性边界](docs/p2/RELIABILITY.md)。P3/P4仍未实施，架构建议不等于新授权。

```powershell
.\.venv\Scripts\python.exe -B tests\run_offline.py
.\.venv\Scripts\python.exe -B scripts\verify_p2_assets.py
$env:COMPLAINT_ENABLE_LIVE = 'false'
$env:COMPLAINT_DB_PATH = 'D:\Projects\complaint_llm_system\.local\p2-pilot-v1\runs.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py
```

用Load saved run打开上面的run_id即可演示真实结果，无需重新付费。别运行旧历史API runner、删预算账本或重建Gold。正常tests仅离线，报告现在写docs/p2，旧P1报告不覆盖。

## Git与资产恢复

首次Git基线提交已尝试，但Git缺少作者身份，提交未产生，SHA unavailable。没有代填身份，也无push/tag/release/reset/clean。28个已审核P1工程文件仍暂存，P2工作树变更和新文件未提交，供人工review。初始安全快照`D:/TEMP/complaint_p2_baseline_0hxiqtuk`、基线范围和未跟踪资产清单见`docs/p2/evidence/baseline-start.json`；最新`change-ledger-*.json`给出前后hash。真实.env未修改，原实验数据/预测/Gold/P1证据保留。

## 后续优先级

先统一Service/Other与unknown边界及证据规则，再建立独立人工holdout和按版本隔离的source attribution统计；失败、unknown和warning分母分别显示并支持原文下钻。不将业务来源当因果或法律责任，不提前实施P4审核/发送。

---
以下保留P1历史交接，供兼容追溯；其中“P2尚未接入”等描述仅指P1结束时状态。

# HANDOFF — P1 可信评测、统一契约与离线纵切片

2026-10-15（Asia/Shanghai）；状态：**P1_ENGINEERING_VERIFIED**。
工作目录：`D:\Projects\complaint_llm_system`。方案 A、SQLite 单机新运行试点与 canonical 八类由本轮用户明确授权，已实际实施。未扩展到 P2 真实模型实验。

## 已实现与验证

- 共享七字段 offline evaluator：分别检查字段/ID/空值，拒绝重复与不完整覆盖，不再缩分母或缺字段自比较。I4E2 wrapper 复用核心；legacy smoke 显式六字段。
- F01–F06 均有测试与修复：严格 provider/v2 契约、八类 taxonomy+unknown、缺报告 unavailable、逐行批次 acceptance。
- `EmailInput / AnalysisResult / RunConfig / AnalysisRun / AnalysisAttempt / ErrorDTO`，input hash、backend/model/prompt/schema/taxonomy、原始/规范输出与阶段状态可追溯。
- `AnalysisService → Analyzer Protocol → OfflineFake / LegacyMock → Repository → SQLite`；服务不依赖 Streamlit、不加载模型配置。fake 始终标记 offline_fake，旧 mock 标记 legacy_mock。
- SQLite emails/runs/results/attempts 四表，同事务保存、FK、部分成功唯一索引、幂等复用、失败隔离、版本关联、新连接读取；无历史导入。
- 实际 `app.py` Single Analysis 已接线：保存、rerun/新session/run_id重读、门店/产品/状态筛选、单版本统计、成员ID下钻原文。四 tab/三个历史模式保留。
- 新批量 CSV 导出与示例生成写 `.local/` 下 UUID 路径，不覆盖旧 outputs 或 Gold。

最终测试 **52/52通过**（0失败/错误/跳过）：缺陷回归10、契约10、评测单元6、历史5、service/SQLite15、AppTest6。约19.21秒，见 [机器结果](docs/p1/evidence/test-results.json) / [完整日志](docs/p1/evidence/full-suite.txt)。测试入口阻断外部socket和冻结资产写入。93个Python文件内存编译通过，pip check正常。

历史仍为 **494/560、66 mismatch、32/80全对**；原400行标记/ID和14张聚合表一致；18条mock仍31 mismatch。没有真实模型调用，fake/AppTest通过不是模型语义准确率证明，也不是浏览器E2E。

## 开始使用与复验

```powershell
Set-Location D:\Projects\complaint_llm_system
.\.venv\Scripts\python.exe -B tests\run_offline.py
.\.venv\Scripts\python.exe -B scripts\verify_p1_assets.py
$env:COMPLAINT_DB_PATH = 'D:\Projects\complaint_llm_system\.local\runs.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py
```

Single Analysis 选择 offline_fake。使用 `[store:A] [negative]`、`[store:A] [positive]`、`[store:B] [neutral]` 和无store的`[neutral]`四封独立synthetic邮件，可验证 A 为1/2=50%；`[fail]`注入失败。fake是token演示协议，不是自然语言模型。保存后记录run_id，刷新或用Load saved run重读；统计选择同一source/version再Open member original。

完整步骤、正文、CLI见 [复现说明](docs/p1/REPRODUCE.md)。默认数据库`.local/runs.sqlite3`，测试临时库；实跑demo记录 [demo-run.json](docs/p1/evidence/demo-run.json)，临时库`D:\TEMP\complaint_p1_demo_m6t5ljyq\runs.sqlite3`保留供本机复查。

## 资产与恢复

原P0 manifest有401文件，包含本轮需修改的源码，不能要求401全不变。按冻结资产清单核对 **262文件原hash全部不变**；其余原文件也检查，只允许明确列出的源码/配置/文档修改。修改前后SHA-256、全部新增文件、保护检查见 [change-ledger.json](docs/p1/evidence/change-ledger.json)。

首次修改前源码/文档本地快照：`D:\TEMP\complaint_p1_recovery_onjain1l`，171文件；不含.env/key，未上传。基线清单见 [baseline.json](docs/p1/evidence/baseline.json)。没有修改Gold、历史outputs、原始论文资产或真实.env。

Git仍main、0 commits、无HEAD；没有commit/push/reset/clean/tag/release。数据库与旁文件被忽略。不要用git reset/clean处理当前未跟踪成果。AGENTS.md规则未变，不新增Skill。

## 文档与实现入口

- [P1验证与缺陷证据](docs/p1/VERIFICATION.md)
- [契约Spec](docs/p1/CONTRACT_SPEC.md) / [JSON Schema](docs/p1/analysis-v2.schema.json)
- [SQLite模型与迁移边界](docs/p1/SQLITE_STORAGE.md)
- [原审计及P1状态更新](docs/audit/2026-10-14-legacy-audit.md)
- [方案A接受记录](docs/architecture/2026-10-14-architecture-options.md)
- [路线与P2输入](docs/plans/PHASED_ROADMAP.md)

实现从`src/domain/contracts.py`、`src/application/analysis_service.py`、`src/application/analyzers.py`、`src/infrastructure/repository.py`、`src/app/offline_slice.py`、`src/evaluation/core.py`进入。tests/test_*.py是标准离线测试；历史API/validate脚本不要当成普通测试全库运行。

## P2剩余输入与风险

1. 新服务仅支持analysis-v2/research-products-v2；歧义legacy类别映射unknown并保留warning/raw，不能把改变分类口径当作能力提高。
2. 旧80是回归/历史参考，review是辅助来源，不能宣称独立holdout。新holdout须模板/近重复分组隔离、独立标注与冻结hash。
3. 下一步可先用fake验证DeepSeek adapter的deadline、预算、重试、错误分类、request_id/usage；真实调用须单独明确模型/样本/最大次数/费用/数据范围授权。
4. SQLite仅单机试点；当前同步终态持久化不保证硬中断前attempt留痕，无后台恢复/生产权限/负载验证。并发唯一性通过不代表模型调用恰好一次。
5. AppTest不是浏览器E2E；上传下载完整流程、真实模型质量/成本/延迟、CI和依赖锁仍待后续。旧CLI main固定输出路径仍保留，不能用于未经隔离的历史重跑。
6. 没有真实API、LangSmith上传、SMTP或邮件发送，也没有新增这类默认功能。
