# Human Gold v1：双人标注、仲裁与冻结

**HUMAN_GOLD_PROTOCOL_READY / HUMAN_GOLD_PENDING / INDEPENDENT_HOLDOUT_PENDING**。130候选是110旧模板代表+20新复杂开发案例；规模以覆盖为依据，没有凑成120。生成参考、项目参考、代理审阅、真实独立人工标注和真实消费者来源分别记录。

工具：`src/evaluation/gold.py`、`scripts/gold_workflow.py`。当前队列文件hash由candidate-manifest.json列出，属于待标注输入快照，不是Gold冻结审批。每位评审独立文件；字段/输入/版本校验后，compare输出逐字段agreement、Cohen kappa和全部分歧；边际完全相同导致kappa分母为0时记null，不伪造1。summary/reply/attribution采用内容差异列表，不假定不同措辞一定错误。

```powershell
python -B scripts/gold_workflow.py compare --dataset DATASET.json --reviewer-a A.json --reviewer-b B.json --output NEW_DISAGREEMENTS.json
python -B scripts/gold_workflow.py freeze --dataset DATASET.json --reviewer-a A.json --reviewer-b B.json --adjudication ADJUDICATION.json --output NEW_FREEZE.json
python -B scripts/gold_workflow.py verify --manifest NEW_FREEZE.json
```

仲裁记录需要reviewer/human_declaration/status=approved、dataset_hash、两份packet_hashes（顺序A/B）、decisions和final_packet。final_packet形状与完整评审packet相同，记录最终七字段和生成参考。每个字段/内容分歧必须有sample_id、field、rationale；即使两位原来一致，仲裁改值也必须说明理由。文件hash使用产品digest的规范JSON，不是编辑器文件字节hash；可用Python `src.domain.contracts.digest(json.loads(...))`计算。

freeze排他创建，已有文件拒绝覆盖。manifest包含源样本、最终样本、两份评审与仲裁原件、agreement、source_dataset_hash、dataset_hash、freeze_id、payload_hash。verify重新执行约束与构建，防止样本、仲裁或hash链不一致。机器验证的是数据完整性与声明；评审身份、独立性、权属和封存访问必须由研究负责人真实管理。

模板族、同义/近重复、来源与历史暴露检查必须在划分前完成。当前全部旧400参与过历史开发，20新样本也已暴露，因而没有独立holdout。holdout_candidate只隔离候选，不能升级为sealed。新独立holdout应由未参与Prompt调整的真人组织，存放限制访问位置，冻结前预注册指标/适用样本/门禁，冻结后任何修改产生新版本和访问记录。仓库不能实现人员访问隔离；不伪称已经封存。

本轮真实评审数=0，仲裁批准数=0，Human Gold冻结数=0，独立准确率=null。单元测试中的unit-test reviewer声明仅存在临时合成fixture，绝不是项目审核人员。
