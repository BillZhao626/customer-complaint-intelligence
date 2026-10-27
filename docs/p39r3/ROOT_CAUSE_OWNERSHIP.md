# P3.9-R3：因果基线、责任归属与独立 Challenger

审计日期：2026-10-17（Asia/Shanghai）。这是 B 线只读审计及独立候选说明；A 线固定实验结果以本轮最终实验报告为准。本审计本身新增真实模型请求 0 次、预算写入 0 次，不修改原始输出、研究参考或冻结 A/B 链。

## 证据范围与身份

|材料|本机只读入口|身份与限制|
|---|---|---|
|P3.6 原始 40 请求|`.local/p36/baseline-v1/`、`catalog-v2/`、`draft-v3/` 下 `run-*.json`|4 / 4 / 32，三种 Prompt，不合并成同一实验|
|P3.7 七例归因|`.local/p37/ROOT_CAUSES7.md`、`.json`|AI 候选归因，不是独立人工 Gold；没有新的模型 raw|
|P3.7 派生重放|`.local/p37/final-replay-v1/`|29 成功原 run 的 87 份显式派生视图，不能替换失败预测|
|P3.9-v1 原失败|`.local/p39/runtime-v1/run-18262cc3-339f-4c09-81f8-f77ee1ee9b93.json`|实际原失败状态只读|
|P3.9-v2 最初三条|`.local/p39/v2/live-delivery-v1/runtime/`|2 接受 / 1 失败；后续 A 线补全另行报告|
|原 gate 初始快照|`.local/p36/recovery/src/application/v3_safety.py`|审计前的 gate1 源码快照，不代表整个 P3.6 各时点均使用它|
|冻结政策及当前实现|`src/domain/analysis_v31.py`、`analysis_v31_context.py`；`src/application/research_policy_v2.py`、`urgency_context_v1.py`、`reply_review.py`|直接检查源码，不根据错误码推定内部模型机制|

`src/evaluation/p39r3_causal.py` 只读取 JSON，验证 input、cohort、idempotency、raw/parsed 身份和读前读后文件字节。它保留原 status、run/config/Prompt/raw hash，只返回诊断状态；没有 provider、SQLite、预算或文件写入路径。`source_identity(root)` 可记录本轮重放实现、旧快照和校验器的字节 SHA-256。gate1 为明确重构的初始快照规则；gate2、gate3、policy-v2 和 context-v1 使用当前保留的相应实现。不同 Schema 不自动迁移，不用 v3.1 政策重解释 v3 raw。

项目 `digest(raw_string)` 与 `SHA256(raw UTF-8)` 是不同口径，工具同时保留，不把它们当成同一 hash。诊断中不输出正文、摘要、回复全文或原异常全文。完整研究原文继续只在原本机文件。

## 同一 raw 的因果差分

|同一保存 raw|旧 / 当前诊断|可成立的结论|
|---|---|---|
|P3.6 baseline-v1 4 条|gate1、gate2、gate3 全部拒绝；2 原文跨度失败、2结构/跨字段失败|早期结构及证据问题已存在，不是 P3.8/P3.9 引入|
|P3.6 catalog-v2 4 条|初始快照 gate1 4 接受，gate2/3 3 接受|初始 gate 漏检一条未经核实的已转交声明；原实际成绩仍 3/4，不把初始快照假定为当时运行门禁|
|P3.6 draft-v3 32 条|初始 gate1 29 接受；gate2/3 各 30 接受；剩余 2 结构失败|只读差分定位一条否定承诺误拒已被早先工程修复。原 29/32 不改为 30/32|
|`4e3497ac-…`，p25-commitment|同 raw 的 gate1 拒绝；gate2/3 接受|原回复是否定付款保证，旧子串门禁 false rejection。raw 的 medium 仍与旧参考 low 不同，门禁修复不证明语义全对|
|P3.9-v1 `18262cc3-…`|policy-v2 在跨字段拒绝 low + general_help；context-v1 在源事实拒绝具体咨询 general_help|错误 basis 在原输出已存在。改变校验位置不能制造成功预测；不能把合理 low 改成 medium 迎合标签|
|P3.9-v2 首对 `50402a3e-…`、`e129c215-…`|两个同 raw 均通过旧 policy-v2 与当前 context-v1|成功依赖模型选了 other；不能单独归功于放宽接受语义，也不足证明 B 优于 A|
|P3.9-v2 `524455eb-…`，P35-171|旧 policy-v2 首先拒绝无明确 equal 证据；当前 context-v1 首先拒绝 repeated_failure 无相应事实|整条拒绝不是新 profile 单独引入。当前最早报错掩盖了其他独立缺陷，不能只修第一个错误码|
|新的中英文 relaxed 同义句 fixture|旧 policy-v2 接受 low + explicit_relaxed；当前 context-v1 拒绝未覆盖的表达|这是 context-v1 新增的有限词汇误拒边界。含义合理不等于当前程序已识别；不把它说成 low 错误|
|引文紧迫词 / 重复失败叠加必要期限 fixture|旧 policy-v2 拒绝；context-v1 接受受支持判断|原机械默认和全邮件词面锚点确有一般缺陷；已有获批修复不意味着所有自然语义都可验证|

