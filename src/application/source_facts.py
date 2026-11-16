"""Source-bound attachment states. A customer report is never a system receipt.

Keep Unicode offsets into the original subject/body; ambiguous clauses remain
mentions, not asserted facts. No normalization is written back as evidence.
"""
import re

MEDIA = re.compile(r'照片|图片|截[图圖]|附件|photo(?:s)?|picture(?:s)?|screenshot(?:s)?|attachment(?:s)?', re.I)
OPTIONAL_PHOTO_ALTERNATIVE = re.compile(
    r'如(?:产品|商品)页面(?:上)?(?:另有|列有)[^。！？!?，,；;\n]{1,36}?'
    r'(?:或者|或)(?P<photo>(?:您|你)(?:已经|已)(?:拍摄|拍下|拍好)的'
    r'(?:标签|铭牌|包装|说明书)?(?:照片|图片|截图))'
    r'(?=[，,]\s*(?:也)?(?:可以|可|欢迎|请)(?:一并|一起|同时|补充)?(?:提供|发送|附上))'
)
REPORTED_TASK_MODIFIER = re.compile(
    r'^\s*(?P<zh>(?:您|你)(?:提到|反映|反馈)的)'
    r'(?=(?:这|上述)?(?:两|二|三|四|五|六|\d+)(?:项|个)(?:需求|事项|核查|请求)已(?:分别|各自)(?:创建|登记|提交)内部)|'
    r'^\s*(?:the )?(?:two |three |separate )?(?:requests|tasks|checks)\s+(?P<en>you (?:mentioned|reported))'
    r'(?=\s+(?:have been|were) (?:created|opened|logged) internally\b)', re.I,
)

