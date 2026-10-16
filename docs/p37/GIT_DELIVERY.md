# P3.7 Git与保护交付收据

起点main为bcccd327d9bd92526374d4baef5e22aabd049ff9，用户授权安全审核后正常提交/push工程源码与脱敏文档。

工程提交`46d5ebeabad2c30dec39e46c8a66c68834cafc5e`已正常推送并经GitHub API核对远程。[工程CI](https://github.com/BillZhao626/customer-complaint-intelligence/actions/runs/38841650068)成功：全新Ubuntu安装依赖、pip check、110项portable及P3离线demo通过。CI不读取本机研究数据，不代表真实模型语义质量通过。

本机完整200/200、portable110/110；干净暂存树导出110/110。原165/78测试ID全部保留，分别新增35/32；无失败或跳过。pip check、源码内存编译和git diff检查通过。工程19个白名单文件、224个Git载荷用既有audit_git_payload审计PASS/0问题，新增载荷另查无完整本地研究邮件正文。

起点1962文件hash留存；仅6个授权旧源码/测试入口/HANDOFF变化，其余1956原文件不变。P3.6完整243文件、预算/SQLite/Prompt/原报告、24题、.env和所有原数据/outputs不变；46组既存未跟踪路径及其中原文件保留。所有新审核包、原文、改写提案、Gold、SQLite/预算与密钥只留本机`.local/p37/`，未进入提交。

本轮新增真实模型请求0次、0元；P3.6仍40次且锁止，未新增配置或开启其他额度。Git采用明确路径白名单及正常push，使用Windows既有loopback代理的单次Git参数，未改全局Git/TLS；无强推、重写历史、Tag、Release或清理用户资产。

本文是后续纯文档收据，最终HEAD/远程/最终CI保存在本机`.local/p37/git-delivery-receipt.json`；不要把工程提交SHA当作后续文档HEAD。完整交付索引见本机`.local/p37/REPORT.md`及[VERIFICATION](VERIFICATION.md)。
