# 400条合成邮件质量审计

**DATASET_AUDIT_VERIFIED**。输入`data/synthetic/customer_emails_full_v1.csv`，SHA-256见[evidence/dataset-statistics.json](evidence/dataset-statistics.json)。原文件和参考标签未改。审计程序`src/evaluation/dataset_audit.py`，命令`python -B scripts/p25.py audit --source data/synthetic/customer_emails_full_v1.csv --out NEW_DIRECTORY`。

## 来源与代表性

400/400行与`generate_full_dataset_v1.generate_records()`纯内存生成结果逐字段相同。源码用固定列表、循环、索引和55个issue模板确定性拼接，没有模型生成步骤。customer_name为Synthetic Customer Fxxx，门店名为生成器固定地名组合；不是真实消费者抽样。原“reviewed”历史标签也不能仅因文件名认定为独立人工Gold。

ID唯一400/400，主题/正文齐全，所有列无空值，七字段枚举合法400/400。英文模板400/400（ASCII及模板源码证据）；正文187–264字符，均值219.3825；句式高度规则，没有真实长邮件、转发线程、口语多语分布。八类商品各50、十门店各40、40种对象各10是人为均衡，不能用于真实经营排名或人群代表性推断。

| 分布 | 数量（分母400） |
|---|---|
| 情绪 | negative 260；positive 70；neutral 70 |
| 投诉 | true 260；false 140 |
| 紧急度 | high 64；medium 216；low 120 |
| 原因 | product quality 50；delivery delay 45；customer service 45；refund request 35；after-sales service 35；wrong item 25；health or safety issue 15；other 10；none 140 |
| 来源分类 | product issue 65；delivery/logistics issue 45；customer service response issue 45；refund/exchange process issue 70；store service issue 25；unclear 10；none 140 |
| 购买渠道 | official website 152；customer service hotline 153；physical store 49；mobile app 46 |

完整所有字段分布、每样本长度/hash/模板/问题、重复关系及疑似样本ID见[evidence目录](evidence/)。没有把统计缺失桶隐含填成unknown；本池本来没有缺门店、缺商品的样本，也没有unknown类别参考。

## 重复与分组

原始正文完全重复0组，但每封正文包含Fxxx编号和替换槽，不能据此证明独立。移除商品、门店、渠道、时间、人名、案例编号后：55组重复覆盖400/400样本，只有55种正文骨架。55模板属于11场景族。去槽字符串SequenceMatcher>=0.92发现额外一对近重复模板，关联F383/F388/F393/F398与F333/F338/F343/F348/F353/F358/F363/F368/F373/F378；相似度0.927778。按模板、场景族、近重复传递合并后10个保守分量。

这些是可复算的模板/词面关系，不是嵌入模型或人类已确认的语义等价；人工仍应检查同义场景。候选划分以整个分量为单位，不能随机分邮件ID后声称无泄漏。

## 标签与语义疑点

146/400条至少触发一个疑似问题规则；下列数量重叠，不能相加当问题邮件总数，也不是已人工确认的错误率。

| 疑点 | 数量 | 依据与例子 |
|---|---:|---|
| mixed praise标签无正文称赞 | 41 | make_record修改局部edge_case_type，但body_for读取原scenario的edge_case_type；F001/F008等未真正进入混合句式分支 |
| high紧急度缺明确紧急正文 | 49 | 每5条额外置high；F001/F006等仅普通故障。安全场景15条另计，需人工看实际风险 |
| 服务对象套用实体问题句式 | 11 | Service/Other与质量/安全/错货场景机械交叉；F008/F016等。服务、礼品卡和会员计划归类本身也需规范审阅 |
| 错货的门店来源依据不明确 | 20 | 25条错货只有5条直接写store staff；其余自动标store service issue，不能作为已证实责任 |
| 语法/主语模板异常 | 64 | 检出I needs/I is/but it received等组合；这是显式模式检测下界，不是完整语言质量评分 |

本机完整audit.json含每条原文证据，远程[evidence/suspect-samples.json](evidence/suspect-samples.json)仅含ID、规则和模板，避免外传原研究邮件。自动枚举合法不代表上述语义正确。未改变expected来消除问题。

## 端到端覆盖差距

基本情绪、投诉、紧急档、商品和业务来源标签已在模板层覆盖；高紧急的证据、真实服务边界及来源归因可信度不足。安全15条只有五种通用句式，可能与对象不合理组合。退款/售后70条可触发承诺风险，但没有真实政策或人工回复约束。

缺门店、缺商品、多问题主次、明确否定/反讽、指令注入、非英语、真实长邮件/语气、摘要事实Gold、回复约束Gold、独立holdout均未覆盖；混合情绪在元数据标41但正文有效覆盖0。coverage机器矩阵区分covered_template_only、insufficient、not_covered；人工语义验证仍pending。

可用途：工程回归、Dashboard演示、待人工标注候选。不可用途：独立准确率、真实消费者总体分布、实际门店因果/责任排名、摘要回复可直接上线证明。

新候选110旧模板代表+20复杂开发案例，保留来源区别；新增涵盖服务边界、缺失信息、混合/多问题、否定/反讽、指令干扰、退款期限、中文/错字等。它们仍是代理编写候选，未人工审核，不能证明模型表现。
