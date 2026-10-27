# P4-RC1 独立产品验收与 LangChain 架构复核

日期：2026-10-19（Asia/Shanghai）。基线 `complaint-product-p4-rc1` / `7d5b8df34b8ce1f451183695c35c3627b974c697`。本次是开发代理从新用户、QA、答辩评审视角重新取得的验收证据，**不是独立真人Gold、盲评或消费者实测**。先完成全部浏览器基线和报告，随后只修复确定的P1工程故障。

**结论：有条件接受为单机、有人审核、仅模拟发送的毕业设计演示。** 核心业务闭环可操作、可追溯、可重启恢复；原版存在CSV输入导致其他Tab中断的P1，已最小修复。不能演示成任意自定义邮件的实时模型理解产品，也不能据此主张模型语义质量合格或生产可用。批量与单条路径、Dashboard引导和来源口径的易理解程度仍需改善。

## 一、可复核证据入口

所有完整本机证据位于 `.local/p4/rc1-independent-20261019/`，含研究raw的文件不上传：

|证据|文件|
|--|--|
|修复前完整报告，先于生产源码修改保存|`BASELINE_REPORT.md`|
|截图索引、真实操作的URL/时间、AX/DOM原文|`browser-index.json`、`EVIDENCE.html`、同目录PNG/TXT|
|原始Git/PR/head、Manifest14项hash匹配、环境仅布尔检查|`baseline.json`、`git-status.txt`、`pr1.txt`、`pr2.txt`、`branches.txt`|
|重启前后完整SQLite记录|`before-restart.json`、`after-restart.json`、`restarted-process.json`|
|最终案例、原文、raw、草稿、事件、回执、统计|`database-final.json`、`browser-product.sqlite3`、`browser-product-analysis.sqlite3`|
|原库与预算只读计数、hash及完整性|`budgets-and-existing-databases.json`、`protection-final.json`|
|LangChain真实历史请求身份、usage、payload hash|`langchain-runtime-evidence.json`|
|源码修复身份、基线/最终测试、Portable、Git状态|`repair-identity.json`、`baseline-full.log`、`csv-before-fix-reproduced.log`、`csv-after-fix.log`、`final-full.log`、`final-portable.log`、`FINAL_VERIFICATION.json`|

实际运行 `app.py`，真实浏览器点击、输入、导航、刷新、关闭重开；全程使用新库，不把AppTest当浏览器。初始窄视口与1366×900桌面布局均观察过。Streamlit内部滚动容器使截图仅覆盖当时可视区域；须结合完整DOM/AX和SQLite，不能把PNG误称为整封页面。早期TXT可为AX差分，后期 `*.ax.txt` / `*.dom.txt` 是完整快照。

可重开本轮库（先停止占用该端口的本轮QA服务，或另选端口；不覆盖已有库）：

```powershell
$env:COMPLAINT_PRODUCT_DB='D:\Projects\complaint_llm_system\.local\p4\rc1-independent-20261019\browser-product.sqlite3'
$env:COMPLAINT_DB_PATH='D:\Projects\complaint_llm_system\.local\p4\rc1-independent-20261019\legacy.sqlite3'
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.port 8519 --server.address 127.0.0.1 --browser.gatherUsageStats false
```

## 二、真实浏览器验收矩阵

以下缩写为case_id前8位；完整ID/分析run_id/版本/事件在JSON和SQLite。证据名均指本机同名PNG及文本，操作步骤可直接重做。PASS只评价所列工程行为，不评价fixture准确率。

