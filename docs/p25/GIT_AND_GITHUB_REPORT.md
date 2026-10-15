# Git与GitHub安全审核

本地P2基线：`5ffa9a9a6899dd2bd0fb4b402781fac273888dad`，提交信息`chore: establish verified P2 engineering baseline`，115个精确路径。初始仓库main无HEAD、28个部分P1暂存文件；已按当前P2工作树刷新审核清单，未把旧index直接冒充P2。有效的用户作者配置与已登录GitHub账号已核实，没有虚构身份。

恢复：修改前522个文件加完整.git（含index）复制到本机新恢复目录；路径保存在`.local/p25/recovery.json`，含本机敏感材料，不上传。旧备份全部保留。原累计README副本在`.local/p25/README.pre-p25.md`。冻结原262资产及本轮342资产hash不变。

## 上传范围

| 类别 | 处理/依据 |
|---|---|
| P1/P2/P2.5工程源码、tests、模板配置 | 逐路径allowlist、全部blob扫描、精确git add；包括未跟踪P2源码，保留兼容旧工程脚本 |
| 新最小合成fixture/P2开发者fixture | 明确人工编写/代理编写的非真实消费者工程数据，安全审核后包含；未含真实模型raw返回 |
| 400合成邮件/旧Gold | 已证实本地模板生成，但没有把来源核查冒充权属批准；保留本机，不上传文本，只传ID/hash/统计/覆盖证据 |
| .env/API Key/GitHub Token | .env忽略；扫描真实.env中密钥值与常见credential模式，报告只输出问题路径，不输出秘密；GitHub凭据在系统keyring |
| SQLite/.local/预算 | 全部排除，包括P2预算、运行库、raw输出、恢复材料 |
| 原历史outputs、P1/P2证据目录 | 保留本机，未外传原始历史预测/模型返回；新汇总重放指标与hash追溯单列 |
| 论文DOCX/PDF/图片、学校/导师资料、外部数据集 | 未确认外传权属，全部排除，未添加项目公开许可或第三方许可猜测 |
| 文档/配置的路径 | 必要工程文档有本机项目/临时目录示例；配置无客户身份/个人邮箱/密钥。新公开报告不含本机完整run路径清单 |

扫描入口`scripts/audit_git_payload.py --ref INDEX/COMMIT --output NEW_LOCAL_REPORT`读取Git blob，不仅扫描工作树。排除类检查、known-local-secret字节检测和token/私钥模式检查加人工文件类别审阅；不声称能识别所有未知秘密或法律权属。

## 可复现性

完整本机108项离线通过；干净检出不包含历史研究资产，不能运行全量历史回归并声称通过。`scripts/run_portable.py`使用安全自包含fixture运行28项工程与评价门禁，实际app.py通过AppTest保存/重读，默认禁用API。完整历史资产依赖和缺失边界已写入README。依赖使用已验证的本机venv，未做全新联网pip安装或依赖锁定验证。

目标仓库：[BillZhao626/customer-complaint-intelligence](https://github.com/BillZhao626/customer-complaint-intelligence)，仅允许Private。创建/推送前须再次核实无同名仓库冲突、origin和全部提交树；不force、不Tag、不Release、不公开。实际远程SHA、可见性、文件集合与干净检出测试证据将在完成推送后补录，避免先写成功再执行。
