"""Scoped action evidence, shared by the adjacent Guard and R4 Judge.

This is a bounded bilingual claim recognizer, not a semantic truth oracle.
Unknown goals/objects stay unknown; absent receipts never prove execution.
"""
import re
from src.domain.contracts import digest

VERSION = 'r11-scoped-evidence-v27-pending-task-scope'
IDENTITY = ('case_id', 'conversation_id', 'run_id', 'arm', 'input_hash')
DOMAINS = {
    'privacy': (r'隐私|privacy|authorized recipient contact|授权收件联系方式', {'support_followup', 'handoff_request'}),
    'feedback': (r'转达|转交|表扬|谢意|感谢|relay|praise|thanks|feedback|kind words|门店服务|store service', {'store_service_request', 'feedback_request', 'feedback_relay'}),
    'refund': (r'退款|退费|refund', {'refund_request', 'refund', 'refund_completed', 'aftersales_request'}),
    'delivery': (r'物流|配送|交付|到货|送达|发货|承运商|快递公司|delivery|logistics|shipment|arriv|dispatch|carrier|pickup|collection|missing[- ]parcel (?:check|verification)|parcel (?:tracking|delivery|status)', {'logistics_followup', 'logistics_request', 'delivery', 'shipment'}),
    'product': (r'咨询|产品|商品|水箱|检修|送检|故障|规格|接口|售后|维修|核实|尺码|试穿|楦型|尺寸|设备.{0,8}(?:占用|授权)|consult|product|repair|specification|verification|\b(?:size|width|depth|fit|licen[cs]e|activation slot)\b', {'human_input_request', 'product_knowledge_request', 'aftersales_request', 'support_followup','clarification_request'}),
    'billing': (r'收费|账单|票据|费用|扣款|余额|激活|billing|charge|invoice|balance|transaction|activation', {'billing_request', 'human_input_request', 'store_service_request'}),
    'store': (r'门店服务|store service|代取|代领|自提|取货授权|\breservation\b|delegate collection|collection authorization|collect on .{0,15}behalf|collect.*instead|proof.*collection', {'store_service_request'}),
    'followup': (r'回复|回访|跟进|答复|follow.?up|reply|respond|callback', {'support_followup','logistics_followup'}),
}

def domains(text):
    return {name for name, (pattern, _) in DOMAINS.items() if re.search(pattern, text, re.I)}

def action_goal(event):
    return event.get('business_goal') or event.get('payload', {}).get('action', {}).get('goal', '')

def task_kinds(domain,state):
    kinds=DOMAINS[domain][1]
    # Aftersales can create an internal fee-verification task. This never
    # establishes an actual charge, refund or completed payment operation.
    return kinds|{'aftersales_request'} if domain=='billing' and state=='INTERNAL_CREATED' else kinds


TASK_COUNT = r'two|three|four|five|six|两|二|三|四|五|六|[2-6]'
TASK_COUNTS = dict(zip(('two','three','four','five','six','两','二','三','四','五','六'), (2,3,4,5,6,2,2,3,4,5,6)))
SEPARATE_TASK_HEADER = re.compile(
    rf'(?:(?P<zh_before>{TASK_COUNT})(?:项|个)(?:独立|单独)?(?:需求|事项|核查|请求|任务)已(?:经)?(?:分别|各自)(?:创建|登记|提交)内部(?:请求|任务|工单)|'
    rf'已(?:经)?(?:创建|登记|提交)(?P<zh_after>{TASK_COUNT})(?:项|个)(?:独立|单独|分别)(?:的)?内部(?:请求|任务|工单|核查))'
    r'(?:[，,]\s*(?:均|都)(?:尚|仍)?待处理)?\s*[：:]|'
    rf'\b(?:(?:we|I)(?: have|[’\x27]ve)? (?:created|opened|logged) (?P<en_after>{TASK_COUNT}) separate internal (?:requests|tasks|checks)|'
    rf'(?P<en_before>{TASK_COUNT}) separate internal (?:requests|tasks|checks) (?:have been|were) (?:created|opened|logged))'
    r'(?: and (?:are|remain) pending)?\s*:', re.I,
)
TASK_COMPONENT = re.compile(
    r'(?:^|[，,]\s*(?:and\s+)?|\s+and\s+)\s*'
    r'(?:(?:另)?一项(?:是|为|用于)|(?:one|another|the (?:second|third|fourth|fifth|sixth))\s+(?:for|to)\b)\s*', re.I,
)
PENDING_STATUS = re.compile(r'(?:尚|仍|均|都)?待处理|\b(?:is|are|remains?|still|currently)\s+(?:(?:still|currently|also)\s+)?pending\b', re.I)
DELEGATION = re.compile(
    r'代取|代领|取货授权|delegate collection|collection authorization|'
    r'\b(?:sister|brother|friend|partner|proxy|nominee|someone else)\b.{0,24}\b(?:collect|pick up)\b|'
    r'\b(?:collect|pick up)\b.{0,55}\b(?:instead|on (?:my|your|their) behalf)\b', re.I,
)
GENERIC_CREATED = re.compile(
    r'(?:目前|当前)?(?:已(?:经)?(?:为您)?创建(?:一项|一个)?内部(?:核查|核实|验证)请求|'
    r'(?:这|该|本)?(?:项)?(?:内部)?(?:核查|核实|验证)?(?:任务|请求|工单)已(?:经)?(?:创建|登记|提交))'
    r'(?:[，,]\s*(?:尚|仍)?待处理(?:[，,]\s*(?:核查|核实|处理)结果和完成时间(?:尚未|仍未)确定)?)?|'
    r'(?:an? |the )?internal (?:verification|check) (?:request|task) (?:has been|was) (?:created|logged|registered)'
    r'(?: and (?:is|remains) pending)?', re.I,
)


