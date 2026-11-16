"""Deterministic screens for explicit, bounded service reply defects."""
import re

from src.application.p5b8r4_evidence import action_goal
from src.application.reply_guidance import source_topics, verified_facts
from src.application.reply_risk_checks import sensitive_intake_findings, sync_findings, tariff_findings
from src.application.source_facts import nonasserted_spans, page_gap_findings

PRIVACY = re.compile(r'隐私|privacy|authorized (?:recipient |order )?contact|授权收件联系方式', re.I)
SHIPMENT = re.compile(r'物流|配送|包裹|parcel|shipment|logistics|delivery|tracking|carrier', re.I)
CREATED = re.compile(
    r'已(?:经)?(?:为您)?(?:登记|创建|提交)|(?:登记|创建|提交).{0,12}(?:待|处理)|'
    r'\b(?:created|logged|opened|registered)\b|(?:is|are) (?:also |both |currently )?pending|\bboth (?:currently )?pending', re.I
)
NOT_CREATED = re.compile(r'尚未|还没|没有|未能|无法确认|尚不能确认|若|如果|\b(?:not|never|if|could be|will be|can be|would be|cannot confirm|can.t confirm)\b', re.I)
LOCAL_CLOCK = re.compile(r'当地时间|本地时间|所在地(?:的)?时间|local time|your time zone|your timezone', re.I)
BUY = re.compile(r'下单|购买|付款|支付|\b(?:purchase|buy|pay|check\s*out)\b|\bcomplete\b.{0,25}\bpayment\b', re.I)
ENDORSE = re.compile(r'建议|请在|即可|就(?:安全|有效|能享)|稳妥|保险|safe|safeguard|recommend|please|should|make sure|go ahead', re.I)
DECLINE = re.compile(r'^\s*(?:(?:但|不过|and|but)\s*)?(?:please\s+)?(?:请勿|请不要|别|不要|不能|无法|不建议|不保证|避免|do not|don.t|cannot|can.t|avoid|never)', re.I)
VERIFICATION_CONDITION = re.compile(
    r'^(?:if|only if)\s+(?:the )?(?:merchant|promotion terms|offer terms|billing team)\b[^,，]{0,110}'
    r'(?:confirm|explicitly state|specify|verify)[^,，]{0,80}(?:cutoff|deadline|time zone|local time)[^,，]*[,，]|'
    r'^(?:仅在|只有|如果|若)(?:商家|活动条款|账务)[^，,]{0,20}(?:明确|确认|核实)[^，,]{0,30}(?:截止|时区|当地时间)[^，,]*[,，]',
    re.I,
)
PAYMENT_BASIS = re.compile(r'付款时间戳|支付时间戳|有效付款时间|payment timestamp|payment event|timestamp qualifies', re.I)
POWER_WORKAROUND = re.compile(
    r'\brunning\b[^.!?;]{0,125}\b(?:one at a time|on (?:separate|different) (?:sockets|circuits))\b'
    r'[^.!?;]{0,45}\b(?:avoids?|solves?|makes? (?:it )?safe)\b|'
    r'\b(?:please|you can|you should)\s+(?:plug|use|run|connect)\b[^.!?;]{0,95}'
    r'\b(?:one at a time|(?:separate|different) (?:sockets|circuits))\b|'
    r'(?:请|建议)(?:您)?(?:分别|改用|轮流)?(?:接入|插入|使用)[^。！？；，,]{0,28}(?:不同|独立|另一个)(?:回路|插座)', re.I,
)
VERIFIED_POWER_CONDITION = re.compile(
    r'\b(?:only after|only if)\b[^.!?;]{0,120}\b(?:qualified electrician|manufacturer)\b'
    r'[^.!?;]{0,85}\b(?:confirms?|verifies?|approves?)\b|'
    r'(?:只有在|仅在|须待)[^。！？；]{0,45}(?:电工|制造商)[^。！？；]{0,28}(?:确认|核实|批准)', re.I,
)
CALENDAR_FALLBACK = re.compile(
    r'(?:用量|用水量|累计升数)[^。！？；，,]{0,18}(?:未知|无法|不清楚|难以)[^。！？；]{0,42}'
    r'(?:则|就|可以)[^。！？；]{0,28}(?:等到|等满|作为兜底|作为备用|作为保底)|'
    r'\bif\b[^.!?;]{0,100}\b(?:can.t|cannot|unable to|do not know)\b[^.!?;]{0,35}\b(?:track|measure|usage|volume)\b'
    r'[^.!?;]{0,75}\b(?:wait until|fall back on|rely on)\b[^.!?;]{0,35}\b(?:months?|calendar|time limit)\b', re.I,
)
CURRENCY_ENDORSEMENT = re.compile(
    r'以(?:最终)?(?:结算页(?:面)?|购物车|商品页(?:面)?)(?:最终)?(?:上|所)?显示的(?:币种|金额)[^。！？；]{0,18}为准|'
    r'\b(?:use|trust|rely on|go by)\s+(?:the\s+)?(?:final\s+)?(?:checkout|cart|listing)\s+(?:page\s+)?'
    r'(?:currency|amount|price)\b[^.!?;]{0,25}(?:as (?:the )?(?:basis|authoritative)|for (?:the )?payment)', re.I,
)
PAYMENT_DIRECTION = re.compile(
    r"\b(?:do not|don't)\s+(?:pay\b|(?:make|send)\b[^.!?;]{0,35}\bpayment\b)|"
    r"\b(?:do not|don't)\b[^.!?;]{0,65}\bor\s+(?:make|send)\b[^.!?;]{0,35}\bpayment\b|"
    r'\b(?:stop|withhold|pause|suspend)\s+(?:all |any |further |the |your )*(?:payments?|paying|balance)\b|'
    r'\bwait\b[^.!?;]{0,95}\bbefore\b[^.!?;]{0,35}\bpaying\b|'
    r'\b(?:continue|keep)\s+paying\b|'
    r'\b(?:you must|you should|you need to|please)\s+(?:continue to |continue |keep )?pay\b|'
    r'(?:不要|不必|无需|暂停|停止|暂缓|先别)[^。！？；，,]{0,22}(?:付款|支付|交尾款)|'
    r'(?:必须|应当|务必|继续)[^。！？；，,]{0,15}(?:支付|付清|缴纳|付尾款)', re.I,
)


