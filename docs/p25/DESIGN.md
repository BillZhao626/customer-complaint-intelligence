# P2.5 实施依据与兼容方案

2026-10-15。用户已授权本地提交、审核后 Private 推送、数据审计、评测与标注工具；未授权新增付费请求。基线提交为 `5ffa9a9a6899dd2bd0fb4b402781fac273888dad`，原77项及新增2项可移植 smoke 共79项通过。

当前 Application Service 输入为 EmailInput(subject/body)，UI 不清洗内容；live adapter 将两者作为 JSON human message。新评测复用这个输入和服务，离线历史重放使用保存的 AnalysisRun JSON，绝不通过 Repository 构造器打开原P2库（它有启动恢复写入副作用）。新执行仅允许 fake，临时 SQLite。历史12和旧80分开，不改任何旧报告。

新增 e2e-evaluation-v1 契约，绑定样本/输入hash、来源、分组、annotation/taxonomy/schema及 RunConfig。七字段与生成内容引用分离；无人工审核只能 pending。分母包含 eligible 中的失败、缺预测，另列 attempted/evaluated/pending。失败是 FN，不是 unknown 的正确预测；指标不跨版本/来源混合。Schema合法不是语义正确。

Human Gold 以独立评审文件、分歧比较、仲裁、排他创建的freeze manifest构成。工具验证结构与签署声明，不能证明签署人确为真人或没有看过预测；真实审核/访问控制仍是流程门槛。当前所有旧400已参与开发/历史实验，新代理编写样本也已暴露，不能把任何一组宣布独立盲测。分组隔离用于候选队列，后续独立holdout须由真人另行创建并控制访问。

Service/Other：已有枚举不变，新增独立决策规则/Prompt实验版本；旧P2 Prompt文件和83/84 expected冻结。仅以明确对象证据分类，不做正文关键词强行覆盖模型结果；默认产品UI仍用P2版本。无新API证据，REAL_MODEL_FIX_PENDING。

验收：原77项、portable smoke、分母/版本/输入绑定负测、Gold门禁、重复和分组泄漏、离线service存储/统计/追溯；262冻结资产及全部本轮起始数据/outputs/P1-P2证据/.env/.local-P2哈希不变。报告分别列工程、语义、生成内容人工评价、浏览器、独立Gold状态。
