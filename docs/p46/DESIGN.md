# P4.6 实现前依据与兼容方案

2026-10-28，基线 `6cdb7ee1fb51a0d2b02a22bd0e561572d9bf0c57`，PR #3 头 `f5fa68850e4d4af428ba952cc07bf49f58e89468`。P4.5 源码、线程 sidecar、418 测试 ID、历史截图均在。工作树只有既存未跟踪研究成果，独立保存清单及 11,743 文件哈希于本机 `.local/p4/p46-20261028/baseline.json`；源码恢复副本也已保存。

采用白底、蓝紫强调、左收件箱/中消息与编辑器/右 Copilot 的会话信息架构。1366/1440 桌面三个独立区域；1024/768 使用工作区域切换，避免把三栏压成不可用的表单。业务分析、研究工具独立导航。普通用户不显示数据库路径、Run ID、Hash。客户邮件保留原语言，所有预写建议标为内部演示。

本机 Streamlit 1.57.0 的实际签名确认 container(height/key)、dialog、popover、tabs 可用；核对官方 [container](https://docs.streamlit.io/1.57.0/develop/api-reference/layout/st.container)、[dialog](https://docs.streamlit.io/1.57.0/develop/api-reference/execution-flow/st.dialog) 文档。只使用有语义的自有 key 类与 data-testid，不用随机类名。没有证据表明需要迁移前端。

持久化仍为 ProductStore v1 + P4.5 不可变线程 sidecar。不迁移 Schema、Taxonomy 或旧研究库。唯一应用协议增量：`insert_suggestion` 事件使用既有 drafts/events 事务，来源绑定原始建议 hash/run/input，显式替换或追加，即使正文未变化也建立新版本并撤销旧审核；已拒绝的草稿仍必须实际修改内容才能重新开启审核，不能用同文插入绕过。所有修改仍受 revision、质量门禁和终态保护。编辑器未保存内容按 case/version 隔离在会话内；刷新只恢复持久化版本，不声称未保存文本已经落库。

验收：保留全部旧测试 ID；增加插入来源/同文重新审核/追加/旧页冲突/终态/串案测试。完整离线与干净检出 Portable；真实浏览器四尺寸、选择同步、插入与覆盖选择、编辑 Diff、审核与幂等模拟、第二轮、阻断、来源、业务下钻及旧 CSV/Evaluation。资产逐字哈希、脱敏审阅后普通提交/push，故障时核对 Git 对象再使用 API。新模型请求和 SMTP/CRM 发送始终为 0。
