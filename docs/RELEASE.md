# 完整工程与版本关系

候选分支为 `codex/full-product-public-20261115`，基于原公开 main 的 `f0a5eb71e7a46c036700f1d406cc3b34b680ff07`。原型提交历史保留，完整工程与新运行入口在其后继续。

工程经过精确文件树与提交祖先审查、从提交重新克隆的安装与离线验收。正式下载入口为 [GitHub Releases](https://github.com/BillZhao626/customer-complaint-intelligence/releases)，当前主线为 [main](https://github.com/BillZhao626/customer-complaint-intelligence/tree/main)。分支、main、Release 和 CI 的实际状态分别以对应远端记录为准。

## 主要变化

- 纳入当前 React、FastAPI、LangChain 及全部应用、provider、业务工具和评价实现。
- 增加可直接检出的合成样本与保存回复，解除演示对私有开发目录和数据库的依赖。
- 采用产品使用顺序重写 README，补充实际运行截图、架构、源码导航及验证方法。
- 清理机器绝对路径，明确历史实验与当前离线运行入口。
- 更新命中安全公告的依赖，并重新执行安装与回归。
- 增加精确发布树审计及 Windows/Linux CI 定义。远端 CI 的实际状态以运行结果为准。

作品集源码入口在正式发布后同步至仓库主页，显示为「GitHub · 完整源码与运行说明」。冻结作品集 v11 原文件继续保留；同步版本另行导出，不改写已冻结成稿。