def nonasserted_spans(text):
    """Bounded surface scopes only; a later independent assertion is still checked.

    Quotation needs an explicit report frame. Quotation marks alone cannot hide
    a claim. Return exact offsets so callers retain the original audit text.
    """
    spans=[]
    for m in re.finditer(r'“[^”]*”|"[^"\n]*"|「[^」]*」',text):
        prefix=text[max(0,m.start()-55):m.start()]
        suffix=text[m.end():m.end()+32]
        if (re.search(r'纸条|说明|模板|包装|写着|写的|提到|上次|上轮|消息|quoted|text|message|says|said|reported',prefix,re.I)
            or re.match(r'\s*是否(?:属于|为|是).{0,10}(?:记录|证据)',suffix)):
            spans.append((m.start(),m.end(),'REPORTED_QUOTATION'))
    for m in re.finditer(r'(?:[^。！？!?；;\n.]|\.(?!\s|$))+',text):
        q=m.group()
        # Conditional scope ends at its clause, not at the next independent claim.
        for c in re.finditer(r'[^，,]+',q):
            # A record/design being requested for verification is an object of
            # the question, not evidence that this application completed it.
            for inquiry in re.finditer(r'(?:为(?:了)?|以便|需要|请)(?:核查|核对|核实|查验)[^，,。；;!?！？\n]{0,40}?(?:记录|方案|图纸)',c.group()):
                spans.append((m.start()+c.start()+inquiry.start(),m.start()+c.start()+inquiry.end(),'VERIFICATION_RECORD_OBJECT'))
            reference=re.search(r'此前已发送的记录(?=.{0,15}(?:不会|不必|无需).{0,12}重复)',c.group())
            if reference:spans.append((m.start()+c.start()+reference.start(),m.start()+c.start()+reference.end(),'REPORTED_RECORD_REFERENCE'))
            if re.match(r'\s*(?:如(?:果|您|你|已|有|页面|记录|订单|物流|后续|遇|需|能|可)|若|假如|if\b|unless\b)',c.group(),re.I):
                spans.append((m.start()+c.start(),m.start()+c.end(),'CONDITIONAL'))
            for reported in re.finditer(r'(?:按您|根据您|依据您)[^，,。；;!?！？\n]{0,24}已发送的记录(?:核对)?',c.group()):
                spans.append((m.start()+c.start()+reported.start(),m.start()+c.start()+reported.end(),'CUSTOMER_REPORT'))
            denied=re.search(r'(?:不|勿)(?:会|应|要)?.{0,8}(?:视为|作为|当作|认定|判定|证明|等于|意味着|代表|表示|说明)|不能.{0,6}(?:视为|作为|当作|认定|判定|证明)|\b(?:do not|does not|cannot|is not|not)\b.{0,35}\b(?:treat|consider|mean|proof|evidence|establish|confirm)\b',c.group(),re.I)
            if denied:
                boundary=re.search(r'但是|不过|然而|并且我们|且我们|而我们|\bbut\b|\bhowever\b|\band we\b',c.group()[denied.end():],re.I)
                end=c.start()+denied.end()+boundary.start() if boundary else c.end()
                spans.append((m.start()+c.start(),m.start()+end,'DENIED_INTERPRETATION'))
            for negative in re.finditer(r'\b(?:nothing|neither (?:item|parcel|request))\s+(?:has|have|was|were)\s+(?:been\s+)?(?:dispatched|collected|delivered|refunded|processed)\b[^,，;；.!?\n]*',c.group(),re.I):
                boundary=re.search(r'\b(?:but|however|and we)\b',negative.group(),re.I)
                end=negative.start()+boundary.start() if boundary else negative.end()
                spans.append((m.start()+c.start()+negative.start(),m.start()+c.start()+end,'NEGATIVE_COMPLETION'))
            # An embedded question after a verification verb has no asserted
            # answer. Limit the mask to its interrogative object.
            for inquiry in re.finditer(r'\b(?:confirm|verify|check|determine|establish)\s+(?:exactly\s+)?(?:what|which item)\s+(?:was|has been)\s+(?:dispatched|delivered|refunded)\b',c.group(),re.I):
                spans.append((m.start()+c.start()+inquiry.start(),m.start()+c.start()+inquiry.end(),'OPEN_INQUIRY'))
            for inquiry in re.finditer(r'(?:核对|核查|核实|确认|查明|查询|明确)[^，,。；;!?！？\n]{0,32}(?:是否|有无)[^，,。；;!?！？\n]*|\b(?:check|verify|confirm|establish|determine)\s+whether\b[^,，.;!?\n]*',c.group(),re.I):
                prefix=re.split(r'是否|有无|\bwhether\b',inquiry.group(),maxsplit=1,flags=re.I)[0]
                if re.search(r'已(?:经)?(?:退款|退费|发货|联系|完成)|already (?:refunded|contacted|dispatched)',prefix,re.I):continue
                boundary=re.search(r'但是|不过|然而|\bbut\b|\bhowever\b',inquiry.group(),re.I)
                end=inquiry.start()+boundary.start() if boundary else inquiry.end()
                spans.append((m.start()+c.start()+inquiry.start(),m.start()+c.start()+end,'OPEN_INQUIRY'))
            # Explicit 是否 is an open alternative even without a leading
            # verification verb. Stop before a separate application assertion.
            for inquiry in re.finditer(r'是否[^，,。；;!?！？\n]{1,45}',c.group()):
                boundary=re.search(r'但是|不过|并且我们|而我们',inquiry.group())
                end=inquiry.start()+boundary.start() if boundary else inquiry.end()
                spans.append((m.start()+c.start()+inquiry.start(),m.start()+c.start()+end,'OPEN_ALTERNATIVE'))
            for inquiry in re.finditer(r'\bwhether\b[^,，.;!?\n]{1,150}',c.group(),re.I):
                boundary=re.search(r'\b(?:but|however|and we|and I)\b',inquiry.group(),re.I)
                end=inquiry.start()+boundary.start() if boundary else inquiry.end()
                spans.append((m.start()+c.start()+inquiry.start(),m.start()+c.start()+end,'OPEN_ALTERNATIVE'))
        if re.search(r'物流显示|物流记录显示|按您描述|您(?:反映|反馈|提到|表示)|you (?:report|mentioned|said)|carrier (?:shows|reports)',q,re.I):
            modifier = REPORTED_TASK_MODIFIER.match(q)
            if modifier:
                start, end = modifier.span('zh' if modifier['zh'] else 'en')
                spans.append((m.start()+start,m.start()+end,'CUSTOMER_REPORT'))
                continue
            # An explicit application subject starts a fresh factual scope.
            cut=re.search(r'[，,]\s*(?:(?:但是|但|不过|然而|but\b|however\b)\s*)?(?:我们|我已|we\b|I have\b|I.ve\b)|[，,]\s*(?:但是|但|不过|然而|but\b|however\b)',q,re.I)
            spans.append((m.start(),m.start()+(cut.start() if cut else len(q)),'CUSTOMER_REPORT'))
    return spans