|#|项目|基线→修复后|步骤、观察与数据库绑定|截图/原始状态证据|
|--|--|--|--|--|
|1|普通咨询|PASS→PASS|选择普通咨询→分析→Evidence→直接批准被缺审核项拦截→填写原因与3项核对→批准→模拟；222db422，v1/rev2，一条唯一回执。修复后新咨询e4b8f5b3重新走完全程。|`01-inquiry-unreviewed`、`01-review-missing-fields`、`01-simulated-sent`、`fix-inquiry-sent`|
|2|多Issue|PASS→PASS|分析三问题，查看三份Evidence；drawer风险minor，原因安全/order1；旧床回收售后/order2；发票billing/order3；客户重要性均unspecified，未由处理顺序推断主次。30df37a2。|`02-multi-evidence`、`02-multi-desktop-final`；JSON的analysis.issues|
|3|严重风险|PASS→PASS|空冷烤盘承重把手故障fixture→severe/high、停用/不复现建议；仅3项普通核对不能批准，补安全核对后批准并模拟。44bb8c3e，v1/rev2。|`03-severe-unreviewed`、`03-safety-required`、`03-severe-sent`|
|4|编辑、退回、Diff|PASS→PASS|灯具回复未来联系承诺被阻断→原因退回→编辑→保存v2→查看v1/v2及Diff→重新勾选批准→模拟v2。ee43da43，rev4，回执hash对应v2；v1保留。|`04-reply-blocked`、`04-returned`、`04-dirty-disabled`、`04-v2-diff`、`04-v2-sent`|
|5|真实N04风险错误|PASS→PASS|搜索86d85387→只读重放；原契约succeeded，analysis层potential_injury_downgrade阻断。改为停骑回复保存v2仍不能批准→拒绝→试退回间接重开仍拒绝。de614da6，v2/rev2；旧实验状态不改。|`05-n04-blocked`、`05-n04-v2-still-blocked`、`05-n04-reopen-rejected`、`fix-n04-still-blocked`|
|6|结构化失败|PASS→PASS|选择结构化契约失败→analysis_failed/v0，raw仅诊断；无草稿、审批或发送按钮。df7efbc1；contract_error/raw保存在分析库。|`06-contract-failure`、`06-contract-final`|
|7|分析器故障恢复|PASS→PASS|选择分析服务失败→analyzer_error:RuntimeError，raw为空/v0；切回普通咨询能重读已有成功；工作历史重新选择失败成员→打开原文和错误。ed6a4cfd。|`07-analyzer-failure`、`07-recovered`、`07-error-history-final`|
|8|自定义unknown|PASS→PASS|填QA合成中文水壶邮件→unknown/pipeline-placeholder、无模型理解声明、中文占位回复；不冒充冒烟语义已识别。105eb9d9，v1/rev0。|`08-custom-unknown`；analysis及config.parameters|
|9|重复、旧页、异常|PARTIAL→PASS（已测路径）|重复成功分析不增案例/回执；终态禁改。两页同案例，另一页改v2后旧页拒绝收到Stale page，无拒绝事件。空CSV异常已修复并验证恢复。初次两页退回/批准交错不单凭截图判为绕过，实际事件见SQLite。|`09-repeat-inquiry`、`09-stale-before`、`09-other-page-v2`、`09-stale-reject-confirmed`、`fix-valid-batch-recovered`|
|10|刷新/重开/重启|PASS→PASS|刷新已发送v2→关闭重开case URL→终止核验过命令/端口的本轮PID34204→同库重启→重读。8案例/9草稿/21事件/3回执前后完全相同。|`10-refresh-sent-v2`、`10-reopened-v2`、`10-service-restarted-v2`及前后数据库JSON|
|11|Dashboard追溯|PARTIAL→PARTIAL|P4按来源和完整cohort隔离，原契约/失败/block及分母可查；成员需先读JSON再回Single历史打开。P3单独读旧分析库，未提示默认Single已写P4；unknown未单列。统计正确性与首次操作可理解性分开评价。|`11-p4-dashboard-members`、`11-p3-source-final`、`11-dashboard-historical`、`database-final.json`|
|12|四Tab/布局/语言|FAIL→PARTIAL|逐个点击四Tab；有效批量1行可导出，但走旧mock而非P4。原空CSV使后续Tab中断，修复后三处无效CSV仅局部提示且可替换恢复。仍有中英文、技术JSON、旧来源标签和导航解释问题。|`12-empty-csv-failure`、`12-empty-csv-dashboard-broken`、`12-evaluation-empty-failure`、`fix-batch-empty-local-error`、`fix-dashboard-survives-bad-batch`、`fix-prediction-empty-local-error`、`fix-golden-empty-local-error`|

修复前：9 PASS、2 PARTIAL、1 FAIL；修复后：10 PASS、2 PARTIAL。修复后只重做受影响CSV边界、有效恢复、普通咨询全闭环和N04门禁；其余沿用同一基线证据加完整回归，不声称重复跑过全部浏览器场景。未验证生产多用户权限、移动端全覆盖、恶意文件资源耗尽、灾备或任意语义泛化。

## 三、缺陷分级和处置

### F01 — P1，必须修复，已完成

复现：Batch Analysis上传0字节 `empty.csv` → `pd.read_csv` 的EmptyDataError未捕获 → 所有Tab按脚本顺序执行，Dashboard和Evaluation中断渲染。点击Dashboard不能清除上传。Evaluation的Prediction/Golden读取同样有问题；技术堆栈可溢出至其他Tab。没有产生草稿、审核事件或模拟回执。

