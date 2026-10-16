# P3.9-v2 获批上下文规则的正式冒烟接线

研究者已批准候选9a0e63fb…、差异包a9117074…及urgency-context-evidence-v1接受规则。新执行层不修改任何获批Prompt、Schema、规则、32输入或64步交错计划；原v3.1默认及P3.9-v1失败保留。

AnalysisService→原live_execution→ContextLiveAnalyzer（原P39Analyzer传输/请求审计）→获批ContextOfflineService.validate_result→ContextLiveRepository→新连接只读重读。A/B使用原获批RunConfig逐字段相等（仅原已批准的arm/Prompt身份不同）。新增执行源码hash独立绑定candidate、runtime、SQLite metadata与收据，不覆盖候选processing_chain_hash。

唯一共享封套保持原root、历史失败1次及保守预留；只追加comparison批准、live_wiring、wire_claim、wire_payloads、wire_stops。原events/lease仍执行累计72/¥10及65计划上限；wire_claim跨并发/中断阻止重复发送。SDK/application/json repair均0次重试，单次4000输出上限；未知发送保留锁与费用预留。生产封套和runtime均唯一固定路径，无新授权创建、重置、复制或剩余阶段执行入口。

验收：离线fake走正式编排、持久化、只读重读、幂等、8输出收据；真实SDK MockTransport验证两臂完整消息/配置一致；失败/未知发送/身份漂移/用量/缓存/请求体异常停首条；批准身份/源码漂移拒绝；完整及portable回归通过后才能调用。GET /models是只读可用性验证，无推理探针；当前官网价核验独立留存。

仅执行前4对8次，之后无自动付费路径。收据只证明工程完成；18维AI候选、Issue语义、证据含义、摘要回复质量与内容安全仍须研究者确认。所有回复是未发送草稿，非独立Holdout。

## 2026-10-17 实际结果

预调用完整286、干净导出192项离线检查通过后，新增真实请求3次、收到3、接受2、失败1，累计含原v1共4次。第三次source证据校验拒绝repeated_failure依据，执行立即停止、封套halted，不发剩余5个smoke请求或remaining56个请求。原raw与失败状态保留，无修答案、无重试、无profile/Prompt变更。

首完整对支持普通具体咨询low+other，两条也能通过旧验证器；不能仅凭此证明接受语义或B整体改进。原文跨度、JSON形状通过仍可能有错误basis、把一起跟进当equal、摘要扩大诉求层次或回复未经核验渠道/联系承诺。自然不急同义表达也暴露有限校验的覆盖边界，后续任何语义改动需新差异确认。

停止收据绑定实际3输出，不伪造8输出smoke pass。新增通用离线反例保留获批行为以记录上述边界，不放宽规则。累计保守预留¥0.170360，高峰未命中估算¥0.060874，实际账单未知。最终完整290项通过；最终干净导出、历史保护及Git/CI见本机交付收据。所有真实原文/raw/内部预算只留本机，不进入Git。
