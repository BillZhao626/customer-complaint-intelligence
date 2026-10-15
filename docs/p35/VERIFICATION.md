# P3.5交付与验证（2026-10-15）

|状态|证据边界|
|---|---|
|CALIBRATION_OWNER_DECISION_SNAPSHOT_VERIFIED|最终24条开发裁决冻结v1.1；用户确认专家结论一致；原始独立专家表未提供，不计算Kappa|
|V3_CONTRACT_AND_COMPAT_VERIFIED|双层Pydantic/JSON Schema、证据/版本约束、v2往返及显式有损投影、SQLite、正式service和UI通过|
|DATASET_CANDIDATE_AUDIT_VERIFIED|172保留记录，160 eligible，12质量隔离；来源/完整性/覆盖/词面泄漏已审计，真人语义审核待做|
|E2E_OFFLINE_V3_VERIFIED|实际Application Service、临时SQLite、只读replay、fake/模拟HTTP、AppTest与限定浏览器切片|
|HUMAN_GOLD_PENDING|开发裁决已冻结；独立Gold协议要求的原始双标/仲裁证据及新候选审核未完成|
|INDEPENDENT_HOLDOUT_PENDING|全部开发候选已暴露，未冒称独立测试|
|REAL_MODEL_V3_QUALITY_PENDING|无真实v3语义实验，离线通过不证明模型质量|

## 实际变更

保留Streamlit/LangChain/DeepSeek/Application Service/SQLite。新增analysis_v3、v3_prompt、v3_safety、v3_statistics、v3_view、calibration、e2e_v3、dataset_audit_v3与offline CLI。原v2 result继续可读；完整v3以版本绑定metadata_json保存，不迁移或重算旧数据。客户重要性、业务顺序、流程团队与责任核实分别表达。依据和复杂方案取舍见[DESIGN](DESIGN.md)，投影损失见[CONTRACT_COMPAT](CONTRACT_COMPAT.md)。

24题处理及补充包台账见[CALIBRATION](CALIBRATION.md)。v1到v1.1为追加冻结，未覆盖先前证据；原空白专家表不再作为“研究者未裁决”的依据。题10可用显式owner-operational-v1复现有损v2夹克选择，同时v3保留equal。新候选重建、12条隔离补充及人工入口见[DATASET_AUDIT](DATASET_AUDIT.md)。

## 自动验证

- 修改前基线：本机120/120（76.598秒）、portable40/40（23.523秒）。
- 最终本机154/154（74.357秒），0失败/错误/跳过；原120全部保留，新增34。portable67/67（28.710秒）；最后干净暂存树导出67/67（26.300秒），含27项可公开新增检查；另7项依赖本地裁决与候选，明确不进入portable。机器ID见[evidence/test-results.json](evidence/test-results.json)。
- 新增覆盖严格类型/枚举/额外字段、Unicode证据跨度、重复issue/关系、equal与业务顺序、尺码兼容、v2无损回程、虚构承诺门禁、幂等/重读/数据库篡改、来源版本隔离、失败/fallback/missing分母、内容审核绑定和关键错误、实际LangChain/OpenAI SDK模拟HTTP、重试预算、实际app.py与审核入口。
- 160条新候选（v2）正式服务链路成功160/160，12排除；160条参考、摘要和回复评分仍pending。状态fixture的2成功/1失败/1fallback/1missing/1排除验证不缩分母。详见[EVALUATION](EVALUATION.md)。
- Python源码内存编译通过，pip check无冲突，git diff --check无空白错误。

失败与修复：测试先行初次3项缺模块错误保存在.local/p35/red-v3.txt；首次导入v3_demo发现一个多余右括号，已修正；整理证据时next(list)错误在写出前发现，改为索引后完成。以上失败不计为通过；没有删除旧测试或改历史expected让回归变绿。

## 浏览器范围

在127.0.0.1本地Streamlit、API/trace关闭下，实际浏览器提交双问题fixture、重复点击仍同run、重启服务与刷新重读、按ID载入；观察两个equal与处理顺序1/2、责任unverified、邮件1/问题2；下载统计并核验SQLite只有一个run。另浏览长中文候选并下载pending审核草稿，未伪造reviewer/human_declaration。记录见[evidence/browser-e2e.json](evidence/browser-e2e.json)，截图与DOM本地保留。

浏览器证据仅限离线v3切片与审核入口，不代表完整批量/真实模型/P4发送E2E。模型注入抵抗与自然语言幻觉的有效性仍需真实实验；保守文本门禁存在误拒/漏检限制。

## 保护、费用和Git

起点HEAD为38e79ec，既存未跟踪资料及源码恢复副本在.local/p35/recovery；未清理/重置它们。314项保护文件hash全部不变，包括历史数据/outputs/论文原件、冻结Prompt、.env、P2试点与账本、24题原包；见[evidence/asset-protection.json](evidence/asset-protection.json)。旧400、80参考、12次真实调用、14张历史表均由原回归继续验证。旧80仍494/560、32/80全对；P2仍83/84、11/12全对。

实际.env的LLM_ENABLE_API=true未修改；所有本轮验证显式关闭API和trace，测试入口阻断外部socket。真实新模型调用0，实际新增API费用0元；未用60次/15元合成生成额度。未发送邮件、未实施P4审批状态机，未创建Tag/Release或重写历史。Git安全交付收据另见[GIT_DELIVERY](GIT_DELIVERY.md)。

## 交接

现成入口：新分析模块、scripts/p35.py、Single Analysis下两个P3.5面板。当前最终开发冻结为calibration-decision-v1.1；最终候选为dataset-candidate-v2。新数据和完整证据只在.local。

后续真人工作：新160条eligible的自然度/证据/标签审核、摘要/回复Rubric评分、独立Gold与holdout组织；不再要求研究者重复确认已冻结的24条。真实v3质量实验需要针对评测用途的新实验授权与独立账本；P4仍需明确审批角色、政策与模拟发送范围。
