# Analysis-v3 契约与兼容

实现：`src/domain/analysis_v3.py`；[EmailAnalysis JSON Schema](analysis-v3.schema.json)。邮件原文仍使用现有 `EmailInput`，hash=digest({subject,body})，保留换行和空格，ID另行绑定。EmailAnalysis包含原文、hash、RunConfig、实际返回模型（未知为null）和AnalysisV3。运行状态、attempt和原始返回仍由AnalysisRun承载。

邮件层保留sentiment（含mixed）、urgency、request_types、complaint_status、mentioned_store/store_verification、contact_channel、purchase_channel、summary、suggested_reply。Issue承载对象/类别/类型/reason、情绪、紧急度、解决状态、证据跨度、业务流程、分派团队、归属确定性/缺失证据、客户诉求/重要性、处理优先级和依据。relations仅支持有原文依据的equal_importance与reported_dependency；业务处理顺序不生成依赖关系。

`responsibility`目前只能是unverified，系统没有核实责任的证据接口。store_verification只区分原文提及/不确定提及/未知/旧格式缺失，没有“已核实门店”。unknown为缺信息；unclear为归属不明；none为不适用；unavailable用于v2没有保存的信息。resolved是原文报告的已解决，不是P4审批工单状态。

原生问题至少一条证据；零基Unicode字符位置、end不包含末字符，严格逐字匹配subject/body。重复issue_id、不存在的关系目标、无依据的重要性、无理由优先级、顶层与未解决投诉冲突、明确安全问题却非high均拒绝。证据出现在原文中仍不证明它支持模型的判断。

## 两种显式有损投影

`to_v2(value, policy)`支持：

- `customer-primary-v1`（默认）：唯一客户primary或仅有一问题时选它；无唯一主问题用unknown/other/unclear，不拿处理顺序改写客户偏好。
- `owner-operational-v1`：显式选择最前且唯一的业务处理顺序作为v2兼容对象，输出有损诊断，保留v3的equal事实。用于复现题10最终冻结v2参考；在RunConfig.parameters.projection_policy中绑定，不静默混版本。

size/fit issue→other；mixed→unknown；v3未知投诉状态只能投影false并显式诊断；v2无可用confidence，填0.0兼容哨兵并诊断，绝不当成校准置信度。证据、渠道、多个问题、生命周期、团队、主次和策略均不能由v2完整表达。新v3统计直接读完整结果，不能用兼容哨兵做语义统计。

`from_v2`保留完整compatibility_origin，`to_v2(from_v2(x))==x`。只创建一条legacy-primary、空证据、unknown解决状态和unavailable渠道，不宣称恢复了原文未保存的多问题。provider不得提交compatibility_origin；只接受native v3。

## 持久化与版本治理

沿用现有SQLite user_version=2及metadata_json列，无破坏性迁移。完整v3、output hash、兼容诊断存在run.metadata；result保存v2投影。离线保存修正为同时持久化metadata，成功写入与attempt仍同一事务。保存、重读和live完成前验证v3 hash/输入/config/投影绑定，篡改拒读。P2历史库没有打开或迁移，本轮新库在.local/p35或临时目录。

schema=analysis-v3、taxonomy=complaint-issues-v3；DeepSeek opt-in prompt=complaint-multi-issue-v3-1，prompt hash由Schema和系统文本计算。旧p2-frozen和service-boundary-v1原文不改。该profile沿用现有LangChain、请求预算、预写attempt、有限重试，不增加额外SDK重试。mock HTTP验证真实SDK路径，不代表实际接口或语义质量。默认UI不启用付费v3。

契约变化必须更新Schema、版本/兼容说明与测试；JSON Schema一致性测试阻止文档漂移，Pydantic补充跨字段/原文约束。新分析保留所有运行版本；兼容投影不是重算旧实验。

## 安全和功能边界

回复始终未审核、未发送。当前保守文本门禁阻断已知退款审批/付款承诺措辞，不是完整的幻觉/提示注入检测器，会有漏检和误拒；其余由绑定输出hash的人工Rubric检查。未经真实模型实验，不能宣布v3提取、摘要、归因或回复质量提升。未实施P4真实发送或审批状态机。
