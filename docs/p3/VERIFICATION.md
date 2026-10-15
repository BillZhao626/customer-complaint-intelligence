# P3 验证与交接（2026-10-15）

**P3_ATTRIBUTION_IMPLEMENTED / P3_DASHBOARD_VERIFIED / OFFLINE_REGRESSION_VERIFIED**。

## 工程证据

- 修改前原108项：108/108通过，58.700秒。最终全套：120/120通过，78.375秒，0失败/错误/跳过；原108保留。机器测试ID见 [test-results.json](evidence/test-results.json)。本机完整日志 `.local/p3/regression-final.txt`。
- 12项新增测试包含明确分母、状态桶、完整成员与原文、门店/产品/情绪和交叉筛选、零分母、版本隔离、重试去重、带时区时间范围、dataset/input/run绑定拒绝、SQLite只读拒写、已知归属误差及实际app.py AppTest。
- 全新Python 3.12虚拟环境安装成功，`pip check`通过；安全候选树导出不含历史资产，portable **40/40通过，17.964秒**，新目录demo成功。直接依赖固定版本，传递依赖实际解析清单见 [fresh-resolved-requirements.txt](evidence/fresh-resolved-requirements.txt)，该清单是Windows环境证据，不宣称跨平台完全锁定。
- 首次fixture错误是重复插入已存在结果，已修复；首次安装烟测在pip安装尚未结束时启动，导致一个缺Streamlit导入错误，已等安装成功后完整重跑40项。失败日志均保留本机，不算通过证据。

## 实际业务能力

Dashboard → P3 versioned attribution：选SQLite绑定manifest或P2已保存JSON，再选唯一版本、门店、产品、情绪、状态与时间。概况→分布/交叉表→统计项→分子或分母成员→原文及保存分析。导出JSON包含来源、dataset hash、配置版本、过滤器、成员及input/output/reference hash。

10条显式合成fixture：7成功、1failed、1fallback、1interrupted_or_unknown；5投诉、4negative、3有效业务归属。投诉全邮件5/10，成功集5/7；negative全邮件4/10，成功集4/7；有效归属3/5。每个指标保留两侧成员ID；failed/fallback不进入成功业务分母；unknown、unclear、none分别保留，legacy归属缺失显示unavailable。

故意错误的 `p3-wrong-attribution` 参考为 delivery/logistics issue、预测为 product issue；P2.5统一评价返回真实P3快照及参考聚合差异，不能靠运行成功掩盖分类误差。P2保存12条重新只读验证，仍83/84字段与11/12邮件；模型修复没有新证据。

统计时间是运行 created_at，非客户购买/投诉发生时间；时间区间内按 email_id+input_hash 取最新run，修订版不是独立消费者。未绑定manifest的库为unregistered并警示来源不可核实。原始门店值精确分组，没有批准的别名映射。旧400保留historical-only入口及原14表，不伪造现代实验元数据。

## 浏览器证据

**BROWSER_E2E_VERIFIED（P3离线切片限定范围）**。通过实际Codex内置浏览器连接本机Streamlit，API及trace开关关闭：

1. 进入P3页面，选 B / Service/Other / negative，剩1成员；打开 `p3-service` 原文与run/input hash。
2. 叠加failed筛选后0成员，rate显示NULL / unavailable，旧详情移除。
3. 切换P2保存结果，确认deepseek_live冻结版本及12条历史记录；打开原文，下载统计JSON，校验dataset/cohort及12条分母。
4. Single Analysis提交同一已注册合成输入到普通offline_fake，生成另一版本run；浏览器刷新后同run ID和原文仍可读取。
5. 回到P3切换两个版本，原fixture cohort仍10条，新offline-demo cohort仅1条，未静默合并。

浏览器发现P3下方混排旧Current Session统计，已修正并加AppTest断言。证据索引见 [browser-e2e.json](evidence/browser-e2e.json)；DOM与截图保留 `.local/p3/browser-*.txt`、`dashboard-overview.png`。截图只作为交互的辅助证据。完整批量上传、真实模型、P4审批/发送不在此浏览器VERIFIED范围内。

## 人工与后续门槛

24条可直接复核包在 `.local/p3/calibration-v1/START_HERE.md`。20条复杂开发样本+4个不同历史模板/场景代表；没有完全重复正文，两两原文SequenceMatcher最大0.7696、>=0.92为0对（仅词面检查，不认证语义独立）。原sample ID/hash保留，来源分成两组，双评审Markdown工作表、空JSON、待签署仲裁齐备。摘要/回复/归因参考包含facts/forbidden/constraints/alternatives待填及rubric说明。身份、人工声明、答案、Gold批准均未自动填写。

**HUMAN_GOLD_PENDING / REAL_MODEL_FIX_PENDING / INDEPENDENT_HOLDOUT_PENDING**。校准案例已暴露，只能开发用途；未来holdout须隔离模板/语义族并封存。当前回复仍是未审核、未发送草稿。

P4进入条件：P3工程基线已具备；下轮明确授权回复编辑、真实人工角色及政策边界、版本绑定审批/撤销/幂等的模拟发送状态机。不得直接接真实SMTP。P5进入条件：P4闭环离线验收、真人审定Gold、隔离holdout、单独模型/数据/调用次数/预算授权，补全浏览器上传到审核模拟发送链路及真实质量评价；不要求技术栈重写。

保护资产结果见 [asset-protection.json](evidence/asset-protection.json)；公开与Git最终结果见 [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md)。本轮新增真实模型调用 **0**，没有发送邮件、Tag、Release或历史重写。

## 公开远程复验

工程commit 7ad569e9ac532a0be64248d11420185e8c904a0b公开后重新clone，确认不含.env/data/outputs/.local；使用本轮新建环境运行portable 40/40通过。GitHub Ubuntu也完成全新安装、pip check、40项测试和demo。远程文件树及历史与本地一致；安全清单由commit audit保存，原未跟踪资料保留本机。
