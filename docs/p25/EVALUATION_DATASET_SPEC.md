# 统一端到端评价数据契约

版本 `e2e-evaluation-v1`。实现：`src/evaluation/e2e_schema.py`；机器 Schema：`evaluation-dataset.schema.json`。JSON Schema校验形状，Pydantic和validate_dataset补充hash、版本、来源及跨split泄漏约束。

每条样本含 dataset_id/sample_id/split；provenance(kind/source/source_hash/independent/exposure)；template_group/semantic_group；subject/email_body/input_hash；input_schema_version/taxonomy_version/annotation_version；expected七字段；summary_reference/reply_reference/attribution_reference；applicable_checks/exclusions；reviewer/adjudication/freeze_id/scenarios。

七字段是 sentiment、urgency、is_complaint、store_location、product_category、complaint_reason、source_attribution。产品名称、key_information、summary、suggested_reply仍属于实际输出契约，但不偷换成七字段准确率；生成内容评价单独覆盖其中的事实。`null`表示参考未完成；`unknown`是有语义的输出标签，不能代替缺参考。

输入复用EmailInput：email_id=sample_id，subject逐字保留，body=email_body逐字保留。hash为原产品digest({subject,body})，不strip、不改变换行、不把subject拼接到body。空正文拒绝。UI、live human JSON消息和离线执行使用同一内容；输入hash不同直接拒绝比较。

expected的template_reference/developer_reference/human_pending/human_gold与预测严格分离。未人工审核的facts/constraints等可以为空，必须pending。批准的参考必须有reviewer、事实要点和约束；冻结Gold还要完整七字段、两位不同评审、仲裁与freeze_id。单有这些字符串不能证明是真人；正式独立指标还需验证完整freeze manifest。

一次报告只允许一个dataset_id、来源、annotation/input/taxonomy版本和RunConfig cohort。RunConfig绑定backend/model/prompt版本和hash、schema、taxonomy及参数；每条run检查idempotency/input/cohort。旧80、P2十二条、portable fixture、新复杂开发集各自报告，禁止跨来源平均。

划分先按模板族、去槽正文完全相同及近重复关系取传递连通分量，再按组分配。数据集验证器拒绝相同template_group、semantic_group或input_hash跨split。400池有55模板、11场景族；0.92字符串相似阈值额外连接两个族，最终10个保守分量。它不是语义模型证明，同义改写还需人工确认。

当前候选是110条旧模板代表（每模板2条）与20条新复杂案例，分两份数据集。旧候选90 development、20 holdout_candidate；新20全部development。全部已暴露，holdout_candidate只代表暂隔离候选，不能声称独立盲测；最终独立holdout需真人另建、跨历史来源/模板/近重复检查并封存。20条新增内容不与旧400共同打一个总分。

最小安全fixture：`tests/fixtures/p25_portable_v1.json`。本机完整候选：`.local/p25/annotations-v2/`；这些包含本机研究邮件，不进入远程仓库。
