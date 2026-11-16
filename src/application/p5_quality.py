"""P5-A developer-authored candidates, never live inference or Human Gold.

Exact source identities are required for replay. Merchant drafts remain unusable
by the model; approval is an external research decision, not a flag this module
can change. The generic workflow still owns review, takeover and simulation.
"""
import copy
import csv
import json
from datetime import date
from pathlib import Path

from langchain_core.runnables import RunnableLambda
from src.application.v31_demo import ReplayV31, fixture, span
from src.application.research_policy_v2 import assess
from src.domain.analysis_v31 import AnalysisV31
from src.domain.contracts import EmailInput, digest

ROOT = Path(__file__).resolve().parents[2] / 'resources' / 'p5a'
VERSION = 'p5a-authored-quality-dev-v1'
POLICY_VERSION = 'p5a-task-tone-policy-v1'
POLICY = dict(version=POLICY_VERSION, status='DEV_CANDIDATE',
    identity='developer_authored_synthetic_not_model_inference_not_human_gold',
    principles=['Facts, intent, merchant knowledge, permissions and tone are separate.',
                'Emotion changes phrasing, never safety severity or business authority.',
                'Missing merchant facts go to internal verification, not repeated customer questions.',
                'Pending merchant drafts are review-only and never live model knowledge.',
                'All outgoing replies require the original review state machine.'],
    allowed_actions=['draft', 'request_local_handoff', 'request_local_knowledge_verification', 'simulate_after_review'],
    forbidden_actions=['real_send', 'refund', 'ship', 'approve_merchant_policy', 'certify_human_gold'])
POLICY_HASH = digest(POLICY)


