# P3.7 语义审核准备与定向修复

2026-10-16（Asia/Shanghai）。起点HEAD bcccd327d9bd92526374d4baef5e22aabd049ff9及其CI已核对。本轮新增真实模型请求**0次、0元**，P3.6预算仍40次且halted=authorization_limit；未创建/注册新付费实验或发送邮件。

|状态|范围|
|---|---|
|ENGINEERING_VERIFIED|旧策略/旧run保留，新增显式安全投影、派生身份、门禁、只读审核UI和回归|
|SEMANTIC_REVIEW_PREPARED|22成功开发输出每条8维AI候选意见和可验证引用；2失败单列，共24题|
|DATASET_QUALITY_REVIEW_PREPARED|32代表逐条不同自然度意见，20保留/11修订/1自然子集隔离建议；11新hash改写仅提案|
|HUMAN_CONTENT_REVIEW_PENDING|所有真人分数null、reviewer空白；AI严重程度只用于审阅排队，不是Gold/准确率|
|REAL_MODEL_RETEST_PENDING|仅真实旧输出离线重放；没有新调用，不宣称模型本身已改善|
|INDEPENDENT_HOLDOUT_PENDING|全部输入开发暴露，不冒称独立测试|

## 基线与离线重放

核验全部40条P3.6 JSON/SQLite一致、input hash、cohort/idempotency、Prompt快照/实际发送hash、Schema/config、raw/parsed、output hash、白名单、独立预算注册/预留。Windows CRLF文件与LF发送文本分开记hash。ReadOnlyRepository及预算mode=ro、query_only；CLI阻断socket、历史文件/目录写和非只读SQLite。

P3.6原143/168、17/24、29/32，以及24全表/23干净子集口径不变。重放29成功run的3个派生视图，共87份，记录新身份、父来源、变更原因与规则hash；3失败不制造伪预测，也不将compatibility差异称为模型准确率提升。完整差异与反例见[COMPATIBILITY](COMPATIBILITY.md)。

## 七个不一致案例

|案例|主要归因|修复与保留|
|---|---|---|
|after_sales|模型流程分类偏差；neutral/negative存在参考解释空间|不重标情绪/流程，缺指引规则与回复质量待审/下一轮Prompt验证|
|no_object|缺信息默认low/unknown边界；v2无法表达unknown投诉状态|保留unknown与投影诊断，不自动填low或改裁决|
|mixed_ambiguous|equal与业务并列混淆；有损投影无唯一首项|只在明确既有业务政策opt-in时派生1、2；equal/证据/关系保留；Schema未降低|
|commitment|工程门禁否定误拒，非输出结构不合法|保留gate2与原failed；gate3用保存真实raw正式离线复验，不补算成功；raw urgency仍需审|
|uncertain|无时间证据却提取延误；去向变责任；unclear被具体来源覆盖|新兼容视图遮蔽来源和不确定门店；reason/summary语义不自动改写|
|typo|不确定店名丢失；无客户主次的多流程被业务顺序选为单来源|新safe投影store unknown/source unclear；size/fit→other保持，问题拆分待审|
|F176|旧模板质量异常与跨字段结构冲突|保持原exclude_clean_semantic和failed，不把其当新172池隔离，不生成替代成功|

完整逐题原文、冻结预期、原预测、六类归因、工程门禁附加归因、派生变化和修复状态仅本机`.local/p37/ROOT_CAUSES7.md/json`。无法只凭输入/输出证实模型内部原因，文档将假说与可观察错误分开。

## 内容与数据审核准备

24题内容包有22份成功输出；每条覆盖重要Issue、证据语义、摘要事实、诉求回应、重复索资料、未经授权承诺/动作、语言/机械免责声明、安全隐私多问题。引用绑定具体input/output字段和Unicode位置、input/config/output/raw hash；校验逐字合法不等于语义成立。2失败的内容评分标不可评，原始返回用于归因。没有把AI意见写入Human Gold或正式语义准确率。

32代表覆盖16类各2条，独立自然度文字32种；实际逐条检查分类指示、零售合理性、危险依据、尺码/商品、来源歧义、双语口语、退款隐私与注入。原172记录全来源/质量叠层保存，160eligible及12隔离原状不变；建议隔离的一条仍为AI提案，未悄悄改源状态。11修订有新ID/input hash、前版关联、reference=null、active_dataset=false，未进入白名单，不能继承旧标签为新Gold。

## 产品与测试

保留Streamlit/LangChain/DeepSeek/Application Service/SQLite、v2与历史Dashboard。新只读工作台可按实验/风险/失败选具体run→原文→问题→AI待审清单。问题卡两列区分客户重要性/业务顺序，显示原文跨度对应的标签待审、报告/推断/不明确来源与建议团队、责任未核实。回复单次展示、始终未审核，词面门禁诊断与真人批准分开。默认展示原始结果，派生视图需显式选择并另有下载身份，不回写run。

起点165/165离线已复核；最终200/200本机、110/110 portable通过，原165/78全部保留。新增32项portable与3项本机资产检查，覆盖新旧投影/反例、独立ID排序、条件式业务策略/安全优先、派生篡改、否定/转折/模糊承诺/已执行动作、8维审核绑定/反伪签、失败不可评分、只读SQL/文件/socket、40条原件与87派生、本机32质量/11修订、AppTest原始/派生/待审及无效包拒绝。AppTest不声称真实浏览器或新模型验证。

首次门禁把“预计明天到账”归为强承诺，已修为人工审，不放为clear；只读审计先发现CRLF文本hash误比，修为发送文本/字节分列；Windows测试临时连接未关闭导致清理报错，已close后复验，未放宽断言或跳过测试。所有失败日志保留本机。源码内存编译、pip check和git diff检查另随最终收据记录。

## 交付导航与下一轮

本机`.local/p37/`：

- `ROOT_CAUSES7.md/json`：七题归因及状态。
- `review-v1/SEMANTIC_REVIEW24.md`、`semantic-review24.json`：研究者可审24题；真人字段仍待审。
- `dataset-review-v1/CANDIDATE_REVIEW32.md`、`review32.json`、`revision-proposals.json`、`source-quality-overlay172.json`：逐条质量意见、改写与完整原池状态。
- `final-replay-v1/`：40条核验、87派生、配对策略差异和3缺预测；前期trial目录保留，不混作最终版本。
- `RESEARCHER_DECISIONS.md`：5项最终判断，不要求重复确认24题。
- `gate3-failed-output-replay.json`：否定承诺离线通过，另两项结构失败仍拒绝，原run不改。
- `REPORT.md`、保护/预算/测试/Git收据：整轮索引。

下一轮提案见[NEXT_AB_PLAN](NEXT_AB_PLAN.md)：计划64次、建议未来最多72次/10元，未授权、未创建账本、未执行。先完成内容/问题粒度审核，再冻结新实验；旧P3.6账本不延伸。

历史数据、outputs、原Prompt、24题、P2/P3.6预算/SQLite、所有既存未跟踪成果与.env按起点hash保护。仅正常提交源码/脱敏文档，不上传本机研究原文、Gold、审核意见原文、预算或密钥。最终Git/CI见[GIT_DELIVERY](GIT_DELIVERY.md)。