def payment_obligation_findings(email, reply, facts):
    if 'cancellation_payment_obligations' not in source_topics(email):
        return []
    authorized = {f['conclusion'].strip().rstrip('.。') for f in verified_facts(email, facts)
                  if f.get('topic') == 'cancellation_payment_obligations'}
    reports = [(a, b) for a, b, _ in nonasserted_spans(reply)]
    findings = []
    for sentence in re.finditer(r'[^.。!?！？;；\n]+', reply):
        quote = sentence.group().strip()
        if quote in authorized:
            continue
        for match in PAYMENT_DIRECTION.finditer(sentence.group()):
            start, end = sentence.start() + match.start(), sentence.start() + match.end()
            if any(a <= start and end <= b for a, b in reports):
                continue
            full_prefix = sentence.group()[:match.start()]
            prefix = re.split(r'[,，]|\bbut\b|\bhowever\b|但是|不过', full_prefix, flags=re.I)[-1]
            negative = r"\b(?:does|do|did|will|can|must|should)\s+not(?:\s+itself)?\s*$|\b(?:not|never|cannot|can't|won't|don't|doesn't)(?:\s+itself)?\s*$|(?:不(?:会|能|应|要|意味着|代表)(?:可以|应当)?|未|无需)\s*$"
            if re.search(negative, prefix, re.I):
                continue
            if re.search(r"(?:do not|don't|cannot|can't)\s+(?:assume|recommend|advise|say)\b[^,，]{0,45}$|不能(?:假定|建议)|不要假定|\bwhether\s*$|是否\s*$", prefix, re.I):
                continue
            if re.search(r'^(?:only if|only after)\b[^,，]{0,110}(?:confirms?|verifies?|approves?)[^,，]{0,75}(?:suspension|extension|payment obligation)|^(?:仅在|只有)[^，,]{0,50}(?:确认|批准)[^，,]{0,25}(?:暂停|延期|付款义务)', full_prefix.strip(), re.I):
                continue
            findings.append(dict(code='UNVERIFIED_CANCELLATION_PAYMENT_DIRECTION', severity='block', scope='reply',
                                 quote=quote, reason='Cancellation review does not establish the balance deadline or suspend or confirm an existing payment obligation.'))
            break
    return findings


