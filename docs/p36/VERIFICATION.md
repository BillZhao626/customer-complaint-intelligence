# P3.6 真实模型开发试点交付

2026-10-15（Asia/Shanghai），基线HEAD `f51a4b315ac7a6f83aeabd799a0424c26af04537`，该HEAD的GitHub Actions成功。保留Streamlit、LangChain、DeepSeek、Application Service、SQLite、v2及历史Dashboard；无P4发送或CRM扩展。

|状态|范围|
|---|---|
|ENGINEERING_VERIFIED|165/165完整离线、78/78 portable；预算/版本/持久化/UI回归|
|REAL_MODEL_PILOT_VERIFIED|40次正式服务真实调用，40收到内容；包含失败与跨版本复验|
|DEVELOPMENT_SEMANTIC_EVALUATED|仅最终单一版本与冻结24题七字段开发参考一致性；非独立准确率|
|HUMAN_CONTENT_REVIEW_PENDING|新候选、问题级参考、证据语义、摘要/回复均未由AI签署|
|INDEPENDENT_HOLDOUT_PENDING|全部输入已开发暴露，不是Holdout|

## 真实结果与明确分母

|独立实验版本|请求|正式通过|失败|Tokens|高峰未命中估算元|
|---|---:|---:|---:|---:|---:|
|原v3-1 / baseline-v1|4|0|4|13242|0.040794|
|证据目录v3-2 / catalog-v2|4|3|1|15476|0.045646|
|双语草稿v3-3 / draft-v3|32|29|3|129891|0.371538|

所有请求经AnalysisService、真实LangChain/DeepSeek和新SQLite；无fake替代真实预测。首轮4条未过后保留原输出，分别冻结新Prompt/参数/cohort再复验。相同4条冒烟正式验收0/4→3/4→4/4，只证明该组工程改善；输出上限也从2000变4000，不能单独归因Prompt或宣称泛化质量提升。旧Prompt及24题裁决未改。

总计40次请求、40收到内容、32通过、8拒绝、0自动重试/超时/网络失败/fallback；跨版本复验8次包含在40中。JSON合法40/40、含跨字段约束的Schema合法36/40；收到内容不等于分析正确，也不代表生产API稳定性。输入135149、输出23460、合计158609实际tokens；高峰缓存未命中上界估算0.457978元，实际账单未知。总体provider p50/p95=3.545/6.318秒（n=40）；最终版3.474/6.429秒（n=32），编排3.551/6.512秒，不是UI全延迟或生产SLO。计价依据：[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，当日高峰输入/输出2/8元每百万token。

独立持久账本预留上界2.435422元；40次先触限，halted=authorization_limit、pending_dispatches=0、active_lease=false。没有复用旧P2或P3.5生成预算。返回alias为deepseek-flash，权重快照不可得，不能声称固定底层权重。

最终版本24题全部尝试，22可用、2缺预测，七字段143/168=85.12%，全字段17/24=70.83%；失败计错。sentiment20/24、urgency21/24、is_complaint22/24、store21/24、category21/24、reason20/24、source18/24。原已标记不自然的F176另从干净子集排除：143/161、17/23、缺预测1/23；24全表仍保留。没有改参考或与前两版混算。

原计划24开发+12候选，预算用于8次跨版本复验后最终为24+8；另4候选未发送。候选12的分母仍保留：8运行、7成功、1失败、4未运行；无正式参考，不报准确率。全部160 eligible自动检查、原12隔离保留，32代表覆盖16语义类各2条；AI中文审核意见留空真人批准，不新增Gold或覆盖数据。

最终29成功邮件含36问题。30结构合法响应中的72/72证据跨度逐字合法；2结构非法响应未计入该跨度分母。逐字合法不证明语义支持。问题数量、漏识别、重复识别、对象/原因、情绪/解决状态、客户重要性/处理顺序和归属不确定性没有已批准v3问题级参考，质量率null。摘要/回复/证据语义各36待审：29有接受预测、3失败、4未运行，0签署。

## Bad Case与修复范围

真实偏移错误与无importance_evidence导致首轮失败；程序生成原文片段目录供模型逐字复制，未放宽Schema，未通过参考制造证据。第二版仍声称已记录，被门禁拒绝；第三版双语草稿边界后同4题真实复验通过。

最终版发现否定句“无法保证明天付款”被旧子串门禁误拒。新gate只对紧邻明确否定消歧，转折后正向承诺仍拒绝；保存真实输出经正式validate_result离线复验通过，原run仍failed、143/168与17/24不变。另两项结构失败仍拒绝。gate修改后新付费复验未执行（额度已耗尽）；未来新实验须冻结gate版本/hash，已有未绑定旧manifest只读。

待审语义风险包括：equal问题都排1导致有损投影不能选择；缺维修指引仍归门店；模糊包裹去向过早归因；发票要求不催退款团队却仍派refunds；反讽问题可能重复拆分；复杂回复遗漏材料发送渠道；英语输入回复中文、重复索要已提供信息或过度解释执行限制。保留输入/预期/真实输出/根因假设/修复/复验台账，没有宣布这些风险已解决。

## 产品与工程证据

Single Analysis独立真实v3普通文本入口默认不调用；必须服务器开关、显式checkbox、冻结白名单和预算均允许才可提交。显示调用模型/Prompt/实验、费用预留、实际tokens；可重开真实结果与下载hash绑定的待审包，人工参考与模型预测分开。预设演示仍独立。问题详情按顺序展示证据、流程/团队/确定性/缺证和客户重要性，回复只显示一次，内部JSON收入溯源面板。旧v2与Dashboard保留。

原154测试全部保留；新增11项覆盖40/15上限、重启/未知请求、配置与白名单、Unicode证据目录、输出额度隔离、真实错误的门禁及否定/转折、缺失分母和AppTest显式启用/保存/幂等/新会话/待审下载。最终165/165与78/78 portable无失败/跳过；pip check通过。AppTest使用显式fake临时库，只支持UI接线工程结论，不声称本轮真实浏览器E2E。全部40真实运行有SQLite重读断言。

## 本机交付与保护

完整原文和结果仅在`.local/p36/`：

- `PILOT_REPORT.md`：完整报告与分母；`budget-and-api-audit-v1.json`：40次真实用量/延迟/预算。
- `COMPARISON24_ZH-v1.md`、`draft-v3/comparison24-v1.json`：逐题七字段对照。
- `CANDIDATE_REVIEW_32_ZH-v2.md`：中文分层复核；`candidate-quality-v1.json`：172记录自动检查。
- `SEMANTIC_REVIEW_ZH-v1.md`、`AI_SEMANTIC_REVIEW-v1.json`：问题/证据/摘要/回复待审。
- `BAD_CASES_ZH-v1.md`、`BAD_CASES-v1.json`：版本化Bad Case；`offline-gate-revalidation-v2.json`：仅离线复验。
- 三个实验子目录分别保存Prompt、配置、原始run、SQLite和独立报告，公共账本只属于本轮。
- `baseline.json`、`asset-protection-v1.json`与测试日志：保护与验证；Git交付另见[GIT_DELIVERY](GIT_DELIVERY.md)。

初始1705文件hash留存，只有授权源码/测试入口/HANDOFF改变，既存未跟踪资料保留；历史数据、outputs、Prompt、24题、P2账本/SQLite及.env不变。新源码与脱敏文档可公开，完整研究原文/Gold/账本/API Key不上传。无强推/Tag/Release。
