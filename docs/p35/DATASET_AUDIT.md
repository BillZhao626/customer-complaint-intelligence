# 新合成候选池及质量审计

状态：DATASET_CANDIDATE_AUDIT_VERIFIED，仅指来源、输入完整性、质量隔离、词面泄漏与覆盖审计已完成；不代表真人语义审核通过。

v1为160条逐条编写的虚构叙事，没有槽位替换扩量，也没有DeepSeek生成请求。Codex编辑检查发现12条过于接近标注说明：涉及刻意解释联系/购买渠道、直接指导分类或主次等，降低普通邮件自然度。v2原样保留这12条并隔离，另写12条更自然的不同叙事。现有172条总记录，160 eligible、12 excluded，v1原文/hash全部保留。F176在独立24题冻结包中排除，不混进新候选池。

生成来源准确记为codex_authored_synthetic；这是AI辅助编写，不是独立人工创作/真人消费者数据，更不是有DeepSeek请求记录的生成数据。没有随文本生成expected或Gold。每条有ID、input_hash、来源/方法/版本、场景/语言、叙事族/语义族、暴露/审核状态、质量异常及排除原因。

|范围|数值|
|---|---|
|全记录语言|英文84、中文73、中英混合15，共172|
|eligible语言|英文78、中文70、中英混合12，共160|
|语义大类|16；叙事逐条编写，不能把172个记录ID叫172个独立语义族|
|精确规范化重复|0（NFKC、大小写、数字和空白规范化）|
|近重复|SequenceMatcher≥0.86为0；最大0.49375|
|历史比较|13个含邮件正文的历史CSV及校准原文，去重后506条；≥0.86为0|
|人工语义抽样|PENDING；Codex进行了文本编辑检查和跨16族32条语义抽样记录，不能冒充独立人工复核|

覆盖以eligible=160为范围，标签可重叠，不是正确输出标签：inquiry 23、praise 17、complaint 97、size_fit 11、wrong_item 9、installation 13、repair 11、refund 17、multiple_issues 11、equal_importance 3、resolved 12、safety 13、negation 20、sarcasm 2、mixed_emotion 5、long_email 3、prompt_injection 8。其余门店/客服/物流、不确定归属、缺对象/门店、错拼、多个实体/诉求、摘要遗漏和回复承诺风险均见[evidence/dataset-audit-summary.json](evidence/dataset-audit-summary.json)。标签来自场景设计，不作为模型准确率参考。

重要风险：样本仍属合成、分布由开发者选择；语言与场景不等于真实客户分布；少量长邮件/反讽/同等重要案例不足以独立估计这些子组质量。近重复词面检查会漏掉翻译和同义场景，同族与跨族仍需真人复核。所有候选均已被研发代理接触，没有sealed holdout。当前没有候选被标为human-reviewed。

所有候选保留development（排除项quarantine）。旧400继续历史工程回归，公开小fixture继续工程回归。未来人工审核后，按语义族、模板族及近重复连通分量整体分配开发/回归，禁止按ID随机切分；跨族同义/翻译也应合并。未来独立holdout另由未参与开发的人组织、另存访问受限位置、冻结原文/参考/hash，不从这172条中改名产生。

本地入口：`.local/p35/dataset-candidate-v2/REVIEW.md`、`candidates.json`、`reviewer-blank.json`。Streamlit Single Analysis → P3.5 candidate review可按ID查看原文、hash、质量标志并下载pending审核草稿；此动作不签署真人身份或批准Gold。复制空白审核包到新文件后真实填写，后续修订另建版本。

原始候选正文、隔离文本、逐条审阅和完整报告只留.local，不在公开仓库。公开摘要只含数量/标签/哈希与限制。真实模型请求0、人民币费用0；本轮60次/15元合成生成预算未使用。