def policy_findings(email, reply, facts):
    if 'promotion_deadline' not in source_topics(email):
        return []
    authorized = {
        f['conclusion'].strip().rstrip('.。') for f in verified_facts(email, facts)
        if f.get('topic') == 'promotion_deadline'
    }
    findings = []
    reported = [(start, end) for start, end, kind in nonasserted_spans(reply) if kind == 'REPORTED_QUOTATION']
    for match in re.finditer(r'[^.。!?！？;\n；]+', reply):
        # Split adversative clauses so an earlier disclaimer cannot protect an
        # independent recommendation. Keep exact customer-visible evidence.
        parts = re.split(r'[,，]\s*(?=但|不过|but\b|however\b|so\s+(?:I|we)\s+won.t\s+suggest\b)', match.group(), flags=re.I)
        offset = match.start()
        for part in parts:
            start = reply.find(part, offset, match.end())
            offset = start + len(part)
            if any(left <= start and offset <= right for left, right in reported):
                continue
            quote = part.strip()
            condition = VERIFICATION_CONDITION.search(quote)
            refuses_clock = re.match(r'^so\s+(?:I|we)\s+won.t\s+suggest\b[^,，]*$',quote,re.I)
            if quote in authorized or DECLINE.search(quote) or refuses_clock or (condition and PAYMENT_BASIS.search(condition.group())):
                continue
            if LOCAL_CLOCK.search(quote) and BUY.search(quote) and ENDORSE.search(quote):
                findings.append(dict(
                    code='UNVERIFIED_PROMOTION_PURCHASE_TIMING', severity='block', scope='reply', quote=quote,
                    reason='A recommendation to purchase by the customer’s local clock requires applicable merchant cutoff and payment evidence.',
                ))
    return findings


def unresolved_risk_findings(email, reply, facts):
    """Block explicit advice that substitutes an unverified safety or payment basis."""
    source = email.subject + '\n' + email.body
    topics = source_topics(email)
    currency_conflict = (
        re.search(r'港币|港元|\bHKD\b|HK\$', source, re.I)
        and re.search(r'人民币|\bCNY\b|\bRMB\b|[¥￥]', source, re.I)
        and re.search(r'不一致|变成|冲突|不同|以哪个|different|conflict|switch|changed', source, re.I)
    )
    if not ({'electrical_load_boundary', 'earliest_consumable_limit'} & topics.keys() or currency_conflict):
        return []
    authorized = {f['conclusion'].strip().rstrip('.。') for f in verified_facts(email, facts)}
    reports = [(a, b) for a, b, kind in nonasserted_spans(reply) if kind == 'REPORTED_QUOTATION']
    findings = []
    for sentence in re.finditer(r'[^.。!?！？;；\n]+', reply):
        quote = sentence.group().strip()
        if not quote or quote in authorized:
            continue
        for applicable, pattern, code, reason in (
            ('electrical_load_boundary' in topics, POWER_WORKAROUND, 'UNVERIFIED_ELECTRIC_WORKAROUND',
             'The recommendation assumes an alternative electrical arrangement is suitable without equipment and circuit verification.'),
            ('earliest_consumable_limit' in topics, CALENDAR_FALLBACK, 'UNVERIFIED_USAGE_FALLBACK',
             'Unknown usage does not establish that the usage limit remains below the replacement threshold.'),
            (currency_conflict, CURRENCY_ENDORSEMENT, 'UNVERIFIED_CURRENCY_BASIS',
             'A disputed display cannot establish the actual payment currency or amount.'),
        ):
            match = pattern.search(sentence.group()) if applicable else None
            if not match:
                continue
            start, end = sentence.start() + match.start(), sentence.start() + match.end()
            if any(a <= start and end <= b for a, b in reports):
                continue
            before = re.split(r'但(?:是)?|不过|\bbut\b|\bhowever\b', sentence.group()[:match.start()], flags=re.I)[-1]
            if code == 'UNVERIFIED_ELECTRIC_WORKAROUND':
                if VERIFIED_POWER_CONDITION.search(before):
                    continue
                # A positive directive after a comma is independent of an earlier refusal.
                if (re.match(r'please\b|you (?:can|should)\b|请|建议', match.group(), re.I)
                        and re.search(r'[,，]\s*(?:(?:and|so)\s+)?$', before, re.I)):
                    before = ''
            if DECLINE.search((before + match.group()).strip()):
                continue
            findings.append(dict(code=code, severity='block', scope='reply', quote=quote, reason=reason))
    return findings