本轮实际读了上述 44 条历史 raw。P3.6 冻结开发成绩仍为 143/168 字段、17/24 封全对、draft-v3 原 29/32 接受；其参考来源为研究者批准的开发参考，不是独立 Gold。表内所有新“接受”均为诊断，未创建成功 run 或回填实验。单一用例可以同时具有模型原缺陷、expected strict rejection 与局部 validator false rejection；分类不是互斥的整封邮件标签。

## 七类机制与 ownership

### 1. urgency_basis 与事实脱节

- **可观察事实 / 最早失效：**v1 具体功能咨询使用 general_help；v2 一个产品复发症状及一次回收失约使用 repeated_failure。缺陷在 Prompt/LLM → Raw Output 已出现，后续跨字段或原文依据校验捕获它。
- **因果基线：**v1 的标签矛盾在两种 profile 均被拒绝；v2 的整条 raw 在旧 profile 也因其他事实约束拒绝。旧 schema 并不要求具体问题必须 general_help，other/unknown 从来可用。
- **当前 / 正确归属：**LLM 负责事实理解与依据选择，Prompt 负责解释枚举；Validator 应检查可验证矛盾与跨度。Schema 不应代替自然语言判断，Runner 不应把此质量失败变成永久 halt。
- **候选修复：**独立 Challenger 的事实清单及 basis 自检；保持原程度、原文和接受标准，不事后替换 basis。给模型一个可核查的事件计数任务，比按错误码修改字段更符合权责。
- **正 / 反回归：**跨键盘、锅具、吸尘器的具体咨询 other/low 正常；low+general_help 仍拒绝；无依据 unknown 不能认证已知 urgency；严重危险仍 high。
- **回滚：**保留 Champion B。若实际改善不足，停用候选配置，不回填原预测。

### 2. 客户重要性、业务顺序与关系混淆

- **事实 / 最早失效：**P3.6 p25-mixed_ambiguous 明确 equal，却给并列业务顺序；P3.9 P35-171 将“一起跟进”扩成 equal 并添加 equal_importance 关系。两个方向都是 LLM 语义问题；旧 v2 业务投影还会丢失来源选择信息。
- **基线：**P3.7 已用显式派生业务政策处理“明确 equal 但业务可排序”，保留 equal 及原 run。P3.9 的 together→equal 早被 v31 policy-v2 禁止，并非 context-v1 新禁令。
- **归属：**LLM 识别客户措辞；业务 policy 建议处理顺序；兼容投影及 UI 明示损失；Validator 检查关系/字段一致性，不能创造客户主次。
- **候选：**Challenger 将 importance、handling、dependency 分开核对。没有明确客户比较时保持 unspecified，不能把流程便利或业务先后变成客户偏好。
- **正 / 反回归：**显式 equal 保留；together/同时处理在中英文不同服务场景不形成 equal；已有 primary 不被业务排序改写；ID 更名、数组倒序不应改变判断原则。
- **回滚：**仅撤回候选 Prompt；旧派生与正式 raw 保持各自身份，绝不以数组顺序硬编码参考答案。

### 3. 重复产品故障与重复服务失败混淆

