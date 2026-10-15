# Public发布安全审计

2026-10-15。目标：[BillZhao626/customer-complaint-intelligence](https://github.com/BillZhao626/customer-complaint-intelligence)。起点main为385dc501e4fb1b8793896bc3b6ae3c7c2a71795a。

用户在本轮明确允许历史QQ提交邮箱公开，同意自有源码采用MIT。原Git作者与提交者均为现有仓库身份BillZhao626，未代改身份、重写历史、强推或删除Git对象。自有源码/工程说明/新开发fixture采用MIT；学校材料、第三方数据、论文及历史研究资产不在许可或上传范围，详见LICENSING.md。

## 全历史范围

`scripts/audit_public_history.py` 检查所有heads/tags/remote refs的可达对象，包含每个提交树、历史删除blob、提交/Tag元数据、已知本机秘密和凭据模式、禁传路径/文件类型；另输出个人信息、绝对路径与版权声明候选供人工式逐项复核。提交前原3个commit、39个tree、154个blob无密钥、真实.env、SQLite、账本或禁传资产；只有main远程分支，无远程Tag。后续新增提交继续扫描，最终对象清单见证据。

复核：历史文档中的绝对路径仅为D盘项目路径和D:/TEMP实验恢复路径；没有用户主目录、密钥内容或完整真实客户信息。历史fixture为明确合成原文。没有vendored第三方代码或未公开学校/导师材料；项目权属依据所有者授权，扫描不作法律认证。Git元数据含QQ邮箱，已获得本人公开许可，报告不重复抄录完整邮箱。

初次额外扫描发现本机 `refs/codex/` 应用快照包含未跟踪历史研究资产，它们不是待公开分支历史；保留本机、不推送。不使用mirror/all refs推送，仅明确推送 `HEAD:refs/heads/main`。最终以远程全部branch/tag树和本地main逐blob核验。

秘密扫描不是未知秘密或权属的绝对证明；安全结论限定于检查过的对象、路径、模式、来源及手工复核候选。

## 可复现与操作依据

README包含原型定位、模块与运行方法、合成来源、98.81%的12×7字段分母及非独立性质、旧400不能作市场排名、Human Gold/浏览器/回复边界。CI无密钥输入、无模型调用，最低contents:read权限，portable runner阻断外部socket；安装依赖单独联网。安全文件清单在 staged/commit audit 中，未提交本机无关历史资产。

已于执行前核查 [GitHub CLI官方参数](https://cli.github.com/manual/gh_repo_edit) 和 [可见性影响](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)：公开后代码及历史可被任何人查看/复制，Actions历史和日志可见，fork关系与安全功能可能变化。只在邮箱、许可、完整历史与CI门槛通过后执行 `gh repo edit ... --visibility public --accept-visibility-change-consequences`。

当前操作结果将由本文件后续验收段和 `evidence/github-final.json` 记录；准备通过不自动等于PUBLIC_VERIFIED。
