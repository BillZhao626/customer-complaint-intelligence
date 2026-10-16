# HANDOFF — P3.8 Research Policy v2 / v3.1 / Dataset Adoption

2026-10-16（Asia/Shanghai）。先读 `docs/p38/VERIFICATION.md`、`COMPATIBILITY.md`、`AB_PLAN.md`、`REPRODUCE.md`。完整研究材料在 `.local/p38/REPORT.md`；本轮新真实模型请求0次、费用0元。

- POLICY_V2_OWNER_APPROVED / SCHEMA_EVOLUTION_VERIFIED：研究者八项未来政策已冻结；analysis-v3.1 / complaint-issues-v3.1使用独立RunConfigV31，原v3源码、严格安全规则和导出Schema不变。严重潜在伤害high，普通抽屉碰撞可medium；风险/紧急度证据、客户主次/业务顺序分离，发票客服协调与有损投影有诊断。
- DATASET_ADOPTION_VERIFIED：最终 `.local/p38/prepared-final-v4/`，183历史版本、172当前，159自然/1对抗/12质量隔离，11旧文superseded保留；20保留、11获批改写、P35-073隔离，32回执，128自然质量待审。所有159自然候选逐项人工语义审核pending；质量采用不是Gold。原12隔离和11旧文均可读。
- E2E_OFFLINE_VERIFIED：最终247/247本机、153/153 portable，旧200/110测试ID保留；64/64明确fake流程演练，正式service→SQLite→重读，实际浏览器验证1邮件/3Issue、风险medium、发票customer_support、未核实责任、刷新/幂等、隔离队列和unsigned下载。fake不证明模型理解正确。
- HUMAN_CONTENT_REVIEW_PENDING：22成功×18维AI意见及引用、2失败单列。审核入口Single Analysis→P3.8；本机 `CONTENT_REVIEW24_V2.md`、`prepared-final-v4/semantic-review-v2.json`，真人分数/关键错误确认仍null。11改写逐条语义比较在 `ADOPTION11.md`，不继承旧参考或预测。
- 原P3.6 40次原始JSON/SQLite/Prompt/input/config/output/预算只读复验；锁止authorization_limit，143/168、17/24、29/32及24题v1.1不变。.env原LLM_ENABLE_API=true仍在，必须显式离线入口；历史资产hash保护报告在本机。
- REAL_MODEL_AB_PENDING：采用同v3.1方案二。A由旧draft-v3最小迁移，B追加业务检查，A不是旧冻结Prompt。32输入/64交错步骤、新白名单/配置/处理链hash、零授权预检可执行。未来72次/10元只是建议，必须新明确授权、官方价格/模型核查、独立P3.8账本、4对冒烟及研究者内容安全复核；未知发送/用量费用异常/身份漂移立即停。不能复用旧40次账本。
- INDEPENDENT_HOLDOUT_PENDING：207节点保守泄漏图5组件，冻结题与候选448主题重合边，不等于已证实同源；精确/近重复/直接来源匹配未发现不能证明独立。全部开发暴露，未登记翻译同源仍需人审。

```powershell
.\.venv\Scripts\python.exe -B tests/run_offline.py
.\.venv\Scripts\python.exe -B scripts/run_portable.py
.\.venv\Scripts\python.exe -B scripts/p38.py prepare --out .local/p38/NEW_PREPARATION
.\.venv\Scripts\python.exe -B scripts/p38.py preflight --manifest .local/p38/prepared-final-v4/ab-manifest.json
```

后续待审仅为内容/新版问题参考、128条质量、独立Holdout与另行付费授权，不重问八项政策或冻结24题。没有真实邮件发送、CRM扩建、强推、Tag或Release。普通Git只交付源码/测试/脱敏文档；实际SHA与远端/CI收据见本机Git记录。

---

# HANDOFF — P3.7 语义审核准备与定向修复

2026-10-16（Asia/Shanghai）。先读`docs/p37/VERIFICATION.md`、`COMPATIBILITY.md`、`NEXT_AB_PLAN.md`及Git收据。本机总入口`.local/p37/REPORT.md`；当前任务新增DeepSeek请求0次、0元。

