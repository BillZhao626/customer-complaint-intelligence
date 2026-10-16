# P3.7 新旧策略与派生身份

旧Schema、Taxonomy、v3原始模型字段、SQLite schema均不变。P3.6的143/168、17/24、29/32保持原记录，不以新视图重算成绩。

|维度|旧策略（保留）|新策略（显式选择）|
|---|---|---|
|客户主次投影|customer-primary-v1|customer-primary-v2-safe，仍不以业务顺序制造客户primary|
|业务顺序投影|owner-operational-v1|owner-operational-v2-safe，仍明确有损业务选择|
|门店|直接显示mentioned_store|uncertain_mention/unknown/unavailable显示unknown；原v3保留原文提及|
|问题归属|直接投选中问题的business_process|unclear/inferred显示unclear，unknown显示unknown；建议团队不证明来源|
|多个流程无客户主问题|可按最前业务顺序投某个来源|不同未解流程且重要性未指定时，邮件级来源保留unclear|
|reported|无独立确定性字段|只代表客户报告的流程域，绝非已证实因果或法律责任|
|v2-origin|无损还原|同样还原，不假装恢复旧版未保存的确定性|

新旧策略在to_v2入口共存；默认仍customer-primary-v1，历史RunConfig仍选择原策略。新正式服务可在parameters.projection_policy显式选新版，存储读取按自己的原版本验证；不批量迁移旧库。

## 业务排序与边界

product-before-store-v1只实现P3.5已有明确业务依据：产品检查先于门店重新预约。需显式opt-in，只处理未解决投诉中equal且业务顺序并列的组，组内所有流程均须被该政策覆盖且可唯一决胜；安全high优先。客户重要性、原始证据、关系与responsibility=unverified保持不变。未知流程、相同流程、缺顺序、非equal或跨组安全冲突均保留原顺序并提示待决，不按sample ID/对象名称/数组顺序硬编码答案。

反例覆盖：同为产品流程不任意排序；物流不套用产品/门店政策；改名issue ID与倒置数组仍得同业务顺序；高风险门店问题先于低风险产品；已有明确客户primary不被改成equal。

新派生视图包含parent_run_id、input/config/output/raw hash、规则版本、规则源代码规范文本hash、策略依据、逐字段old/new/reason、analysis/projection hash与derived_id。它不是模型run，不进入原SQLite或原指标，失败无接受预测时不制造替代结果。verify_derived重算完整身份拒绝篡改。

完整重放最终29个成功run的3类派生视图，共87份；3失败仍缺预测。差异报告同时列同一选择语义的v1→v2配对比较，以及相对原P3.6业务投影的差异，避免把改选客户/业务视图混成新规则改善。

## 回复门禁

原v3-draft-gate-2-negation保留、默认不变。新增v3-draft-gate-3-scoped-review通过parameters.reply_gate_version显式启用：否定限定在谓词和分句，转折后肯定承诺重新检查；英文/中文已执行动作、无授权物质承诺阻断；预计/应该等模糊付款退款表述要求人工审；报告/条件语境不自动授予付款权限。无命中状态叫no_lexical_signal，不叫安全通过或人工批准。

门禁是可复核的保守词面规则，有漏检/误拒边界；它不替代摘要事实/证据语义/回复诉求的真人评价。保存的真实否定承诺回复经新gate正式validate_result离线通过，原failed和历史分母不变；另两份结构非法返回仍拒绝。

哈希口径：文件保护用原字节SHA-256；项目digest用于规范JSON以及其封装的字符串（包括raw_output）。Windows Prompt快照保存CRLF，实际发送system字符串为LF，重放分别核对文件字节hash、规范换行文本hash和attempt记录的实际Prompt hash，避免把文件换行与已发送内容混为一谈。