def separate_tasks(text):
    header = SEPARATE_TASK_HEADER.search(text)
    if not header:
        return None
    count = next(value.lower() for value in header.groups() if value)
    expected = int(count) if count.isdecimal() else TASK_COUNTS[count]
    tail = text[header.end():].strip()
    parts = list(TASK_COMPONENT.finditer(tail))
    if len(parts) != expected or parts[0].start() != 0:
        return []
    return [tail[part.end():parts[index+1].start() if index+1 < len(parts) else len(tail)].strip()
            for index, part in enumerate(parts)]


def claim(quote, state, start=None):
    from src.application.source_facts import mask_nonasserted
    asserted=mask_nonasserted(quote)
    if state=='INTERNAL_CREATED':
        # A preservation condition is not an additional asserted operation.
        # Actual delivery/refund task predicates elsewhere remain in scope.
        asserted=re.sub(r'\bwhile keeping\b[^,;.!?\n]{0,110}\b(?:unchanged|as they are)\b','',asserted,flags=re.I)
    target = re.search(r'(?:向|给)([^，。；\s]{2,16}店)|\bstore\s+(?!(?:team|staff|colleague|manager|service)\b)([A-Za-z0-9_-]+)', quote, re.I)
    objects = re.findall(r'水箱|耳机|礼盒|面霜|办公椅|咖啡机|\b[A-Z][A-Z0-9]*-?\d+\b', quote)
    return dict(claim_type=state, business_object=sorted(domains(asserted)), object_mentions=objects,
                target=next((x for x in target.groups() if x), None) if target else None,
                asserted_status={'INTERNAL_CREATED':'created','EXTERNAL_COMPLETED':'completed','PENDING_EXECUTION':'scheduled'}.get(state,'requested'),
                span=dict(start=start, end=start+len(quote) if start is not None else None, text=quote), quote=quote, state=state,asserted_scope=asserted,
                task_components=separate_tasks(asserted) if state == 'INTERNAL_CREATED' else None,
                states_pending=bool(state == 'INTERNAL_CREATED' and PENDING_STATUS.search(asserted)))


LOCKER_PENDING = re.compile(
    r'(?:an?|the) (?:internal )?logistics verification request (?:covering|to (?:check|verify)) '
    r'(?P<goal>[^.!?;\n]{1,150}?) (?:is (?:currently )?pending|has been created)'
    r'(?P<other>[^.!?;\n]*)\.?', re.I,
)
LOCKER_NO_COLLECTION = re.compile(
    r'\b(?:do not mark (?:it|the parcel) (?:as )?collected|'
    r'(?:parcel|package) (?:must|should) not be marked (?:as )?collected)\b|不得标记(?:为)?取走', re.I,
)
LOCKER_SECOND_CHECK = re.compile(
    r',?\s+and (?:a separate|another) (?:internal )?pending (?:check|request) '
    r'(?:records|covers) (?:that )?(?:the )?(?:parcel|package) (?:must|should) not be marked (?:as )?collected', re.I,
)
LOCKER_GOALS = {
    'reissue': re.compile(r'code reissue|reissu(?:e|ing).{0,15}(?:pickup |collection )?code|取件码.{0,8}重发|重发.{0,8}取件码', re.I),
    'extension': re.compile(r'\bexten(?:sion|d)\b|延期|延长', re.I),
    'fee': re.compile(r'\b(?:fees?|charges?)\b|费用|收费', re.I),
    'alternative': re.compile(r'\balternative(?:s| arrangements?)?\b|替代方式|替代取件', re.I),
}
EXPEDITED_DELIVERY = re.compile(r'加急(?:配送|发货|交付)|\bexpedited (?:shipping|delivery)\b', re.I)


