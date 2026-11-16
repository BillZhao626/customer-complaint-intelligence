# 发布候选安全审查

审查日期为 2026-11-16，范围是拟公开文件树及该分支实际继承的提交历史。详细文件范围见 PUBLIC_FILES.json，最终提交和验证状态见 RELEASE.md 与本轮交付记录。

## 文件与隐私

精确候选树同时检查常见凭据格式、原开发机已知配置值、私有和生成资产类别、机器绝对路径及媒体位置。当前树扫描未发现待处理命中。扫描输出只记录路径、哈希与问题类别，不包含密钥值。

当前源码没有遗漏原项目的 `src/` 模块。个人目录被改为可移植路径；运行使用提交内 examples 和临时数据库。学校材料、真实 `.env`、私人数据库、原始预算账本、完整请求归档和第三方参考截图没有进入公开树。

邮件和回复是项目合成研究内容。保留的历史参考标签与精确版本裁决分别说明来源。公开截图是该候选运行界面的完整视口，没有拼接不同案例、修改数字或改写回复。

历史检查只针对候选实际携带的提交祖先，不将本地其他研究分支或应用内部引用一并推送。原公开 main 的历史保持可追溯，新提交使用 GitHub noreply 身份。

## 依赖修复

| 组件 | 原锁定版本 | 公开版本 |
| --- | --- | --- |
| Vite | 7.1.12 | 7.3.8 |
| LangChain | 1.3.1 | 1.3.9 |
| LangChain Core | 1.4.0 | 1.4.6 |
| Starlette | 1.0.0 | 1.3.1 |
| Pillow | 12.3.0 | 13.0.0 |
| Streamlit | 1.57.0 | 1.67.0 |

Vite 更新处理已公开的开发服务器路径访问公告。Python 审计命中 LangChain、Pillow 和 Starlette，Streamlit 同时更新以兼容 Pillow 修复版。更新后 npm audit 与针对锁文件的 pip-audit 均报告没有已知漏洞。版本与修复范围参考 [Vite 发布记录](https://github.com/vitejs/vite/releases/tag/v7.3.8)、[Vite 安全公告](https://github.com/vitejs/vite/security/advisories/GHSA-rq7h-c2jc-7f22)、[LangChain 包记录](https://pypi.org/project/langchain/1.3.9/)、[Starlette 包记录](https://pypi.org/project/starlette/1.3.1/) 和 [Pillow 发布说明](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)。

漏洞扫描反映审查时已公布的数据库结果，不能证明不存在未知问题。工程回归和保存模型结果的语义质量分别记录，依赖升级没有重写历史模型分数。

兼容性回归发现早期 Streamlit 统计下钻把草稿修订号用于选择值，编辑后可能保留已失效的选择。候选改为按稳定案例标识跟随最新记录；同时适配新版 AppTest 对单个 URL 参数返回字符串的接口。原文、保存回复及研究评价未改变。

## 默认运行范围

`review.py` 强制关闭模型调用和 tracing，绑定本机回环地址，只提供本地事项及模拟发送。API 验证检查实时调用被拒绝、原保存回复不变、修改生成新版本及退回审核。历史研究脚本和 provider 源码保留，但历史授权文字不构成新的模型调用授权。
