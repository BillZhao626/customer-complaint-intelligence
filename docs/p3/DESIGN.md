# P3 归因与统计冻结（2026-10-15）

依据：P2.5 ANNOTATION_GUIDE、EVALUATION_PROTOCOL、analysis-v2，以及旧生成器的 purchase_channel / expected_source_attribution。本轮用户授权实施；不改冻结 Prompt、taxonomy、SQLite schema 或旧 14 表。

|概念|正式用途与边界|
|---|---|
|store_location|邮件明确提及的门店；不代表责任方。原文精确值分组，无获批别名表，故不猜测合并。|
|product_category|主要商品或服务对象。明确预约/安装/服务咨询可为 Service/Other；缺对象为 unknown，不能把 unknown 兜底成服务。|
|complaint_reason|主要投诉内容：如迟到、退款请求。咨询/赞扬非投诉为 none。|
|source_attribution|预测的主要业务归属，五个具体类别；不是已证实因果或法律责任。运输迟到可对应物流，联系热线不自动对应客服责任。|
|channel|联系/接收渠道；旧 purchase_channel 是购买渠道，也不能冒充联系渠道。analysis-v2 没有该字段，新 Dashboard 显示 unavailable，不从来源归属推断。|

unknown=信息或模型判定不足；unclear=投诉存在且多方归属不清（如店铺/快递均可能）；none=不适用（非投诉）；unavailable=没有保存字段、缺结果或 legacy adapter 未提供。failed、running、interrupted_or_unknown 是运行状态；fallback 单列并排除业务成功分母。unknown 不是失败；none 不是 unknown。模型声称的 key_information 不是人工确认的原文证据。详情显示全文与未审核模型线索，禁止伪造归因证据跨度。

## 兼容与查询决定

新增普通 Python AttributionService，接收只读运行源和可选 P2.5 Sample manifest；原 AnalysisService.aggregate 保留原定义。Repository 增加单独 ReadOnlyRepository：URI mode=ro、query_only，禁止初始化/迁移/过期状态写入。P2 使用冻结 run JSON 与固定 fixture 绑定，不打开历史预算或运行库。旧400仅原页面 historical-only；没有现代 cohort 元数据，不导入伪造。

来源、dataset hash（有 manifest 时）、backend/model/prompt/schema/taxonomy/config hash 均展示；一次快照只允许一个来源与 config cohort。时间采用带时区 ISO-8601 的闭区间，先时间再每 email_id+input_hash 取最新运行（created_at、run_id 排序）；同输入失败重试不重复计邮件。变更正文是独立邮件修订版，明确标注计数单位，不宣称独立消费者。记录 superseded IDs 和所有过滤条件。无法注册来源的 SQLite 邮件标为 unregistered，不能声称某个实验数据集。

## 分母

全部邮件修订版=所选时间/状态/门店/产品/情绪过滤后的最新运行，包括失败与 fallback；successful=成功、有结果且无 fallback；complaints=successful 中 is_complaint；valid_attribution=complaints 中五个具体来源类别。投诉/负面同时提供全部邮件及 successful 两种比率；门店/产品和交叉分布以 successful 为分母，原因和来源分布以 complaints 为分母；另提供成功集的来源状态桶及具体来源/valid_attribution 分母。零分母为 null/UI unavailable，不默认为0%。筛选业务字段会排除无结果运行，界面保留筛选前状态数和被排除数。

每项 metric 包含 numerator、denominator、denominator_name、rate、member_run_ids、denominator_run_ids；snapshot 包含成员 sample/input/run/output/config hash。未运行的 manifest 样本单独 missing，不能伪造 run ID，运行统计不声称覆盖全部候选。

## 验收

显式 fixture 涵盖 Service/Other、unknown、unclear、none、failed、fallback、uncertain、版本变化、重复尝试、空分母。核验每项成员集合、最新运行/版本/时间隔离、只读重读原文、参考与预测聚合差异；AppTest 实际 app.py 过滤/下钻；浏览器独立执行离线操作后才记录 VERIFIED。原108离线测试及历史哈希保持。人工校准包不预填身份、不签署、不改原参考；真实模型修复继续 pending。