def expedited_aftersales_scope(text):
    """An expedited option within one check is distinct from a shipment task."""
    if not re.search(r'售后核实请求|aftersales verification request', text, re.I):
        return False
    if not re.search(r'核查|核对|核实|\b(?:check|verify)\b', text, re.I):
        return False
    remaining, occurrences = EXPEDITED_DELIVERY.subn('', text)
    return occurrences == 1 and 'delivery' not in domains(remaining)


def locker_pending_scope(assertion):
    """A fee question belongs to an identified pending locker check.

    Match the complete assertion. An additional independent payment or outside
    action cannot borrow this scope, and a separate check needs a second receipt.
    """
    if assertion['state'] != 'INTERNAL_CREATED':
        return None
    matched = LOCKER_PENDING.fullmatch(assertion.get('asserted_scope', assertion['quote']).strip())
    if not matched:
        return None
    goal, other = matched.group('goal', 'other')
    if other and not LOCKER_SECOND_CHECK.fullmatch(other):
        return None
    requirements = {name for name, pattern in LOCKER_GOALS.items() if pattern.search(goal)}
    if not {'reissue', 'fee'} <= requirements:
        return None
    payment_status = bool(re.search(r'\b(?:paid|completed|waived|deducted|credited|refund)\b|已扣|已退|减免成功', goal, re.I))
    return requirements, bool(other), payment_status


def distinct_receipts(choices, used=()):
    if not choices:
        return used
    for event_id in choices[0]:
        if event_id not in used:
            assigned = distinct_receipts(choices[1:], (*used, event_id))
            if assigned:
                return assigned
    return ()


def compound_support(assertion, runtime, h, *, strict):
    components = assertion['task_components']
    checks = []
    for text in components:
        part = claim(text, 'INTERNAL_CREATED')
        part['task_components'] = None
        part['states_pending'] = assertion['states_pending']
        checks.append(support(part, runtime, h, strict=strict))
    ids = distinct_receipts([check['event_ids'] for check in checks])
    reasons = {reason for check in checks if not check['supported'] for reason in check['reasons']}
    if not ids:
        reasons.add('missing_distinct_pending_receipts' if components else 'unresolved_pending_task_scope')
    return dict(supported=bool(ids), support_status='supported' if ids else 'evidence_mismatch',
                event_ids=list(ids), negative_event_ids=sorted({i for check in checks for i in check['negative_event_ids']}),
                reasons=sorted(reasons), unavailable_identity_fields=sorted({k for check in checks for k in check['unavailable_identity_fields']}),
                evidence_identity='STRICT_BOUND' if strict else 'AVAILABLE_FIELDS_ONLY_NOT_CERTIFIED')


