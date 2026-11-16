"""Versioned, authored P4.5 scenarios. No model or retrieval is performed."""
import copy
from langchain_core.runnables import RunnableLambda
from src.application.product_demo import SCENARIOS as OLD_SCENARIOS, example as old_example
from src.application.v31_demo import ReplayV31, pipeline_probe, span
from src.domain.contracts import EmailInput, digest

SCENARIOS = OLD_SCENARIOS + ('配送已送达但包装受损', '安全风险低估（阻断演示）')
TITLES = ('相机是否支持有线连接？', '抽屉、门店取件与发票的三个问题', '烤盘承重把手脱落',
          '台灯故障，需要核对支持选项', '保修咨询 · 输出无效演示', '尺寸咨询 · 分析失败演示',
          '新客户邮件', '包裹已送达，但被雨淋湿', '折叠车锁扣脱开 · 错误分析样例')
FOLLOWUP = 'The model printed on my camera is DemoCam C200. Does that mean it supports a wired connection?'
FOLLOWUP_SUBJECT = 'Re: ' + TITLES[0]


def example(name):
    index = SCENARIOS.index(name)
    base = OLD_SCENARIOS[0] if index == 7 else OLD_SCENARIOS[2] if index == 8 else name
    email, data = old_example(base)
    email = EmailInput(email_id='p45-' + str(index), subject=TITLES[index], body=email.body)
    data = copy.deepcopy(data)
    if index == 0:
        i = data['issues'][0]
        i.update(customer_requests=['核实相机是否支持有线连接'], missing_evidence=['具体型号', '商家提供的官方连接规格'])
        data.update(summary='客户询问相机连接功能，明确表示没有故障；不是投诉。',
                    suggested_reply='Thank you for your question. Which camera model do you have? Wired connection support needs to be verified against the official specifications for that model; it cannot be confirmed from the information available here.')
    elif index == 1:
        data['summary'] = '三个待处理问题：抽屉碰撞隐患、门店未上门取旧床、发票漏项。'
        data['suggested_reply'] = ('I am sorry you have had to deal with these three problems. '
            'For the drawer that stays open, please keep the walkway clear to avoid a collision; the product model would help identify the appropriate support. '
            'For the missed old-bed collection, please share the booking reference so the booking record can be verified. '
            'For the missing invoice item, the invoice reference and missing item are needed to review the discrepancy. '
            'The available resolution and any new collection date still require confirmation; none has been arranged here.')
        for i, request, missing in zip(data['issues'], ['抽屉故障及碰撞隐患', '门店取旧床爽约', '发票漏项'],
                                        [['商品型号'], ['取件预约编号'], ['发票编号与漏记商品']]):
            i.update(customer_requests=[request], missing_evidence=missing)
    elif index == 2:
        data['summary'] = '承重把手脱落，即使冷盘、空盘且无人受伤，仍按严重潜在伤害处理。'
        data['issues'][0].update(customer_requests=['安全处理承重把手故障'], missing_evidence=['商品型号', '已有安全照片；不得复现故障'])
        data['suggested_reply'] = ('I am sorry the load-bearing handle detached. Please do not use the tray or reproduce the failure. '
            'Even with a cold, empty tray and no injury, a handle failure could cause serious harm during normal use. '
            'Keep it aside and seek a qualified manual safety assessment. Please share the model and any existing photos taken safely; '
            'the available after-sales options still need verification.')
    elif index == 7:
        email = email.model_copy(update={'body': 'My order arrived today, but the courier left the box in the rain. The packaging is soaked and damaged. What should I do about the damage?'})
        i = data['issues'][0]
        ev = span(email, email.body)
        i.update(object_name='delivered package', object_type='service', category='Service/Other', issue_kind='complaint',
                 reason='other', sentiment='negative', urgency='medium', resolution='unresolved', evidence=[ev],
                 business_process='delivery/logistics issue', routing_team='logistics', attribution_certainty='reported',
                 customer_requests=['处理已送达包裹的雨淋损坏'], missing_evidence=['订单编号', '已有包装照片', '商品本体是否受损'],
                 urgency_evidence=[ev], risk_evidence=[], risk_level='none')
        data.update(summary='包裹已送达；客户报告雨淋造成包装受损，未声称配送延误。', sentiment='negative', urgency='medium',
                    complaint_status='current_unresolved', request_types=['investigation'],
                    suggested_reply='I am sorry the delivered packaging was left wet and damaged. Please keep the packaging and any existing photos. Could you share the order reference and whether the item itself is also damaged? This information is needed to assess the damage and applicable after-sales options. No refund or replacement has been approved here.')
    elif index == 8:
        email = email.model_copy(update={'body': 'The folding bicycle frame lock opened while I was riding. I stopped safely and nobody was injured.'})
        i = data['issues'][0]
        ev = span(email, email.body)
        i.update(object_name='folding bicycle', category='Sports/Outdoor', evidence=[ev], risk_evidence=[ev], urgency_evidence=[ev],
                 risk_level='minor', urgency='medium', risk_rationale='Intentionally incorrect offline fixture: no injury was used to downplay risk')
        data.update(summary='错误样例：原分析把骑行中的锁扣脱开低估为轻微风险，必须人工介入。', urgency='medium',
                    suggested_reply='Please do not ride the bicycle or reproduce the failure. Keep it aside for a qualified safety assessment.')
    return email, data


class CopilotFake(ReplayV31):
    def __init__(self, email, scenario, *, context_hash=None, data=None):
        expected, authored = example(scenario)
        if data is None:
            if scenario != SCENARIOS[6] and email != expected:
                raise ValueError('预设案例内容已改变；请使用新邮件 unknown 模式。')
            data = pipeline_probe(email).model_dump() if scenario == SCENARIOS[6] else authored
        if scenario == SCENARIOS[4]:
            data = '{"invalid":true}'
        super().__init__({email.input_hash: data}, dataset_id='p45-authored-service-scenarios-v1')
        self.config = self.config.model_copy(update={'prompt_version': 'p45-authored-context-v1',
            'parameters': dict(self.config.parameters, product_scenario=scenario, context_hash=context_hash,
                               semantics='authored_fixture_or_unknown_not_model_inference')})
        self.scenario = scenario
        self.chain = RunnableLambda(self._respond).with_config(run_name='P45_authored_fixture')

    def _respond(self, email):
        if self.scenario == SCENARIOS[5]:
            raise RuntimeError('Explicit offline analyzer failure')
        return super().analyze(email)

    def analyze(self, email):
        return self.chain.invoke(email, config={'callbacks': []})
