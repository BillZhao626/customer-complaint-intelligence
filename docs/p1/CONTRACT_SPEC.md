# P1 契约 Spec — analysis-v2

2026-10-15；用户已批准方案 A、SQLite 新运行试点和八类 canonical taxonomy。实现位于 `src/domain/contracts.py`；可导出的结构定义见 `analysis-v2.schema.json`。JSON Schema 表达结构；Python 还拒绝纯空白字符串与非有限浮点数。

## 业务单位与含义

一次分析是一封邮件的一个主要投诉问题、主要产品、主要门店/渠道和主要业务来源。`source_attribution` 是报告归属，不表示已证实因果、法律责任或真实市场经营结论。暂不建立独立 issue、多产品计数、审核或发送实体。

原始字段缺失为契约失败；显式 `unknown` 为已提供但未知的业务值。`none` 表示不适用，`unclear` 表示来源不清，均不等于 missing。`is_complaint` 只接受真正 JSON boolean，不从字符串或数字推断。

## 产品枚举与版本

Taxonomy：`research-products-v2`。来源是只读 `data/synthetic/customer_emails_full_v1.csv` 的全部实际唯一值；测试与该文件逐项核对。

| canonical 值 | 意义 |
|---|---|
| Beauty/Personal Care | 原研究类别 |
| Clothing | 原研究类别 |
| Electronics | 原研究类别 |
| Food/Beverage | 原研究类别 |
| Furniture | 原研究类别 |
| Home Appliances | 原研究类别 |
| Service/Other | 原研究业务类别，不能当未知值 |
| Sports/Outdoor | 原研究类别 |
| unknown | 新增显式未知桶，不计为 Service/Other |

旧 provider 的 Electronics/Home Appliances/Clothing/Furniture 按原值保留。Beauty Products/Sportswear/Service/Other 与 v2 名称的范围不完全等价，本轮未批准上下文推测映射，`adapt_legacy` 输出 unknown 与不兼容 warning，并保留 raw。未知旧枚举、缺失字段或错误类型先失败，不能通过这个映射获得通过。

Legacy mock 原结构没有 source_attribution：独立验证其实际字段后，在适配阶段明确记录“原契约不支持该字段”，规范结果设 unknown，normalization=incompatible。其身份为 legacy_mock，不是 offline_fake 或 DeepSeek；不参与历史 raw 指标改写。

## 实体

| 实体 | 必需信息/约束 |
|---|---|
| EmailInput | email_id（1–200 字符且非空白）、subject（可空，最多 2000）、body（1–100000 且非空白）；严格字符串 |
| AnalysisResult | store_location、product_name、product_category、sentiment、urgency、is_complaint、complaint_reason、source_attribution、key_information（字符串数组）、summary、suggested_reply、confidence（有限 0–1）；不允许额外键 |
| RunConfig | backend、model_id、prompt_version、schema_version、taxonomy_version；cohort_id 是规范 JSON 的 SHA-256 |
| AnalysisRun | UUID run_id、幂等键、完整 EmailInput、input_hash、RunConfig、cohort_id、终态、创建时间、可空结果、attempts |
| AnalysisAttempt | 编号、起止 UTC 时间、原始输出、parse/contract/normalization/business 状态、warnings、ErrorDTO |
| ErrorDTO | error_type、脱敏固定模板消息、occurred_at；不输出提供方异常正文或客户内容 |

sentiment：positive/neutral/negative/unknown；urgency：low/medium/high/unknown。reason 为既有九值（product quality、delivery delay、customer service、wrong item、after-sales service、health or safety issue、refund request、none、other）加 unknown。source 为既有七值（product issue、store service issue、delivery/logistics issue、customer service response issue、refund/exchange process issue、unclear、none）加 unknown。

输入 hash 为 UTF-8、按键排序、紧凑 JSON 的 subject/body 摘要；不 trim 原文、不把 hash 当匿名化。幂等键另外包含 email_id 与全部 RunConfig。同一外部 email_id 内容变化保留多个输入版本，不覆盖原文。

## 验证顺序

1. 原文输入校验；失败不调用 analyzer、不创建运行。
2. 显式调用注入的 Analyzer，要求返回原始 JSON 文本；新服务不加载 `.env`、不调用网络后端、无失败降级链。
3. JSON 解析：passed/failed/not_run。
4. 原始结构检查：passed/failed/not_run。空对象、数组、缺字段、错类型、非法 bool、未知枚举全部失败。
5. 规范化：offline_fake 为 identity；legacy mock 为显式 incompatible；legacy provider 只允许上述精确同名映射。raw 与 normalized 分开。
6. 业务一致性：非投诉却有投诉 reason/source、投诉却 reason=none 记录 warning，不擅自断定所有边界案例错误。
7. 语义准确性：**未由这些校验证明**。fake 的 confidence=1 只属于测试协议，不能解释成模型置信校准或真实正确率。

当前同步服务仅持久化 succeeded/failed 终态。正常可捕获失败会保存 attempt 与原文；进程硬中断前未提交的尝试不会产生持久记录。没有后台恢复、排队或生产并发保证。

## 版本与统计

当前实现只支持 analysis-v2 和 research-products-v2；未知 schema/taxonomy 不冒充已支持。将来实现新契约时必须增加版本及兼容测试。幂等键测试覆盖 schema/taxonomy 字段变化；当前可实际运行的 prompt/input 变化已有持久化隔离测试。

聚合必须指定 cohort_id，默认不混合 backend/model/prompt/schema/taxonomy。成功运行是统计成员单位，一条成功运行对应一个邮件输入版本；同 email_id 的不同原文版本是不同成员，UI 明示此口径。负面率 = negative 成功运行数 / 该组全部成功运行数（含 positive、neutral、unknown 情绪）；失败运行不进入分子或分母。每组含 numerator、denominator、source、cohort_id、全部成员 run_id 和负面成员 run_id，可读回 email_id、原文、hash 和版本。空组不输出伪 0% 比例。

## 评测兼容

`src/evaluation/core.py` 是统一核心。先分别检查双方 ID、字段与空值，再一对一对齐；重复/空 ID 和缺字段抛 ValueError，覆盖缺失/多余返回 invalid 诊断且不产生任何分数。expected、matched、coverage 和 missing/extra 明确返回，不用交集缩分母。

默认七字段：sentiment、urgency、is_complaint、store_location、product_category、complaint_reason、source_attribution。Legacy smoke 和 UI 的显式六字段选项保留兼容；不会为第七字段补值。raw 对比仅沿用旧词法规则（strip/lower、布尔拼写），不执行类别映射、产品上下文推断或 Gold 修订。I4E2 wrapper 使用同一核心并保留旧返回协议。旧 80：494/560、66 mismatch、32/80 全对；旧 18 smoke：77/108、31 mismatch。