def support(c, runtime, h, *, strict=False):
    """Return matching IDs only. Never pass a context/query ID as support."""
    if c.get('task_components') is not None:
        return compound_support(c, runtime, h, strict=strict)
    expected = dict(runtime.get('identity', {}), input_hash=h)
    events = runtime.get('events', [])
    reasons = []; matched = []; negative = []; unavailable = set(); covered=set()
    wanted=set(c['business_object'])
    delegate = 'store' in wanted and bool(DELEGATION.search(c['asserted_scope']))
    if delegate:
        # Collection authorization is store work. An independently asserted
        # shipment check in the same clause still needs its own logistics event.
        if not re.search(r'物流|配送|包裹|shipping|shipment|carrier|delivery|tracking|logistics',c['quote'],re.I):
            wanted.discard('delivery')
        if not re.search(r'表扬|感谢|谢意|转达|转交|praise|thanks|feedback|relay', c['asserted_scope'], re.I):
            wanted.discard('feedback')
    # Generic "product verification" words do not cancel a specific relay,
    # refund, billing or delivery goal in the same asserted task.
    specific=wanted-{'product','followup'}
    explicit_product=bool(re.search(r'售后|产品咨询|aftersales|product (?:inquiry|consultation)',c['quote'],re.I))
    required=(specific | ({'product'} if explicit_product else set())) or wanted
    allowed = {'INTERNAL_CREATED':{'created','assigned','handoff_pending','scheduled','executed','completed'},
               'PENDING_EXECUTION':{'scheduled'}, 'EXTERNAL_COMPLETED':{'completed','executed'}}.get(c['state'], set())
    if c.get('states_pending'):
        allowed = {'created','handoff_pending'}
    locker_scope = locker_pending_scope(c)
    expedite_scope = c['state'] == 'INTERNAL_CREATED' and expedited_aftersales_scope(c['asserted_scope'])
    locker_main_ids, locker_constraint_ids = set(), set()
    if locker_scope and locker_scope[2]:
        return dict(supported=False, support_status='evidence_mismatch', event_ids=[], negative_event_ids=[],
                    reasons=['payment_status_requires_separate_evidence'], unavailable_identity_fields=[],
                    evidence_identity='STRICT_BOUND' if strict else 'AVAILABLE_FIELDS_ONLY_NOT_CERTIFIED')
    generic_request = c['state'] == 'INTERNAL_CREATED' and GENERIC_CREATED.fullmatch(c['asserted_scope'].strip())
    if generic_request:
        inventory = runtime.get('receipt_inventory', events)
        eligible = [e for e in inventory if e.get('status') in allowed and e.get('input_hash') == h
                    and not e.get('kind','').endswith('_lookup') and action_goal(e)]
        # Only a unique current task can identify an otherwise generic creation.
        # The normal loop below still validates input, binding and intrinsic IDs.
        if len(eligible)==1:
            kind=eligible[0]['kind']
            domain=next((d for d,(_,kinds) in DOMAINS.items() if kind in kinds and d in domains(action_goal(eligible[0]))),None)
            if domain:required={domain};wanted={domain}
    for e in events:
        b = e.get('_binding', {}); conflicts = []
        for k in IDENTITY:
            actual = e.get(k, e.get('conversation_id') if k=='case_id' else b.get(k))
            if k in expected and actual is not None and actual != expected[k]: conflicts.append(k)
            if actual is None: unavailable.add(k)
        if b:
            if b.get('event_hash') != digest({k:v for k,v in e.items() if k!='_binding'}): conflicts.append('payload_hash')
        if conflicts:
            reasons.append('identity:'+','.join(conflicts)); continue
        if strict and any(k not in expected or (e.get(k, b.get(k)) is None and not (k=='conversation_id' and e.get('conversation_id'))) for k in IDENTITY):
            reasons.append('identity_missing'); continue
        if e.get('input_hash') != h or not e.get('event_id'):
            reasons.append('identity_missing'); continue
        kind=e.get('kind',''); goal=action_goal(e)
        # A generic consultation claim can be scoped by the event's product goal.
        relevant = required
        if not relevant:
            reasons.append('claim_goal_unknown'); continue
        eligible_domains = {d for d in relevant if kind in task_kinds(d, c['state'])}
        if delegate and not DELEGATION.search(goal):
            eligible_domains.discard('store')
        expedited_option = (expedite_scope and kind == 'aftersales_request' and
                            e.get('status') in ('created', 'handoff_pending') and
                            EXPEDITED_DELIVERY.search(goal) and
                            re.search(r'核查|核对|核实|\b(?:check|verify)\b', goal, re.I))
        if expedited_option:
            eligible_domains.add('delivery')
        locker_main = locker_constraint = False
        if locker_scope and kind == 'logistics_followup' and e.get('status') in ('created', 'handoff_pending'):
            requirements, separate, _ = locker_scope
            locker_main = bool(re.search(r'\b(?:check|verify|confirm)\b|核实|核查|核对', goal, re.I)) and all(LOCKER_GOALS[name].search(goal) for name in requirements)
            locker_constraint = separate and bool(LOCKER_NO_COLLECTION.search(goal))
            if locker_main:
                eligible_domains.update(relevant & {'delivery', 'billing'})
        if locker_scope and not (locker_main or locker_constraint):
            continue
        if not eligible_domains:
            reasons.append('kind_mismatch'); continue
        if kind.endswith('_lookup'):
            reasons.append('lookup_not_action'); continue
        generic_kind_claim=bool(re.search(r'product (?:inquiry|consultation)|aftersales verification|internal verification|产品咨询|售后核实|内部核实|store service request|门店服务请求',c['quote'],re.I)) and not c.get('object_mentions') and not c.get('target')
        # An explicitly typed but otherwise generic request can be supported by
        # that exact executor kind with a nonempty business goal. Never let a
        # generic product task support a specific praise/refund/delivery claim.
        typed_generic=(bool(generic_request) and len(eligible)==1 and e.get('event_id') == eligible[0].get('event_id')) or generic_kind_claim and not (specific-{'feedback','store'}) and (
            (kind in {'human_input_request','product_knowledge_request','aftersales_request','clarification_request','support_followup'} and relevant=={'product'}) or
            (kind=='store_service_request' and relevant<= {'feedback','store'} and bool(re.search('store service request|门店服务请求',c['quote'],re.I))))
        # A compound assertion still needs separate matching kinds. The literal
        # typed task noun can scope a short source-grounded goal such as 外箱破损.
        typed_domains=set()
        if locker_main:
            typed_domains.update(('delivery', 'billing'))
        elif locker_constraint:
            typed_domains.add('delivery')
        if re.search('物流核查|logistics verification',c['quote'],re.I) and kind=='logistics_followup' and goal:typed_domains.add('delivery')
        if explicit_product and kind in {'aftersales_request','human_input_request'} and goal:typed_domains.add('product')
        if re.search('收费核查|billing verification',c['quote'],re.I) and kind=='billing_request' and goal:typed_domains.add('billing')
        if kind=='store_service_request' and goal and re.search(r'门店服务请求|store service request',c['quote'],re.I):
            if not re.search(r'转达|转告|relay|pass on|praise|thanks',c['quote'],re.I):
                typed_domains.update(('store','feedback'))
        if goal and not (domains(goal) & relevant) and not typed_generic and not (typed_domains & relevant):
            reasons.append('business_goal_mismatch'); continue
        if strict and not goal:
            reasons.append('business_goal_missing'); continue
        if c.get('target') and (strict or goal or e.get('target')) and c['target'] not in goal and c['target'] != e.get('target'):
            reasons.append('target_mismatch'); continue
        if c.get('object_mentions') and goal:
            objects=claim(goal,c['state'])['object_mentions']
            if objects and not set(objects)&set(c['object_mentions']):
                reasons.append('object_mismatch'); continue
        if e.get('status') in ('failed','cancelled','rejected'):
            negative.append(e['event_id']); continue
        if e.get('status') not in allowed:
            reasons.append('status_mismatch'); continue
        if c['state']=='EXTERNAL_COMPLETED':
            payload=e.get('payload',{}); result=payload.get('result',{})
            if not (payload.get('external_execution') is True and result.get('status')=='SUCCEEDED' and result.get('authority') in ('AUTHORIZED_FIXTURE','VERIFIED_CONNECTOR') and result.get('source_id')):
                reasons.append('external_authority_missing'); continue
        if c['state']=='PENDING_EXECUTION':
            from src.application.p5b8r1_guard import future_supported
            if not future_supported(dict(runtime, events=[e]),h)[0]:
                reasons.append('schedule_missing'); continue
        matched.append(e['event_id'])
        if locker_main:
            locker_main_ids.add(e['event_id'])
        if locker_constraint:
            locker_constraint_ids.add(e['event_id'])
        covered.update(d for d in eligible_domains if d in domains(goal) or d in typed_domains or typed_generic or (not strict and not goal))
    if locker_scope:
        _, separate, _ = locker_scope
        distinct = any(main != other for main in locker_main_ids for other in locker_constraint_ids)
        if not locker_main_ids or (separate and not distinct):
            reasons.append('missing_distinct_locker_receipt' if separate else 'missing_locker_fee_check_receipt')
            matched = []
    if matched and not required<=covered:
        reasons.append('incomplete_business_goal_coverage');matched=[]
    status = 'supported' if matched else 'negative_evidence' if negative else 'evidence_mismatch' if reasons and any(x!='identity_missing' for x in reasons) else 'evidence_missing' if not events else 'unknown'
    return dict(supported=bool(matched), support_status=status, event_ids=matched, negative_event_ids=negative,
                reasons=sorted(set(reasons)), unavailable_identity_fields=sorted(unavailable),
                evidence_identity='STRICT_BOUND' if strict else 'AVAILABLE_FIELDS_ONLY_NOT_CERTIFIED')

