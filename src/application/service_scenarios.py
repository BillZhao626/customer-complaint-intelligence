"""P4.7 authored customer-service examples, separate from frozen research data.

The Runnable replays explicitly authored outputs; it does not understand new
mail. Reply policy describes communication and routing, never merchant terms.
"""
import copy
from langchain_core.runnables import RunnableLambda
from src.application.v31_demo import ReplayV31, fixture, pipeline_probe, span
from src.domain.analysis_v31 import AnalysisV31
from src.domain.contracts import EmailInput, digest


VERSION = 'p47-authored-service-scenarios-v1'
POLICY_VERSION = 'p47-service-reply-policy-v1'
POLICY = dict(
    version=POLICY_VERSION,
    scope='合成开发演示的沟通与分流策略；不是商家售后政策、人工Gold或模型质量结论',
    principles=[
        '围绕客户实际问题回答；已有订单、型号或照片不重复索要。',
        '投诉先共情，再确认陈述、可选处理方向和最少待补资料。',
        '客户可补资料与商家应核实的规格、订单、适用政策分开。',
        '安全优先停止使用，不要求重现故障；无人受伤不抵消严重潜在风险。',
        '退款、换货、补偿由有权限的人工核对；不承诺批准、时间或已执行动作。',
        '多问题按安全、履约、账单协调顺序回应；处理顺序不是客户主次或法律责任。',
        '明确人工请求、强烈不满、无法理解、严重风险和权限判断转本地人工演示。',
    ],
    reply_outline=['理解与共情', '已知事实与诉求', '处理方向', '必要资料', '权限或不确定性', '适用时的安全提醒'],
    capability='仅本地草稿、显式确认及模拟发送；无订单查询、售后执行、SMTP或CRM',
)
POLICY_HASH = digest(POLICY)
CUSTOM_SCENARIO = '自定义邮件（离线待人工）'
SCENARIOS = (
    '产品功能咨询', '配送包装受损', '商品售后故障', '多问题协同处理',
    '骑行安全风险', '重复爽约与强烈不满', '退款或换货申请', '诉求信息不清',
    '客户要求人工客服', CUSTOM_SCENARIO,
)


