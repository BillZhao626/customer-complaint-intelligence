"""Integrate current evidence into a new thesis draft; keep old thesis immutable."""
import json,re,sys
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];DOC=ROOT/'docs/p5b8'
def main():
    r=json.loads((DOC/'RESULTS.json').read_text(encoding='utf-8'));b=json.loads((DOC/'BASELINE.json').read_text(encoding='utf-8'));repair=json.loads((DOC/'REPAIR_RESULTS.json').read_text(encoding='utf-8'))
    p=r['resource_paths'];v=r['insights'];old=ROOT/'docs/p5b7/thesis_full_draft_p5b7_v1.md'
    text=f'''# P5-B8 研究与论文结果

正式题目：**Research and Web Implementation of Customer Complaint Sentiment Analysis and Source Attribution System Based on Large Language Model and LangChain**。

**主要结论：工程链路已经连接；本轮不能证明结构化情绪与Issue分析对回复有稳定、可泛化的语义优势。** 实验A自动主要终点2对改善、25对持平、63对未评分；实验B1对退步、10对持平。改善包含一个直接链JSON解析失败，另一个“记录/转达表扬”Judge判定存在一致性争议。不得据此宣传情绪分析带来7.4%的普遍质量提升。

| 导师要求 | 真实功能 | 本轮证据与结果 | 状态 |
|---|---|---|---|
| 生成含门店/产品/赞美或投诉的邮件 | 历史真实DeepSeek生成90；本轮冻结后新增4个问题家族 | B7 raw生成90原样；B8N原始请求/响应；自然度未人工认证 | VERIFIED生成 / HUMAN_PENDING代表性 |
| LangChain识别情绪及来源 | 既有ChatOpenAI实际请求；新增表达/体验/投诉/Issue独立层 | B7新分析87/90接受，迁移4/4；证据子串验证；无新独立Gold | VERIFIED链路 / HUMAN_PENDING语义 |
| 产品与门店统计 | 确定性按Case/类别去重与原文下钻 | 90派发、87有效、3失败，负面表达23、负面体验55、投诉yes24/uncertain38，未知来源保留 | VERIFIED复算 / 非真实经营结论 |
| 自动客服回复 | 原文→分析→本地查询/任务→回执→回复→门禁→草稿审核 | A90配对、B11独立数据库、新族4配对、8消融、6修订 | IMPROVED_NOT_CERTIFIED |
| 友好Web应用 | 保留React工作台、业务洞察、质量实验 | 94封全部导入、失败无草稿、本地审核/模拟/重启、5视口CSS实测 | VERIFIED本地产品 |

## 定义与RQ1：识别了什么

`ANNOTATION_GUIDELINES.md`冻结研究适配：A客户表达情绪、B体验、C投诉意图、D每Issue情绪、E时限/风险、F报告业务来源。客观故障可以表达neutral、体验negative；投诉纠正与愤怒不同。混合评价保留多个方面。风险依事实而非愤怒。业务归因不证明因果或法律责任。

[SemEval-2016论文](https://aclanthology.org/S16-1002/)及[官方指南](https://alt.qcri.org/semeval2016/task5/data/uploads/absa2016_annotationguidelines.pdf)提供方面/证据建模思路，但其neutral包括轻微评价，与本项目客观查询neutral不等价；不能直接宣称复现。多方面异极性参照[MAMS](https://aclanthology.org/D19-1654/)。[Front](https://help.front.com/en/articles/4874880)客服规则支持将无情绪的故障报告与负面情绪分开。[GoEmotions](https://research.google/pubs/goemotions-a-dataset-of-fine-grained-emotions/)用于多标签/不明状态及多评者方法参考；[Senta](https://github.com/baidu/Senta)用于中文基准研究，未部署其大型模型。本轮未迁入外部语料，版本、许可与领域差异见规范。

历史80均为合成开发参考，不是独立泛化Gold。原情绪LLM78/80=97.5%，Macro-F1={b['llm']['macro_f1']:.4f}；原创轻量词表19/80=23.75%，Macro-F1={b['rule']['macro_f1']:.4f}。词表在旧negative52例的Recall=0，neutral14例=1，positive14例=5/14；LLM依次50/52、14/14、14/14。该差距既包含词表覆盖不足，也包含旧业务极性与新表达定义不一致，不能证明新表达维度达到97.5%。全部混淆矩阵与其他字段在BASELINE.json/HISTORICAL_CLASSIFICATION.json。

历史560字段494一致、66差异、32/80邮件七字段全对保持。产品原40/80保持；18标签口径+10缺食品类不能当作28次语义修复；11分类轴歧义、F376理解错误候选仍待相应语义确认。F201/F260新层提出neutral表达/negative体验的合理解释，旧negative参考与原预测均不改。旧24裁决、16客服开发Gold不重签。

本轮B7新层87/90接受；表达positive14/negative23/neutral44/mixed6，体验positive13/negative55/neutral10/mixed7/unknown2，投诉yes24/no25/uncertain38。3条缺uncertainty字段首次失败保留。新表达/体验/Issue/来源没有独立人工真值，Accuracy、Macro-F1、逐类Recall与Kappa均不可计算；这些分布不是准确率。

## RQ2：相同信息下的受控回复增益

两组同完整原文、模型deepseek-flash、temperature0、thinking disabled、输出上限4000、事实/政策、附件清单为空和**完全相同真实回执**；唯一输入差异是结构化分析。A共同回执来自分析规划，故只估计给定此回执条件下的回复增益，不能估计独立动作能力。每封按奇偶轮换先后，首次响应不可替换。

预注册主要终点为自动Judge无H01..H07且B1事实、B2诉求覆盖均2分。90对全量派发，其中27对预冻结Judge抽样；两组暂定通过分别25/90和27/90，另63对UNKNOWN（不能把其算通过或当成已证实失败）。**在27个已评分对子中**为25/27与27/27，改善2、退步0、持平25；条件差异+7.41个百分点，配对bootstrap95%区间[0,18.52]个百分点，McNemar双侧p=.5。目的抽样/合成数据不支持客群总体推断。

B7-010涉及表扬记录/将来转达，Judge对两组相近措辞的判定可争议；B7-085直接链JSON少闭合括号，解析后输入Judge为空串，因此该改善主要是工程可用性，不能归因于情绪理解。全部原始无效JSON仍在CASEBOOK，不能用空串展示代替原始失败输出。完整邮件和两组**完整首次回复**见CASEBOOK.md与AB_COMPARISON.csv。

A直接链平均{p['A_DIRECT']['mean_tokens']:.0f} tokens、{p['A_DIRECT']['mean_serial_ms']/1000:.3f}s、费用上界¥{p['A_DIRECT']['mean_upper_cny']:.6f}/邮件；增强路径计入分析后平均{p['A_GUIDED']['mean_tokens']:.0f} tokens、{p['A_GUIDED']['mean_serial_ms']/1000:.3f}s、¥{p['A_GUIDED']['mean_upper_cny']:.6f}。同90封上增加约{p['A_GUIDED']['mean_tokens']-p['A_DIRECT']['mean_tokens']:.0f} tokens、{(p['A_GUIDED']['mean_serial_ms']-p['A_DIRECT']['mean_serial_ms'])/1000:.3f}s、¥{p['A_GUIDED']['mean_upper_cny']-p['A_DIRECT']['mean_upper_cny']:.6f}。时延为真实模型阶段串行合计，未含UI等待；本地工具毫秒级耗时未单独计时，不能伪称纯模型之外已精确分摊。

8个去情绪消融首次输出已保存，但固定前8封以正面反馈为主，没有独立Judge配对评价，不能分离情绪字段与Issue字段的因果贡献。4新族配对Judge全持平，样本极小且同Provider；其中多轮样本把Case ID写成订单号，属于生成自然度/独立性缺陷，保留不重生成、不移出分母。

## RQ3：完整业务流程

B基础链从原文另用一次模型规划允许动作；完整链从既有首次结构化分析规划。两组同政策、工具权限、默认UNKNOWN事实，各Case/每组从独立空SQLite开始。保存真实请求/执行/created/handoff_pending，只有本地待处理请求，无商家事实时不编造。

11对全部Judge：基础链11/11、完整链10/11主要终点暂定通过，0改善/1退步/10持平。B7-009完整链“将转达感谢”被Judge标H04，但这涉及未来意图/承诺与完成式的边界，应真人裁决；冻结主结果不静默改分。不能证明完整链优于基础链。

B基础路径（含规划）平均{p['B_DIRECT']['mean_tokens']:.0f} tokens、{p['B_DIRECT']['mean_serial_ms']/1000:.3f}s、¥{p['B_DIRECT']['mean_upper_cny']:.6f}；完整路径（含分析）{p['B_GUIDED']['mean_tokens']:.0f} tokens、{p['B_GUIDED']['mean_serial_ms']/1000:.3f}s、¥{p['B_GUIDED']['mean_upper_cny']:.6f}。复用分析在账本只付一次，路径比较重新归属其开销，不能把各路径总和误作实际账单。

R2为已曝光开发修订：3次分析+6次回复+6次Judge，独立运行身份与Prompt增补；补齐required-key要求、避免重复处理已发送照片、避免无执行系统的未来回访承诺、按负面体验将实际产品故障路由售后。2/3分析恢复，B7-034仍漏uncertainty；6/6回复可解析。Judge3改善/3持平仅开发诊断，分析仍失败的Case即使Judge高分也不能算端到端成功。主A/B和新族首次结果不被替换。

确定性Guard v2补充了真实失败中的“已经将查询请求提交”“已经在内部提交查询请求”等谓词，严格绑定当前input_hash、event_id与对应created任务；查过UNKNOWN不支持“已提交”。安全否定/条件式不作危险正向指令。旧Guard输出与新派生重评分并存。语言、附件、偏好与多Issue仍有代理争议，不能用Schema合法替代语义正确。最终工作台门禁另保留旧独立危险事实、证据偏移与未来执行能力规则（workspace-guard-3），94个Case中66待审、28阻断（含4个无可审草稿的分析/JSON失败），并非66个人类认可。B7-036的安全否定没有误拒，仍因无执行系统的“我们会尽快回复”承诺被拦截。该最终门禁是事后产品兼容检查，不回写主实验评分。完整679离线回归在最后适配前完成；最后适配后11专项通过，时间范围分开。

## Judge可信度与局限

复用B1..B5，不用固定Gold回复。8个本轮政策控制全部精确，但本轮没有额外H01正向危险指令付费控制，仅继承历史控制及离线安全测试；此局限单列。A/B顺序交换6对，分数/错误码完全相同4/6，不等于真人一致率；情绪分与自然度多为顶分，可能有天花板。提示明确不奖励长度，但没有独立人工长度控制，不能宣称已排除长度偏好。条件式、未来承诺与完成式在B7-009/B7-010仍有评分争议。

本轮独立真人数值评分0、双人标注0、新人类Gold0；Kappa不可计算。模型同Provider的生成/分析/Judge存在相关错误。OWNER_DECISIONS按5个语义族集中问题，保留空白真人决定，不预填认可分数。

## RQ4：可追溯统计

分母90邮件，87有效分析、3结构失败；旧B2仍72/90，绝不把旧72当全部输入。新口径区分23表达负面、55体验负面、24确定投诉、38投诉意图不确定、6混合表达。产品排行按每邮件每类别去重，Issue原始数量与邮件关联数量分别保存；跨类可重复。同一Case可从统计分子/分母下钻原文、分析、工具、完整回复和评价。门店只按历史显式中英文别名归并，未知保留，不猜测分支。

统计示例数据及每个Case成员见RESULTS.json的insights。24确定投诉不能代替全部负面体验，也不能忽略38不确定；uncertain均判yes的敏感性上界为62/87，判no为24/87，两者都不是人工确认投诉率。不得把分类来源写成真实经营责任或因果。

## 资源、运行与证据

398/400底层请求，输入1,231,593、输出104,943、合计1,336,536 tokens；高峰全未命中计价上界¥3.302730，硬上限¥12，实际独占账单UNKNOWN。账本halted=P5B8_EXPERIMENT_COMPLETED，无自动重试；后续新付费不恢复旧账本。全部首次raw/错误/usage/回执、冻结Prompt/版本及SHA已保存。生成90来自旧B7账本，本轮没有重复付费生成这90；本轮4新邮件、94分析、188 A回复、33 B规划/回复、8消融、56主Judge/控制和15修订合计398。

工程：原B2、原Gold、data、outputs、旧SQLite和账本/.env保持Hash；只新增本轮文件和最小共享入口。Web真实操作与5视口CSS证据见UI_ACCEPTANCE.md，全部离线回归结论见VERIFICATION.json。学校Word/PDF未排版或人工终审，不能称毕业设计已获导师质量认证。

## 交付状态

VERIFIED：来源核对、规范、关键词程序、真实398请求、A/B隔离、工具回执、Trace、确定性统计、React浏览器与ZIP内容完整性。IMPROVED_NOT_CERTIFIED：工程与6案开发修订。HUMAN_PENDING：新Gold、语义质量、自然度、Judge争议、真人认可与独立泛化。FAILED：B7-034修订仍缺字段；3条主回复JSON失败保留；系统级主实验未显示优势。NOT_RUN：独立双人标注/Kappa、广覆盖情绪消融评价、真实外部业务、最终Word/PDF。AUTHORIZATION_BLOCKED：真实发信/退款/物流联系/订单预约修改/正式发布（本轮未授权，无尝试）。

![配对主要终点](figures/paired-primary.png)
![不同统计口径](figures/separate-statistical-definitions.png)
![额外资源](figures/resource-costs.png)
'''
    (DOC/'RESEARCH_AND_THESIS_RESULTS.md').write_text(text,encoding='utf-8')
    draft=old.read_text(encoding='utf-8').split('# P5-B7 当前实现')[0]
    def section(heading,content):
        nonlocal draft
        pattern=r'(?m)^'+re.escape(heading)+r'\n[\s\S]*?(?=^#{1,3} |\Z)'
        draft,n=re.subn(pattern,lambda m:heading+'\n\n'+content+'\n\n',draft,count=1)
        if n!=1:raise ValueError('Section not found: '+heading)
    draft=draft.replace('# P5-B7 学校论文草稿更新版（未最终认证）','# P5-B8 毕业论文整合稿（研究质量未最终认证）')
    draft=re.sub(r'英文题目候选：.*', '正式英文题目：Research and Web Implementation of Customer Complaint Sentiment Analysis and Source Attribution System Based on Large Language Model and LangChain',draft)
    draft=re.sub(r'本版由历史I7F草稿派生，.*?\n\n',f'本版按章节增量整合P5-B7草稿，原件SHA256={sha256(old.read_bytes()).hexdigest()}。历史来源及实验结论保留边界；当前实现与研究以本章内容为准。学校Word/PDF排版与真人质量终审未完成。\n\n',draft,count=1)
    section('## 摘要','本文实现基于LangChain与大语言模型的投诉邮件情绪分析、业务来源识别及客服辅助Web系统。研究将客户表达情绪、体验倾向、投诉意图和Issue情绪分开，保留原文证据及版本。React界面连接邮件、分析、本地事实查询与任务、真实回执、完整回复、审核与可追溯统计。\n\n系统复用90封真实LLM合成邮件，执行控制信息的90对回复实验和独立工具状态的11对业务实验，另有4个新问题家族。自动Judge在27个已评分A对子中得到2改善/25持平，63对仍未知；B得到1退步/10持平。一次A改善与JSON解析失败有关，部分动作评分有争议，未证明结构化分析的稳定语义优势。增强路径增加Token、时延与费用。历史80三分类97.5%仅为开发参考，新维度暂无独立人工Gold。本轮398请求全未命中费用上界¥3.302730。结果说明真实链路和证据追溯可实现，语义质量、情绪贡献和实际消费者泛化仍需独立人工验证。')
    section('## Abstract','This thesis implements a LangChain-based customer complaint analysis and source-attribution system with a React service workspace. Expressed sentiment, experience polarity, complaint intent, aspect sentiment, urgency, and reported business source are recorded separately. Analysis precedes local fact queries and permitted tasks; actual receipts then ground response drafting and review.\n\nA controlled-information study dispatched 90 paired replies; 27 pairs received provisional automatic judgments, with two improvements and 25 ties, while 63 remain unknown. A separate 11-pair workflow study recorded one regression and ten ties. One improvement concerned invalid JSON rather than demonstrated emotional understanding, and some action judgments are disputed. Four new synthetic families and development repairs were retained separately. The guided path increased tokens and latency. The historical 97.5% three-class result is development-reference agreement, not independent expressed-sentiment accuracy. No new independent human Gold or generalization certification is claimed.')
    section('### 1.3 研究目标与主要内容','本文围绕四个研究问题：RQ1在明确规范下能否识别表达情绪、体验和来源；RQ2同事实/回执下结构化分析是否改善回复；RQ3完整流程中是否改善动作及可审核性、代价如何；RQ4如何得到包含失败、unknown和混合反馈的可追溯业务统计。导师五项要求通过同一真实产品链及证据包对应，不将建议架构当作已实现功能。')
    section('### 2.2 情绪分析','情绪分析需要区分客观负面事件与客户表达评价。本项目在SemEval-2016方面/证据框架基础上适配多维标注，并参考MAMS多方面异极性与Front客服边界。SemEval neutral含轻微正负评价，本项目neutral含无评价查询，二者不可直接比较。GoEmotions的细情绪和多评者设计只作方法参照。完整定义、原创边界案例和许可审查见附录标注规范。')
    section('### 3.4 系统总体架构','实际实现沿用现有Provider、事件表及草稿存储，新增薄编排而非Agent平台。\n\n```mermaid\nflowchart LR\n E[邮件与完整上下文] --> A[LangChain情绪与Issue分析]\n A --> Q[本地可靠事实查询]\n Q --> T[允许的内部任务]\n T --> R[真实事件回执]\n R --> D[同模型生成完整回复]\n D --> V[契约与事实动作门禁]\n V --> H[草稿与demo_test审核]\n A --> S[确定性统计与Case下钻]\n```\n\n历史B2分析与回复同次完成、业务任务其后创建的问题在新实验链中拆开，历史首次输出保留。')
    section('### 3.5 数据集构建与人工复核设计','保留400行/55程序模板池与80条AI辅助复核开发参考；24分类裁决和16客服开发Gold已存在，不重签。P5-B7真实DeepSeek生成90封，新标注不是生成意图标签。本轮另冻4新问题家族为synthetic family-transfer，依然无独立人类真值、同Provider生成与评价，不能代表真实消费者。数据用途DEV/Calibration/Independent synthetic分别记录，原文/input_hash与运行版本关联。')
    section('### 3.6 结构化输出字段设计','保留旧analysis-v3.2和产品Taxonomy。本轮p5b8-calibration-1独立新增表达、体验、投诉、Issue与风险证据。精确quote先校验，再确定性定位；不让模型估算字符偏移。新契约接受率不与旧72/90直接等同。工作台显示投影有单独哈希，原始Provider输出、分析ID、回复ID及工具事件保持绑定。')
    section('### 3.7 评测体系设计','先冻结主要终点、样本ID与评分器。实验A同事实/回执，仅是否提供分析不同；实验B各自执行工具且每Case隔离数据库。主要终点自动Judge无严重错误且事实和覆盖均2分；分母保留全部派发及未评。严重错误、工程JSON、语义、动作、自然度分开。没有真人标签的维度不计算伪Accuracy或Kappa。')
    section('### 4.1 工程结构与文件化输出','保留Streamlit历史入口与React工作台，正式本轮本地端口8773。src/application/p5b8_pipeline.py组织分析、事实工具、动作与回复；既有ChatOpenAI实际请求记录wire/raw/usage；p5b8_product将可复核投影接入原ProductStore。Case Registry采用引用旧Registry的overlay，未新建平行Gold平台。')
    section('### 4.2 单条邮件分析页面','React客服工作台展示完整客户原文、表达/体验/投诉、多个Issue及来源证据、真实本地任务、完整待审回复和Trace。英文原文与英文回复实际核对，照片声称已发送不等于系统收到附件。所有草稿需审核；演示审核与模拟发送标demo_test，不充当人类Gold。')
    section('### 4.3 批量邮件分析页面','本轮批量在独立授权账本执行；网页导入94封真实保存记录，不重复推理。失败分析或JSON结果也作为Case导入，阻止可审草稿；不会只显示旧72个成功结果。')
    section('### 4.4 Dashboard 页面','业务洞察区分表达负面、负面体验、确定投诉、投诉不确定和Issue评价；按邮件/类别去重并保留成员。原旧口径继续单列。1440视口内容宽1382px，修复研究页面只占Grid一列的根因；其他视口与截图在UI验收。\n\n![业务洞察](browser/insights-final-1440.jpg)')
    section('### 4.5 历史开发参考评测结果展示页面','质量实验包含历史开发参考混淆矩阵、新层分类分布、A/B完整回复、未评Case和Trace。Gold签署不占业务首屏；集中离线包包含所有已知失败及争议。\n\n![质量实验](browser/quality-final-1440.jpg)')
    section('### 4.6 批量推理与文件化保存','独立¥12/400请求授权逐次预留，实际398次、1,336,536tokens，上界¥3.302730，实际独占账单未知。Provider UNKNOWN不自动重发；账本关闭。原始首次响应、无效JSON、任务事件及费用不覆盖；业务事实UNKNOWN不通过本地任务伪装成商家确认。')
    result_part=text.split('## RQ2：')[1].split('## 交付状态')[0]
    draft=re.sub(r'(?m)^## 第5章 实验设计与结果分析\n[\s\S]*?(?=^## 第6章)',lambda m:'## 第5章 实验设计与结果分析\n\n### 5.1 规范、基线与历史范围\n\n'+text.split('## 定义与RQ1：识别了什么')[1].split('## RQ2：')[0]+'\n### 5.2 受控对照、质量与资源\n\n'+result_part+'\n\n',draft,count=1)
    draft=re.sub(r'(?m)^## 第6章 总结与展望\n[\s\S]*?(?=^## 参考文献草稿)',lambda m:'## 第6章 总结与展望\n\n本文完成真实邮件→LangChain分析→本地任务与回执→完整客服回复→审核→统计的可追溯研究原型。工程可用性有所改善，但A的有限自动优势与B的单例退步、Judge争议及语义标签缺口说明不能宣称结构化情绪分析普遍优于直接回复。后续应先完成盲化人工双评、语义家族隔离和有覆盖的情绪消融，再判断实际客群泛化。旧基线和所有失败保持。\n\n',draft,count=1)
    draft=draft.replace('## 参考文献草稿','## 参考文献\n\n1. Pontiki et al. (2016). SemEval-2016 Task 5: Aspect Based Sentiment Analysis. https://aclanthology.org/S16-1002/\n2. Jiang et al. (2019). A Challenge Dataset and Effective Models for Aspect-Based Sentiment Analysis. https://aclanthology.org/D19-1654/\n3. Demszky et al. (2020). GoEmotions: A Dataset of Fine-Grained Emotions. https://research.google/pubs/goemotions-a-dataset-of-fine-grained-emotions/\n4. Front (2026-06-23). Building AI classification in Front. https://help.front.com/en/articles/4874880\n5. Baidu Senta official repository. https://github.com/baidu/Senta\n\n历史文献占位与学校引用格式仍需最终核对：')
    (DOC/'thesis_full_draft_p5b8_v1.md').write_text(draft,encoding='utf-8');print('Integrated thesis and research results written')
if __name__=='__main__':main()
