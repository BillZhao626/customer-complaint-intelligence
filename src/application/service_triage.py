"""P4.7 local service routing and explicit confirmation, without model inference.

Routing is a product aid, never a replacement for analysis/reply quality gates.
Ownership is derived from immutable P4 events; no research snapshot is edited.
"""
import re

from src.domain.contracts import digest


VERSION = 'p47-service-triage-v1'
SERVICE_POLICY_VERSION = 'p47-service-reply-policy-v1'
SERVICE_POLICY_VERSIONS = (SERVICE_POLICY_VERSION, 'p47-service-reply-policy-v2')
LABELS = dict(ai_assist='AI 建议处理', human_confirm='需人工确认', human_required='需人工接管')


def explicit_human_request(text):
    """Recognize a bounded affirmative request, rather than a free-form intent."""
    for clause in re.split(r'[。！？!?；;\n，,]|\bbut\b|但是|不过', text, flags=re.I):
        if re.search(r'不用|无需|不需要|不要|不想|不必|不转|别转|\b(?:no need|do not|don.t|without)\b', clause, re.I):
            continue
        if re.search(r'人工客服|转人工|人工坐席|真人客服|(?:找|要|请|接通|联系).{0,8}人工|\b(?:human|live)\s+(?:agent|support|representative)\b|\bspeak (?:to|with) (?:a |an )?(?:person|agent)\b', clause, re.I):
            return True
    return False


def current_customer_text(case):
    """Do not treat a simulated outgoing reply as the latest customer request."""
    body = case['run'].email.body
    marker = '[customer · current message]\n'
    if marker in body and (case['run'].config.parameters or {}).get('context_hash'):
        return body.rsplit(marker, 1)[1]
    return case['run'].email.subject + '\n' + body


def is_p47_case(case):
    return (case['run'].config.parameters or {}).get('service_policy_version') in SERVICE_POLICY_VERSIONS


def service_strategy(case):
    """Dispatch exact source versions; never rebind a v1 snapshot to v2 rules."""
    version = (case['run'].config.parameters or {}).get('service_policy_version')
    if version == 'p47-service-reply-policy-v2':
        from src.application.service_scenarios_v2 import strategy
        return strategy(case)
    if version == SERVICE_POLICY_VERSION:
        from src.application.service_scenarios import strategy
        return strategy(case)
    return None


def ownership(case):
    event = next((e for e in reversed(case.get('events', [])) if e['action'] in ('request_handoff', 'take_over')), None)
    return dict(handoff='none' if event is None else 'taken_over' if event['action'] == 'take_over' else 'requested',
                owner=event['actor'] if event and event['action'] == 'take_over' else None,
                handoff_event=event)


def triage(case):
    """Conservative actual-data checks take precedence over authored strategy."""
    quality = case['quality']
    data = case.get('analysis') or {}
    issues = data.get('issues') or []
    text = current_customer_text(case)
    owned = ownership(case)
    reasons, codes = [], []
    level = 'ai_assist'

    def add(code, reason, target):
        nonlocal level
        if code not in codes:
            codes.append(code); reasons.append(reason)
        if ('ai_assist', 'human_confirm', 'human_required').index(target) > ('ai_assist', 'human_confirm', 'human_required').index(level):
            level = target

    if not case['accepted']:
        add('analysis_failed', '分析未通过校验，需要人工阅读客户原文。', 'human_required')
    if quality['status'] == 'blocked':
        add('quality_blocked', '当前质量门禁阻断；接管或改写回复不能解除分析错误。', 'human_required')
    if quality.get('safety_review_required') or any(i.get('risk_level') == 'severe' for i in issues):
        add('safety', '涉及人身安全，须先接管并核对停止使用与后续处理路径。', 'human_required')
    if explicit_human_request(text):
        add('customer_requested', '客户明确要求人工客服。仅在本地演示转交，不连接真实坐席。', 'human_required')
    if not issues or data.get('sentiment') == 'unknown' or data.get('complaint_status') == 'unknown' or any(i.get('issue_kind') == 'unknown' for i in issues):
        add('unknown_intent', '尚不能可靠识别诉求；离线占位不能作为 AI 理解结果。', 'human_required')
    if re.search(r'赔偿|补偿|退款|退钱|退货|换货|换新|\brefund|\bcompensation|\breplacement\b', text, re.I):
        add('authority', '退款、补偿或换货需要有权限的人工核实订单与适用政策。', 'human_required')
    if re.search(r'太失望|无法接受|不能接受|气死|愤怒|离谱|再也不|一直推诿|踢皮球|气坏|\bfurious\b|\bunacceptable\b|\bdisgusted\b', text, re.I):
        add('strong_emotion', '客户强烈不满，需要人工接住情绪并确认处理路径。', 'human_required')
    if any(f['severity'] == 'review' for f in quality.get('findings', [])):
        add('quality_review', '现有质量诊断需要人工确认原文与建议。', 'human_confirm')
    if len(issues) > 1:
        add('multiple_issues', '有多个诉求，需要核对覆盖情况及处理顺序。', 'human_confirm')

    policy = None
    if is_p47_case(case):
        policy = service_strategy(case)
        if policy:
            add('scenario_strategy', policy['reason'], policy['tier'])
        else:
            add('unbound_strategy', '场景与版本化策略身份未匹配，需要人工确认。', 'human_required')
    else:
        add('legacy_source', '历史来源保留原审核流程；没有继承 P4.7 轻确认授权。', 'human_confirm')

    if owned['handoff'] == 'requested':
        add('handoff_requested', '已记录本地转人工请求，等待操作者接管。', 'human_required')
    elif owned['handoff'] == 'taken_over':
        # A deliberate takeover keeps the conversation human-owned, even when
        # the reply defect that originally triggered it has been edited away.
        add('human_owned', '当前会话已由本地操作者接管。', 'human_confirm')
    if not reasons:
        reasons = ['明确的常见咨询，可参考建议后进行轻确认。']
    quick = (is_p47_case(case) and policy is not None and level == 'ai_assist'
             and not quality.get('findings') and bool(case.get('draft'))
             and case['state'] == 'pending_review'
             and owned['handoff'] == 'none')
    result = dict(version=VERSION, level=level, label=LABELS[level], reasons=reasons,
                  reason_codes=codes, requires_takeover=level == 'human_required',
                  takeover_complete=owned['handoff'] == 'taken_over', can_quick_confirm=quick,
                  **owned, simulation_only=True,
                  next_step=('先接管并核实阻断；不能批准或模拟发送。' if quality['status'] == 'blocked' or not case['accepted'] else
                             '先接管，再核对回复和必要信息。' if level == 'human_required' and owned['handoff'] != 'taken_over' else
                             '核对当前回复后确认并模拟发送。' if quick else '核对回复并完成必要审核后模拟发送。'))
    result['routing_hash'] = digest({k: v for k, v in result.items() if k != 'handoff_event'})
    return result