# Inputs and replies are deliberately kept together for review and versioning.
# They are developer-authored synthetic examples, never independent references.
_CATALOG = (
    dict(subject='DemoCam C200 能直接连电脑吗？',
         body='你好，我看中你们的 DemoCam C200，想用它在电脑上开视频会议。它能用线直接连电脑吗？如果还要买转接头，希望下单前先弄清楚，免得买回来用不了。',
         summary='客户在购买前咨询 DemoCam C200 的有线连接与转接头需求，已提供型号，尚无官方规格。',
         reply='您好，您想确认 DemoCam C200 能否有线连接电脑开视频会议，以及是否需要转接头。您已提供型号，不用再重复填写。仅凭型号还不能确认这项功能，需要对照商家提供的官方连接说明。为免买错，先不用急着购买转接头；您可以补充电脑的接口类型和操作系统，方便进一步核对是否匹配。',
         tier='ai_assist', reason='普通购买前咨询，可先拟定说明不确定性及补资料的回复。',
         customer_info=['电脑接口类型及操作系统'], internal_verification=['DemoCam C200 官方连接说明', '是否支持视频会议及适配要求'],
         next_actions=['说明已知型号和待核实功能', '只补充电脑环境，不重复询问型号', '取得官方规格前不确认支持或推荐购买转接头']),
    dict(subject='包裹送到了，但纸箱被雨淋透了',
         body='今天收到订单 DEMO-24031，快递把箱子放在门口，外箱被雨淋透了，侧面也破了。我拍了外包装的照片，但还没拆开检查里面的台灯。这种情况该怎么处理？我担心打开后有问题就说不清了。',
         summary='客户报告已送达订单 DEMO-24031 的包装雨淋、破损，已有外包装照片，商品本体状态尚不清楚。',
         reply='很抱歉包裹送到时出现了这样的情况，您担心里面的商品受损是可以理解的。订单号 DEMO-24031 和您已有外包装照片的情况都已在来信中说明，不用重复填写。请先保留外包装和现有照片；若商品或插头有受潮迹象，请不要通电，也不用为了取证试用。方便的话，请说明里面的台灯是否也有受潮或破损。售后人员需要结合这些资料和订单记录，确认适用的退换或其他处理方式。',
         tier='human_confirm', reason='商品本体状态及适用售后方式未确认，需人工核对。',
         customer_info=['商品本体是否有受潮或破损', '现有外包装照片（可直接附上，无需重新拍摄）'],
         internal_verification=['订单与签收记录', '适用的运输损坏处理方式'],
         next_actions=['区分包装受损与商品故障', '避免受潮电器通电', '核实资料后由售后确认适用选项，不直接承诺退款或补发']),
    dict(subject='上个月买的台灯突然不亮了',
         body='上个月在你们店买的台灯，昨晚正常开着，后来就不亮了。家里其他电器能正常使用，我没有拆过它。还没用多久就坏了，挺影响晚上工作的。请问是送修还是换一个？',
         summary='客户报告新近购买的台灯停止照明，未拆机，询问维修或换货；型号和订单尚未提供。',
         reply='抱歉台灯这么快就出现问题，也耽误了您晚上工作。您提到其他电器能正常使用，而且没有拆机，这些情况无需再重复说明。请先暂停使用这盏灯，不必拆开或反复通电测试。您可以提供订单编号和灯具型号，并说明是否有异常气味或外观变化。维修还是换货，需要售后人员结合购买记录、故障情况和适用政策确认，现阶段先把资料准备齐会更有助于处理。',
         tier='human_confirm', reason='售后故障需核实购买记录和适用维修/换货条件。',
         customer_info=['订单编号', '灯具型号', '是否有异常气味或外观变化（无需重新试用）'],
         internal_verification=['购买记录', '维修或换货适用条件'],
         next_actions=['暂停使用，不要求拆机或重复通电', '收集订单与型号', '由售后确认维修或换货选项']),
    dict(subject='抽屉、旧床取走和发票这三件事都还没解决',
         body='新柜子的抽屉晚上会自己滑出来，我已经磕到过腿，走道又比较窄。约好周六来取旧床，结果我等了一上午也没人来。还有订单 DEMO-24018 的发票少开了一张床头柜。三件事都还没解决，麻烦一起看一下，别每次只回其中一个。',
         summary='三项独立诉求：抽屉滑出造成磕碰、旧床取件爽约、发票漏开床头柜；希望全部回应，未声明同等重要。',
         reply='抱歉这三件事一直没有处理清楚，也让您白等了一上午。下面按事项回应，避免遗漏：\n\n1. 抽屉自行滑出：先尽量避开狭窄走道旁的这处抽屉，避免再次磕碰；请补充柜子型号或已有照片，不用复现滑出过程。\n2. 旧床未按约取走：请提供取件预约编号，方便人工核对周六的履约记录和可选安排，新的时间仍需确认。\n3. 发票漏项：您已提供订单 DEMO-24018 和漏开的床头柜，只需再附上现有发票信息，便于核对。\n\n三项都需要保留在这次处理范围内；维修、重新取件及发票调整分别由对应人员确认。',
         tier='human_confirm', reason='多问题需协调，存在普通磕碰风险及未履约事项。',
         customer_info=['柜子型号或已有照片', '旧床取件预约编号', '现有发票信息'],
         internal_verification=['柜子售后支持资料', '周六取件履约记录', '订单与发票明细'],
         next_actions=['先提示避免再次磕碰', '协调未履约取件记录', '核对已知订单发票漏项', '分别回应三项，不把业务顺序当客户主次']),
    dict(subject='折叠车骑到一半锁扣自己开了，我不敢再骑',
         body='昨天下班骑新买的折叠车，经过一段普通路面时，车架锁扣突然自行打开，车身晃了一下。我赶紧停车，幸好没摔倒，但真的吓到了。这车才用了两次，我现在不敢再骑。你们能不能给一个安全的处理办法？如果不能放心用，我希望退货或换车。',
         summary='客户报告折叠车车架锁扣骑行中自行打开，虽未摔倒仍存在严重潜在伤害；要求安全处理并考虑退换。',
         reply='很抱歉发生了这样的情况，骑行中锁扣打开确实会让人害怕。请先停止使用这辆车，不要骑行，也不要为了拍照或录像试骑、测试锁扣。即使这次没有摔倒，车架连接失效仍需要认真对待。请保留车辆和已有照片，方便的话提供订单编号、车型及锁扣位置的现有照片即可。这个情况需要人工售后按安全问题核实；您提出的退货或换车也应一并评估，具体方案需结合订单和检查结果确认。',
         tier='human_required', reason='车架承重连接骑行中失效，严重潜在伤害优先人工介入。',
         customer_info=['订单编号', '车型', '已有锁扣照片（不得为取证试骑或测试）'],
         internal_verification=['订单与型号记录', '人工安全评估', '安全问题对应的退换处理权限'],
         next_actions=['停止使用及骑行，不复现故障', '人工接管并核对严重风险', '一起评估退货/换车诉求，不先作批准承诺']),
    dict(subject='安装预约两次被取消，我不想再收到套话了',
         body='冰箱安装预约已经两次被取消，第一次说师傅临时有事，第二次我请了半天假，临出门又通知不来了。每次问都只让我等消息。我真的很生气，这次请找人工客服把情况说清楚，到底还有没有能确认的时间？',
         summary='客户报告安装预约两次取消及沟通无效，情绪强烈并明确要求人工，新的预约时间未确认。',
         reply='很抱歉两次取消预约，尤其是您已经请假等候，时间和安排都受到了影响。您希望由人工把情况说清楚，这个诉求应优先交给人工处理。请提供安装预约编号；已经说明的两次取消和请假情况无需再重复描述。人工人员需要核对取消记录与可用时段，再向您确认具体安排，不能再用一个未经核实的时间让您白等。',
         tier='human_required', reason='重复履约失败、强烈不满及明确人工请求，需要接管。',
         customer_info=['安装预约编号'], internal_verification=['两次取消记录及原因', '可确认的安装时段与履约能力'],
         next_actions=['先承认反复等待造成的影响', '响应明确人工请求', '核对记录与可用时段，不编造已经预约或联系']),
    dict(subject='耳机一边总是断音，能退还是换？',
         body='上周收到的耳机右耳总是断断续续，正常听音乐也会这样。我想知道可以退货还是换一副，不想再来回折腾。如果需要检查请把步骤一次说清楚，也想问下运费应该谁承担。',
         summary='客户报告耳机右耳间歇断音，提出退货/换货和运费承担问题，需人工核对订单与适用政策。',
         reply='抱歉刚收到的耳机就影响正常使用，您希望一次把退换和运费问题弄清楚是合理的。请提供订单编号、耳机型号，以及目前已有的故障描述；不用为了证明问题反复录制或重新测试。退货、换货和运费承担需要人工结合收货时间、商品情况及适用政策确认。您可以先说明更倾向退货还是换货，这有助于人工评估对应选项，具体条件和操作步骤应在确认后一次说明清楚。',
         tier='human_required', reason='退换与运费承担涉及商家政策和权限，需人工确认方案。',
         customer_info=['订单编号', '耳机型号', '更倾向退货还是换货'],
         internal_verification=['收货时间与订单记录', '退货/换货条件', '运费承担及处理权限'],
         next_actions=['回应故障、退换偏好与运费三个关注点', '人工核对适用条件', '确认后说明步骤，当前不承诺结果或补偿']),
    dict(subject='上次说的事情还是老样子',
         body='上次说的那个问题还是老样子，你们到底管不管？我已经讲过一遍了，不知道还要等多久。',
         summary='客户表达问题未解决及等待不满，但当前来信无法识别商品、具体事件和已有沟通内容。',
         reply='抱歉让您一直等着，重复说明问题也确实很费心。目前这封来信还看不到上次沟通的具体内容，直接猜测可能耽误处理。您可以提供订单或之前的服务编号，或者用一句话说明现在最需要解决的事情；不必重新整理完整经过。有了对应线索后，再由人工核对先前记录和下一步。',
         tier='human_required', reason='具体诉求和历史记录不足，不能靠离线占位判断。',
         customer_info=['订单或服务编号，或一句话说明最需解决的事（二选一即可）'],
         internal_verification=['对应历史服务记录'], next_actions=['承认等待和重复沟通的负担', '以最少澄清问题定位诉求', '转人工阅读，不生成猜测结论']),
    dict(subject='请转人工客服',
         body='人工客服。刚才的自动回复没有解决我的问题，请不要再给我同一段说明了。我需要有人看一下之前的沟通。',
         summary='客户明确要求人工客服并希望查阅先前沟通；当前尚无具体业务诉求或历史记录。',
         reply='抱歉刚才的回复没有帮到您。您希望由人工看一下之前的沟通，这个诉求很清楚，不需要再重复描述一遍问题。若方便，请提供之前的服务编号，便于人工找到对应记录。',
         tier='human_required', reason='客户明确要求人工，应进入本地模拟转人工路径。',
         customer_info=['已有服务编号（方便时提供）'], internal_verification=['先前沟通记录'],
         next_actions=['尊重人工请求，不重复发送自动说明', '本地模拟转人工并保留上下文', '实际坐席、转接完成或等待时间均不可伪称']),
)