def mask_nonasserted(text):
    chars=list(text)
    for start,end,_ in nonasserted_spans(text):
        chars[start:end]=[' ']*(end-start)
    return ''.join(chars)

PAGE_JUMP = re.compile(
    r'\b(?:skips?|jumps?)\s+(?:directly\s+)?from\s+page\s*(\d+)\s+to\s+(?:page\s*)?(\d+)\b|'
    r'(?:从)?第?\s*(\d+)\s*页(?:直接|一下|后)?(?:跳到|跳至|接着是|紧接着是)\s*第?\s*(\d+)\s*页', re.I,
)
PAGE_RANGE = r'(\d+)\s*(?:页\s*)?(?:[-–—−~～]|\bto\b|到|至)\s*(?:第\s*)?(\d+)'
MISSING_PAGES = tuple(re.compile(pattern, re.I) for pattern in (
    r'\bmissing\s+pages?\s+' + PAGE_RANGE + r'\b',
    r'\bpages?\s+' + PAGE_RANGE + r'\s+(?:are\s+|were\s+)?missing\b',
    r'(?:缺少|缺失|少了)\s*第?\s*' + PAGE_RANGE + r'\s*页',
    r'第?\s*' + PAGE_RANGE + r'\s*页(?:都|均|已)?(?:缺失|缺少|不见了)',
))


def page_jump_facts(email):
    source = email.subject + '\n' + email.body
    facts = []
    for match in PAGE_JUMP.finditer(source):
        first, last = (int(number) for number in match.groups() if number is not None)
        if last > first + 1:
            facts.append(dict(source_quote=match.group(), first_observed_page=first, next_observed_page=last))
    return facts


def page_gap_findings(email, reply):
    """An observed page cannot be included in the asserted missing interval."""
    jumps = page_jump_facts(email)
    if not jumps:
        return []
    nonasserted = [(a, b) for a, b, kind in nonasserted_spans(reply) if kind != 'CUSTOMER_REPORT']
    findings = []
    for pattern in MISSING_PAGES:
        for match in pattern.finditer(reply):
            if any(a <= match.start() and match.end() <= b for a, b in nonasserted):
                continue
            before = re.split(r'[.。!！?？;；,，\n]|\bbut\b|但是|不过', reply[:match.start()], flags=re.I)[-1]
            after = re.split(r'[.。!！;；,，\n]', reply[match.end():], maxsplit=1)[0]
            if re.search(r'\bwhether\b|\b(?:may|might|could|not)\b|是否|可能|并非|尚不能确认', before, re.I) or re.match(r'^\s*[?？]', after):
                continue
            first, last = map(int, match.groups())
            for jump in jumps:
                if any(first <= endpoint <= last for endpoint in (jump['first_observed_page'], jump['next_observed_page'])):
                    findings.append(dict(code='SOURCE_PAGE_RANGE_CONFLICT', severity='review', scope='reply',
                                         quote=match.group(), source_quote=jump['source_quote'],
                                         reason='The stated missing range includes an observed page in the customer’s report.'))
                    break
    return findings


