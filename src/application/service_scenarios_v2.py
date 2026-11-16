"""Additive safety/delivery variants and a source-bound demonstration policy.

P4.7 v1 inputs, authored replies and policy identities remain unchanged. These
examples are not merchant terms, independent labels or new model predictions.
"""
import copy
from langchain_core.runnables import RunnableLambda

from src.application.service_scenarios import SCENARIOS as V1_SCENARIOS, example as v1_example
from src.application.v31_demo import ReplayV31, span
from src.domain.analysis_v31 import AnalysisV31
from src.domain.contracts import EmailInput, digest


VERSION = 'p47-authored-aftersales-scenarios-v2'
DEMO_AFTERSALES_POLICY_VERSION = 'p47-demo-aftersales-application-v1'
DEMO_AFTERSALES_POLICY = dict(
    version=DEMO_AFTERSALES_POLICY_VERSION,
    title='演示售后申请规则 v1',
    source='项目编写的本地演示规则；未接入任何商家的实际售后条款',
    scope='仅本模块安全故障及配送受损合成场景；用于说明申请路径，不确定真实资格或批准结果',
    options=['维修申请', '更换申请', '退货申请'],
    application_steps=[
        '涉及安全或受潮电器时停止使用，保留商品及已有资料，不要求复现故障。',
        '在当前会话说明申请偏好，只补充尚未提供的订单、型号和商品状态；已有照片可附上，不冒险补拍。',
        '由人工核对订单记录、商品情况和必要检查结果，再确认适用的维修、更换或退货方案。',
        '在有权限人员确认方案前，不自行寄回或拆修；寄回方式等操作指引也需要人工确认。',
    ],
    approval_boundary='提出申请不等于符合条件或已获批准；本系统未实际提交申请、预约检查、转接坐席或执行退换。',
    unknown_terms=['实际商家适用条款', '退货或维修期限', '运费承担', '检查与处理时间', '补偿标准'],
    simulation_only=True,
)
DEMO_AFTERSALES_POLICY_HASH = digest(DEMO_AFTERSALES_POLICY)
POLICY_VERSION = 'p47-service-reply-policy-v2'
POLICY = dict(
    version=POLICY_VERSION,
    source='开发者编写的安全沟通演示策略；不是研究者新增政策裁决或Human Gold',
    principles=[
        '同一骑行中承重连接失效事实，在担忧、平静或生气表达下均为严重风险与高紧急度。',
        '配送包装受损与商品本体损坏分开，不能凭包装雨淋认定制造缺陷、延误或售后资格。',
        '先回应客户实际情绪；平静陈述不虚构恐惧，生气表达不降格为态度问题。',
        '停止使用和骑行，不为照片、视频或故障确认而复现。',
        '给出维修、更换、退货的申请路径，资格和方案仍须人工核订单与检查结果。',
        '只询问尚未提供的最少资料，不声称已经受理、联系、批准或完成处理。',
    ],
    demo_aftersales_policy_version=DEMO_AFTERSALES_POLICY_VERSION,
    demo_aftersales_policy_hash=DEMO_AFTERSALES_POLICY_HASH,
    reply_outline=['贴合情绪的回应', '停止使用与不复现', '申请选项与资料', '人工确认及下一步'],
)
POLICY_HASH = digest(POLICY)
SCENARIOS = ('骑行安全风险 · 担忧（v2）', '骑行安全风险 · 平静（v2）', '骑行安全风险 · 生气（v2）',
             '配送包装受损 · 售后申请（v2）')


