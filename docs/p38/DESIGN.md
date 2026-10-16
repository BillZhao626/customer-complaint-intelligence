# P3.8 契约演进决定与验收

2026-10-16，研究者本轮明确授权八项未来政策、v3.1最小扩展、数据采用与离线接线；新付费调用0次/0元。

源码依据：旧 `Issue.consistency` 强制安全投诉high；reason/process无发票枚举；原文证据逐字校验但不证明语义支持；importance、priority、relations已分开。SQLite原metadata列可保存新契约，不需DDL迁移。

采用独立 `analysis-v3.1` / `complaint-issues-v3.1`。继承既有字段，新增问题风险等级/依据、紧急程度依据、政策身份和回复语言；安全minor可medium，severe必须high。新版本不接受v2 origin；旧v3模型、Schema快照与严格安全约束不变。原始响应、完整预测、兼容派生分别有hash；SQLite按schema精确分派读取和校验，拒绝版本错配。发票路由customer_support仅为协调建议；v2投影reason=other、source=unclear并诊断，无虚构refund或客服过错。

政策检查只阻止可确定的结构矛盾及有限明确危险表达，无法程序证明全部自然语言蕴含；语境、漏识别、摘要和回复有用性继续人工pending。合同测试不作为模型质量证明。

数据采用另建快照：原172记录保留、11旧文superseded、11新文不继承reference/prediction；20保留、1对抗、128未审、12质量隔离。数量从实际状态计算。记录版本血缘、输入hash和保守泄漏组件，全部开发暴露，不产生holdout。

A/B选择方案二：同一v3.1、最小迁移基线A与业务优化B。A不是P3.6冻结Prompt。模型别名、采样、Schema、证据目录、投影、gate、预算和输入相同；仅Prompt指令变化。64计划请求+最多8复验是未来建议，不是授权。当前可执行预检、离线fake演练和配对评价；付费入口硬拒绝零授权，后续必须新授权、核价、独立账本和4对冒烟门槛。

验收：旧200/110测试不删改expected；新增政策反例、v31原生/旧v3拒绝、service/SQLite重读与篡改、分母、数据血缘、审核反伪签、零预算与A/B身份漂移、AppTest和浏览器实际UI。历史P3.6的40请求、143/168、17/24、29/32及锁止账本只读复验；所有起始资产逐字hash复核。