def reported_delivery_claim(reply,quote,email):
    """A literal object plus reported delivery is context, not an app action.

    Limited to delivery-status paraphrases; no refund/payment/contact authority.
    Returns source evidence so this exception is inspectable and reversible.
    """
    start=reply.find(quote)
    if start<0 or not re.search(r'已送达|已到货|已签收|has been delivered|was delivered',quote,re.I):return None
    left=max(reply.rfind(c,0,start) for c in '。！？!?，,；;\n：:')+1
    clause=reply[left:start+len(quote)]
    if re.search(r'我们|我方|we\b|our\b|I\b',clause,re.I):return None
    obj=re.split(r'已送达|已到货|已签收|has been delivered|was delivered',clause,flags=re.I)[0].strip()
    if not 2<=len(obj)<=30:return None
    source=email.subject+'\n'+email.body
    for m in re.finditer(r'[^。！？!?，,；;\n]+',source):
        q=m.group()
        if obj in q and re.search(r'到了|已到|送达|签收|arrived|delivered',q,re.I) and not re.search(r'没到|未到|没有|未签收|not|never',q,re.I):
            return dict(quote=q,start=m.start(),end=m.end(),authority='CUSTOMER_REPORT_ONLY_NOT_VERIFIED_DELIVERY')
    return None

def attachment_facts(email, manifest=()):
    source = email.subject + '\n' + email.body
    records = []
    for m in re.finditer(r'[^。！？!?\n]+', source):
        q = m.group()
        if not MEDIA.search(q):
            continue
        if re.search(r'上次|上一轮|之前|此前|last (?:time|week)|previous|earlier', q, re.I):
            state = 'HISTORICAL_UNVERIFIED'
        elif re.search(r'没有.{0,6}(?:发|拍)|没.{0,4}(?:发|拍)|尚未|未发送|未拍|还没|not .{0,10}sent|haven.t sent|didn.t send|not attached|no photos', q, re.I):
            state = 'DENIED_OR_NOT_SENT'
        elif re.search(r'已.{0,5}(?:发|附)|发过|发给|发送了|随信|附上|attached|have sent|already sent|sent .{0,20}(?:photo|picture)|uploaded', q, re.I):
            state = 'CUSTOMER_REPORT_SENT'
        elif re.search(r'已.{0,4}拍|拍了|拍好|拍过|took|taken|photographed', q, re.I):
            state = 'CUSTOMER_REPORT_TAKEN'
        elif re.search(r'可以|可提供|能提供|愿意|can |could |will |happy to', q, re.I):
            state = 'OFFER_TO_PROVIDE'
        else:
            state = 'MENTION_UNCLEAR'
        records.append(dict(state=state, quote=q, start=m.start(), end=m.end(), coordinate='subject+newline+body Unicode codepoints'))
    received = [x for x in manifest if x.get('status') in ('received', 'viewed')]
    viewed = [x for x in received if x.get('status') == 'viewed' and x.get('view_receipt')]
    return dict(source_mentions=records, received_files=received, viewed_files=viewed,
                absent=not records, instruction='Use only stated source levels. Offers, taken, reported sent, system received and viewed are distinct. No mention means no photo history. Ask conditionally when useful. Historical sending is unverified now. Ambiguous mentions do not establish taking or sending.')

