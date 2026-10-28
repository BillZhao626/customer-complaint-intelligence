# P4.5 客户邮件处理与回复助手

2026-10-27，基于 P4 Final（`f5fa68850e4d4af428ba952cc07bf49f58e89468`）增量实现。当前是可操作的离线演示与历史重放候选版。新模型调用 0，真实 SMTP/CRM 发送 0；工程验收不代表模型准确率或独立人类语义验收。

## 入口与信息架构

`app.py` 默认打开「智能接待」。1366×900 首屏同屏展示邮件、回复编辑区、主要操作和判断依据。左侧为历史邮件、状态和场景；中间为当前原文、回复、审核、版本与往返；右侧为客户诉求、原文 Evidence、风险和待补信息。正常操作无需展开 JSON 或运行身份。

「业务分析」独立呈现来源版本组、统计分母、状态筛选、六种维度和原文下钻。「研究与开发者工具」保留四个旧入口、历史真实 run 重放、完整原始输出及事件；每个旧组件单独处理异常。数据路径和完整 hash 位于开发者详情。

首次空库预览不写数据库。点击「载入邮件与回复建议」才建立案例。主操作随草稿是否修改、是否批准而变化；审核清单和说明仍必需。模拟发送终态显示保存回执和后续邮件入口。未经保存的编辑不会进入邮件历史。

## 代表场景与回复依据

演示数据由本轮开发代理显式编写，版本 `p45-authored-context-v1`，与旧 P4 fixture、400 封模板合成集和历史模型结果分离。

| 场景 | 已知诉求与证据 | 回复处理及缺口 |
| --- | --- | --- |
| 相机有线连接咨询 | 没有故障，询问功能；非投诉 | 请求具体型号；需商家官方规格，不凭空确认有线能力 |
| 第二轮相机来信 | 客户提供 DemoCam C200 | 回复引用新增型号，不再重复索要型号；型号仍未经核实，官方规格缺失，不能建议购买适配器 |
| 抽屉／旧床取件／发票 | 三个独立 Issue，分别绑定原文 | 提醒避开碰撞、索要预约编号、核对发票漏项；不承诺已预约、已联系或已解决 |
| 包裹已送达但雨淋 | 包装湿损，无延误陈述 | 保留已有照片与包装，询问订单及本体受损情况；原因 other、业务来源 delivery/logistics，不擅自判为 delay |
| 冷空烤盘承重把手脱落 | 无人受伤仍存在可预见严重伤害 | severe/high，停止使用、不复现故障，转人工安全复核 |
| 折叠车风险低估样例 | 故意错误的 minor/medium 分析通过结构契约 | 独立质量门禁阻断；修改成安全回复也不能批准或模拟发送 |
| 台灯不当承诺 | 预写回复含未验证执行承诺 | 修改后保存新版本，再审核；不得把回复润色当分析纠错 |
| 契约失败／服务失败 | 无可信结构化结果 | 保留输入和失败状态，无可审核草稿 |
| 任意自定义邮件 | 非预设输入 | 显示「未进行AI理解 · unknown流程占位」，不套用相机分析 |

这里没有已验证的商品知识库。`DemoCam C200` 只是演示型号，不能作为真实规格依据。现有边界宁可保留缺失信息，不把虚构知识包装成检索结果。

## 最小邮件往返与兼容性

实现位于 `src/application/mail_threads.py`。原产品 SQLite v1、原分析契约、原研究者政策保持不变；新线程存在独立 `*-threads.sqlite3`，`user_version=1`。父子关联和上下文有 hash 及不可变触发器；陌生数据库拒绝初始化。客户消息保留原文；客服消息仅来自已保存模拟回执，包含发送方、时间、case/issue、来源和 hash。

父案例必须已模拟发送且无阻断，才能建立子案例。每个父案例一个后续节点；同输入重试幂等，冲突不覆盖。关联写失败后可重试并复用已保存分析。新案例仍走原分析校验、质量门禁及审核流程。相机第二轮严格匹配初始输入、后续主题和正文；任何其他后续文本只保存角色上下文并返回 unknown。第三轮以上可保留消息，但没有动态多轮语义推理。独立 sidecar 与产品库不是跨库原子事务；异常时保留已写分析，重试恢复，不删除历史。

## LangChain 的真实执行路径

| 路径 | 源码与作用 | 本轮状态 |
| --- | --- | --- |
| 当前客服示例 | `copilot_demo.CopilotFake` → `RunnableLambda` → `ReplayV31` 按输入 hash 返回预写 JSON | 实际运行；不调用模型，不做检索 |
| 统一应用服务 | `ProductAnalysis.submit` → `AnalysisService.analyze/validate_result` → JSON/Pydantic `AnalysisV31` 与原文 Evidence 校验 → 分析库 → `ProductStore.create` → 质量门禁、版本审核与模拟回执 | 实际运行；契约接受不等于语义正确 |
| 上下文 | `MailThreads.assemble_context/follow_up` 将角色与消息文本显式组装；context hash 绑定 analyzer config | 实际运行；没有隐式 Agent memory |
| 真实 SDK 适配 | `src/infrastructure/deepseek.py` 的版本化 messages → `ChatOpenAI.ainvoke`，禁用 SDK 重试／缓存／tracing | 既有能力，Mock HTTP 离线回归覆盖；新付费请求未启用 |
| 旧兼容链 | `src/chains/langchain_complaint_chain.py` 的 `ChatPromptTemplate`、`ChatOpenAI`、旧 JSON 解析 | 保留独立入口，不与预写演示拼称为实时推理链 |

来源必须区分：离线 Fixture／unknown、历史真实 run 重放、真实 SDK＋Mock HTTP、未来新真实请求。UI 强制关闭 paid/live/tracing，不读取旧剩余额度发新请求。历史重放保留原输入/raw/契约状态；业务统计按完整来源及版本组独立计算。

## 启动与验收

使用已有 Python 环境。下面的输出目录必须是新的；脚本遇到已存在目录即拒绝，不覆盖历史。

```powershell
.\.venv\Scripts\python.exe -B scripts/p45_demo.py --out .local/p4/NEW_P45_DEMO
$env:COMPLAINT_PRODUCT_DB=(Join-Path $PWD '.local/p4/NEW_P45_DEMO/product.sqlite3')
$env:COMPLAINT_DB_PATH=(Join-Path $PWD '.local/p4/NEW_P45_DEMO/legacy.sqlite3')
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

脚本创建九个分析案例，草稿均未审核；两种失败案例没有草稿。浏览器演示选择 `demo_test`，不会代签独立人类评价。原 CSV 仍为 legacy_mock，导出到新的 `.local/exports/` 文件，不写 P4 审核库。

研究者人工复验清单：

- [ ] 首屏读清当前客户邮件、回复和缺失信息。
- [ ] 相机第一轮不编造规格；第二轮引用新型号且仍等待官方资料。
- [ ] 展开三个 Issue，逐项核对原文与回复覆盖。
- [ ] 修改、保存、查看 Diff、核对清单、批准、模拟发送；再刷新查看回执。
- [ ] 风险低估案例编辑后仍阻断；冷空烤盘仍 severe/high。
- [ ] 切换业务来源与状态，确认分母、未知值和下钻原文一致。
- [ ] 确认自定义邮件是 unknown，历史重放不冒充新请求。
- [ ] 独立判断回复语义和产品体验。此清单尚未由研究者签署，human_score 保持 pending。

真实截图、测试及浏览器点击路径见 [VERIFICATION.md](VERIFICATION.md)，实现前依据见 [DESIGN.md](DESIGN.md)。
