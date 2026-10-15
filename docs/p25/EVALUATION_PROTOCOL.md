# 分层评价协议

执行路径：Dataset Manifest → validate_dataset/EmailInput → AnalysisService或只读AnalysisRun JSON → analysis-v2 → 七字段计分 → summary/reply人工记录 → 产品统计复核 → sample/run/hash追溯 → JSON报告。入口`python -B scripts/p25.py --help`，没有新付费调用模式。

## 运行方式

```powershell
python -B scripts/p25.py offline --dataset tests/fixtures/p25_portable_v1.json --out .local/p25/new-smoke
python -B scripts/p25.py replay-p2 --runs .local/p2-pilot-v1 --fixture tests/fixtures/p2_pilot_v1.json --out .local/p25/new-p2-replay
python -B scripts/p25.py evaluate --dataset PATH_TO_DATASET --runs PATH_TO_RUNS_JSON --reviews PATH_TO_REVIEWS --out NEW_DIRECTORY
```

目录必须新建，受保护历史目录拒绝写入。offline仅构造OfflineFake，经正式service与临时SQLite。recorded_replay读取已保存JSON，不构造原P2 Repository、不打开/迁移旧库、不请求API。原始run不在远程，报告保留源run hash；本机JSON可审计raw、parsed、normalized和attempt。新API请求是另一授权任务。

## 分母与计分

| 层次 | 规则 |
|---|---|
| 样本 | eligible=全部已验证manifest样本；attempted=有attempt记录的逻辑样本，另列真实dispatch预写条数；succeeded=成功且无fallback；failed/uncertain/fallback/missing分别显示 |
| 七字段 | 每字段分母=适用且有参考的全部样本，包括失败/缺预测/不确定/fallback；这些使用独立失败哨兵，不能匹配unknown。无参考不打分，列pending和排除原因 |
| evaluated/pending | evaluated=七字段均有参考且适用的可计分样本（失败也计错）；pending=其余样本。它不是“成功预测数” |
| 分类 | 各字段Accuracy、每类precision/recall/F1、混淆矩阵、Macro-F1。标签集合是参考与实际合法预测的并集，失败哨兵不是类别，但计入真实类别FN；零分母指标为null |
| 七字段全对 | 分母=完整七字段参考的适用样本，失败计0。整体字段比率是明确的字段计数/字段总数；不与生成质量、耗时或业务rate平均 |
| 调用结构 | accepted以eligible为分母；JSON/Schema以所有attempt记录为分母，含尚未调用/失败。dispatch另列，不能用这个结构指标宣称API可用性；retry/error/unknown usage各自显示 |
| 耗时和成本 | elapsed_ms仅已记录attempt；明确n和p50/p95。缺Token/成本总量为null，known subtotal单列。估算不是账单；沿用旧试点记录，不对未来价格作承诺 |
| 摘要/回复 | eligible=applicable_checks指定样本，evaluated=有绑定人工批准记录；缺预测或缺审核仍pending。参考未批准不能评分。任何critical error阻断通过，不能只算平均分 |
| 聚合 | 复用AnalysisService.aggregate的门店/产品成功run口径，校验numerator、denominator、negative_rate、成员ID和原文。unknown作为独立组，failed/uncertain/missing/fallback显示排除数 |
| 聚合语义 | 另用参考标签生成门店/产品/source分组和预测分组的count差，明确参考覆盖数；这是评价器的比较，不冒充产品新SQL source查询已完成。模板或开发参考只证明与该参考一致 |
| 系统 | 幂等、保存、重读、版本隔离、失败持久化和UI由具名工程测试证明；recorded replay不自动证明系统从UI重新运行，更不证明浏览器E2E |

## 生成内容Rubric

summary：关键事实、主要问题、无编造、实体与诉求。reply：事实忠实、问题覆盖、不擅自承诺、礼貌清晰、是否需修改。每项0=关键不满足，1=部分满足/需改，2=完全满足。逐项报告score_sum/实际审核n/每项最大2，不计算系统总分。

关键错误包括：编造门店/商品/订单、把未发生动作说成已发生、批准未授权退款/赔偿/期限、漏掉明确安全问题、服从邮件中的恶意指令。reference包含facts、forbidden、constraints、alternatives；多种正确文本均可接受。

人工输出review字段必须正好包含sample_id、kind(summary/reply)、run_id、input_hash、cohort_id、output_hash、rubric_version=content-rubric-v1、reviewer、status=approved、scores、critical_errors、evidence。输出hash为digest(result.model_dump())，重写草稿后旧审核失效。evidence写具体输出和原文依据；空critical_errors显式表示未发现关键错误。即使reply评分通过，ready_to_send仍false，P4批准与发送尚未实现。

Independent Accuracy默认null。只有完整可验证的双评审/仲裁freeze、sealed且independent的holdout、同一真实deepseek_live cohort时才可返回独立全对比例；真实性仍依赖实际人工与访问控制，工具不能认证人类身份。没有独立Gold、没有真人审核的本轮报告全部保持pending。

本轮结果：P2 replay 12/12成功、83/84字段、11/12全对；portable 5条/4成功/1预期故障、28/35字段、4/5全对。后者仅故障分母工程证据，不能作为NLP准确率。两份结果绝不合并。