def _json(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def list_cases():
    """Fresh independent copies; no mutable process-global dataset."""
    return _json('cases_dev.json')


load_cases = list_cases


def candidate(case_id):
    for item in list_cases():
        if item['case_id'] == case_id:
            return item
    raise ValueError('Unknown P5 developer candidate')


get_case = candidate


def families():
    with (ROOT / 'scenario_family_matrix.csv').open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def knowledge_drafts():
    return _json('knowledge_drafts.json')


def approved_knowledge(*, records=None, retrieval_key, as_of, case_scope=None):
    """Exact, time- and case-scoped lookup. No fuzzy match or pending bypass.

    ``records`` allows explicit isolated test fixtures. It is not exposed as an
    approval API. Production defaults contain only OWNER_PENDING drafts.
    """
    today = date.fromisoformat(as_of)
    matches = []
    for record in knowledge_drafts() if records is None else copy.deepcopy(records):
        if (record.get('owner_approval') != 'APPROVED' or record.get('use_in_model') != 'YES'
                or record.get('retrieval_key') != retrieval_key or not record.get('source_ref')
                or not record.get('effective_from') or record.get('conflict', False)):
            continue
        if date.fromisoformat(record['effective_from']) > today:
            continue
        if record.get('effective_to') and today > date.fromisoformat(record['effective_to']):
            continue
        if record.get('kind') == 'ORDER_FIXTURE' and (not case_scope or record.get('case_scope') != case_scope):
            continue
        matches.append(record)
    if len(matches) != 1:
        return None
    return matches[0]


def knowledge_answer(*, records=None, retrieval_key='DemoCam C200:wired_meeting', as_of='2026-10-28', case_scope=None):
    """Small contract demonstration, not an approval or generative answer path."""
    record = approved_knowledge(records=records, retrieval_key=retrieval_key, as_of=as_of, case_scope=case_scope)
    if record is None:
        return dict(action='ASK_HUMAN_INPUT', answer=None, knowledge_refs=[],
                    internal_question='核实该型号有线视频会议的接口、协议、系统支持及必要配件；提供可追溯规格版本。')
    answer = record.get('claims', {}).get('customer_answer')
    if not isinstance(answer, str) or not answer.strip():
        return dict(action='ASK_HUMAN_INPUT', answer=None, knowledge_refs=[], internal_question='已定位资料缺少该问题的明确答案。')
    return dict(action='ANSWER', answer=answer,
                knowledge_refs=[dict(knowledge_id=record['knowledge_id'], version=record['version'], hash=digest(record),
                                     source_ref=record['source_ref'])], internal_question=None)


def _issue(email, spec, n, urgency):
    quote = spec.get('quote') or email.body
    ev = span(email, quote)
    risk = spec.get('risk_level', 'none')
    complaint = spec.get('complaint', True)
    finding = assess(email.body)
    return dict(issue_id='issue-' + str(n), object_type=spec.get('object_type', 'product'),
                object_name=spec['object_name'], category=spec.get('category', 'Electronics'),
                issue_kind='complaint' if complaint else 'inquiry', reason=spec.get('reason', 'product quality') if complaint else 'none',
                sentiment='negative' if complaint else 'neutral', urgency=urgency,
                resolution='unresolved' if complaint else 'not_applicable', evidence=[ev],
                business_process=spec.get('business_process', 'product issue') if complaint else 'none',
                routing_team=spec.get('routing_team', 'product_support'),
                attribution_certainty='reported' if complaint else 'not_applicable',
                missing_evidence=spec.get('missing_evidence', ['商家内部记录与适用规则待核实']),
                responsibility='unverified', customer_requests=spec['customer_requests'], customer_importance='unspecified',
                importance_evidence=[], handling_priority=n,
                priority_rationale='开发候选的处理顺序；不推断客户主次或法律责任。', extraction_basis='native',
                risk_level=risk, risk_evidence=[ev] if risk in ('minor', 'severe') else [],
                risk_rationale=spec.get('risk_rationale', '本例未陈述严重安全事件；不认证商品安全。'),
                urgency_basis='safety' if risk == 'severe' else finding['basis'] if finding['urgency'] else 'other',
                urgency_evidence=[ev])


def example(case_id):
    item = candidate(case_id)
    email = EmailInput(email_id=item['case_id'], subject=item['subject'], body=item['body'])
    data = fixture().model_dump()
    severe = any(i.get('risk_level') == 'severe' for i in item['issue_specs'])
    urgency = 'high' if severe else assess(email.body)['urgency'] or 'medium'
    issues = [_issue(email, spec, n, urgency) for n, spec in enumerate(item['issue_specs'], 1)]
    complaint = any(i['issue_kind'] == 'complaint' for i in issues)
    data.update(issues=issues, relations=[], summary=item['understanding']['summary'],
                suggested_reply=item['customer_reply'], reply_language=item['language'],
                sentiment='negative' if complaint else 'neutral', urgency=urgency,
                complaint_status='current_unresolved' if complaint else 'no_complaint',
                request_types=['investigation'] if complaint else ['information'])
    return email, AnalysisV31.model_validate(data).validate_input(email).model_dump()


def _identity(item, email, data):
    return digest(dict(version=VERSION, candidate=item, input_hash=email.input_hash, analysis=data, policy_hash=POLICY_HASH))


class P5CandidateAnalyzer(ReplayV31):
    model_id = 'p5a-authored-candidate-replay'

    def __init__(self, email, case_id):
        if isinstance(case_id, dict):
            case_id = case_id['case_id']
        expected, data = example(case_id)
        if email != expected:
            raise ValueError('P5候选正文已改变；不能继承预写分析，请使用离线人工阅读入口。')
        item = candidate(case_id)
        super().__init__({email.input_hash: data}, dataset_id=VERSION)
        self.config = self.config.model_copy(update=dict(model_id=self.model_id,
            prompt_version=POLICY_VERSION, prompt_hash=POLICY_HASH,
            parameters=dict(self.config.parameters, p5_candidate_id=case_id, p5_case_id=case_id, p5_policy_version=POLICY_VERSION,
                            p5_policy_hash=POLICY_HASH, p5_candidate_hash=_identity(item, email, data),
                            knowledge_snapshot_id=item['knowledge_snapshot_id'],
                            semantics='developer_authored_synthetic_not_model_inference_not_human_gold')))
        self.chain = RunnableLambda(lambda value: super(P5CandidateAnalyzer, self).analyze(value)).with_config(run_name='P5A_authored_candidate')

    def analyze(self, email):
        return self.chain.invoke(email, config={'callbacks': []})


def is_p5_case(case):
    return (case['run'].config.parameters or {}).get('p5_policy_version') == POLICY_VERSION


def p5_strategy(case):
    """Bound developer guidance, no P4.7 quick-confirm or approval authority."""
    run = case['run']; params = run.config.parameters or {}
    if (not is_p5_case(case) or run.config.backend != 'offline_fake' or not case.get('accepted')
            or run.config.model_id != P5CandidateAnalyzer.model_id or run.config.prompt_version != POLICY_VERSION
            or params.get('p5_policy_hash') != POLICY_HASH or run.config.prompt_hash != POLICY_HASH):
        return None
    try:
        item = candidate(params.get('p5_candidate_id')); expected, data = example(item['case_id'])
    except ValueError:
        return None
    if (run.email != expected or case.get('analysis') != data or params.get('p5_case_id') != item['case_id']
            or params.get('p5_candidate_hash') != _identity(item, expected, data)
            or params.get('fixture_hash') != digest({expected.input_hash: data})
            or params.get('knowledge_snapshot_id') != item['knowledge_snapshot_id']):
        return None
    action = item['policy_decision']['action']
    tier = 'human_required' if action in ('HARD_BLOCK', 'HANDOFF') else 'human_confirm'
    return dict(version=POLICY_VERSION, hash=POLICY_HASH, scenario=item['case_id'], tier=tier,
                reason=item['policy_decision']['reason'], action=action,
                customer_info=item['policy_decision']['customer_questions'],
                internal_verification=item['policy_decision']['internal_questions'],
                next_actions=item['reply_plan']['next_actions'], tone_plan=item['reply_plan']['tone_plan'],
                customer_emotion=item['understanding']['emotion'], knowledge_refs=item['knowledge_refs'],
                knowledge_snapshot_id=item['knowledge_snapshot_id'], owner_approval='OWNER_PENDING',
                reply_outline=[], semantics='DEV_CANDIDATE_NOT_HUMAN_GOLD')


strategy = p5_strategy
bound_strategy = p5_strategy
