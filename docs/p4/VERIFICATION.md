# P3.11–P4 工程验收证据

工程候选 `complaint-product-p4-rc1`。完整回复的独立人工评价、独立Gold/holdout和新真实模型再认证仍未完成；不据离线工程测试声称模型质量提升。

## 验证层次与结果

|层次|实际执行|证据|
|---|---|---|
|原回归基线|361项通过，无skip|`.local/p311/baseline-regression.log`|
|扩展完整回归|396项通过，无skip；包含原361个测试及35个产品测试|`.local/p4/full-final-v1.log`、`full-frozen-v2.log`及test-evidence|
|最终反例修复复验|35项产品测试通过，含5项实际app.py AppTest；普通否定责任表达及拒绝后间接重开状态反例|`.local/p4/product-final-v3.log`|
|Portable/CI|原Portable加全部P4产品测试，关闭外网；私有历史缺失明确skip；另跑公开P4纵向demo|`.local/p4/portable-final.log`、精确HEAD GitHub Actions收据|
|明确语义机制fixture|37条，6机制族；18预期信号、19预期无信号，作者预期FP=0/FN=0|`.local/p4/counterexamples-final.json`；非独立语义统计|
|来源/政策|14条run/input/raw/状态及附件hash核验；N33未纠错；244同raw分层诊断|`.local/p311/audit-final-v4/audit.json`|
|纵向服务/SQLite|10条场景，独立连接重读，integrity_check=ok，foreign_key_check空|`.local/p4/demo-v1/acceptance.json`|
|实际浏览器|普通咨询全流程、退回编辑v2再审并模拟发送、真实风险阻断并拒绝、Dashboard、新tab及真实服务重启恢复|`.local/p4/browser-acceptance.json`与screenshots|

最终小范围修复是在完整回归之后补充普通否定表达，并阻止已拒绝草稿通过退回状态间接重开审批，保留所有先前失败日志并对受影响的完整产品路径重跑。冻结源码身份见candidate-manifest，精确Git/CI状态及最终日志以本机交付收据为准。Python内存编译和 `pip check` 通过；不运行历史付费API脚本。

## 用户场景验收矩阵

|场景|输入/分析/证据/草稿|审批或拒绝|重读/历史/统计|实际浏览器|
|---|---|---|---|---|
|普通信息咨询|明确offline fake，单Issue及Evidence|审批→模拟发送|SQLite、AppTest新会话恢复|完成|
|多Issue不同顺序|三Issue分别Evidence；主次与顺序分列|审批→模拟发送|SQLite和实际app.py AppTest|本轮未逐个浏览器操作|
|严重潜在风险合规fixture|severe/high，停用且不复现|额外安全核对项后审批/模拟|SQLite和AppTest|已浏览器验证真实风险错误阻断；合规fixture用AppTest|
|结构化契约失败|raw诊断，无法创建草稿|服务端禁审禁发|失败单列，业务分母排除|AppTest覆盖，未逐个浏览器操作|
|分析器失败|保存analyzer_error及运行身份|无草稿，无发送|SQLite重读与失败分母|服务集成覆盖|
|回复需修改|未授权未来联系承诺被拦|退回→编辑新版本→重新审核→模拟|v1/v2/diff、事件和回执绑定新版本|完成|
|拒绝草稿|原分析保留，记录原因|拒绝后不能直接批准或模拟|历史和状态统计|完成真实N04重放拒绝|
|页面/服务恢复|已批准v2及receipt持久化|重开后锁定模拟终态|服务进程重启、新tab、所有3个案例摘要一致|完成|

## 故障与边界

产品集成测试包含：未审核/拒绝/失败/安全block发件，未知动作，缺身份/原因/核对项，旧页面revision、并发批准、重复operation_id/请求hash冲突、重复批准/发送、已发送编辑拒绝、已批准编辑失效、策略身份变化后拒发、SQL/事件写入异常回滚、提交后读失败的幂等恢复、来源与草稿完整性、只读历史、已有库版本拒绝迁移和FK一致性。

浏览器验收使用实际页面点击和填写，保留截图及SQLite记录。自动操作身份为demo_test；没有签署独立人类内容评估。浏览器驱动个别定位超时通过重新观察和可见标签处理，未当成产品成功；截图仅在已观察到最终状态后保存。浏览器未逐项覆盖附件上传/下载、全部旧研究面板、多用户/移动端/生产负载，以上没有被AppTest冒称已验证。

## 历史资产及预算保护

初始5,544个非运行时文件逐一hash保护，含旧未跟踪资产、原raw/Gold/实验/账本及.env。允许变化仅本轮公开工程入口、离线runner、CI、README/HANDOFF；完整差异在protection-final。旧预测、旧分母、预算、数据和历史指标不被回填。

只读直接核验P3.10 ledger：180 reservations、180 outcomes、0 leases、halted=`authorization_request_limit_180_complete`。P3.9 shared envelope：71 usage receipts（旧1+固定64+探索6）、0 leases；最后1次未消耗。新增付费0、真实发送0。没有预算克隆、Gold签署、强推、主分支合并、正式Release或真实外部业务写入。
