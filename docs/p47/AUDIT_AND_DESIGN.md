# P4.7 实施前审计与兼容决定

2026-10-28 Asia/Shanghai。基线 fc48894；初始仅59项既有未跟踪研究成果（以本机baseline实际清单为准），未做清理或覆盖。完整hash与源码恢复副本在 `.local/p47-20261028/`。先完成源码、交接与实际浏览器审计，本文在业务代码修改前记录。

|类别|最早失效环节 / 证据|责任模块与本轮处理|
|---|---|---|
|UI|已有三栏，但默认预览与已存案例脱节；全局研究Tab与客服同级；重复下一步/审核表单使主流程像工作台|UI信息架构；沿用Streamlit稳定组件改成会话主区、明确队列、轻确认及次级研究入口，不重写底层|
|场景|product_demo/copilot_demo英文短句服务于测试，9条中有错误/失败/unknown，与正常客户案例混列|新增版本化中文场景目录，旧版本保持，错误示例收纳次级入口|
|内容|Keep it aside、No refund ... approved here来自预写策略，而非模型调用失败|新增回复策略及客户可补/商家应核实资料分离；共情、事实、下一步、权限与安全按场景组织|
|流程|全部案件同样三项核对+身份+说明，风险分层未影响操作路径|新增独立路由层，普通建议轻确认；不确定需人工确认；安全/权限/强烈情绪/明确要求人工需接管|
|门禁|闭集诊断始终review_required；风险错误在analysis scope阻断；不能靠改回复解除|原quality政策、Schema、Taxonomy不改；新路由不能充当semantic通过；高风险仍须安全核对|
|研究资产|raw/Gold/预算/旧SQLite/历史截图及未跟踪成果已有可复核身份|全部只读保护；新库与实验用独立目录；不改.env，不用旧授权付费|
|LangChain|RunnableLambda返回预写fixture；真实ChatOpenAI适配与持久化、QA Mock HTTP存在|明确来源标签与研究说明；无实时推理宣称；服务端live继续硬关闭|

因果基线核对：不把P4.5故意低估折叠车样例改成正确分析来掩盖门禁；新增正常severe/high折叠车场景并保留原错误分析。回复改善由新场景/策略负责，不放宽guard。轻审核改变产品交互，不改历史研究结论。

## 兼容与验收

保留 ProductStore SQLite v1、不可变版本/事件、MailThreads v1、分析契约及原问答库。允许在既有通用事件表追加request_handoff/take_over事件，状态仍是原审核状态，接管归属与审批状态分开；无Schema迁移。所有批准仍由显式操作者触发并写原审核事件，模拟发送复用原幂等回执与质量hash。普通路径仅在明确低风险、无不确定路由、无阻断情况下提供轻确认；高风险必须接管且原审核条件全保留。

新增场景身份包含输入hash、fixture hash、策略版本/hash；旧预写目录不变。任意输入仍unknown，需要人工，不夸大离线语义。客户输入人工客服可触发本地演示转交，未接真实坐席。

验收：保留全部445个原测试ID，新增路由/接管/轻确认/高风险阻断/内容与浏览器交互测试；完整离线及干净Portable；真实浏览器1366/1440/1024/768前后截图、普通→确认→模拟、高风险→接管→审核、坏分析不可绕过、多轮/问答/恢复、Dashboard/CSV兼容；受保护hash、白名单Git及精确SHA CI。

## 公开产品机制参考（2026-10-28读取）

- [Intercom升级机制](https://www.intercom.com/help/en/articles/12396892-manage-fin-ai-agent-s-escalation-guidance-and-rules)：明确人工请求、强烈不满、重复循环可触发转交。本项目借鉴分层，不复刻其生产能力。
- [Zendesk会话交接](https://support.zendesk.com/hc/en-us/articles/4408824482586-Managing-conversation-handoff-and-handback)：会话归属和AI/人工交接是独立流程概念，据此分离handoff与审批。

本轮开发代理审计与合成内容审阅不等于独立人工质量评估；研究者接受/拒绝留空。P5仍需真实模型新预算、独立Gold/holdout和正式业务政策。
