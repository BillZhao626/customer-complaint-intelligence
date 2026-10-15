# P3.6 Git交付收据

起点main为`f51a4b315ac7a6f83aeabd799a0424c26af04537`，起点CI成功。用户授权完成安全检查与测试后正常提交/push源码和脱敏文档。

工程提交为`8c2a8bdf17957e93a57be83ab6a864887424d53c`，15个白名单文件。已正常推送并由GitHub API核对远程main。[工程CI](https://github.com/BillZhao626/customer-complaint-intelligence/actions/runs/38762562641)的portable job成功，包含全新Ubuntu安装依赖、pip check、78项离线检查及P3离线demo。CI不读取本机开发原文或真实预测，不构成语义评价。

本机165/165完整离线、78/78 portable；干净暂存树导出78/78通过。210文件Git载荷使用既有audit_git_payload审计通过、0问题；新增15个文件还检查没有完整本地研究正文。原1705文件中仅5个授权源码/测试入口/HANDOFF变化，其余1700原hash不变；46组既存未跟踪路径保留，既存文件内容未改。

完整研究原文、24题裁决/Gold、全部候选、原始真实预测、预算/SQLite、API Key均留本机。暂存使用明确路径白名单，没有git add全库，没有强推、Tag、Release、reset或clean。

首次普通直连push遇连接重置，随后按Windows已配置的loopback代理使用单次Git参数正常推送成功；未修改全局Git配置或关闭TLS校验。

本文为后续纯文档收据提交；最终HEAD、远程与对应CI查询保存在本机`.local/p36/git-delivery-receipt.json`，不要把工程提交SHA当作后续文档提交的SHA。完整报告见本机`.local/p36/PILOT_REPORT.md`，公开摘要见[VERIFICATION](VERIFICATION.md)。