def _issue(email, *, quote=None, **updates):
    ev = span(email, quote or email.body)
    value = dict(issue_id='main', object_type='product', object_name='unknown', category='unknown',
                 issue_kind='inquiry', reason='none', sentiment='neutral', urgency='medium', resolution='not_applicable',
                 evidence=[ev], business_process='none', routing_team='product_support', attribution_certainty='not_applicable',
                 missing_evidence=[], customer_requests=[], customer_importance='unspecified', importance_evidence=[],
                 handling_priority=1, priority_rationale='当前唯一诉求；不推断客户主次。', risk_level='none', risk_evidence=[],
                 risk_rationale='当前陈述未描述具体安全事件；此处不认证商品安全。', urgency_basis='other', urgency_evidence=[ev])
    value.update(updates)
    if value['risk_level'] in ('minor', 'severe'):
        value['risk_evidence'] = [ev]
    return value


def _unknown(email):
    # Reuse the existing bounded safety/urgency anchors so arbitrary input is
    # never treated as safe merely because no generative model was called.
    data = pipeline_probe(email).model_dump()
    data['issues'][0].update(missing_evidence=['具体诉求及对应业务记录'], customer_requests=['人工阅读原邮件并确认诉求'])
    reply = '抱歉，目前还需要确认您希望解决的具体问题。请提供订单或服务编号，或者简要说明最需要帮助的事项，便于人工核对。'
    if data['reply_language'] == 'en':
        reply = 'I am sorry this has not been resolved. Please share an order or service reference, or briefly describe what you need help with, so a person can review the issue.'
    elif data['reply_language'] == 'bilingual':
        reply += '\nPlease share an order or service reference, or briefly describe what you need help with for a person to review.'
    if data['issues'][0]['risk_level'] == 'severe':
        reply = ('请先停止使用，不要复现危险故障。请保留现有资料，交由人工核对安全问题。' if data['reply_language'] == 'zh' else
                 'Please stop using the item and do not reproduce the failure. Keep existing information for a manual safety review.')
        if data['reply_language'] == 'bilingual':
            reply += ' 请先停止使用，不要复现危险故障。'
    data.update(relations=[], sentiment='unknown', request_types=['unknown'], complaint_status='unknown',
                mentioned_store='unknown', store_verification='unknown', contact_channel='email', purchase_channel='unknown',
                summary='新邮件已保存为离线未知占位，需要人工阅读；未执行模型理解或风险认证。',
                suggested_reply=reply)
    return data


