# Service/Other 与 unknown 边界

P2 `p2-inquiry`，run `104c892c-f289-4400-9d82-da7795f25945`，输入hash `9c64d9bde178c72dbc4b579d423ba1cb682f5cc2f58138cb16d0ed1bba281dc7`。原文询问Birch Store营业时间及in-store fitting service。expected Service/Other，实际unknown；摘要却正确识别了服务咨询。

源码可证实Prompt同时写了“缺product/category为unknown”和“explicit service-only subject Service/Other”，后又强调“Missing product is unknown”。因此已确认存在规则优先级歧义；不能窥知模型内部推理，也不能断言这是唯一因果。原83/84、expected、P2 Prompt和原始run保持不变。

| 证据场景 | 新决策 | 边界/反例 |
|---|---|---|
| fitting service，未选商品 | Service/Other | 明确服务对象，缺商品名不等于缺类别 |
| 单纯维修预约/安装服务 | Service/Other | 商品本身缺陷才是主问题时取商品类别 |
| 营业时间咨询 | Service/Other | 明确门店运营服务；不是“完全无对象” |
| 售后流程投诉 | Service/Other | 若主要请求修复损坏电器，取Home Appliances并保留流程信息 |
| 员工态度投诉，无商品 | Service/Other | 仅出现staff但实际是商品缺陷不能机械覆盖 |
| 明确耳机商品咨询 | Electronics | 不因是“咨询”而变成服务类别 |
| “我需要帮助”，没有对象 | unknown | Service/Other不是所有未分类对象的兜底 |
| 商品与服务同时出现 | 按明确主要未解决对象 | 没有主次：unknown并记录歧义，等待审阅 |

新规则版本`service-boundary-v1`、新Prompt`complaint-v2-service-boundary-1`，枚举和research-products-v2不变，分类优先级与说明显式版本化。旧历史参考可能不符合新解释；不得重标旧Gold。营业时间及服务流程口径仍需真人在Gold规范中批准，不借单元测试声称完成业务人员审定。

`category_boundary.decide_category`只接收已经提取/审阅的对象证据和主次，是可执行决策表，**不是正文关键词分类器**。不会批量把unknown强改为Service/Other。候选Prompt通过可选`DeepSeekAnalyzer(..., prompt_profile='service-boundary-v1')`接正式Application Service，默认UI仍用p2-frozen。实际payload、预算预留和attempt中的Prompt hash均绑定新版本；独立临时账本验证旧config不兼容。

测试先行：初始P2.5测试15项缺模块错误留存于本机red日志；规则正反例、新旧Prompt隔离、fake provider实际service链和新预算配置绑定已覆盖。开发回归入口：`python -B tests/run_offline.py test_p25.py`。其临时ledger与provider注入不触发外部调用；真实实验必须另获样本/模型/次数/费用授权，再用新目录创建带config/input whitelist的PilotBudget，禁止复用或重建P2账本。

状态：**BADCASE_CAUSE_VERIFIED（规范冲突证据） / BADCASE_RULE_REGRESSION_VERIFIED / REAL_MODEL_FIX_PENDING**。没有新DeepSeek验证，不宣称实际模型已经修好。