def request_handoff(store, case_id, *, expected_revision, actor='demo_operator', actor_type='demo_test',
                    reason, operation_id=None):
    return store.act(case_id, 'request_handoff', expected_revision=expected_revision, actor=actor,
                     actor_type=actor_type, reason=reason, operation_id=operation_id)


def take_over(store, case_id, *, expected_revision, actor='demo_operator', actor_type='demo_test',
              reason, operation_id=None):
    return store.act(case_id, 'take_over', expected_revision=expected_revision, actor=actor,
                     actor_type=actor_type, reason=reason, operation_id=operation_id)


def quick_confirm_and_simulate(store, case_id, *, expected_revision, actor, actor_type, confirmed, operation_id):
    """One explicit confirmation, two original transactions, resumable by ID.

    A failed step is surfaced immediately. An explicit repeat using the same
    operation ID recovers committed steps; a new draft or intervening event is
    rejected. No provider, real send, automatic retry or invented human score.
    """
    from src.application.product_workflow import Conflict
    if confirmed is not True or not isinstance(operation_id, str) or not operation_id.strip():
        raise Conflict('请明确确认当前回复，并保留本次操作标识；不会自动批准或发送。')
    case = store.get(case_id)
    if case is None:
        raise Conflict('Case not found')
    approval_id = operation_id + ':approve'
    send_id = operation_id + ':send'
    approval = next((e for e in case['events'] if e['operation_id'] == approval_id), None)
    reason = '操作者明确确认当前回复的事实、权限与诉求覆盖；仅本地模拟发送，不计独立人工评价。'
    if approval:
        anchor = approval['details'].get('checks', {}).get('quick_confirmation', {})
        if (approval['action'] != 'approve' or anchor.get('expected_revision') != expected_revision
                or approval['actor'] != actor or approval['actor_type'] != actor_type
                or approval['version'] != case['current_version']
                or approval['details'].get('body_hash') != case['draft']['body_hash']):
            raise Conflict('轻确认操作与原版本不一致，请重读当前会话。')
        checks = approval['details']['checks']
    else:
        route = triage(case)
        if case['revision'] != expected_revision:
            raise Conflict('Stale page: reload current case before changing it')
        if not route['can_quick_confirm'] or case['state'] != 'pending_review':
            raise Conflict('当前会话需要人工确认或接管，不能使用轻确认路径。')
        checks = dict(facts_evidence=True, authority_privacy=True, all_issues=True,
                      quick_confirmation=dict(confirmed=True, expected_revision=expected_revision,
                                              routing_version=VERSION, routing_hash=route['routing_hash'],
                                              run_id=case['run'].run_id, input_hash=case['run'].input_hash,
                                              body_hash=case['draft']['body_hash'], simulation_only=True))
    approved = store.act(case_id, 'approve', expected_revision=expected_revision, actor=actor,
                         actor_type=actor_type, reason=reason, checks=checks, operation_id=approval_id)
    approval = next(e for e in approved['events'] if e['operation_id'] == approval_id)
    return store.act(case_id, 'simulate_send', expected_revision=approval['revision'], actor=actor,
                     actor_type=actor_type, reason='', checks={}, operation_id=send_id)


confirm_and_simulate = quick_confirm_and_simulate
