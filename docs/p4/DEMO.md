# 本机可操作演示

在 `D:\Projects\complaint_llm_system` 执行。此候选版本的UI强制禁止付费API和tracing，不读取新的模型额度。

```powershell
.\.venv\Scripts\python.exe -B -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

打开Streamlit提示的本地URL。默认工作库为 `.local/p4/product.sqlite3`，新增分析库为同目录 `product-analysis.sqlite3`。可通过 `COMPLAINT_PRODUCT_DB` 指向已创建演示库。旧研究数据源和原Dashboard仍可在原入口查看。

## 六分钟答辩路径

1. Single Analysis工作台选择普通产品信息咨询，说明Offline Fake是显式工程fixture。点击“分析并保存草稿”，查看输入、Issue、Evidence、来源和版本。
2. 先观察“模拟发送”不可用。保持演示身份 `demo_test`，填写原因并勾选核对项，批准后模拟发送。展示 `simulation_only`、获批版本和正文hash。
3. 选择“需要修改的回复”。未授权的“将联系客户”使批准不可用。填原因退回，删去承诺，保存新版本，展开v1/v2与diff；重新审核后模拟发送。
4. 选择“多Issue与处理顺序”，展示三个Issue、独立Evidence、客户重要性和业务顺序。选择“严重潜在安全风险”，展示severe/high、停用建议和额外安全审核项。
5. 选择“结构化契约失败”。raw只供诊断，没有草稿/审批/模拟发送；Dashboard显示失败并排除业务分母。
6. 选择真实历史run只读重放，搜索 `86d85387`。原P3.10 N04纠错仍是succeeded，但新安全层阻断minor/medium。不通过修改回复掩盖分析错误，可填写原因拒绝。说明原实验状态不变。
7. 从工作历史打开已模拟发送案例，刷新或关闭重开带case_id的URL。展示内容/版本/审核记录仍在SQLite。Dashboard的P4视图可按来源与版本查看计数及成员；原历史400条图表保持独立。

如果实际人工使用，明确选择 `local_human` 并填写自己的本地身份。不要把演示/自动化核对记录计为人类评测。未保存的编辑不是已归档版本。

## 自动构建完整离线演示

```powershell
.\.venv\Scripts\python.exe -B scripts/p4_demo.py --out .local/p4/NEW_DEMO --real-replay
```

输出目录必须不存在。`--real-replay`只在本机历史库可用时启用；公开检出省略它即可。脚本生成10条纵向场景证据，输出 `acceptance.json` 和含数据库环境变量的 `START.md`。真实重放不会引发新调用；所有脚本批准均为demo_test。

本次已构建 `.local/p4/demo-v1/`；按其中 `START.md` 可以打开持久化演示。实际浏览器另用 `.local/p4/browser-product.sqlite3`，避免混淆CLI与浏览器证据。

## 截图来源

截图来自本机运行的 `app.py` 和实际浏览器操作，保存在 `.local/p4/screenshots/`。包含恢复后的模拟回执、草稿版本差异、真实安全阻断和工作台。没有生成产品效果图；历史raw页面截图仅保留本机，不随Git上传。
