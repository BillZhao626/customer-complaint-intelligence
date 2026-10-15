# 当前真实端到端能力矩阵

**COVERAGE_MATRIX_VERIFIED**，基于当前源码和本轮108项离线测试。P2真实证据仅已保存的12条开发者fixture，不是本轮新增请求。

| 能力 | 实际实现/入口 | 自动测试 | 真实证据 | 语义/功能缺口 |
|---|---|---|---|---|
| A 输入与校验 | app.py→offline_slice→EmailInput，完整subject/body | test_contracts、test_streamlit、test_p25输入hash负测 | P2全部12输入hash+1次实际AppTest提交 | 实际浏览器上传/下载E2E未验 |
| B LangChain/DeepSeek调用 | deepseek.py、live_execution.py、预算claim/attempt/有限重试 | test_live：fake、SDK MockTransport、错误/超时/预算 | P2 12/12首轮accepted，0重试 | 不是生产可用性/SLO；新Prompt真实表现pending |
| C 七字段 | analysis-v2严格契约，business warnings | 契约、历史评测、字段分母/F1/版本隔离 | P2 83/84，旧80另为494/560 | 无独立Human Gold；合法JSON不是理解正确 |
| D 摘要/key_information/实体事实 | AnalysisResult.summary、key_information、product_name | 必填结构；新人工Rubric状态/hash门禁 | P2保存12份summary，只有代理定性审阅 | 关键事实、遗漏、编造、实体混淆的独立人工评价pending |
| E suggested_reply | 保存、显示未审核未发送草稿 | 必填结构、Rubric关键错误门禁 | P2保存12份草稿 | 事实/承诺/实用性人工评价pending；无发送批准 |
| F SQLite运行版本 | Repository、AnalysisService，claim、attempt、重读、幂等 | test_service/test_live/test_streamlit，portable smoke | P2 SQLite及UI新会话重读、幂等历史证据 | 单机SQLite，非生产并发与灾备认证 |
| G 门店/商品/来源统计 | 新service.aggregate支持store_location/product_category；旧Dashboard有来源分布 | 原14表复算、分母/成员/版本测试 | P2保存run可查询 | 新SQLite source聚合、别名/证据/不确定状态完整Dashboard仍P3 |
| H 成员与原文追溯 | member_run_ids→repo.get→UI Open member original | test_streamlit及e2e evaluator的成员、input/output/reference hash | P2运行与原文保存；并未真人逐项验全部浏览器交互 | 跨历史导入统一追溯仍未实现 |
| I failed/unknown/fallback/不确定 | 新链路失败持久化、无自动fallback、unknown桶、单版本筛选；旧批次拒收混合后端 | 故障注入、服务/UI状态、分母负测 | P2真实失败为0，故障语义来自离线注入 | 未把离线故障测试当真实API错误率；完整P3展示仍待扩展 |
| P4 人工批准/模拟发送 | 未实现 | 无当前通过证据 | 无 | 保留未来扩展，reply.ready_to_send恒false |
| 浏览器E2E | 未实施 | AppTest不等于浏览器 | 无 | BROWSER_E2E_PENDING |

本轮评价器的aggregate reference comparison会按source_attribution生成对照统计，但那是评测程序，不是已经新增产品SQL查询或P3页面。分层结果不能合并成一个“系统准确率”。机器能力清单见[evidence/e2e-capabilities.json](evidence/e2e-capabilities.json)。

P3进入条件：现有工程基线、契约、可追溯统计测试已具备，可继续离线开发；先明确source归属证据/unknown/failed/fallback分母、别名与版本兼容验收，服务边界进入人工规范审定。任何模型语义/经营结论需独立Gold及单独授权评测，不能以本轮工程通过代替。P4批准/发送不在本轮完成范围。