def communicated_checks(email, reply, receipts):
    """Audit named pending updates for independently applicable privacy/shipment checks."""
    topics = source_topics(email)
    if not {'contact_privacy', 'missing_shipment'} <= topics.keys():
        return []
    result = []
    clauses = []
    shared=[]
    for part in re.split(r'[.。!?！？;\n；]+',reply):
        if ((len(re.findall(r'\b(?:requests?|tasks?|tickets?)\b|请求|任务|工单',part,re.I))>=2
             or re.search(r'\btwo (?:separate |distinct )?(?:internal (?:verification )?)?(?:requests|tasks|checks)\b|两(?:项|个)(?:独立|单独)?(?:内部)?(?:核实)?(?:请求|任务)',part,re.I))
            and re.search(r'have both been|are both|were both|both (?:currently )?pending|均已|都已|均待处理|都待处理',part,re.I)
            and CREATED.search(part) and not NOT_CREATED.search(part[:CREATED.search(part).start()])):
            shared.append(part.strip())
    independent_request = r',?\s+and\s+(?=(?:an?|the)\s+[^.]{0,55}\b(?:request|task|ticket)\b)'
    for part in re.split(r'[.。!?！？;\n；]+|'+independent_request, reply, flags=re.I):
        marker = CREATED.search(part)
        if marker and not NOT_CREATED.search(part[:marker.start()]):
            clauses.append(part.strip())
    for name, pattern, other, kinds in (
        ('contact_privacy', PRIVACY, SHIPMENT, {'support_followup', 'handoff_request'}),
        ('missing_shipment', SHIPMENT, PRIVACY, {'logistics_followup'}),
    ):
        events = [event['event_id'] for event in receipts
                  if event['kind'] in kinds and pattern.search(action_goal(event))]
        # A mention in an apology or evidence request is not an update. Keep
        # merged updates distinct from omitted checks and missing execution.
        distinct = next((part for part in clauses if pattern.search(part) and not other.search(part)), None)
        merged = next((part for part in clauses if pattern.search(part) and other.search(part)), None)
        if not distinct:
            distinct=next((part for part in re.split(r'[.。!?！？;\n；]+',reply)
                if pattern.search(part) and other.search(part) and CREATED.search(part)
                and re.search(r'\band a separate (?:logistics|privacy) check\b',part,re.I)
                and re.search(r'have both been (?:created|logged)',part,re.I)),None)
        if not distinct:
            distinct=next((part for part in shared if pattern.search(part) and other.search(part)),None)
        if not distinct:
            pair=next((part for part in clauses if pattern.search(part) and other.search(part)
                       and (len(re.findall(r'\bone\s+for\b',part,re.I))>=2
                            or re.search(r'分别.{0,20}(?:隐私|物流)|(?:隐私|物流).{0,25}各(?:一|1)(?:项|个)',part))),None)
            if pair:distinct=pair
        status = 'NO_PENDING_RECEIPT' if not events else 'DISCLOSED' if distinct else 'MERGED' if merged else 'NOT_EXPLICITLY_DISCLOSED'
        result.append(dict(goal=name, status=status, event_ids=events, reply_quote=distinct or merged))
    return result


def review(email, reply, runtime, receipts, *, relay_requested):
    facts = runtime.get('facts', {})
    findings = policy_findings(email, reply, facts)
    findings.extend(payment_obligation_findings(email, reply, facts))
    findings.extend(unresolved_risk_findings(email, reply, facts))
    findings.extend(sync_findings(email, reply, facts))
    findings.extend(sensitive_intake_findings(email, reply))
    findings.extend(page_gap_findings(email, reply))
    findings.extend(tariff_findings(email, reply, facts))
    communication = communicated_checks(email, reply, receipts)
    for check in communication:
        if check['status'] in ('MERGED', 'NOT_EXPLICITLY_DISCLOSED'):
            findings.append(dict(
                code='PENDING_CHECK_NOT_DISTINCT', severity='review', scope='reply',
                quote=check['reply_quote'] or '', goal=check['goal'],
                reason='A matching pending receipt exists but the reply does not identify that check separately.',
            ))
    relay = re.search(
        r'我(?:们)?(?:会|将).{0,12}(?:转达|转告)|\b(?:we|I)(?: will|[’\x27]ll).{0,24}(?:relay|pass on|forward).{0,25}(?:praise|thanks|compliment|kind words)',
        reply, re.I,
    )
    relay_grounded = None
    if relay:
        relay_grounded = relay_requested and any(
            event['kind'] == 'store_service_request'
            and re.search(r'转达|转告|relay|pass.{0,20}thanks|gratitude', action_goal(event), re.I)
            for event in receipts
        )
        if not relay_grounded:
            findings.append(dict(
                code='UNGROUNDED_RELAY_INTENT', severity='review', scope='reply', quote=relay.group(),
                reason='A future praise relay needs customer intent and its own matching pending task. This is not a completion claim.',
            ))
    return dict(findings=findings, customer_informed_of_actions=communication,
                intended_action_grounded=relay_grounded)
