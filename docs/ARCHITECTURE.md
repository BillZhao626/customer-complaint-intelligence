# 架构与源码导航

应用由 React 工作台、FastAPI 接口、Python 应用服务和 SQLite 存储组成。模型生成、确定性校验、业务动作和人工审核分别保留依据。

| 任务 | 关键实现 | 数据流 |
| --- | --- | --- |
| 邮件输入与会话 | `src/application/mail_threads.py`、`src/domain/contracts.py` | 原信、上下文及输入哈希 |
| 分析编排 | `src/application/r6u0_workflow.py` | 消息 → 分析 → 规划 → 草稿 |
| LangChain 调用 | `src/infrastructure/p5b8r3_execution.py`、`structured_reply_provider.py` | ChatOpenAI、ainvoke、工具参数输出、受控请求 |
| 结构化校验 | `src/application/p5b8r1_contracts.py`、`p5b8_pipeline.py` | JSON、类型、问题编号及逐字引用 |
| 回复与业务工具 | `src/application/service_response.py`、`p5b5r2_pipeline.py` | 诉求与事实 → 本地查询/事项回执 → 回复上下文 |
| 草稿和审核 | `src/application/product_workflow.py` | 版本、修订号、状态、检查和审查事件 |
| 风险与评价 | `src/application/p5b8r2_guard.py`、`src/evaluation/` | 事实、安全、动作依据及辅助评分 |
| 统计与下钻 | `src/application/research_insights.py`、`p5b8r5_insights.py` | 去重邮件成员、分子分母及原文 |
| Web API | `src/app/p5_api.py`、`p5b5r2_api.py`、`p5b8r5_api.py` | 会话令牌、请求校验、工作流及查询 |
| 前端 | `web-client/src/p5b5.tsx`、`research.tsx` | 邮件、分析依据、事项、审核、统计 |

## 持久化与迁移

迁移沿用实际应用的初始化和幂等升级方法，没有额外的 Alembic 目录。

- `src/application/product_workflow.py` 创建草稿、工作流、事件、模拟发送表，并协调 revision 与 version。
- `src/infrastructure/repository.py` 保留分析运行存储与已有升级逻辑。
- `src/infrastructure/copilot_repository.py` 创建知识条目、问答运行、操作记录与相应升级。
- `src/application/mail_threads.py` 维护消息、会话与关联。
- `src/application/p5b5r2_pipeline.py` 保存本地业务事件及幂等身份。

离线启动对全新临时目录执行同一初始化路径，退出后移除临时数据库。原始保存回复从 examples 载入，不以 UI 编辑覆盖这些文件。

## 输出工具与业务执行

回复输出工具约束模型如何返回草稿；业务工具则是应用层执行的资料查询与内部事项记录。只有 matching input、task、scope 的回执能支持相应动作声明。一个 pending 内部请求不代表外部售后或配送已完成。

## 运行记录

详情页保存模型分析和工作流事件，可用于核对输入、结构和输出。展示名称按实际记录内容理解；本项目没有以这些 JSON 声称完整的 LangChain 调用 span 瀑布图。