_FACT = '昨天下班骑折叠车时，车架锁扣突然自行打开，车身明显晃了一下。'
_CATALOG = (
    dict(kind='safety', emotion='担忧', subject='骑车时车架锁扣突然开了，现在有点不敢碰这辆车',
         body=_FACT + '我赶紧停在路边，把车推回了家。这车才用了两次，现在想到那一下还是很后怕。我不敢再骑了，应该怎么处理？能申请换车或者退货吗？',
         empathy='很抱歉让您遇到这种情况，骑行时车架突然晃动，您现在担心再骑是可以理解的。',
         summary='客户报告骑行中车架锁扣自行打开，担忧后续安全，询问换车或退货申请。',
         requests=['安全处理车架锁扣失效', '了解换车或退货申请路径']),
    dict(kind='safety', emotion='平静', subject='折叠车车架锁扣骑行中打开，请说明售后处理流程',
         body=_FACT + '我停车后把车推回家，目前没有再使用。请说明这个故障需要准备哪些资料、怎样申请检查，以及检查后是维修、更换还是退货。',
         empathy='您好，您已把车推回家并暂停使用，谢谢您把经过说明清楚。骑行中车架锁扣自行打开，需要按安全问题认真处理。',
         summary='客户平静报告骑行中车架锁扣自行打开，已暂停使用，询问检查及维修、更换、退货流程。',
         requests=['确认安全检查所需资料', '了解维修、更换或退货申请路径']),
    dict(kind='safety', emotion='生气', subject='才骑两次车架锁扣就自己打开，这样的车怎么让人放心？',
         body=_FACT + '才骑两次就出这种问题，真的太让人生气了。我已经把车推回家，不会再骑。请别只让我自己检查锁扣，我要一个明确的售后处理办法，退货还是换车该怎么申请？',
         empathy='抱歉新车才骑两次就出现这样的故障，您的生气和对安全的质疑有充分理由。处理重点应当是车辆安全和明确的售后路径，不应把判断故障的负担推给您。',
         summary='客户因新车骑行中车架锁扣自行打开而生气，拒绝自行检查，要求明确退货或换车申请路径。',
         requests=['由人工处理安全故障而非要求自行检查', '明确退货或换车申请路径']),
    dict(kind='delivery', emotion='担忧', subject='包裹送到了，但纸箱被雨淋透了',
         body=v1_example(V1_SCENARIOS[1])[0].body,
         empathy='很抱歉包裹送到时被雨淋湿、外箱也破了，您担心里面的台灯受损是可以理解的。',
         summary='订单 DEMO-24031 已送达，包装雨淋破损且已有照片；商品本体状态未知，可提出售后申请，方案待人工确认。',
         requests=['确认台灯是否受潮或损坏', '了解维修、更换或退货申请路径']),
)


def _reply(record):
    if record['kind'] == 'delivery':
        return (record['empathy'] + '\n\n'
                '您已提供订单号 DEMO-24031，也拍了外包装照片，不用再重复填写或重新拍摄。'
                '请保留包装和已有照片；若商品或插头有受潮迹象，请不要通电，也不用为取证试用。\n\n'
                '您可以在这次会话中提出更换、退货或维修申请，并说明更倾向哪种处理方式。'
                '方便的话，请补充里面的台灯是否也有受潮或破损；人工售后需要结合商品状态、订单记录和必要检查确认适用方案。'
                '提出申请不代表已经获批，先不要自行寄回或拆修，寄回方式等操作指引也需要人工确认。')
    safety = ('请继续停止使用这辆车，不要骑行，也不要为拍照、录像或确认故障而试骑、测试锁扣。'
              '现有照片可以保留；没有照片也不用冒险补拍。')
    application = ('您可以提出维修、更换或退货申请，并说明更倾向哪种处理方式。'
                   '请提供订单编号和车型，人工售后需要结合订单与安全检查结果确认适用方案。'
                   '在人工确认处理方式前，请先不要自行寄回或拆修，寄回方式等具体步骤也需一并确认。')
    return record['empathy'] + '\n\n' + safety + '\n\n' + application


def example(name):
    """New inputs bind identical severe/high facts to three communication tones."""
    index = SCENARIOS.index(name)
    record = _CATALOG[index]
    email = EmailInput(email_id=f'p47-aftersales-v2-{index}', subject=record['subject'], body=record['body'])
    safety = record['kind'] == 'safety'
    _, data = v1_example(V1_SCENARIOS[4] if safety else V1_SCENARIOS[1])
    data = copy.deepcopy(data)
    ev = span(email, _FACT if safety else email.body)
    issue = data['issues'][0]
    issue.update(evidence=[ev], risk_evidence=[ev] if safety else [], urgency_evidence=[ev],
                 risk_level='severe' if safety else 'none', urgency='high' if safety else 'medium', urgency_basis='safety' if safety else 'other',
                 risk_rationale='骑行中承重车架连接失效存在严重潜在伤害，情绪表达不影响风险等级。' if safety else '目前只报告包装受损；商品安全状态需人工核对，不据此确认电器安全。',
                 missing_evidence=['订单编号', '车型', '已有安全照片（如有）', '订单记录与人工安全检查结果'] if safety else
                                  ['台灯本体是否有受潮或破损', '已有包装照片（可直接附上）', '订单记录与必要检查结果'],
                 customer_requests=list(record['requests']))
    data.update(summary=record['summary'], suggested_reply=_reply(record), reply_language='zh',
                sentiment='negative', urgency='high' if safety else 'medium', request_types=['investigation', 'repair', 'replacement', 'refund'])
    return email, AnalysisV31.model_validate(data).validate_input(email).model_dump()


