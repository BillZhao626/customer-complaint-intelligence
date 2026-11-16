"""Explicit offline examples and unknown placeholder via a LangChain Runnable.

The fixture outputs are authored engineering examples, never model predictions.
"""
import copy
import json
from langchain_core.runnables import RunnableLambda
from src.application.v31_demo import EMAIL, fixture, span, ReplayV31
from src.domain.contracts import EmailInput, digest

SCENARIOS = ('普通产品信息咨询', '多Issue与处理顺序', '严重潜在安全风险', '需要修改的回复', '结构化契约失败', '分析服务失败', '自定义邮件（unknown占位）')


def example(name):
    data = copy.deepcopy(fixture().model_dump())
    if name == SCENARIOS[1]:
        return EMAIL.model_copy(update={'email_id': 'p4-multi'}), data
    body = {
        SCENARIOS[0]: 'Does this camera support a wired connection? Nothing is broken.',
        SCENARIOS[2]: 'The load-bearing handle of my baking tray detached while I lifted it. It was cold and empty. Nobody was injured.',
        SCENARIOS[3]: 'My desk lamp stopped working. Could the product details be checked?',
        SCENARIOS[4]: 'Please explain the warranty terms for this desk lamp.',
        SCENARIOS[5]: 'Please explain the dimensions of this desk lamp.',
        SCENARIOS[6]: '在这里输入客户邮件。此模式保存 unknown 占位结果，不进行真实语义分析。',
    }[name]
    email = EmailInput(email_id='p4-' + str(SCENARIOS.index(name)), subject='Offline fake example', body=body)
    ev = span(email, body)
    issue = data['issues'][0]
    inquiry = name in (SCENARIOS[0], SCENARIOS[4], SCENARIOS[5], SCENARIOS[6])
    severe = name == SCENARIOS[2]
    issue.update(issue_id='item', object_name='baking tray' if severe else 'camera' if name == SCENARIOS[0] else 'desk lamp',
                 category='Electronics' if not severe else 'Home Appliances', reason='none' if inquiry else 'health or safety issue' if severe else 'product quality',
                 issue_kind='inquiry' if inquiry else 'complaint', resolution='not_applicable' if inquiry else 'unresolved',
                 evidence=[ev], business_process='none' if inquiry else 'product issue', routing_team='product_support',
                 attribution_certainty='not_applicable' if inquiry else 'reported',
                 missing_evidence=['Model, purchase details and cause verification'], customer_requests=['Information or safe assessment'],
                 customer_importance='unspecified', importance_evidence=[], handling_priority=1,
                 priority_rationale='Single active matter; no inferred customer comparison',
                 risk_level='severe' if severe else 'none', risk_evidence=[ev] if severe else [],
                 risk_rationale='Foreseeable failure under hot load' if severe else 'No specific safety incident in this explicit fixture',
                 urgency='high' if severe else 'low' if inquiry else 'medium', urgency_basis='safety' if severe else 'other', urgency_evidence=[ev],
                 sentiment='neutral' if inquiry else 'negative')
    reply = 'Thank you for your question. Please share the camera model so its connection specifications can be verified.'
    if severe:
        reply = 'Please do not use the tray or reproduce the failure. Keep it aside. Existing photos and the model information can help a qualified person assess the handle structure and available options.'
    if name == SCENARIOS[3]:
        reply = 'Thank you for explaining the lamp problem. We will contact you with an update.'
    data.update(issues=[issue], relations=[], sentiment=issue['sentiment'], urgency=issue['urgency'],
                complaint_status='no_complaint' if inquiry else 'current_unresolved', request_types=['information' if inquiry else 'investigation'],
                summary='Explicit offline engineering fixture: ' + body, suggested_reply=reply, reply_language='en')
    return email, data


class ProductFake(ReplayV31):
    def __init__(self, email, scenario):
        _, data = example(scenario)
        if scenario == SCENARIOS[6]:
            from src.application.v31_demo import pipeline_probe
            data = pipeline_probe(email).model_dump()
        if scenario == SCENARIOS[4]:
            data = '{"invalid":true}'
        super().__init__({email.input_hash: data}, dataset_id='p4-explicit-offline-examples-v1')
        self.config = self.config.model_copy(update={'prompt_version': 'p4-offline-runnable-v1',
            'parameters': dict(self.config.parameters, product_scenario=scenario, semantics='explicit_fixture_or_unknown_placeholder')})
        self.scenario = scenario
        self.chain = RunnableLambda(self._respond).with_config(run_name='P4_explicit_offline_fake')

    def _respond(self, email):
        if self.scenario == SCENARIOS[5]:
            raise RuntimeError('Explicit offline analyzer failure')
        return super().analyze(email)

    def analyze(self, email):
        return self.chain.invoke(email, config={'callbacks': []})