def attachment_claim_audit(reply, email, manifest=()):
    facts = attachment_facts(email, manifest)
    states = {x['state'] for x in facts['source_mentions']}
    findings = []
    # A reply saying "you mentioned photos" is itself a source claim and must
    # still be checked. Only non-asserted quotations/conditions are masked here.
    audit_chars=list(reply)
    for start,end,kind in nonasserted_spans(reply):
        if kind!='CUSTOMER_REPORT':audit_chars[start:end]=[' ']*(end-start)
    # An optional photo in a conditional list is not a premise about what the
    # customer took. Remove only that noun phrase, not the rest of the sentence.
    for match in OPTIONAL_PHOTO_ALTERNATIVE.finditer(reply):
        start, end = match.span('photo')
        audit_chars[start:end] = [' '] * (end - start)
    audit_text=''.join(audit_chars)
    for m in re.finditer(r'[^。！？!?，,；;\n.]+', audit_text):
        q=m.group()
        # Future completion in an until-clause is a prerequisite, not a past
        # viewing assertion. Restrict it to its own sentence; later assertions
        # are independently audited.
        q=re.sub(r'\buntil\b[^.。!?\n]{0,90}\b(?:has|have|is|are)\s+(?:been\s+)?(?:reviewed|received)\b','',q,flags=re.I)
        q=re.sub(r'(?:您|你)(?:表示)?(?:愿意|可以|能|可)(?:拍摄|拍照|拍|提供|发送|发来)','',q)
        # An indefinite restrictive relative does not assert existence. Keep
        # any independent system-viewing/receipt predicate in the same clause.
        q=re.sub(r'(\bany (?:photos|pictures|screenshots))\s+you(?:\s+have|[’\x27]ve)?\s+(?:already\s+)?(?:taken|sent)\b',r'\1',q,flags=re.I)
        if not MEDIA.search(q):
            continue
        # Questions, conditional proposals, and explicit negation assert no past event.
        optional_possession=(re.match(r'\s*(?:and\s+)?(?:keep|retain|save|send|provide|share)\s+any\s+(?:photos|pictures|screenshots)\s+you\s+(?:have\s+)?(?:taken|sent)\b',q,re.I)
            and not re.search(r'\b(?:we|I)\s+(?:have\s+)?(?:received|reviewed|seen|looked at)\b',q,re.I))
        if optional_possession or re.search(r'如果|若|如(?:您|你|已|有)|是否|请|可以|方便|未确认|无法确认|尚未|还没|没拍|没发|没有|未收到|未查看|不代表|if |please |could you|can you|cannot|can.t|not (?:received|reviewed|taken|sent)|haven.t|whether|(?:any )?photos you may have (?:taken|sent)',q,re.I):
            continue
        level=None
        if re.search(r'看过|查看了|已查看|reviewed|have seen|looked at',q,re.I):level='VIEWED'
        elif re.search(r'已收到|收到了|we received|have received',q,re.I):
            # Receipt of a named physical parcel does not claim receipt of a
            # picture that is requested later in the same clause.
            if not re.search(r'(?:您|你)已收到的[^。！？!?，,]{1,24}(?:上的|的)(?:运单号或|面单|标签|外箱)',q):
                level='RECEIVED'
        elif re.search(r'已.{0,4}(?:发送|发来|提供)|您.{0,5}(?:发的|发来)|提到.{0,6}(?:发送|发)|you.{0,25}(?:sent|sending|attached)|photos you sent',q,re.I):level='SENT'
        elif re.search(r'已.{0,4}拍|您.{0,8}(?:拍摄|拍了)|提到.{0,8}拍|you.{0,20}(?:took|taken)|photos you took',q,re.I):level='TAKEN'
        supported = level is None or (level=='VIEWED' and bool(facts['viewed_files'])) or (level=='RECEIVED' and bool(facts['received_files'])) or (level=='SENT' and 'CUSTOMER_REPORT_SENT' in states) or (level=='TAKEN' and bool(states & {'CUSTOMER_REPORT_TAKEN','CUSTOMER_REPORT_SENT'}))
        if not supported:
            findings.append(dict(code='ATTACHMENT_PREMISE',severity='block',scope='reply',quote=reply[m.start():m.end()],asserted_level=level,source_states=sorted(states),reason='Past attachment assertion lacks corresponding source or system receipt'))
    return dict(facts=facts,findings=findings,coverage='Scoped bilingual explicit attachment assertions; ambiguous language requires semantic review')
