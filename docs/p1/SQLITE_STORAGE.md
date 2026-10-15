# P1 SQLite 存储与迁移边界

实现：`src/infrastructure/repository.py`；数据库 `PRAGMA user_version=1`。仅保存本轮之后新运行，没有迁移历史 CSV，也不伪造历史 HTTP attempt/request/usage。

默认 `.local/runs.sqlite3`；通过 `COMPLAINT_DB_PATH` 配置。Repository 拒绝项目 data/outputs/docs 下的数据库位置，要求专用 .sqlite3/.sqlite/.db 后缀。`.local/` 和数据库/旁文件被 Git 忽略。测试全部使用临时目录，未将运行数据库放入文档或实验目录。

| 表 | 主键/约束 | 内容 |
|---|---|---|
| emails | input_id PK；UNIQUE(email_id,input_hash) | 完整 subject/body、外部 ID、输入 hash |
| runs | run_id PK；input_id FK；状态 CHECK | 输入关联、幂等键、cohort_id、配置 JSON、终态、时间 |
| results | run_id PK/FK | v2 normalized JSON |
| attempts | (run_id,attempt_no) PK；run_id FK | raw JSON 文本、阶段状态、错误、起止时间、warnings |

每个连接启用 foreign_keys，10 秒 SQLite busy timeout；使用 BEGIN IMMEDIATE 与单一事务保存 email/run/result/attempt。结果或 attempt 任一插入失败，所有新插入回滚，异常传至 UI；UI 不显示成功。成功事务提交后才返回从数据库重读的 receipt。

部分唯一索引 `successful_key` 对 status=succeeded 的 idempotency_key 唯一。同配置同输入先复用已有成功运行；并发在提交竞争时读取已有成功运行。四线程重复提交测试最终只有一个成功 run；不意味着已证明生产负载或 provider 调用恰好一次。失败重试创建新的 failed/succeeded run，失败记录保留，绝不作为幂等成功缓存。

查询每次新建并关闭连接；没有依赖 Streamlit session 的原文或结果。刷新通过 session/run_id URL 参数恢复，完全新 session 可输入 Run ID to reopen。统计下钻使用保存的 run_id。

迁移策略：仅初始化空新库/version1 的已知表；遇到未知 user_version 直接拒绝，不自动升级、清空或重建。后续变更应先复制关闭后的数据库或使用 SQLite backup API，增加迁移版本、迁移前后验证与回退方案。P1 不提供生产权限、加密、备份调度、跨主机共享和后台崩溃恢复。

源码恢复副本（未上传、排除 .env 和密钥）在 `docs/p1/evidence/baseline.json` 的 snapshot 路径。它是恢复修改前文件的材料，不应通过删除新数据库或覆盖历史实验恢复代码。Git 无 HEAD，不能依赖 reset/clean。
