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

目标仓库：[BillZhao626/customer-complaint-intelligence](https://github.com/BillZhao626/customer-complaint-intelligence)，仅允许Private。创建/推送前须再次核实无同名仓库冲突、origin和全部提交树；不force、不Tag、不Release、不公开。实际验证结果见下方；证据是执行后记录。


## 已执行的远程核验

**LOCAL_GIT_BASELINE_VERIFIED / PRIVATE_GITHUB_PUSH_VERIFIED**。

- 仓库URL：https://github.com/BillZhao626/customer-complaint-intelligence；GitHub API返回isPrivate=true。
- 第一笔P2完整工程基线：5ffa9a9a6899dd2bd0fb4b402781fac273888dad。
- 第二笔P2.5工程：7e3f5153654174aac79781e9744086ba3a5795b2。推送后local HEAD、origin/main、git ls-remote均一致。
- GitHub Git Trees API返回150个blob，未截断；路径与每个Git blob SHA均与本地该commit完全一致。两个commit的全部文件均重新扫描，0禁传文件、0已知密钥/模式命中。逐文件SHA-256安全清单与远程核验见[evidence/github-verified-tree.json](evidence/github-verified-tree.json)。
- 从远程新clone到本机空临时目录，确认没有.env、data、outputs、.local、论文资产；28/28 portable测试通过（8.301秒），实际app.py AppTest可运行；offline evaluator另外执行成功，5样本/4成功/1预期故障，28/35计分。没有运行缺资产的完整历史测试并误报成功。
- 为保留事后证据，另作一笔仅文档/证据的提交；工程受测SHA保持上面的7e3f515。该文档提交的最终SHA由git log与本机.local/p25/github-final-receipt.json记录，避免自引用hash问题。最终推送后继续核对HEAD与远程及完整文件集合，不force、不Tag、不Release。
- 本机原未跟踪历史资产仍存在；tracked工程无未提交修改。不能把“不上传这些资产”解释成已删除它们。

干净检出复验只使用已有venv，不是一次全新依赖解析安装；AppTest不是浏览器E2E。原始日志和clone位置保存在.local/p25/，不上传。原P2预算/运行库和.env保持原hash；全轮新模型调用0。
