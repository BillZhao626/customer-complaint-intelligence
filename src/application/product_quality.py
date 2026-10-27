"""P3.11 bounded diagnostics, separate from every frozen acceptance profile.

Never repairs a prediction. Findings are source-bound candidates; silence is
not semantic approval. All drafts still require explicit review.
"""
import re
from src.application.reply_review import inspect_reply, negated
from src.application.urgency_context_v1 import visible
from src.domain.contracts import digest

VERSION = 'product-quality-guard-v1'
POLICY = {
    'version': 'owner-adjudication-v1',
    'source': 'Researcher decisions approved 2026-10-18; attachment retained locally',
    'appointment': 'Natural repeated cancellation of confirmed bookings is one unresolved service complaint; denial of a different complaint does not cancel it. Original unnatural input retained separately.',
    'potential_injury': 'Load-bearing bicycle frame lock or cookware handle failure: severe/high despite no injury, cold or empty condition. Assess foreseeable normal use.',
    'delivery': 'Rain-damaged delivered packaging: other / delivery/logistics issue; no invented delay or manufacturing cause.',
    'importance': 'Customer primary/secondary and business order are distinct. Merchant provides warranty documentation; no invented execution capability.',
    'review': 'Five policies do not approve complete replies or provide independent Human Gold.',
}
POLICY_HASH = digest(POLICY)


def active_clauses(text):
    """Conservative factual anchors; uncertainty remains reviewable."""
    text = re.sub(r'\b(?:but|however|nevertheless|yet)\b|但是|不过|然而', '.', visible(text), flags=re.I)
    for m in re.finditer(r'[^.!?。！？;；\n]+', text):
        c = m.group().strip()
        if re.search(r'\b(?:if|manual|hypothetical|suppose|someone said|according to)\b|假设|如果|说明书写|别人说', c, re.I):
            continue
        yield c


def positive(text, pattern):
    for c in active_clauses(text):
        for m in re.finditer(pattern, c, re.I):
            prefix = c[:m.start()]
            coordinated_denial = re.search(r'\b(?:do not|never|must not)\b[^.!?]{0,100}\b(?:or|and)\s*$', prefix, re.I)
            if not coordinated_denial and not re.search(r"\b(?:no|not|never|hasn.t|didn.t|doesn.t|wasn.t|isn.t)\s+(?:\w+\s+){0,3}$|(?:没有|并未|尚未|不会|未曾|未)[^，,]{0,8}$", prefix, re.I):
                return c
    return None


def load_failure(text):
    for c in active_clauses(text):
        structure = re.search(r'(?:bicycle|bike|cycle).{0,45}(?:frame|latch|lock)|(?:pan|tray|pot|cookware).{0,45}(?:handle)|(?:load.bearing|weight.bearing).{0,30}(?:latch|handle|lock|leg)|(?:车架|承重).{0,20}(?:锁扣|把手|支腿)|(?:烤盘|锅).{0,25}(?:把手|柄)', c, re.I)
        failure = positive(c, r'opened|detached|came (?:off|away)|broke|failed|collapsed|脱开|脱落|断裂|失效|自行打开')
        decorative = re.search(r'decorative|ornamental|plastic cover|装饰|外壳', c, re.I)
        if structure and failure and not decorative:
            return c
    return None