最小修复：`src/app/csv_input.py:9` 统一处理空文件、解析失败、编码错误、读取异常和仅表头无数据；`app.py:485` 把错误显示在相应Tab并立即返回，**不把无效上传替换成历史预测**；批量、Prediction、Golden及已有评测文件读取使用同一边界。不改Schema、Prompt、模型结果、Gold、业务政策或数据库。

修复前新增实际app.py集成测试在三处分别失败；修复后单元和集成通过。真实浏览器三处均复测，提示不含文件正文/堆栈；无效批量CSV留存时Dashboard和Single仍能使用。替换有效CSV后批量继续。测试同时确认已有P4来源、草稿、事件和状态不变。

### F02 — P2，建议明确边界；统一服务留P5

`app.py:109` 批量调用旧规则mock，CSV导出不进入AnalysisService或ProductStore；Single默认是P4。批量spinner虽说mock，完成页没有同等持久来源说明。P3空库提示“Single分析Offline Fake再打开Dashboard”，实际默认Single写入另一个库。复现：P4有案例→P3 versioned attribution→No saved runs。应修正入口解释与完成页标签；批量统一归档/审核是功能增量，本轮未实施。

### F03 — P2，建议改善统计披露和追溯入口

P4按完整cohort分组是正确隔离，但表格不显示cohort_id；fixture_hash包含输入使多个相同model/prompt行看起来重复。成员只有JSON中的case_id，需返回Single手动选历史；没有Dashboard直接成员打开控件。历史400总量旁显示“Formal accuracy88.21%”，即使其他位置有提示，仍宜在该指标旁明确80封×7字段、494/560、开发参考来源。不要改历史成绩。

unknown占位目前进入“原契约成功且无analysis block”的业务分母，符合现有实现口径；但UI未单列unknown数量。**不能把negative/business_denominator自行解释成已知情绪样本的负面率。** 基线8案例：accepted6、failed2、N04分析block1、业务分母5，其中unknown1/negative3；最终新增一条普通咨询后9案例：accepted7、failed2、业务分母6、unknown1/negative3。原契约成功不等于语义认证；演示操作计数不是真人审核通过率。P4新路径没有自动fallback，旧mock来源仍须单独解释。

### F04 — P3，建议的展示改进

中文操作与英文Tab、状态、字段、错误混排；Evidence理由以JSON展开；完整原始身份、事件和模拟回执对新用户冗长。工作历史选择和“打开”是两步，选项状态在操作后曾短暂滞后于当前状态标题。建议中文显示标签、简明Issue内容和折叠审计信息；保留底层枚举与证据。它们是已观察到的理解成本，没有据此虚构审批绕过。本轮未重构UI。

P0未发现；已测路径未发现分析block可由编辑回复解除、失败可发送、已拒绝间接重开审批、重复回执或SQLite记录丢失。有限反例不等于风险清零。

## 四、LangChain专项审查

### 1. 实际职责与答辩查验位置

|源码|评审可查验的实际作用|边界|
|--|--|--|
|`src/chains/langchain_complaint_chain.py:394`|旧链 `ChatPromptTemplate.from_template` → `prompt \| llm` → 内容取出；419起创建ChatOpenAI|历史兼容链，含宽松提取/标准化/mock fallback；当前P4并不调用它，不能拿它代表当前严格链|
|`src/infrastructure/deepseek.py:38`|版本化Prompt/profile绑定；80起创建LangChain ChatOpenAI，97起async request，106调用ainvoke并取usage/response_metadata|ChatOpenAI统一消息/响应接口；DeepSeek字段适配、禁SDK重试、HTTP/截止时间及禁tracing是自有控制|
|`src/application/product_demo.py:54`|ProductFake→RunnableLambda(_respond).with_config→chain.invoke|真实执行LangChain Runnable，但返回人工编写fixture/unknown占位，无推理|
|`src/application/analysis_service.py:27`|严格JSON结果后的Pydantic、原文Evidence、业务门禁和有损v2投影；54起幂等/失败/保存|服务和领域层负责，不是LangChain自动保障语义|
|`src/application/live_execution.py:26`|durable claim、attempt预写、预算reserve、provider request、严格解析/验证、usage结算及终态保存|应用编排/经济安全，不是LangChain重试链；strict_json拒重复键/非有限值|
|`src/app/product_workspace.py:109`|显式fixture或历史只读重放→未审工作副本；25起展示Evidence、编辑和审核|UI无新付费provider分支；Human审核与模拟回执由ProductStore承担|
|`src/application/product_workflow.py:179`|SQLite事务内的revision/hash、草稿版本、核对项、审批和回执门禁|Pydantic身份/SQLite持久化和确定性统计，不是模型或LangChain状态机|

