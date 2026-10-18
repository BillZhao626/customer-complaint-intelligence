# P3.11–P4 产品候选版交付入口

版本：**complaint-product-p4-rc1**，2026-10-18，Asia/Shanghai。工程候选；独立模型质量认证仍pending。未晋升P3.10 Challenger。

已实现完整纵向流程：输入邮件/真实run只读重放 → LangChain离线编排或原模型结果 → 结构化Issue/Evidence → 未审草稿 → 编辑版本和diff → 本地审核批准/退回/拒绝 → 仅模拟发送 → SQLite恢复、历史和Dashboard。

## 文档导航

- [实际架构与LangChain边界](ARCHITECTURE.md)
- [数据表、状态机、幂等和恢复](DATA_AND_WORKFLOW.md)
- [五项政策、因果归属与语义边界](POLICY_AND_CAUSAL_AUDIT.md)
- [可操作演示与启动方式](DEMO.md)
- [验收证据](VERIFICATION.md)
- [论文素材、历史结果及P5计划](THESIS_AND_P5.md)
- [冻结源码身份](candidate-manifest.json)

## 本机证据

|证据|仓库根目录下路径|
|---|---|
|原附件与研究者原文|`.local/p311/adjudication/`|
|14条身份/原接受状态；244条同raw分层诊断|`.local/p311/audit-final-v4/audit.json`|
|N03新自然开发版本|`.local/p311/audit-final-v4/N03-natural-v1.json`|
|37条闭集反例|`.local/p4/counterexamples-final.json`|
|10条纵向演示与SQLite重读|`.local/p4/demo-v1/acceptance.json`|
|实际浏览器操作/关闭重开/进程重启|`.local/p4/browser-acceptance.json`|
|真实运行产品截图|`.local/p4/screenshots/`|
|完整测试与故障注入|`.local/p4/full-frozen-v2.log`、`.local/p4/test-evidence/`|
|历史资产与预算不变核验|`.local/p4/protection-final.json`、`budget-readonly-verification.json`|
|分支、提交、普通push及精确HEAD CI|`.local/p4/git-delivery.json`|

本机研究附件、完整raw/诊断、预算、SQLite、截图及交付压缩包不随Git公开；源码、显式工程fixture、测试和脱敏文档可独立检出复验。公开检出缺少私人历史素材的检查会明确skip，不能把skip当作本机资产已验证。

## 能力边界

本轮新增付费调用0，真实邮件发送0，旧P3.9剩余1次未动，P3.10保持180/180锁账。严重分析错误无法由修改回复或勾选审核项绕过；复杂语义仍需人工审核。演示和自动化操作均标为demo_test；没有新增独立人类Gold、holdout或完整回复人类评分。

历史400封为确定性模板生成。自定义邮件的离线unknown占位不冒称新模型理解，真实结果演示使用历史输出。真实SMTP/CRM、生产多用户权限、生产负载与独立语义质量认证未实现，后续授权边界见P5计划。