- **事实 / 最早失效：**P35-171 的反复操作/复发症状被当重复未履约；另一个服务仅有一次未到场。产品次数、操作次数、服务违约次数被混用，失效在 LLM 事件理解。
- **基线：**旧 policy-v2 仅核对 repeated_failure→medium 组合，可能接受无支撑的依据；新 context-v1 增加有限事实检查是 expected strict rejection。整条历史 raw 旧版也拒绝，不将个别 predicate 差异误写成整条接受改善。
- **归属 / 候选：**模型列明“哪个主体、哪次服务、什么未履行事实”；Prompt 强调计数对象。Validator 只审可支持的重复未履约，不把“几次”自动解释为服务多次失败。
- **正 / 反回归：**数次承诺回电且未兑现可 repeated_failure；显示器复闪、门锁重复弹开不够；一次未到访不够；已解决历史不自动升级当前紧急度。
- **回滚：**不放宽当前 repeated_failure 检查；若自然表达漏检，另立 profile 差分，不修改 A 线。

### 4. 保管去向、来源域与责任混淆

- **事实 / 最早失效：**P3.6 p25-uncertain 原文是包裹归谁保管不明，raw reason 推为 delay，摘要扩大为责任；p25-typo 的不确定门店提及在旧投影变成确定门店。
- **基线：**P3.7 的 safe projection 已明确遮蔽 unclear/inferred 与 uncertain mention，但不会改变 raw 中错误的 reason/summary。该缺陷早于 P3.8/P3.9。
- **归属：**模型保留事实与不确定性；兼容层负责避免丢失 certainty；UI 展示来源分类及未核实责任。 routing_team 是建议协作方，不是法律责任方。
- **候选：**Challenger 分别核对地点、流程、持有、时限及核实状态；无时间事实不造配送延误，不靠门店名字选择责任。
- **正 / 反回归：**跨包裹/维修物/发票的去向不明保留 unclear；明确逾期可以支持 delay；具体未答送修流程不因有门店名自动路由 store service。
- **回滚：**不修改参考、不对历史 raw 进行确定性情绪/归属重标；保持旧与 safe 视图并存。

### 5. 自然语言宽松时间表达

- **事实 / 最早失效：**P35-171 发票事项的自然宽松表达语义支持 low，但当前 RELAXED 词汇未命中；独立 predicate 能看到该问题，正式流程此前已被 repeated_failure 阻断。
- **基线：**同类新的中英文 fixture 在旧 policy-v2 通过，在 context-v1 失败，属于 introduced bounded-validator false rejection；不是所有低紧急度都错，也不是整个 raw 必须接受。
- **归属：**自然语义解释属于模型；Validator 的有限词汇覆盖必须如实声明。新增更全面识别需独立 profile 与差分，不能宣称枚举/Schema 没变就没有接受语义变化。
- **候选 / 边界：**本轮 Challenger 提醒理解近义、否定、引文、转折，不伪造标准短语引文。本候选仍用冻结 profile，因此该误拒可能继续存在；单改 Prompt 不能证明修复这个 Validator 边界。
- **正 / 反回归：**no rush/不着急继续可接受；no hurry/晚一点补可重现边界；引用、not no rush、转折后的必要期限及严重危险不能被低优先级短语盖住。
- **回滚：**保留严格拒绝及诊断，后续另版本对照；不在固定 A/B 期间静默扩词或删约束。

### 6. 机械免责声明、虚假动作和客服承诺

- **事实 / 最早失效：**P3.6 p25-commitment 的真实否定保证被旧 gate1 误拒；catalog-v2 有初始门禁未覆盖的“已转交”声明；P3.9 P35-171 回复暗示未核实接收渠道、未来联系能力，且摘要扩大跟进范围。前者 Validator 错误，后两者 LLM 内容缺陷；无词面命中不证明事实安全。
- **基线：**gate2/3 对否定同 raw 已通过，对否定后转折肯定承诺仍拒绝。渠道/未来联系错误当前门禁可能漏检，不伪称本轮新修了旧误拒。
- **归属：**Prompt/LLM 生成有用但无授权动作的草稿；应用服务提供可验证能力上下文；安全 gate 拒绝明确危险声明；人工审核事实及沟通质量。不能让词面 Validator 承担完整语义审批。
- **候选：**Challenger 不以“将联系/已转交/请发此客服邮箱”代替实际能力；接收渠道未知就明确需要确认。保留针对客户诉求的下一步、语气和安全建议，减少机械内部免责声明。
- **正 / 反回归：**“无法保证”不误拒；but/但是后的肯定付款仍拒；含糊退款、已批准、已执行动作不放宽；一般核查建议可用，但不计人工批准。
- **回滚：**安全 gate 保持冻结，不以减少免责声明为由删除关键安全说明或绕过 review_required；候选仍未审核未发送。