### 2. 真实运行证据与Offline Fake的区别

N04 `86d85387-9dcc-49be-80a1-0ac55019af65` 是2026-10-17历史真实请求：backend=deepseek_live、prompt=complaint-p310-bounded-multifinding-3、schema=analysis-v3.1、context接受profile。其attempt为response_received，4797输入+644输出=5441 tokens，实际payload SHA256 `b57d4543…`；response_id_kind=langchain_message_id，另有provider_response_id。原status=succeeded，风险仍错；此次仅只读重放，不是新请求。

该请求具体沿 `p310_experiment.ResearchAnalyzer:126` → `P39Analyzer.request:163` → 继承的`DeepSeekAnalyzer.make_client:80` → ChatOpenAI.ainvoke（`p39_experiment.py:184`）。context校验由`ResearchService:134`复用ContextOfflineService，不能省略成普通v3.1 reader。raw、版本、用量和payload身份可在本机runtime证据及原只读库核对；模型alias不等于不可变权重快照。

P4浏览器fixture则为backend=offline_fake、model=explicit-v31-fixture-replay、prompt=p4-offline-runnable-v1；`ProductFake`通过Runnable返回预写JSON或故障。自定义邮件由`v31_demo.pipeline_probe:51`产生unknown/有限词面提示，绝不能把工程通路通过率称作模型准确率。研究者owner-adjudication-v1政策、新质量诊断、demo_test/local_human审核事件、模拟回执彼此独立；本轮没有代签local_human。

### 3. 是否已清楚体现统一接口、Prompt、Runnable、结构化？

- **统一调用接口：有实际使用，但要准确归属。** LangChain ChatOpenAI提供消息/响应和async调用适配；外层Analyzer Protocol和AnalysisService是项目自有接口。当前provider有显式DeepSeek白名单，不能声称任意模型已无缝切换。
- **Prompt：有版本化模板，但当前真实链是自有messages函数。** LangChain ChatPromptTemplate明确位于旧链；当前DeepSeek真实链接收版本化消息tuple，P4 fake不执行模型Prompt。不要把三个文件拼成一个不存在的实时流程。
- **Runnable：P4确实调用，但很薄。** 是单RunnableLambda，不是多阶段智能编排；旧链有LCEL组合，当前真实链没有复杂Runnable pipeline。
- **结构化：完整处理存在，主要由自有代码/Pydantic完成。** response_format=json_object只约束输出形状倾向；strict_json、Schema、Evidence和语义门禁在项目内，未使用LangChain with_structured_output，也不能用合法JSON代替语义正确。

因此框架作用是真实且可验的，但P4屏幕本身不能证明“当前模型端到端运行”。答辩应展示源码、历史真实收据和当前离线闭环三种证据的不同身份。

### 4. 为什么保留LangChain，而不是直接用兼容SDK？

保留现有ChatOpenAI适配可复用统一消息/响应、异步调用、usage和callbacks接口，维持已验证的历史集成；以后确有provider变更时可评估收益。当前只是单次模型调用，直接OpenAI兼容SDK也能实现同样功能；没有证据证明LangChain使准确率更高或不可替代。现有`_get_request_payload`私有方法适配与依赖只有下界是升级兼容风险，应以锁定环境和payload测试控制，不能为答辩另加LangGraph/RAG/多Agent。

### 5. P5最小接入方案（提案，本轮不启用）

保留现有闭环，增加一个可注入的产品分析协调入口：UI显式选真实模式→经服务器授权/新白名单与新预算→匹配冻结接受profile的AnalysisService及Repository→DeepSeekAnalyzer/ChatOpenAI→持久AnalysisRun→ProductStore.create(saved_run)→同一编辑/审核/模拟状态机。幂等重试只补产品快照，不重复请求；产品失败不吞分析运行。若采用context profile，服务校验和新连接reader必须成对匹配；不要直接把普通service替换成已冻结研究runner，也不晋升P3.10 Challenger。

需显式处理当前app.py强制关闭API的服务器能力策略，不能靠把.env改true绕过。复用transport/attempt/预算的机制，不复用旧P3.9剩余1次或P3.10账本。先用fake HTTP做输入→provider→raw→验证→SQLite→审核→模拟的离线验收，另行取得真实用途/数据/调用数/金额授权后才做真实浏览器端到端。批量若进入该闭环，也调用同一协调入口，不继续生成另一套不可审核结果。

