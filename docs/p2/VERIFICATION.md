# P2 验证与交接

2026-10-15（Asia/Shanghai）。状态：**P2_ENGINEERING_VERIFIED / REAL_MODEL_PILOT_VERIFIED**。

## 离线工程证据

最终正式套件77/77，0失败、0错误、0跳过，52.87秒：[机器结果](evidence/test-results.json)、[完整日志](evidence/final-verified-suite.txt)。

| 分组 | 方法数 | 结果 |
|---|---:|---|
| 原P1契约/评测/缺陷/服务/SQLite/历史/AppTest | 52 | 52通过，原测试未修改 |
| P2 provider/可靠性/预算/迁移/实际SDK MockTransport/UI | 23 | 23通过，全离线 |
| P2报告分母、失败计分、未知usage/成本、分位数 | 2 | 2通过，全离线 |

P1原6项AppTest继续通过，P2新增1项实际页面的开关→fake provider→live adapter→service→SQLite→新会话重读。实际LangChain+OpenAI SDK用MockTransport检查请求体、max_tokens、thinking disabled、JSON模式、429重试次数及request/response元数据；没有隐藏SDK重试。真实API测试不属于77项离线数字。

已注入429、5xx、认证拒绝、timeout、network_error、空响应、非法JSON、重复键/NaN、空对象/数组、缺字段、错bool、normalization失败、存储前/后失败、进程残留状态和并发重复提交。验证最多2次、20次持久上限、12输入上限、20元检查、单lease、配置绑定、不可重置账本、没有fallback和不确定请求不重放。缺Token/成本为null。

首次P2测试失败是Windows asyncio内部socketpair被旧离线网络封锁误伤，以及新预算初始化连接未关闭导致临时SQLite清理失败。保留`p2-first-tests.txt`/`p2-tests-2.txt`；修复仅允许标准库本机socketpair，显式关闭连接，随后18项全绿。追加报告测试曾因Windows默认GBK读取UTF-8失败，已修复并保留`report-test-encoding-failure.json`和`final-suite.txt`。最终77项重跑通过，没有把失败阶段计作通过。

`pip check`无冲突，没有安装或升级依赖。最终Python内存编译及资产台账见evidence目录。

## 历史兼容与保护

原80条仍494/560，66 mismatch，七字段全对32/80；原18条legacy mock保持77/108、31 mismatch；原400条ID/标记和14张Dashboard表一致。这些由正式历史测试复核，无真实全量重跑。

262冻结资产原hash不变；P1原始报告和证据未覆盖。新数据/预测/数据库在`.local/p2-pilot-v1`，版本化报告在`docs/p2/evidence/pilot-*`。代码前后hash及新增文件见`change-ledger-*.json`。复验命令：`python -B scripts/verify_p2_assets.py`；不要运行会改写P1台账的旧writer。

Git初次本地提交已按授权尝试：只暂存28个已检查工程文件，排除.env、实验数据、运行库和不确定的历史文档；审阅staged diff/文件列表并扫描密钥标记。提交因作者身份缺失被Git拒绝，SHA unavailable，没有伪造身份。恢复快照`D:/TEMP/complaint_p2_baseline_0hxiqtuk`保留，包含修改前源码/文档、P1基线复验、staged-review.diff。28个P1基线文件仍在index；P2修改未提交，新文件仍untracked。未执行push、tag、release、reset、clean。`baseline-start.json`列出覆盖范围及初始未暂存资产。

## 真实验证

独立真实阶段：1条smoke、10条语义、1条真实app.py AppTest。12封/12次请求；全部首次accepted；0retry、0fallback。字段83/84，邮件11/12；Token15451，保守估算0.044156元，实际账单unknown。[完整结果与限制](LIVE_REPORT.md)。实际UI重复点击2次请求数仍12。完成后账本halted=pilot_completed，无后台任务或后续自动调用。

从Streamlit到SQLite的真实链路已有证据，仍未验证真实浏览器E2E、生产负载、独立人工Gold和模型权重固定性。服务延迟指标是定义明确的编排区间，不含初始/最终SQLite提交；UI提交到渲染另有1样本9.209秒。request_id未获得，首条provider completion ID未保留，不回填伪造。以上是观测限制，不把null记0。

## P3输入（建议，未实施）

1. 先澄清服务对象明确但商品缺失时Service/Other与unknown的边界，给出标注决策表及反例。新的规则/Prompt另版本，不改这12条expected来消除本轮错误。
2. 建立模板/近重复分组隔离、独立人工标注及盲测holdout；开发者fixture只保留为回归。
3. 新Dashboard按backend/model/prompt/schema/taxonomy版本隔离；逐项展示accepted、failed、unknown、warning分母，保留成员run_id和原文下钻。
4. Source attribution保留证据与歧义，不解释成已证明因果或责任；审核与发送仍属于P4，未实施。

详细设计：[DESIGN](DESIGN.md)；调用与状态：[RELIABILITY](RELIABILITY.md)；本机演示：[REPRODUCE](REPRODUCE.md)。