def creation_support(text,runtime,h):
    result=support(claim(text,'INTERNAL_CREATED'),runtime,h)
    return result['supported'],result['event_ids']

EXTRA = re.compile(r'(?:已(?:经)?(?:为您)?(?:办理|完成|安排|联系|提交|创建|登记|退款|退费|到货|发货|送达)[^。！？;；\n，,]{0,45}|(?:退款|包裹|货物|物流)[^。！？;；\n，,]{0,10}已(?:经)?[^。！？;；\n，,]{1,22}|(?:I|we)(?: have|[’\x27]ve)?\s+(?:refunded|contacted|submitted|created|opened|logged|relayed|passed)[^.!?;\n,]{0,140}|(?:has been|was)\s+(?:refunded|delivered|dispatched)[^.!?;\n,]{0,45})',re.I)

CONTACT = re.compile(
    r"\b(?:I|we)(?: have|[’\x27]ve)?\s+(?:asked|told|informed|notified|emailed|called)\s+"
    r"(?:(?:the|your|our)\s+)?(?:store|repair (?:desk|team|centre|center)|carrier|merchant|supplier|billing team)[^.!?;\n,]{0,140}|"
    r'已(?:经)?(?:向|跟|和)(?:门店|维修台|维修点|维修中心|承运商|商家)[^。！？;；\n，,]{0,45}'
    r'(?:咨询|联系|沟通|说明|告知)[^。！？;；\n，,]{0,45}|'
    r'已(?:经)?(?:为您)?(?:联系|通知|告知|致电)(?:了)?(?:门店|维修台|维修点|维修中心|承运商|快递公司|商家|供应商|账务团队)'
    r'[^。！？;；\n，,]{0,38}', re.I,
)