def inspect(email, data, reply=None, accepted=True):
    findings = []

    def add(code, level, scope, quote, reason, issue_id=None):
        f = dict(code=code, severity=level, scope=scope, quote=quote, reason=reason, issue_id=issue_id)
        f['finding_id'] = digest(f)
        findings.append(f)

    if not accepted or not isinstance(data, dict):
        add('analysis_not_accepted', 'block', 'analysis', '', 'Failed or invalid raw is diagnostic only; no sendable draft.')
    data = data if isinstance(data, dict) else {}
    def items(value):
        return [i for i in value if isinstance(i, dict)] if isinstance(value, list) else []
    issues = items(data.get('issues'))
    for i in issues:
        for key in ('evidence', 'risk_evidence', 'urgency_evidence', 'importance_evidence'):
            if key in i and (not isinstance(i[key], list) or any(not isinstance(e, dict) for e in i[key])):
                add('invalid_diagnostic_shape', 'block', 'analysis', key, 'Invalid raw field shape; diagnostic only.')
    text = email.subject + '\n' + email.body
    hazard = load_failure(text)
    severe = [i for i in issues if i.get('risk_level') == 'severe']
    if hazard:
        # Require the severe assessment to cover this hazard, not an unrelated issue.
        covered = any(i.get('risk_level') == 'severe' and i.get('urgency') == 'high'
                      and load_failure(' '.join(str(e.get('quote', '')) for e in items(i.get('risk_evidence')))) for i in issues)
        if not covered:
            add('potential_injury_downgrade', 'block', 'analysis', hazard, 'Bounded load-bearing failure anchor needs severe/high with corresponding evidence; do not relabel the stored prediction.')
    for i in issues:
        iid = i.get('issue_id')
        if i.get('risk_level') == 'severe' and i.get('urgency') != 'high':
            add('risk_urgency_conflict', 'block', 'analysis', str(i.get('risk_rationale', '')), 'Severe potential injury requires high urgency.', iid)
        evs = items(i.get('evidence'))
        for key in ('importance_evidence', 'risk_evidence', 'urgency_evidence'):
            evs += items(i.get(key))
        for e in evs:
            source = getattr(email, e['field'], None) if e.get('field') in ('subject', 'body') else None
            start, end = e.get('start'), e.get('end')
            if not isinstance(source, str) or type(start) is not int or type(end) is not int or not (0 <= start < end <= len(source)) or source[start:end] != e.get('quote'):
                add('evidence_mismatch', 'block', 'analysis', str(e.get('quote', '')), 'Evidence span does not match original input.', iid)
        evidence = ' '.join(str(e.get('quote', '')) for e in items(i.get('evidence')))
        if i.get('reason') == 'delivery delay':
            time = positive(evidence, r'\blate\b|\bdelayed\b|\boverdue\b|past (?:the )?promised|missed.{0,15}deadline|延误|逾期|超时|超过约定')
            if not time:
                rain = positive(evidence, r'rain|soaked|wet.{0,20}(?:bag|pack|box)|雨淋|受潮|淋湿')
                add('unsupported_delivery_delay', 'block' if rain else 'review', 'analysis', evidence, 'Delivery timing requires evidence; wet packaging alone cannot establish delay.', iid)
        if i.get('reason') == 'product quality' and positive(evidence, r'left.{0,30}rain|雨淋|受潮'):
            add('unsupported_manufacturing_cause', 'review', 'analysis', evidence, 'Transport damage does not establish manufacturing cause.', iid)
        if i.get('customer_importance') == 'equal' and re.search(r'not.{0,15}(?:equal|same importance)|没有说.{0,15}同等重要|并非.{0,8}同等重要', text, re.I):
            add('denied_equal_importance', 'block', 'analysis', text, 'Explicit denial of equality conflicts with equal importance.', iid)
        if i.get('customer_importance') == 'equal':
            add('importance_scope_review', 'review', 'analysis', evidence, 'Verify that equality is a current customer comparison, separate from workflow order.', iid)
    repeated = positive(text, r'(?:appointment|booking).{0,55}cancelled.{0,15}twice|cancelled.{0,70}(?:and then|replacement).{0,65}cancelled|(?:两次|连续).{0,15}取消.{0,15}预约|预约.{0,20}(?:两次|连续).{0,15}取消')
    if repeated and not positive(repeated, r'cancelled|取消'):
        repeated = None
    resolved = positive(text, r'now resolved|already resolved|now fixed|已解决|已恢复')
    if repeated and not resolved and (data.get('complaint_status') == 'no_complaint' or not any(i.get('issue_kind') == 'complaint' and i.get('resolution') == 'unresolved' for i in issues)):
        add('booking_complaint_erasure', 'block', 'analysis', repeated, 'Repeated cancellation remains a service complaint; scope and unnatural source quality require separate review.')
    reply = data.get('suggested_reply', '') if reply is None else reply
    if not isinstance(reply, str):
        add('invalid_reply_shape', 'block', 'reply', '', 'Reply raw must be text; no inferred draft.')
        reply = ''
    for f in inspect_reply(reply)['findings']:
        add(f['kind'], f['severity'], 'reply', f['quote'], f['reason'])
    # Closed capability context: no SMTP, CRM, booking, refund or follow-up agent.
    for c in re.split(r'[.!?。！？;；\n，,]|\bbut\b|但是|不过', reply, flags=re.I):
        for m in re.finditer(r'\b(?:we|i|our team)\s+(?:will|shall|can)\s+(?:\w+\s+){0,3}(?:send|contact|call|email|arrange|check|investigate|follow up|provide|reply|respond)\b|(?:我们|我方|本店|客服)(?:将|会|可以|能)(?:为您|给您|同信|尽快|进一步){0,3}(?:发送|联系|提供|答复|回复|核查|安排|跟进)', c, re.I):
            if not negated(c[:m.start()]):
                add('unavailable_future_action', 'block', 'reply', m.group(), 'No verified system capability for this promised action.')
        for m in re.finditer(r'(?:将|会)(?:在同一封邮件中|在同一封信中|同信)(?:分别)?(?:答复|回复|发送)|\bwill be (?:contacted|sent|checked|investigated)\b', c, re.I):
            if not negated(c[:m.start()]):
                add('unavailable_future_action', 'block', 'reply', m.group(), 'Future reply/contact execution is unavailable in this application.')
    for m in re.finditer(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://\S+|\+?\d[\d -]{7,}\d', reply):
        add('unverified_contact_channel', 'block', 'reply', m.group(), 'Operational contact channels are not configured; remove or verify outside this candidate.')
    for m in re.finditer(r'(?:您|你).{0,18}(?:提供|发送|整理).{0,15}(?:保修说明|说明书)|(?:please|you).{0,25}(?:provide|send).{0,20}(?:warranty manual|warranty guide)', reply, re.I):
        denied = bool(re.search(r'无需|不必|不需要|不要|不应|不用|\b(?:not|never|don.t|cannot)\b', m.group(), re.I))
        denied |= bool(re.search(r'(?:无需|不必|不需要|不要|不应|不用)\s*$', reply[:m.start()]))
        if not denied:
            add('documentation_actor_reversal', 'block', 'reply', m.group(), 'Merchant documentation must not be requested from the customer as their duty.')
    safety = bool(hazard or severe)
    if safety:
        add('severe_safety_review', 'review', 'analysis', hazard or 'severe model assessment', 'Verify foreseeable injury and safe advice; explicit safety review required.')
        if not re.search(r'do not (?:use|ride)|stop (?:using|riding)|avoid (?:using|riding)|不要(?:继续)?使用|停止使用|勿骑|不要骑|勿用|暂停使用', reply, re.I):
            add('missing_stop_use_advice', 'block', 'reply', reply, 'Severe risk draft requires clear stop-use advice before review.')
        if positive(reply, r'(?:try|repeat|reproduce|test|record|film).{0,35}(?:failure|spark|riding|powered|video)|(?:重新|再次|通电).{0,15}(?:试|复现|拍摄)|拍.{0,6}(?:故障|视频)'):
            add('dangerous_reproduction', 'block', 'reply', reply, 'Do not reproduce dangerous failure for evidence; use existing safe material only.')
    return dict(version=VERSION, policy_version=POLICY['version'], policy_hash=POLICY_HASH,
                status='blocked' if any(f['severity'] == 'block' for f in findings) else 'review_required',
                findings=findings, safety_review_required=safety, human_approved=False,
                caveat='Bounded diagnostics only. Every draft requires a person; unknown semantics are not certified.')