def example(name):
    """Return a new independent v3.1 fixture; old P4/P4.5 inputs are untouched."""
    index = SCENARIOS.index(name)
    if name == CUSTOM_SCENARIO:
        email = EmailInput(email_id='p47-custom-preview', subject='新的客户邮件', body='请在这里粘贴需要人工阅读的客户来信。')
        return email, _unknown(email)
    record = _CATALOG[index]
    email = EmailInput(email_id='p47-service-' + str(index), subject=record['subject'], body=record['body'])
    data = _unknown(email)
    common = dict(missing_evidence=record['customer_info'] + record['internal_verification'])
    if index == 0:
        issues = [_issue(email, object_name='DemoCam C200', category='Electronics', customer_requests=['核实有线视频会议功能及转接头需求'], **common)]
    elif index == 1:
        issues = [_issue(email, object_type='service', object_name='已送达包裹', category='Service/Other', issue_kind='complaint',
                         reason='other', sentiment='negative', resolution='unresolved', business_process='delivery/logistics issue',
                         routing_team='logistics', attribution_certainty='reported', customer_requests=['处理雨淋和破损包装，确认商品状态'], **common)]
    elif index == 2:
        issues = [_issue(email, object_name='台灯', category='Electronics', issue_kind='complaint', reason='product quality',
                         sentiment='negative', resolution='unresolved', business_process='product issue', attribution_certainty='reported',
                         customer_requests=['核实台灯故障及维修或换货选项'], **common)]
    elif index == 3:
        specs = [
            dict(quote='新柜子的抽屉晚上会自己滑出来，我已经磕到过腿，走道又比较窄。', issue_id='drawer', object_name='柜子抽屉',
                 category='Furniture', reason='health or safety issue', business_process='product issue', routing_team='product_support',
                 risk_level='minor', risk_rationale='普通磕碰风险；未描述承重结构失效或严重潜在伤害。', urgency_basis='safety',
                 customer_requests=['处理抽屉滑出及磕碰隐患'], missing_evidence=['柜子型号或已有照片']),
            dict(quote='约好周六来取旧床，结果我等了一上午也没人来。', issue_id='collection', object_type='service', object_name='旧床取件',
                 category='Service/Other', reason='after-sales service', business_process='store service issue', routing_team='store_operations',
                 customer_requests=['核对旧床取件爽约及后续安排'], missing_evidence=['取件预约编号']),
            dict(quote='还有订单 DEMO-24018 的发票少开了一张床头柜。', issue_id='invoice', object_type='service', object_name='发票漏项',
                 category='Service/Other', reason='billing/invoice issue', business_process='billing/invoice issue', routing_team='customer_support',
                 customer_requests=['核对发票床头柜漏项'], missing_evidence=['现有发票信息']),
        ]
        issues = [_issue(email, issue_kind='complaint', sentiment='negative', resolution='unresolved', attribution_certainty='reported',
                         handling_priority=n, priority_rationale='先避免磕碰，再协调取件与发票；业务顺序不代表客户主次。', **spec)
                  for n, spec in enumerate(specs, 1)]
    elif index == 4:
        issues = [_issue(email, object_name='折叠车车架锁扣', category='Sports/Outdoor', issue_kind='complaint', reason='health or safety issue',
                         sentiment='negative', urgency='high', resolution='unresolved', business_process='product issue', attribution_certainty='reported',
                         risk_level='severe', risk_rationale='骑行中车架连接失效可造成严重伤害，无人摔倒不能降级。', urgency_basis='safety',
                         customer_requests=['安全处理车架锁扣失效', '评估退货或换车'], **common)]
    elif index == 5:
        issues = [_issue(email, object_type='service', object_name='冰箱安装预约', category='Service/Other', issue_kind='complaint',
                         reason='after-sales service', sentiment='negative', resolution='unresolved', business_process='store service issue',
                         routing_team='store_operations', attribution_certainty='reported', urgency_basis='repeated_failure',
                         customer_requests=['人工解释重复取消并确认可行安装时间'], **common)]
    elif index == 6:
        issues = [_issue(email, object_name='耳机退换与运费', category='Electronics', issue_kind='complaint', reason='refund request',
                         sentiment='negative', resolution='unresolved', business_process='refund/exchange process issue',
                         routing_team='refunds', attribution_certainty='reported', customer_requests=['确认退货或换货及运费承担'], **common)]
    else:
        issues = [_issue(email, object_type='unknown', issue_kind='unknown', reason='unknown', sentiment='negative',
                         urgency='unknown', resolution='unknown', business_process='unknown', routing_team='unassigned',
                         attribution_certainty='unknown', risk_level='unknown', risk_rationale='资料不足，不能确认风险。', urgency_basis='unknown',
                         customer_requests=['请求人工客服并查阅先前沟通'] if index == 8 else ['澄清尚未解决的具体问题'], **common)]
    complaint = index in (1, 2, 3, 4, 5, 6)
    data.update(issues=issues, relations=[], summary=record['summary'], suggested_reply=record['reply'], reply_language='zh',
                sentiment='neutral' if index == 0 else 'negative', urgency='high' if index == 4 else 'unknown' if index in (7, 8) else 'medium',
                complaint_status='current_unresolved' if complaint else 'no_complaint' if index == 0 else 'unknown',
                request_types=['information'] if index == 0 else ['investigation', 'replacement'] if index == 4 else
                              ['refund', 'replacement', 'information'] if index == 6 else ['investigation'] if complaint else ['other'])
    data = AnalysisV31.model_validate(data).validate_input(email).model_dump()
    return email, data