REFUND_COMPLETION = re.compile(r"\b(?:(?:I|we)(?: have|[’\x27]ve)?\s+(?:(?:already|just|successfully)\s+)?(?:completed|processed|issued|paid)\s+(?:your |the |a |this )?refund\b(?!\s+(?:request|check|inquiry|enquiry|verification))|(?:your |the )?refund\s+(?:has been|was|is(?: now)?)\s+(?:completed|processed|issued|paid|complete)\b)",re.I)

LICENCE_RELEASE_COMPLETION = re.compile(
    r'已(?:经)?(?:为您)?(?:解除|释放|撤销)[^。！？；，,\n]{0,18}(?:设备[^。！？；，,\n]{0,8}(?:占用|授权)|许可占用)|'
    r'(?:设备[^。！？；，,\n]{0,8}(?:占用|授权)|许可占用)[^。！？；，,\n]{0,8}已(?:经)?(?:解除|释放|撤销)|'
    r"\b(?:we|I)(?: have|[’\x27]ve)?\s+(?:released|reset|cleared)\s+(?:your |the )?"
    r"(?:licen[cs]e activation|device activation slot|activation slot)\b", re.I,
)

PENDING_INTERNAL = re.compile(
    r'\b(?:an?|the)\s+(?:separate\s+)?internal\s+[^.!?;,\n]{0,65}?\b(?:request|task)\b'
    r'[^.!?;,\n]{0,160}?\b(?:is|remains)\s+(?:also\s+)?pending\b|'
    r'(?:内部)?(?:售后|物流|收费|隐私|产品咨询|核实|核查)[^。！？；，,\n]{0,24}(?:请求|任务)'
    r'[^。！？；，,\n]{0,15}(?:仍待处理|待处理)', re.I,
)