- ENGINEERING_VERIFIED：原165/78基线保留；最终200/200完整离线、110/110 portable，新增32公开工程与3本机资产检查。无Schema/Taxonomy/SQLite迁移，无P4发送。
- P3.6原40条JSON/SQLite、input/config/cohort/idempotency、Prompt/Schema、raw/parsed/output、白名单和预算全只读核验；143/168、17/24、29/32冻结不改。原账本40次、halted=authorization_limit，未注册配置或重启付费。
- 新显式customer-primary-v2-safe / owner-operational-v2-safe遮蔽不确定门店及unclear/inferred归属；多个不同未解流程无客户主次时邮件级来源保留unclear。旧v1默认/历史重放均保留，来源不是责任。见兼容说明及反例。
- 只有显式product-before-store-v1业务政策预览才将可决的equal并列顺序派生为1、2，保留客户equal/引用/关系/责任unverified。派生独立身份、父hash、逐字段原因和规则源码hash；29成功run共87派生见`.local/p37/final-replay-v1`，3失败不制造新预测。前期trial目录仅保留过程证据。
- gate2否定门禁保持默认；新增gate3-scoped-review opt-in，覆盖中英文否定/转折/模糊物质承诺/已执行动作，词面无信号不等于批准。保存的commitment真实raw正式离线复验通过，原failed不改；另两结构失败仍拒绝。REAL_MODEL_RETEST_PENDING。
- SEMANTIC_REVIEW_PREPARED：`.local/p37/review-v1/SEMANTIC_REVIEW24.md/json`对应22成功的8维AI意见、2失败不可评分；引用与run/input/config/output/raw绑定，所有human_score=null、reviewer空白。HUMAN_CONTENT_REVIEW_PENDING，不重裁24冻结值，不记入Gold。
- DATASET_QUALITY_REVIEW_PREPARED：32代表独立评语，建议20保留/11修订/1自然子集隔离，均AI候选；11改写新hash仅提案未启用。完整172来源/原160eligible/12隔离不变，见`.local/p37/dataset-review-v1`。独立Holdout仍pending。
- 本机`ROOT_CAUSES7.md/json`分六类逐题归因；`RESEARCHER_DECISIONS.md`列5项未来口径/内容/数据待决，无需重签24题。after_sales、urgency默认、问题粒度、原摘要原因等不能靠确定性映射假装模型已修复。
- UI新增只读历史实验/风险/失败队列→原文→问题卡→AI待审包；原始/派生视图区分、客户重要性/业务顺序两列、证据标签/确定性/建议团队清晰。无新真实调用或发送入口。
- 下一轮A/B仅提案：64计划、建议未来最多72次/10元，未授权未执行，不延伸P3.6账本。`.env`仍旧LLM_ENABLE_API=true，未修改；用离线入口，勿运行历史API脚本。
- 起点1962文件hash留存，原P3.6整个243文件范围、预算、Prompt、24题、旧data/outputs、既存未跟踪成果均保护；只允许本轮源码/测试入口/HANDOFF更新。源码/脱敏文档正常Git交付，完整原文/审核包/Gold/账本/密钥不上传。

```powershell
python -B tests/run_offline.py
python -B scripts/run_portable.py
python -B scripts/p37.py replay --out .local/p37/NEW_REPLAY_DIRECTORY
```

---

# HANDOFF — P3.6 真实v3开发试点

2026-10-15（Asia/Shanghai）。先读 `docs/p36/VERIFICATION.md`、`DESIGN.md`、`REPRODUCE.md` 及Git交付；完整研究证据仅本机 `.local/p36/PILOT_REPORT.md`。

- ENGINEERING_VERIFIED：165/165完整离线、78/78 portable，原154保留；新增独立DevelopmentBudget、版本化Prompt、真实普通文本入口及待审包，保留原架构、v2和历史Dashboard。
- REAL_MODEL_PILOT_VERIFIED：40次正式AnalysisService/LangChain/DeepSeek请求，40收到内容、32接受、8失败、0自动重试/fallback；包含8次跨版本复验。账本`.local/p36/budget.sqlite3`已halted=authorization_limit，不可重建/借旧额度；预留上界2.435422元。实际tokens158609；高峰缓存未命中估算0.457978元，实际账单未知。
- 三独立cohort：baseline-v1=0/4接受；catalog-v2=3/4；draft-v3=29/32。同4冒烟0→3→4仅工程改善，不宣称总体语义提升。最终24开发题全部尝试，8新候选已运行，4新候选预算未运行。各版本Prompt、返回、SQLite和报告均保留，不混算。
- DEVELOPMENT_SEMANTIC_EVALUATED仅七字段冻结开发参考：最终143/168字段、17/24全对，缺预测2保留分母；排除原已标记F176的23题为143/161、17/23。不是独立Gold/Holdout；未改24题裁决。问题级、证据语义、摘要回复HUMAN_CONTENT_REVIEW_PENDING，独立Holdout仍pending。
- 新160 eligible自动复核、原12隔离保留，32代表覆盖16类各2条，中文审核在`.local/p36/CANDIDATE_REVIEW_32_ZH-v2.md`。真人签名留空。完整逐题比较、语义待审包、版本Bad Case与本地保护hash见完整报告链接。
- 最终“无法保证明天付款”被旧gate误拒，已修复紧邻否定并用保留真实raw离线复验；原run/成绩不改，未新增付费复验。旧未绑定gate哈希manifest只读，新实验要新身份；其余错路由/优先级/模糊归属/重复问题是待审风险，未声称修复。
- `.env`仍LLM_ENABLE_API=true，未修改；默认离线入口。真实UI要求服务器开关、显式checkbox、白名单与独立账本，费用/身份可见；本轮账本已停，仍可重开保存结果。无实际发送或P4实现。
- 初始1705文件逐字hash留存；旧资产、P2账本/运行库、24题、原Prompt与既存未跟踪资料保留。正常Git交付仅源码及脱敏文档，不含本机研究原文/Gold/账本/API Key。