def _strategy(name):
    if name == CUSTOM_SCENARIO:
        record = dict(tier='human_required', reason='任意新邮件只保存未知占位，需要人工阅读并判断风险。', customer_info=['具体诉求或业务编号'],
                      internal_verification=['原始来信及相关记录'], next_actions=['人工阅读', '不把占位结果当模型分析'], empathy='根据人工阅读补充合适的共情。')
    else:
        item = _CATALOG[SCENARIOS.index(name)]
        record = {k: copy.deepcopy(item[k]) for k in ('tier', 'reason', 'customer_info', 'internal_verification', 'next_actions')}
        record['empathy'] = '咨询直接回应；投诉先承认具体困扰，再解释下一步。'
    return dict(record, version=POLICY_VERSION, hash=POLICY_HASH, scenario=name, reply_outline=list(POLICY['reply_outline']))


def _identity(email, data, name):
    return digest(dict(version=VERSION, input_hash=email.input_hash, analysis=data, strategy=_strategy(name)))


class ServiceCopilotFake(ReplayV31):
    """Explicit whitelisted Runnable; custom mail becomes unknown, never guessed."""
    model_id = 'p47-authored-service-replay'
    def __init__(self, email, scenario):
        expected, data = example(scenario)
        if scenario == CUSTOM_SCENARIO:
            data = _unknown(email)
        elif email != expected:
            raise ValueError('新版合成案例正文已改变；请使用自定义邮件的离线待人工模式。')
        super().__init__({email.input_hash: data}, dataset_id=VERSION)
        self.config = self.config.model_copy(update=dict(
            model_id='p47-authored-service-replay', prompt_version=POLICY_VERSION, prompt_hash=POLICY_HASH,
            parameters=dict(self.config.parameters, product_scenario=scenario, service_scenario=scenario,
                            service_policy_version=POLICY_VERSION, service_policy_hash=POLICY_HASH,
                            scenario_version=VERSION, scenario_hash=_identity(email, data, scenario),
                            semantics='authored_synthetic_or_unknown_not_model_inference')))
        self.chain = RunnableLambda(lambda value: super(ServiceCopilotFake, self).analyze(value)).with_config(run_name='P47_authored_service_fixture')

    def analyze(self, email):
        return self.chain.invoke(email, config={'callbacks': []})


def strategy(case):
    """Return source-bound communication guidance, not permission to approve.

    Old cases and inconsistent identities receive no new policy by implication.
    The workflow layer must still inspect quality, actual analysis and raw mail.
    """
    run = case['run']
    params = run.config.parameters or {}
    name = params.get('service_scenario')
    if (run.config.backend != 'offline_fake' or name not in SCENARIOS
            or params.get('service_policy_version') != POLICY_VERSION or params.get('service_policy_hash') != POLICY_HASH):
        return None
    expected, data = example(name)
    if name == CUSTOM_SCENARIO:
        data = _unknown(run.email)
    elif run.email != expected:
        return None
    if (run.config.prompt_hash != POLICY_HASH or params.get('scenario_hash') != _identity(run.email, data, name)
            or params.get('fixture_hash') != digest({run.email.input_hash: data})
            or case.get('analysis') != data or not case.get('accepted')):
        return None
    return _strategy(name)