### 7. 普通模型质量拒绝导致全实验停止

- **事实 / 最早失效：**原 `run_smoke()` 在 durable failed run 后直接 `budget.halt('failure_requires_review'); break`，使首请求错误或第3个请求错误阻止后续配对。质量缺陷最早在模型输出，实验停止的新增后果发生在 Runner。
- **基线：**v1 与 v2 源码都如此；不是 Context Validator 拒绝本身出错。先后都具有 orchestration failure，不能靠降低校验严度修实验连续性。
- **归属：**Service 保存原始失败与用量；Experiment Runner 区分质量终态与工程安全异常，推进已授权固定计划；Evaluator 保留失败分母；UI 不展示失败为可发送成功草稿。
- **实施：**由本轮 A 线独立 `evaluation-continuity-v1` 处理；B 线不修改冻结链或预算。质量拒绝保持 failed、无重试/fallback，不应继续需要审批/支付/身份漂移/持久化不确定等真正工程安全事故。
- **正 / 反回归：**A failed 后同邮件 B 仍尝试、重启不重发已完成3条、64步包括失败全部可审计；未知发送、身份漂移、用量异常或存储失败立即停。
- **回滚：**遇工程安全异常停止新请求并保留恢复证据；不用删除预算、重新建账或重发样本恢复进度。

## 独立候选及验收强度

独立模块 `src/application/p39r3_challenger.py` 的 API 为 `system()`、`messages(email)`、`prompt_hash()` 和 `candidate_identity()`。它检查父 B hash 后，仅追加事实与 ownership 自检；human message 与原 B 的 email/input/evidence catalog 完全相同，无样本 ID、门店、hash、研究参考或预期答案分支。它不返回“修正预测”，不修改 Validator/Schema/投影/回复 gate。

|身份|值|
|---|---|
|版本|`complaint-p39r3-B-fact-ownership-1`|
|父 B Prompt SHA-256|`a4ecfaa52c37103a5dcd1544240f55c566be0adaa433132848a9c12a90c7027a`|
|候选 Prompt SHA-256|`080c53abf1b44181ffb1c1418bc1ba6f66a889efa553bf8f675cfb5f4490239c`|
|候选规则 SHA-256|`7917d8fabae5b565808b91ad020b0b885443b0ca0a5efdb2599b2d07bad3b4cf`|
|候选身份 hash|`347bd00e80c13ca386295d3af255ce4ce6f2cfb1fe85e428beae420ce30b98e3`|
|校验语义|沿用 `urgency-context-evidence-v1`，接受语义不变|

两份新增测试共 **17/17** 通过。覆盖单元、新旧差分、历史真实 raw 原状态保护、解析脱敏、跨产品中英文、引用/否定/转折/已解决/信息不足、严重风险不降级、显式临时 SQLite 保存→新连接重读→幂等、父 Prompt 漂移拒绝，以及输入重命名变形后的 payload/evidence 不变。历史资产在公开 checkout 缺失时明确 skip；其余 authored fixture 不需要私有 raw。测试数据不是 Gold，ReplayV31 是明确 fake，未评测模型理解。

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_p39r3_causal tests.test_p39r3_challenger -v
```

本报告不声称 17 个测试证明 Prompt 语义提高，也不把早先 gate2 修复重新记为本轮成果。最有力的本轮确定性修复是 A 线 Runner 权责调整；本独立 Prompt 候选需固定 64 次完成后，才可在已授权探索额度内使用，保留原 B 对照、不同调用时刻及模型服务端变化风险。任何探索结果单列，不能回填正式 A/B。

独立人工 issue/reference、证据语义、摘要回复 18 维评分与真正独立 holdout 继续 pending。p25-after_sales 的情绪/流程、p25-no_object 默认低与 unknown、F176 数据自然性/参考解释空间仍保留为 reference ambiguity 或待审核语义；不通过确定性重标制造模型准确率。自然时间表达覆盖、隐含承诺与复杂事件关联仍是未解决边界，真实探索不足时应如实报告证据不足。