def reconcile(prior, reply, runtime, h, *, strict=False):
    """Replace each action assessment and its matching finding atomically."""
    import copy
    out=copy.deepcopy(prior); assessments=out['assessments']
    for clause in re.finditer(r'[^.。!?！？;；\n]+', reply):
        header = SEPARATE_TASK_HEADER.search(clause.group())
        if not header:
            continue
        quote = clause.group()[header.start():].strip()
        fragments = {a['quote'] for a in assessments if a['state'] == 'INTERNAL_CREATED' and a['quote'] in quote}
        assessments[:] = [a for a in assessments if a['state'] != 'INTERNAL_CREATED' or a['quote'] not in fragments]
        out['findings'] = [f for f in out['findings'] if f['code'] != 'H04' or f['quote'] not in fragments]
        assessments.append(dict(state='INTERNAL_CREATED',quote=quote))
    if runtime.get('future_intent_policy')=='owner-nonrigid-v1':
        for m in re.finditer(r'(?:保证|承诺|确保|一定)[^。；;\n]{0,25}(?:回复|回访|联系|答复)|(?:I|we) (?:promise|guarantee)[^.\n]{0,45}(?:reply|call|contact|respond)',reply,re.I):
            if re.search(r'无法|不能|不|not|cannot',reply[max(0,m.start()-8):m.start()],re.I):continue
            if not any(a['state']=='PENDING_EXECUTION' and (m.group() in a['quote'] or a['quote'] in m.group()) for a in assessments):
                assessments.append(dict(state='PENDING_EXECUTION',quote=m.group()))
    for m in sorted([*EXTRA.finditer(reply),*CONTACT.finditer(reply),*REFUND_COMPLETION.finditer(reply),
                     *LICENCE_RELEASE_COMPLETION.finditer(reply),*PENDING_INTERNAL.finditer(reply)],key=lambda m:m.start()):
        q=m.group()
        if any(q in a['quote'] or a['quote'] in q for a in assessments): continue
        prefix=re.split(r'[，,。;；]|但是|不过|但|并且|\bbut\b|\band\b',reply[max(0,m.start()-24):m.start()],flags=re.I)[-1]
        if re.search(r'尚未|没有|并未|不能|无法|如果|若|\b(?:not|never|nothing|if)\b',prefix,re.I): continue
        inquiry_created = re.match(
            r"(?:I|we)(?: have|[’\x27]ve)?\s+(?:created|opened|logged|submitted)\s+"
            r"(?:an?|the)\s+(?:internal\s+)?product\s+inquiry\b", q, re.I
        )
        contact=bool(CONTACT.fullmatch(q))
        licence_release=bool(LICENCE_RELEASE_COMPLETION.fullmatch(q))
        state='EXTERNAL_COMPLETED' if contact or licence_release else 'INTERNAL_CREATED' if inquiry_created or re.search(r'请求|任务|工单|待办|核实|需求|request|task|ticket|case|logged.{0,30}thanks',q,re.I) else 'EXTERNAL_COMPLETED'
        if domains(q) or contact or licence_release: assessments.append(dict(state=state,quote=q))
    updated=[]; findings=list(out['findings'])
    assessments=sorted(assessments,key=lambda a:reply.find(a['quote']) if reply.find(a['quote'])>=0 else len(reply))
    for a in assessments:
        original_quote=a['quote']
        # The inherited recording screen emits an INTERNAL_CREATED assessment
        # for nouns such as "a fault-report record" and ordinary input notes.
        # Keep its separate RECORD_REVIEW; these do not assert creation of a
        # business task. Actual request nouns and completed business predicates
        # continue through strict receipt validation below.
        record_context=(a['state']=='INTERNAL_CREATED' and re.search(r'记录|记下|recorded|noted',original_quote,re.I)
            and not re.search(r'请求|任务|工单|申请|request|task|ticket',original_quote,re.I)
            and not re.search(r'已(?:经)?(?:退款|退费|发货|送达|联系|完成|办理)|\b(?:refunded|contacted|dispatched|delivered|processed the refund)\b',original_quote,re.I))
        if record_context:
            findings=[f for f in findings if not (f['quote']==original_quote and f['code']=='H04')]
            updated.append(dict(a,state='NON_EXECUTION_CONTEXT',original_recognizer_state=a['state'],supported=None,event_ids=[],scope_reason='Input recording or a record noun is not task creation. RECORD_REVIEW retained.'))
            continue
        if a['state']=='INTERNAL_CREATED':
            marker=re.search(r'已(?:经)?(?:为您)?(?:创建|登记|提交)|\b(?:I|we)(?: have|[’\x27]ve)?\s+(?:created|opened|logged|submitted)\b',original_quote,re.I)
            if marker and marker.start()>0:
                prefix=original_quote[:marker.start()]
                if re.search(r'已记录|已记下|recorded|noted|您(?:希望|表示|提到|反馈)|you (?:requested|asked|said)',prefix,re.I) and not EXTRA.search(prefix):
                    scoped=re.split(r'[,，]',original_quote[marker.start():],maxsplit=1)[0].strip()
                    a=dict(a,quote=scoped,source_context_quote=original_quote,reason='Task creation is scoped separately from customer context and recording acknowledgement.')
        # Observed "I've created an internal request to pass your thanks..." was
        # cut before its business goal by the older recognizer. Use its own full
        # sentence only when the fragment has no domain; never infer from another event.
        if (a['state']=='INTERNAL_CREATED' and not domains(original_quote)
            and not re.search(r'已(?:经)?(?:为您)?(?:记录|记下)|\b(?:recorded|noted)\b',original_quote,re.I)):
            start=reply.find(original_quote)
            if start>=0:
                left=max(reply.rfind(x,0,start) for x in ('。','！','？','\n','.','!','?'))+1
                ends=[reply.find(x,start+len(original_quote)) for x in ('。','！','？','\n','.','!','?')]
                right=min([x for x in ends if x>=0] or [len(reply)])
                scoped=reply[left:right].strip()
                if domains(scoped) or GENERIC_CREATED.fullmatch(scoped):a=dict(a,quote=scoped)
        c=claim(a['quote'],a['state'],reply.find(a['quote']))
        if (c['state']=='INTERNAL_CREATED' and not c['business_object']
            and re.fullmatch(r'(?:这|该|本)?(?:项)?(?:内部)?(?:核查|核实|验证)?(?:任务|请求|工单)已(?:经)?(?:创建|登记|提交)',c['quote'].strip())):
            for antecedent in reversed(updated):
                span=antecedent.get('span',{});end=span.get('end');start=c['span']['start']
                if (antecedent.get('state')=='INTERNAL_CREATED' and antecedent.get('supported') is True
                    and antecedent.get('business_object') and type(end)is int and type(start)is int
                    and 0<=end<=start and '\n\n' not in reply[end:start]):
                    c['business_object']=antecedent['business_object'];c['object_mentions']=antecedent.get('object_mentions',[]);c['target']=antecedent.get('target')
                    c['antecedent_quote']=antecedent['quote'];c['antecedent_event_ids']=antecedent['event_ids']
                    break
        # Preserve recording and attachment-specific gates, not task evidence.
        attachment=bool(re.search(r'照片|附件|图片|photo|attachment',a['quote'],re.I))
        record_ack=bool(re.search(r'已(?:经)?(?:为您)?(?:记录|记下)|\b(?:recorded|noted)\b',a['quote'],re.I))
        # A business record being checked is not an acknowledgement that the
        # sender has recorded something. Only actual attachment/recording
        # predicates retain their specialised audit; future checks still pass
        # through scoped future-intent reconciliation below.
        if a['state']=='PROPOSAL' or (attachment or record_ack) and not re.search(r'请求|任务|工单|request|task|ticket',a['quote'],re.I):
            updated.append(dict(a,**{k:v for k,v in c.items() if k not in a}));continue
        result=support(c,runtime,h,strict=strict)
        findings=[f for f in findings if not (f['quote'] in (a['quote'],original_quote) and f['code'] in ('H04','H03','FUTURE_INTENT_REVIEW'))]
        a=dict(a,**c,**result)
        if not a['supported']:
            callback=bool(re.search(r'回复|回访|联系|同步|告知|reply|respond|follow up|contact',a['quote'],re.I))
            strict_callback=callback
            if callback and runtime.get('future_intent_policy')=='owner-nonrigid-v1':
                start=reply.find(a['quote']);sentence=re.split(r'[。！？!?\n]',reply[start:])[0]
                strict_callback=bool(re.search(r'保证|确保|一定|承诺|明天|今天|今晚|\d+\s*(?:小时|分钟|点)|(?:周|星期)[一二三四五六日天]|guarantee|promise|definitely|today|tomorrow|tonight|within\s+\d+|by\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d)',sentence,re.I))
            code=('H03' if strict_callback else 'FUTURE_INTENT_REVIEW') if a['state']=='PENDING_EXECUTION' else 'H04'
            findings.append(dict(code=code,quote=a['quote'],reason=a['support_status']+': '+','.join(a['reasons']),severity='review' if code=='FUTURE_INTENT_REVIEW' else 'block',scope='reply',finding_id=digest(a)))
        updated.append(a)
    # Observed R6 fee-waiver assertion is a policy claim, not proof of task
    # creation. A pending billing query cannot authorize an exemption.
    policy=re.compile(r"you(?:'re| are) (?:under )?no obligation to pay[^.!?\n]*(?:further|extra|additional|fee)[^.!?\n]*|you (?:do not|don't) (?:have|need) to pay[^.!?\n]*(?:extra|additional|fee)[^.!?\n]*|(?:无需|不需要)(?:再)?支付[^。！？\n]*(?:额外|费用|服务费)[^。！？\n]*",re.I)
    for match in policy.finditer(reply):
        prefix=re.split(r'[。！？!?\n,，;；]',reply[:match.start()])[-1]
        if re.search(r'无法确认|不能确认|不代表|\b(?:if|cannot confirm|can.t confirm|not saying)\b',prefix,re.I):continue
        facts=runtime.get('facts',{})
        supported=facts.get('status')=='KNOWN' and any(f.get('input_hash')==h and f.get('source_id') and f.get('authority') in ('VERIFIED_CONNECTOR','AUTHORIZED_FIXTURE') and f.get('conclusion')==match.group() for f in facts.get('facts',[]))
        if not supported:findings.append(dict(code='UNVERIFIED_FEE_POLICY',quote=match.group(),reason='A fee exemption needs a current-input verified policy fact; a pending billing task is insufficient.',severity='block',scope='reply',finding_id=digest(dict(h=h,quote=match.group(),kind='fee_policy'))))
    out.update(version=VERSION,assessments=updated,findings=findings)
    if any(a.get('supported') and any(f['quote']==a['quote'] and f['severity']=='block' for f in findings) for a in updated):
        raise ValueError('GUARD_INTERNAL_CONTRADICTION')
    return out