def _strategy(name):
    record = _CATALOG[SCENARIOS.index(name)]
    safety = record['kind'] == 'safety'
    return dict(version=POLICY_VERSION, hash=POLICY_HASH, scenario=name, tier='human_required' if safety else 'human_confirm',
                reason='骑行中车架承重连接失效，须人工接管并按安全问题核实；情绪不改变严重风险。' if safety else
                       '商品本体受损状态尚不清楚，需人工核对售后申请选项及适用方案。',
                customer_emotion=record['emotion'], empathy=record['empathy'],
                customer_info=['订单编号', '车型', '已有安全照片（如有；不要求为取证重新操作车辆）', '倾向维修、更换还是退货'] if safety else
                              ['台灯本体是否有受潮或破损', '已有包装照片（可直接附上）', '倾向更换、退货还是维修'],
                internal_verification=['订单与型号记录', '人工安全检查结果', '实际商家适用的售后条款与处理权限'] if safety else
                                      ['已知订单 DEMO-24031 的记录', '商品状态与必要检查结果', '实际商家适用的售后条款与处理权限'],
                next_actions=['停止使用和骑行，不试骑或测试取证', '说明申请偏好并补充订单、车型及现有资料',
                              '人工核订单及安全检查结果后确认方案，寄回或拆修步骤也须确认'] if safety else
                             ['保留包装和现有照片，受潮商品不通电', '只补商品本体状态和申请偏好，不重复索要已知订单或重新拍照',
                              '人工核商品状态、订单及必要检查后确认方案，寄回方式须确认'],
                reply_outline=list(POLICY['reply_outline']),
                demo_aftersales_policy=copy.deepcopy(DEMO_AFTERSALES_POLICY),
                demo_aftersales_policy_version=DEMO_AFTERSALES_POLICY_VERSION,
                demo_aftersales_policy_hash=DEMO_AFTERSALES_POLICY_HASH)


def _identity(email, data, name):
    return digest(dict(version=VERSION, input_hash=email.input_hash, analysis=data, strategy=_strategy(name)))


class ServiceCopilotFake(ReplayV31):
    """Versioned authored outputs via RunnableLambda, without a model request."""
    model_id = 'p47-authored-aftersales-replay-v2'

    def __init__(self, email, scenario):
        expected, data = example(scenario)
        if email != expected:
            raise ValueError('安全情绪变体仅支持原文绑定的合成案例；新来信请使用离线待人工模式。')
        super().__init__({email.input_hash: data}, dataset_id=VERSION)
        self.config = self.config.model_copy(update=dict(
            model_id=self.model_id, prompt_version=POLICY_VERSION, prompt_hash=POLICY_HASH,
            parameters=dict(self.config.parameters, product_scenario=scenario, service_scenario=scenario,
                            scenario_version=VERSION, scenario_hash=_identity(email, data, scenario),
                            service_policy_version=POLICY_VERSION, service_policy_hash=POLICY_HASH,
                            demo_aftersales_policy_version=DEMO_AFTERSALES_POLICY_VERSION,
                            demo_aftersales_policy_hash=DEMO_AFTERSALES_POLICY_HASH,
                            semantics='authored_synthetic_safety_variant_not_model_inference')))
        self.chain = RunnableLambda(lambda value: super(ServiceCopilotFake, self).analyze(value)).with_config(run_name='P47_safety_emotions_v2')

    def analyze(self, email):
        return self.chain.invoke(email, config={'callbacks': []})


def strategy(case):
    """Only matching immutable v2 source snapshots can inherit demo guidance."""
    run = case['run']
    params = run.config.parameters or {}
    name = params.get('service_scenario')
    if (run.config.backend != 'offline_fake' or name not in SCENARIOS or not case.get('accepted')
            or params.get('service_policy_version') != POLICY_VERSION or params.get('service_policy_hash') != POLICY_HASH
            or params.get('demo_aftersales_policy_version') != DEMO_AFTERSALES_POLICY_VERSION
            or params.get('demo_aftersales_policy_hash') != DEMO_AFTERSALES_POLICY_HASH):
        return None
    expected, data = example(name)
    if (run.email != expected or run.config.model_id != ServiceCopilotFake.model_id
            or run.config.prompt_version != POLICY_VERSION or run.config.prompt_hash != POLICY_HASH
            or params.get('scenario_version') != VERSION or params.get('scenario_hash') != _identity(run.email, data, name)
            or params.get('fixture_hash') != digest({run.email.input_hash: data}) or case.get('analysis') != data):
        return None
    return _strategy(name)
