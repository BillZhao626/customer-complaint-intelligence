# 开发集裁决版本台账

状态：CALIBRATION_OWNER_DECISION_SNAPSHOT_VERIFIED。24/24已由研究者最终复核；研究者明确确认两位专家结论一致。记录类型保持 `RESEARCH_OWNER_CALIBRATION_DECISION`，不冒充独立双人原始标注。

|版本|本地位置|用途|
|---|---|---|
|v1|`.local/p35/calibration-decision-v1/snapshot.json`|补充包到达前：明确裁决与重读建议分开，保留缺少旧草案时的真实证据状态|
|v1.1（当前冻结）|`.local/p35/calibration-decision-v1.1/snapshot.json`|收到补充包及研究者最终确认后的24条完整七字段裁决；链接v1 payload hash，不覆盖v1|
|补充原件|`.local/p35/supplement-original/`|ZIP内JSON、Markdown、说明和SHA256 manifest原字节保留；只读校验|

核验24个sample_id、subject/body逐字一致、产品EmailInput哈希、全部七字段严格枚举、引用片段原文位置、两份原工作表hash，以及补充包3个文件的字节数与SHA256。原reviewer A/B和仲裁模板未填写；不存在工具伪签的专家身份或独立性声明。补充材料列出的两个更早外部草案不在ZIP中，它们的hash仅作为上游自述保留，没有声称已核验那两个原件。

|题号/ID|冻结处理|
|---|---|
|01 fitting|neutral，非投诉，明确试穿服务 Service/Other|
|02 repair|negative/medium；after-sales service；预约取消归store service issue，责任未核实|
|03 installation|已有架子的安装服务咨询，非投诉|
|04 hours|仅营业时间→unknown；新人工策略，不回写旧service-boundary-v1|
|05 after_sales|negative、投诉；缺送修指引→customer service response issue|
|06 staff|无购买也可投诉门店员工；Service/Other|
|07 product|耳机功能咨询→Electronics，无故障投诉|
|08 no_object|unknown对象，neutral、非投诉|
|09 mixed_primary|水壶火花为明确主问题，high；表扬不抵消安全问题|
|10 mixed_ambiguous|保留两问题与equal；夹克先处理为业务策略。冻结v2参考Clothing/product quality/product issue是明确有损选择|
|11 no_store|烤面包机冒烟→high；门店unknown|
|12 negation|否定损坏与退款，清洗咨询|
|13 sarcasm|三次承诺无回复→negative/medium，客服响应流程|
|14 injection|耳机失效，引用垃圾指令不构成退款或泄露授权|
|15 commitment|neutral、投诉true、refund request；未审批，不虚构经理批准或明日付款|
|16 resolved|positive、非当前投诉；v3可保留已解决历史物流问题|
|17 uncertain|negative、投诉true、other、unclear|
|18 chinese|安全问题仍未解决→high；员工友好另记|
|19 typo|v2 other，v3 size/fit issue；门店unknown/疑问式提及，不能当wrong item|
|20 long_request|夹克为明确主问题，椅子及正常试穿为背景|
|21 F176|保留原文及冻结参考；不自然会员计划维修模板，排除干净语义评测|
|22 F096|重复无回复→medium，客服响应；历史合成来源保留|
|23 F051|超过配送窗口→medium，物流流程；热线是购买渠道|
|24 F001|正常使用耳机失效，low；不推断额外安全风险|

v1重读建议与最终附件的差异明确由v1.1取代：02 reason为after-sales service；10保留附件的有损v2夹克选择；F176 source为unclear。最终24条不再待研究者重复确认。摘要/回复参考是AI编制工作参考，正式质量评分仍待真人。

冻结API排他创建文件，拒绝覆盖；验证器重算payload、原始记录及原始目录hash。文件系统所有者仍可手工修改文件，所以“不可覆盖”指工具的append-only行为和可检测的hash链，不宣称WORM硬件或身份认证。修改裁决须新版本、新依据与前版hash。

HUMAN_GOLD_PENDING / INDEPENDENT_HOLDOUT_PENDING / REAL_MODEL_V3_QUALITY_PENDING；Kappa=null。独立专家原始标注过程未提供，无需补造，也不再要求重复确认本次最终开发集裁决。