## 五、Git、回归和保护结论

基线Manifest14个规范化源码hash全部匹配；修复后保留原Manifest，另记repair-identity，不伪称修复后的工作树仍逐项等同冻结候选。源码变更仅 `app.py`、新增 `src/app/csv_input.py`、新增 `tests/test_csv_input.py`，以及将新测试加入Portable列表。新CSV集成修复前3个子场景失败，修复后通过。

|最终验证|实际结果|范围|
|--|--|--|
|独立修复前完整基线|396/396通过，0 skip；550.060秒|包含私人历史资产的隔离副本|
|修复后完整回归|398/398通过，0 skip；512.274秒|原396个测试ID全部保留；外部socket被阻断|
|干净Portable导出|304项执行，297通过，7 skip；364.982秒|git archive HEAD加4个修复源码/测试文件；7项私人raw/附件/真实重放材料缺失明确跳过|
|CI同类演示脚本|P3 10例、P4 7例均成功|公开导出无私人真实重放；新目录、无API，SQLite integrity=ok/FK空|
|独立SQLite直接只读校验|9案例/10草稿/24事件/4模拟回执，全部hash/事件连续性/版本绑定有效|重启前后原8案例快照完全相等；无local_human代签|
|环境与静态检查|pip check、修改Python内存编译、git diff --check通过|现有Windows Python3.12环境；没有重新安装依赖|

完整机器结果见本机FINAL_VERIFICATION.json；现有HEAD的上游CI成功，**本轮未提交修复没有新的远端CI结果**。不把Portable的7个skip算作本机历史验证成功，也不用历史CI替未提交工作树背书。

PR #2基于PR #1的分支；PR #1又基于codex/p39-r3-continuity。远端main仍为f0a5eb7，当前候选四个提交在它之后；两个PR查询时均MERGEABLE且portable成功。这只说明各自对基分支的状态，不能证明任意顺序/直接改base到main安全。建议人工按P3.9→PR #1→PR #2依赖处理，每次重定向base后重新检查最终树、差分和CI；不要在依赖没合入时删除基分支或把展开的研究变更误当P4新增。本轮未commit/push/merge/tag/release，新修复需另行授权Git交付。

5618个原文件无丢失，除授权的app.py与测试入口外hash不变；旧未跟踪成果、raw/Gold/outputs、论文、.env、原产品库保留。原默认产品库0案例、原浏览器库3案例/2回执、原demo-v1库10案例/5回执均只读核验。P3.9 usage71、剩1，P3.10 reservations/outcomes180且halted不变；两个账本hash与基线相同。新付费请求0、新付费账本0、真实SMTP/CRM发送0，无外部数据上传。

## 六、毕业设计与P5的最小充分路线

1. **演示交付：** 采用Offline Fake完整审核/模拟路径，另展示历史真实N04“契约成功但语义错误仍被阻断”。开场说明当前模式；不要现场把unknown占位当智能理解。核心业务把事实、风险、客户主次、处理顺序、未核实归属和执行能力分开，是合理的；质量门禁是闭集补充，必须保留人工核对。
2. **产品接线：** 新协调入口/匹配profile/新预算/同一审核状态机；首先离线fake HTTP覆盖，再在明确授权后执行少量真实浏览器完整链。真实发送与生产角色认证继续单独立项，毕业演示不需要。
3. **独立Gold：** 未参与开发的人准备新的分层场景，模板/同源翻译按族隔离；两位盲于模型输出的标注者与第三方仲裁，完整保存版本、时间、理由和hash。旧24/32/新40、N03变体都属于开发暴露，不能换名holdout。回复另按rubric真人评分，空项保持null。
4. **研究认证：** 预注册模型/Prompt/接受profile/首轮与纠错预算、严重漏报定义、失败/unknown/fallback分母；所有尝试均保留，字段一致率明确N×字段数、整封全对明确N，Issue匹配与回复质量分别统计。不能用待测模型生成的参考自证准确率。
5. **论文：** 使用本轮状态机、模块责任、真实截图及失败修复作为工程证据；历史400是程序模板合成，N04等是真实模型对合成输入的历史输出，不是真实消费者邮件；P3.10未达质量目标和所有独立人工pending必须披露。先交付诚实、可复核的单机系统，再做新授权的质量实验。
