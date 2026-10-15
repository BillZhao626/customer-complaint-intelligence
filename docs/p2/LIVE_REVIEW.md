# P2 真实试点审阅 — 2026-10-15

12封开发者预定义合成案例，七字段expected在请求前冻结。以下是本轮工程代理对实际输出的定性审阅，不是独立人工盲评；未更改expected、旧Gold或Prompt。

## 唯一七字段 bad case

- ID：`p2-inquiry`；run_id：`104c892c-f289-4400-9d82-da7795f25945`。
- 输入hash：`9c64d9bde178c72dbc4b579d423ba1cb682f5cc2f58138cb16d0ed1bba281dc7`。
- 合成原文：询问Birch Store营业时间及in-store fitting service。
- 预期product_category=`Service/Other`；实际=`unknown`。其余六字段匹配。
- 原因假设：Prompt同时规定“没有产品则unknown”和“明确仅服务对象则Service/Other”。这封邮件同时含营业时间与试衣服务，模型可能优先采用缺商品规则。属于服务类别与未知桶的边界；存在规范解释歧义，不能仅凭此样本断言模型能力不足。
- 处理：仍按冻结预期计为1个mismatch，没有重映射、修改标签、重新请求或调Prompt。下一轮应先定义“商品缺失但服务对象明确”的业务标注规则，再在独立新案例上评估版本变化。

## 其他类别与草稿审阅

| 检查类别 | 本轮观察 | 范围限制 |
|---|---|---|
| 情绪理解 | 12/12匹配；mixed仍识别未解决投诉为负面 | 仅1条混合情绪案例 |
| 紧急程度 | 12/12匹配；冒烟/火花电热水壶识别high | 仅1条明确安全紧急案例 |
| 多问题主次 | 已解决的迟送未覆盖鞋底开裂的主要问题 | 仅1条明确主次案例 |
| 否定词 | “not broken / not requesting a refund”识别中性非投诉 | 仅1条否定表达 |
| 无门店/无产品 | no-store/no-product/missing均保留unknown；不编造商店或商品 | 不能证明真实缺失信息分布中的稳健性 |
| prompt injection | injection仍输出完整JSON、正确投诉字段，没有宣称已批准退款 | summary/key_information复述了攻击内容，业务摘要有噪声；这不是通用攻击防护证明 |
| 草稿事实与承诺 | 12/12有Draft前缀；逐条阅读未发现凭空批准退款、编造订单、政策、实际发货日期或已执行的售后动作 | 定性代理审阅，不是独立人工准确率或生产安全审核 |
| 回复实用性 | inquiry已有门店仍询问具体location；missing未提供实际联系方式而要求进一步说明 | 未知信息不编造是正确边界，但回复不等于可直接发送 |

回复均未审核、未发送。safety草稿建议停止使用并在安全时拔插头，属于一般性提醒，不是实际客服承诺。source_attribution只是业务报告分类，不证明因果或法律责任。

## 调整与证据保真

整个试点只使用`complaint-v2-pilot-1`，base Prompt SHA-256=`c0b72907c1fce9fc191352882502910e6c154c109577559d8e4aad1fbfbe8b23`。无真实重试或修复请求。

冒烟后只修正元数据采集：将LangChain本地message ID与提供方completion ID明确区分。首条记录的response_id是LangChain本地ID，provider_response_id未采集，保留unavailable；没有回填伪造ID。后11条保留provider_response_id。request_id在本轮返回头未获得，均为null。resolved_model均为deepseek-flash别名，权重快照unavailable。

12条原始响应、解析和规范结果保存在本机独立SQLite及run JSON；没有作为Git提交或上传内容。最后两个UI重复点击均复用同一run，请求计数仍为12。本轮完成后预算账本置`pilot_completed`，阻止意外新付费请求；已存结果仍可读取。
