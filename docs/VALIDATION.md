# 工程验证与研究档案范围

使用 Python 3.12、Node.js 22、锁定依赖和提交内的 examples。安装需要软件包仓库，离线测试和回放不需要 API 密钥。

```text
python -m pip install -r requirements.lock.txt
python -m pip check
cd web-client
npm ci
npm test
npm run build
cd ..
python -B tests/run_offline.py
python -B verify_review.py
```

2026-11-16，从待发布分支的提交重新克隆，在没有 `.env`、私有数据库和已安装依赖的目录中按上述步骤安装。Python 3.12.8、Node.js 22.20.0、npm 10.9.3 下，锁文件安装及 `pip check` 通过；前端 15 项测试和生产构建通过。安全依赖升级与兼容修复后的全量离线检查收集 896 项，828 项通过、68 项跳过，零失败、零错误，耗时 450.579 秒。

最终代码检查提交为 `72c0e7bc984011c4c0696c2d7f8c0518ace41128`。其后发布文档与清单更新不改变已测代码及样本。实际 HTTP 启动的 9 个页面、API 和静态资源检查全部返回成功，健康接口报告 14 份保存案例及付费调用关闭。API 回放验证另行通过；npm audit 与锁文件 pip-audit 在本轮审查时报告零项已知漏洞。

## 通过与跳过分别统计

离线 runner 阻断外部连接，并使用临时数据库；examples 也在写保护范围内。验证包括结构化约束、原文证据、问题规划、同臂回执、事实检查、风险拦截、预算边界、版本冲突、审核及统计成员。

68 项跳过中，9 项是原有条件测试，另 59 项依赖未公开的私人历史研究档案。`tests/archive_support.py` 和各测试上的 `requires_archive(...)` 明确列出缺少的输入。原断言保留，恢复合法的原档案后可运行。它们不计入通过数，也不作为本次公开检出的模型质量证据。

公开的服务规划回归直接读取 examples 中的 90 封保存样本及一份特定损坏分析；预算测试使用显式临时 fixture。没有为通过测试编造私人原始账本、扩大人工确认范围或重新生成模型输出。

## API 回放

`verify_review.py` 在临时目录验证真实 API 的静态前端、14 份保存记录、历史分类、统计成员和原文、业务事件、风险批准拒绝、瑜伽垫原回复及精确评价、草稿新版本和退回动作。它通过内存中的 TestClient 运行，与人工浏览器操作分别记录。

## 浏览器与截图

README 的三张图片来自候选应用实际运行的完整浏览器视口，未改变截图内容。Codex 内置浏览器在本聊天返回 `Local browser access is unavailable for this chat`，即使用户确认启用仍未建立可控制的标签；因此不将尚未执行的内置浏览器全流程验收标记为通过。

## CI

工作流定义了 Windows 和 Ubuntu 上的锁文件安装、源码与历史扫描、前端测试、构建、依赖检查、离线测试和 API 回放。远端状态以 [GitHub Actions](https://github.com/BillZhao626/customer-complaint-intelligence/actions) 对应提交的实际结果为准，本地验收与远端 CI 分别记录。