```powershell
python -B tests/run_offline.py
python -B scripts/run_portable.py
python -B scripts/p36.py report --experiment draft-v3
```

---

# HANDOFF — P3.5 多问题契约、开发裁决与离线评测

2026-10-15（Asia/Shanghai）。先读 `docs/p35/VERIFICATION.md`、`CONTRACT_COMPAT.md`、`CALIBRATION.md`、`DATASET_AUDIT.md`、`EVALUATION.md`；Git实际交付见 `docs/p35/GIT_DELIVERY.md` 及本机收据。下方P3及更早交接按历史时点保留。

- CALIBRATION_OWNER_DECISION_SNAPSHOT_VERIFIED：补充包及用户最终确认后的24题冻结为 `.local/p35/calibration-decision-v1.1/snapshot.json`。v1保留，v1.1通过前版hash关联。专家结论一致由研究者确认；独立原始专家表未提供，Kappa=null，不伪造签署或Gold。
- V3_CONTRACT_AND_COMPAT_VERIFIED：原文EmailInput不变；AnalysisV3包含Issue[]、证据跨度、客户重要性、业务顺序、团队、未核实责任。完整v3及投影诊断存在SQLite原metadata_json列；v2数据不迁移/重算。题10默认customer-primary-v1保守投影；显式owner-operational-v1可复现有损夹克选择，v3仍equal。
- DATASET_CANDIDATE_AUDIT_VERIFIED：`.local/p35/dataset-candidate-v2/`共172保留记录，160 eligible、12编辑质量隔离并补充；v1不覆盖。160 eligible语言78英文/70中文/12混合，全部开发暴露、人工语义参考pending。REVIEW.md、reviewer-blank.json和Single Analysis的candidate review是人工入口。
- E2E_OFFLINE_V3_VERIFIED：原120+新增34=154/154；portable67/67。正式service→临时SQLite→replay；160/160仅占位fake工程通过，非语义质量。浏览器验证双issue、equal/顺序1/2、1邮件/2问题、幂等、重启重读和下载审核草稿，范围受限。
- HUMAN_GOLD_PENDING / INDEPENDENT_HOLDOUT_PENDING / REAL_MODEL_V3_QUALITY_PENDING。24题无需再次研究者确认；新候选审核、内容Rubric及真正独立评测仍需真实人类过程。
- 314项保护hash不变；旧400、80参考、P2十二次调用及账本、论文和冻结Prompt保留。新增真实调用0、API费用0元。真实.env仍LLM_ENABLE_API=true；必须使用离线入口，不能直接运行历史API脚本。

```powershell
python -B tests/run_offline.py
python -B scripts/run_portable.py
python -B scripts/p35.py offline --dataset .local/p35/dataset-candidate-v2/candidates.json --out .local/p35/NEW_RUN
```

保留Streamlit/LangChain/DeepSeek/应用服务/SQLite。v3 DeepSeek profile为multi-issue-v3，只有fake与模拟HTTP证据；本轮生成用60次/15元授权未使用，不能延伸为真实模型质量实验授权。P4发送/审批状态机未实现。继续工作时先核对Git HEAD、现有变更和本机不可公开资产，不把旧计划中的PROPOSED当成现有功能。

---

# HANDOFF — P3 归因 Dashboard 与 Public 发布

2026-10-15（Asia/Shanghai）。P3_ATTRIBUTION_IMPLEMENTED / P3_DASHBOARD_VERIFIED / OFFLINE_REGRESSION_VERIFIED。原108 + 新12 = 120/120离线通过；新环境portable 40/40。BROWSER_E2E_VERIFIED仅指P3离线筛选、原文下钻、已存P2结果读取/下载、fake提交重读与版本隔离，不代表全产品上传/审批/发送E2E。

