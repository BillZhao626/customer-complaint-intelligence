# v3端到端评测协议与复现

`scripts/p35.py`只提供offline、replay、audit和verify-calibration；没有付费调用入口。离线链路使用实际AnalysisService和EmailInput，经临时SQLite保存、重读，再导出原始AnalysisRun。重放只读JSON，检查样本原文、input/config/cohort/输出hash及dataset hash，不另写简化API。

```powershell
python -B scripts/p35.py offline --dataset .local/p35/dataset-candidate-v2/candidates.json --out .local/p35/NEW_RUN
python -B scripts/p35.py replay --dataset .local/p35/dataset-candidate-v2/candidates.json --runs .local/p35/NEW_RUN/runs.json --out .local/p35/NEW_REPLAY
python -B scripts/p35.py verify-calibration --snapshot .local/p35/calibration-decision-v1.1/snapshot.json --source .local/p3/calibration-v1
python -B tests/run_offline.py
python -B scripts/run_portable.py
```

out必须新建；拒绝历史data/outputs/docs/P2/P2.5/P3目录。offline默认使用明确标识的unknown占位fake来检查全输入链路；`--fixture-outputs`可提供按input_hash绑定的显式工程fixture。无expected时不计算质量分，不能把占位输出拿来宣称NLP正确率。

|层次|分母及证据|
|---|---|
|eligible/excluded|全部已验证manifest减去带明确exclusion_reason的记录；排除ID单列|
|attempted|eligible中有attempt记录的逻辑样本；额外记录所有attempt、parse、contract、retry、dispatch数量|
|succeeded/failed/pending|按同一sample最新run判定；fallback单列；missing/running/interrupted_or_unknown归运行pending；失败不缩语义分母|
|参考pending|reference_pending独立于运行pending；运行成功但没有参考仍待语义评价|
|七字段与邮件全对|完整v3参考的v2同策略投影；每字段/七字段全对均以全部适用有参考邮件为分母，失败/缺预测/fallback计错|
|邮件语义|sentiment、urgency、request_types、complaint_status全组一致，独立于七字段|
|问题数量及完整详情|以全部有参考邮件为分母；额外逐问题对象、类别、kind/reason、情绪/紧急度/状态、流程/团队、确定性、诉求/重要性/处理顺序与证据计分|
|问题匹配|优先原文跨度重合，再对象名匹配的确定性贪心对齐；输出unmatched_predictions。严格详情比较忽略任意issue_id及排列，检查关系；自由文本理由不做逐字准确率|
|证据|严格原文子串匹配和参考证据集合一致性；不把词面匹配叫语义蕴含|
|摘要/回复|每条绑定run/input/cohort/output hash、rubric版本及真实reviewer；无审核pending；任何critical_errors阻断，不以高均分掩盖|
|统计|同一dataset/cohort内按email_id+input_hash取最新运行；邮件修订版、成功邮件、问题数分别列；failed/fallback不进入成功业务分母；每个统计保留分子/分母成员及原文|

问题对齐为保守工程近似，改写对象/拆分合并/不同证据选择可能不匹配，需要人工核查。指标不是统一“系统总分”；schema acceptance也不是API稳定性。v2历史/P2重放继续用原评测协议，不改变83/84或494/560。

## 人工内容Rubric

`--reviews`接收JSON数组。每项含sample_id、kind(summary/reply)、run_id、input_hash、cohort_id、output_hash、rubric_version=p35-content-rubric-v1、reviewer、status=approved、evidence、scores、critical_errors。scores必须正好为facts、requests、all_important_issues、no_invention、safety，每项0/1/2；安全不适用时说明依据，不机械声称输出了安全建议。绑定不符、重复审核、失败输出审核均拒绝。

关键错误包括：编造订单/责任、未批准的退款/赔偿/期限、假称已执行操作、遗漏明确安全问题、重要问题消失、服从正文注入。语义无统一唯一句，真人评价解释具体原文/输出依据。参考和审核可以新版本补充，不能覆盖旧预测。

## 本轮运行证据

- 16个场景代表冒烟：16 eligible/16 succeeded，16 reference_pending。
- v1初池160条：160/160链路成功；v2编辑质量复核后172条、160 eligible、12 excluded。v2最终160 attempted/160 succeeded/0 failed/0运行pending，160语义reference_pending；summary/reply各160待审，独立准确率null。
- 状态故障fixture：6条总记录，5 eligible、4 attempted、2 succeeded、1 failed、1 fallback、1 missing/pending、1 excluded。七字段全对2/5、逐问题原因4/10仅证明失败分母计算正确，不能当自然语言质量成绩。
- 同一Application Service的模拟provider重试和真实LangChain/OpenAI SDK模拟HTTP均有断言；所有付费账本是测试临时fixture，不构成真实调用费用。

本地证据：`.local/p35/smoke-16-v1/`、`offline-candidates-v2-final/`、`e2e-state-fixture-v1/`及回归日志。新候选、决策原件、SQLite和完整run不进入公开Git。

HUMAN_GOLD_PENDING / INDEPENDENT_HOLDOUT_PENDING / REAL_MODEL_V3_QUALITY_PENDING。最终24条开发裁决已冻结不等于新172条候选已审核，也不等于独立Gold。未来真实v3语义评价需新的实验清单/输入白名单/配置/预算；本轮最多60次、15元的授权仅针对合成邮件生成，本轮未使用。
