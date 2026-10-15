# P2 真实模型实验报告

日期：2026-10-15（Asia/Shanghai）。**REAL_MODEL_PILOT_VERIFIED**。这是developer-fixture preliminary evaluation，不是独立人工盲测准确率，也不是生产SLO。

[完整生成报告](evidence/pilot-20261015T053209176447Z/REPORT.md) · [机器指标JSON](evidence/pilot-20261015T053209176447Z/metrics.json) · [逐邮件CSV](evidence/pilot-20261015T053209176447Z/predictions.csv) · [逐attempt CSV](evidence/pilot-20261015T053209176447Z/attempts.csv) · [mismatch CSV](evidence/pilot-20261015T053209176447Z/mismatches.csv) · [定性审阅与原因假设](LIVE_REVIEW.md)。较早的报告目录保留，不覆盖。

## 样本、调用和结构

计划12封，实际发送12封（1冒烟+10语义+1真实UI），12次实际模型请求，12次首轮成功，0次重试，0失败，0不确定，0fallback。预算预留12/20，实际独立输入12/12，并发1；累计保守预留上界0.313116元，小于20元。

非空响应、JSON解析、原始Schema、identity normalization均12/12；业务一致性warning为0/12；最终accepted为12/12封。Schema通过不代表语义全对。

请求及返回模型均为`deepseek-flash`。非思考、temperature=0、JSON object、max_tokens=1800、SDK retries=0。实际模型权重快照unavailable，不把alias当固定版本。Prompt/schema/taxonomy/软件包版本见本机manifest和文档证据。

## 七字段匹配

| 字段 | 匹配/已发送邮件 |
|---|---:|
| sentiment | 12/12 |
| urgency | 12/12 |
| is_complaint | 12/12 |
| store_location | 12/12 |
| product_category | 11/12 |
| complaint_reason | 12/12 |
| source_attribution | 12/12 |

字段总体83/84=98.81%；七字段完全匹配11/12=91.67%。唯一mismatch是服务咨询的类别边界，预期Service/Other、实际unknown；保留原预期。小样本且由开发者定义，不能与旧80条88.21%直接比较宣称模型提升。

## 延迟、Token和成本

- provider调用耗时（含客户端准备/SDK处理，非纯服务端时间），n=12：p50=2019.78ms，p95=7975.22ms。
- 逻辑编排耗时（claim之后至终态提交之前），n=12：p50=2110.96ms，p95=8062.95ms。该计时不含起止SQLite提交开销，不能冒充完整浏览器用户延迟。
- 实际UI AppTest提交到完成渲染：9208.63ms，n=1；包含模型、保存和UI渲染。仅一个样本，不推导UI p95。
- 12/12 attempt有usage：输入13242、输出2209、合计15451 Tokens。
- 按[官方高峰缓存未命中价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)保守估算0.044156元；实际账单扣费unknown，未填0。所有请求均在预算内，无在线评测、LangSmith上传或真实邮件发送。

## 实际UI链路证据

run_id=`790173b1-f0b7-4df2-a48f-5cb786160d6d`，email_id=`p2-delivery-ui`。

实际app.py Single Analysis选择deepseek_live → AnalysisService → DeepSeekAnalyzer/ChatOpenAI → 官方API → 严格JSON/Schema/identity normalization → SQLite → 页面显示成功 → 新AppTest会话Load saved run重读原文及结果。调用计数由11增至12；随后实际UI重复点击两次仍为12，返回同一run。

这是实际应用入口的AppTest live path，不是浏览器E2E。证据见`.local/p2-pilot-v1/ui-evidence-790173b1-f0b7-4df2-a48f-5cb786160d6d.json`和`ui-idempotency.json`。

## 版本和复现边界

冻结fixture：`tests/fixtures/p2_pilot_v1.json`。本机`.local/p2-pilot-v1/`包含manifest、冻结fixtures/prompt、preflight源码hash、预算SQLite、运行SQLite、12个run JSON及控制台记录。Prompt、预期和历史Gold未因试点输出修改。只读报告可用`python -B scripts/p2_pilot.py report`生成新版本，不产生API调用。

试点完成后账本已暂停为pilot_completed；保留剩余8次未用额度，不自动消耗。复现演示优先读取保存结果，详见[REPRODUCE](REPRODUCE.md)。P3应先明确服务类别与unknown边界、独立标注流程、版本化统计分母和下钻证据；本轮未实现P3/P4业务。