先读 docs/p3/VERIFICATION.md、DESIGN.md、PUBLIC_RELEASE.md 与 evidence；仓库已PUBLIC_VERIFIED，MIT，工程SHA 7ad569e9ac532a0be64248d11420185e8c904a0b，GitHub CI 40/40成功；文档receipt之后的最终SHA以git/gh及.local/p3/github-final-receipt.json为准。用户明确授权QQ历史邮箱公开及自有源码MIT；不得扩大到学校/第三方/历史研究数据。仅main推送，不推送本机refs/codex快照。

- Dashboard → P3 versioned attribution；SQLite可选 COMPLAINT_DATASET_MANIFEST，未注册来源明确warning。P2只读JSON，不打开预算或历史数据库。旧三模式在Historical dashboards。
- 四类明确分母、unknown/unclear/none/unavailable及failed/fallback、最新邮件修订版、成员input/output/reference hash；不等于因果或法律责任。联系渠道在v2缺失，显示unavailable；原Prompt/契约未改。
- 新安全demo：python -B scripts/p3_demo.py --out .local/NEW_DIRECTORY；API和trace关，见README。已有本机演示在.local/p3/demo-v1；浏览器额外保存一个独立offline-demo cohort，原fixture仍10条。
- 真人24条校准包：.local/p3/calibration-v1/START_HERE.md；20复杂+4不同模板，双评审/仲裁留空。HUMAN_GOLD_PENDING / REAL_MODEL_FIX_PENDING / INDEPENDENT_HOLDOUT_PENDING。
- 本轮新模型调用0；原实验与.env/预算哈希不变；恢复副本、全部日志在.local/p3。完整回归 python -B tests/run_offline.py；公开检出 python -B scripts/run_portable.py。
- P4需下一轮授权回复版本与人工审批/模拟发送、确认政策和角色；P5需该闭环通过、独立Gold/holdout、单独真实评测预算。无真实发送、Tag或Release。

---

# HANDOFF — P2.5 评价基础与安全Git交付

2026-10-15（Asia/Shanghai）。本轮完成工程实现与离线验证；人工/模型语义门槛保持pending。以下P1/P2原交接按历史原文保留，其中无Git提交等描述只适用于当时。

- 完整P2基线提交：5ffa9a9a6899dd2bd0fb4b402781fac273888dad。P2.5工程提交7e3f5153654174aac79781e9744086ba3a5795b2已推送Private；远程干净检出28/28通过。最终文档核验提交见docs/p25/GIT_AND_GITHUB_REPORT.md及本机最终receipt，不根据下方历史Git段落推断当前状态。
- 108/108离线通过（原77+portable2+P2.5新增29）；portable入口覆盖28项。数据400/400、55模板、11场景族、10保守泄漏分量；146条触发至少一项疑点，未改原参考。
- 130候选：110旧模板代表+20新复杂开发案例。人工标注队列：.local/p25/annotations-v2/，两位reviewer和仲裁均未签署；HUMAN_GOLD_PENDING。20个holdout_candidate只是隔离候选，全部已暴露，INDEPENDENT_HOLDOUT_PENDING。
- 新统一Schema/框架见src/evaluation/e2e_schema.py、e2e.py、gold.py、dataset_audit.py；scripts/p25.py仅offline/replay，无付费模式。新结果与参考用sample/input/run/output/reference/config哈希追溯；来源/版本拒绝混合，失败保持分母。
- 旧P2十二条只读run JSON重放，83/84和11/12不变。摘要/回复人工评价PENDING；fake/AppTest不替代模型语义/浏览器E2E。
- 服务边界新Prompt complaint-v2-service-boundary-1以可选profile接入正式service，默认P2冻结Prompt不变。BADCASE_RULE_REGRESSION_VERIFIED / REAL_MODEL_FIX_PENDING；只确认规范冲突，不声称解释模型内部原因。
- 原262项及本轮342项保护资产哈希全不变，.env、P2预算和运行库未修改；恢复快照位置在.local/p25/recovery.json。真实.env旧开关启用，因此不要直接运行历史API脚本；普通测试强制关闭API并阻断socket。

下一轮先读docs/p25/VERIFICATION.md、E2E_COVERAGE_MATRIX.md、EVALUATION_PROTOCOL.md、HUMAN_GOLD_PROTOCOL.md、BADCASE_REVIEW.md。P3可以基于已有工程基线推进离线统计和证据下钻；先定source/unknown/failed/fallback、别名与版本口径。任何新付费调用需独立明确授权和新预算目录，绝不重建P2账本。P4审批/发送仍未实现。

```powershell
python -B scripts/run_portable.py
# 本机有历史资产时：
python -B tests/run_offline.py
python -B scripts/p25.py offline --dataset tests/fixtures/p25_portable_v1.json --out .local/p25/new-run
```

---

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
