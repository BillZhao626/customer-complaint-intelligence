"""Bounded checks for destructive file advice and sensitive email intake."""
import re

from src.application.reply_guidance import source_topics, verified_facts
from src.application.source_facts import nonasserted_spans


CLAUSE_BREAK = re.compile(r'[.。!?！？;；\n]+|\b(?:but|however)\b|但是|不过|然而', re.I)
SYNC_OPERATION = re.compile(
    r'\b(?:move|delete|remove|drag|cut|erase|relocate|trash|(?P<gerund>moving|deleting|removing|dragging|cutting|erasing|relocating|trashing))\s+'
    r'(?:(?:the|your|this|that|original|local|device|synced)\s+){0,3}'
    r'(?:files?|folders?|it|them|originals?|(?:downloaded )?cop(?:y|ies)|downloads?)\b|'
    r'(?:把|将)[^，。；！？\n]{0,13}(?:文件|原件|副本)[^，。；！？\n]{0,6}(?:移出|移走|移动|搬走|挪出|挪走|挪到|删除|清除|剪切)|'
    r'(?:移出|移走|移动|搬走|删除|清除|剪切)[^，。；！？\n]{0,12}(?:文件|原件|副本)',
    re.I,
)
SYNC_DIRECTIVE = re.compile(
    r'\b(?:please|try|just|go ahead and|feel free to|you (?:can|could|should|may|need to)|'
    r'(?:recommend|suggest|(?:option|step|safest) (?:is|would be))(?:\s+(?:that you|to))?|or)\s*$|'
    r'(?:请|建议|可以|可先|先|最好|不妨|然后|或者|再)(?:您)?\s*$', re.I,
)
SYNC_EXPLANATION = re.compile(r'\b(?:whether|how|why)\s+(?:(?:you|to)\s+)?$|(?:是否|如何|能否)\s*$', re.I)
SYNC_DENIAL = re.compile(
    r"\b(?:do not|don't|never|avoid|must not|should not|cannot|can't|shouldn't|not to)\s*(?:yet\s+)?$|"
    r'(?:请勿|请不要|不要|别|不得|不能|避免|不建议)\s*(?:先|立即)?\s*$', re.I,
)
DENIED_ALTERNATIVE = re.compile(
    r"(?:\b(?:do not|don't|never|avoid)\b|请勿|不要|别)[^,，]{0,65}"
    r'(?:\bor\b|或(?:者)?)\s*$', re.I,
)
SYNC_PRECONDITION = re.compile(r'\b(?:only (?:if|after)|once|after)\b|只有|仅在|核实后|确认后', re.I)
CONFIRMED_SYNC_BEHAVIOR = re.compile(
    r'\b(?:confirms?|verif(?:y|ies|ied)|checks?)\b[^.。]{0,90}\b(?:sync|synced|propagat\w*|deletion)\b|'
    r'(?:确认|核实|查清)[^。]{0,28}(?:同步|传播|云端)', re.I,
)
VERIFIED_RECOVERY = re.compile(
    r'\b(?:verify|test|check|verified|tested)\b[^.。]{0,45}\b(?:independent|separate|offline)\b[^.。]{0,45}'
    r'\b(?:restor\w*|recover\w*|open\w*)\b|(?:验证|测试|确认)[^。]{0,22}(?:独立|离线)[^。]{0,22}(?:恢复|打开|还原)',
    re.I,
)
SYNC_GUARANTEE = re.compile(
    r"\b(?:deleting|removing|moving)\b[^,，.!?]{0,55}\b(?:will not|won't|does not)\s+"
    r'(?:delete|remove|affect|touch|change)\b[^,，.!?]{0,35}\b(?:cloud|sync(?:ed)?)\b|'
    r'(?:删除|移出|移动)[^，。！？]{0,16}(?:不会|不影响)[^，。！？]{0,16}(?:云端|同步副本)', re.I,
)


def sync_findings(email, reply, facts):
    if 'sync_file_recovery' not in source_topics(email):
        return []
    authorized = {fact['conclusion'].strip().rstrip('.。') for fact in verified_facts(email, facts)
                  if fact.get('topic') == 'sync_file_recovery'}
    quotes = [(a, b) for a, b, kind in nonasserted_spans(reply) if kind == 'REPORTED_QUOTATION']
    findings = []
    start = 0
    for delimiter in [*CLAUSE_BREAK.finditer(reply), None]:
        end = delimiter.start() if delimiter else len(reply)
        clause = reply[start:end]
        evidence = clause.strip()
        risky = False
        if evidence and evidence not in authorized:
            for match in SYNC_OPERATION.finditer(clause):
                if any(a <= start + match.start() and start + match.end() <= b for a, b in quotes):
                    continue
                prefix = clause[:match.start()]
                tail = re.split(r'[,，]', prefix)[-1].strip()
                if SYNC_DENIAL.search(tail) or DENIED_ALTERNATIVE.search(tail) or SYNC_EXPLANATION.search(tail):
                    continue
                directed = (not tail and not match['gerund']) or SYNC_DIRECTIVE.search(tail)
                conditioned = (SYNC_PRECONDITION.search(prefix) and CONFIRMED_SYNC_BEHAVIOR.search(prefix)
                               and VERIFIED_RECOVERY.search(prefix))
                if directed and not conditioned:
                    risky = True
                    break
            guarantee = SYNC_GUARANTEE.search(clause)
            if guarantee and not any(a <= start + guarantee.start() and start + guarantee.end() <= b for a, b in quotes):
                prefix = re.split(r'[,，]', clause[:guarantee.start()])[-1]
                if not re.search(r'\bwhether\b|\bcheck if\b|\b(?:cannot|can.t|don.t|do not)\b|是否|无法确认|不能确认', prefix, re.I):
                    risky = True
        if risky:
            findings.append(dict(code='UNVERIFIED_SYNC_MUTATION', severity='block', scope='reply', quote=evidence,
                                 reason='Verify this product’s sync behavior and an independent recoverable copy before recommending a potentially destructive file operation.'))
        start = delimiter.end() if delimiter else end
    return findings


SECRET = re.compile(
    r'取件码|门锁密码|门禁密码|密码(?!重置|找回|修改)|完整(?:身份证|证件|第三方电话|他人号码)|'
    r'\b(?:pickup code|collection code|key code|door code|password(?![- ]reset\b))\b|(?<![A-Za-z0-9])PIN(?:码|号)?(?![A-Za-z0-9])|'
    r'full (?:ID|identity document|third.party (?:phone )?number)', re.I,
)
CARD_NUMBER = re.compile(r'卡号|卡片号码|卡背号码|卡密|卡背(?:信息|照(?:片)?)|\b(?:gift[ -]card |card )(?:(?:redemption|claim) )?(?:number|code)\b', re.I)
INTAKE = re.compile(
    r'(?:^\s*|请\s*|并\s*|再\s*|另\s*|然后\s*|(?<![无無不未])需(?:要)?\s*)(?:您)?(?:通过(?:普通)?(?:邮件|邮箱))?(?:发送|发来|回复|提供|上传|告诉|附上|提交)|'
    r'\b(?:send|email|share|provide|forward|attach|reply with|include|paste|upload)\b', re.I,
)
REFUSAL = re.compile(
    r"(?:请勿|别|不要|无需|不必|不用|无须|避免|不能|\b(?:do not|don't|never|without|no need to|avoid)\b)\s*"
    r'(?:通过(?:普通)?邮件|by (?:ordinary )?e-?mail)?\s*$', re.I,
)
REFUSED_NOUN = r'(?:(?:a|an|the|your|full)\s+|完整)*(?:(?:password|PIN(?:码|号)?|pickup code|collection code|(?:gift[ -])?card number)(?![A-Za-z0-9])|密码|取件码|卡号|卡密|卡背(?:信息|照(?:片)?)?)'
REFUSED_LIST = REFUSED_NOUN + r'(?:\s*(?:\bor\b|\bnor\b|\band\b|或|和|、)\s*' + REFUSED_NOUN + r')*'
REFUSAL_TARGET = re.compile(
    r'(?:\b(?:not|rather than|instead of|without(?: (?:sending|sharing|providing|including|emailing))?)\s+|'
    r'(?:而非|不是|(?:请勿|别|不要|无需|无须|不用|不必)(?:通过(?:普通)?(?:邮件|邮箱))?(?:提供|发送|回复|上传|附上)?))'
    + REFUSED_LIST + r'|\bno\s+' + REFUSED_LIST + r'\s+(?:is\s+|are\s+)?(?:needed|required)\b', re.I,
)
LIMITED_DIGITS = re.compile(r'\b(?:last|first|final)\s+(?:[2-6]|two|three|four|five|six|few)\s+digits?\s+(?:of\s+)?(?:(?:the|your)\s+)?$|(?:部分|尾号|末[二三四五六2-6２-６]位(?:的)?)\s*$', re.I)
LIMITED_DIGITS_AFTER = re.compile(r'^\s*(?:的)?(?:末|最后|后)(?:[二三四五六2-6２-６]|几)位')
IN_PERSON = re.compile(r'在(?:柜台|门店).{0,14}(?:出示|提供)|(?:出示|提供).{0,14}(?:柜台|门店)', re.I)
INTAKE_ALTERNATIVE = re.compile(r'^\s*(?:or\b|或者|或)', re.I)


def sensitive_intake_findings(email, reply):
    source = email.subject + '\n' + email.body
    gift_card = bool(re.search(r'礼品卡|储值卡|\bgift[ -]card\b', source, re.I))
    refused = [match.span() for match in REFUSAL_TARGET.finditer(reply)]
    reported_quotes = [(a, b) for a, b, kind in nonasserted_spans(reply) if kind == 'REPORTED_QUOTATION']
    findings = []
    for clause in re.finditer(r'[^.。!?！？;；,，\n]+', reply):
        text = clause.group()
        matches = [(m, False) for m in SECRET.finditer(text)]
        matches.extend((m, True) for m in CARD_NUMBER.finditer(text)
                       if gift_card or re.search(r'gift[ -]card', m.group(), re.I))
        for match, card_number in sorted(matches, key=lambda pair: pair[0].start()):
            start, end = clause.start() + match.start(), clause.start() + match.end()
            if any(a <= start and end <= b for a, b in refused + reported_quotes):
                continue
            prefix = re.split(r'\b(?:but|however)\b|但是|不过|然而', text[:match.start()], flags=re.I)[-1]
            verbs = list(INTAKE.finditer(prefix))
            if not verbs and INTAKE_ALTERNATIVE.match(prefix):
                prefix = CLAUSE_BREAK.split(reply[:clause.start()])[-1] + prefix
                verbs = list(INTAKE.finditer(prefix))
            if not verbs:
                continue
            verb = verbs[-1]
            if REFUSAL.search(prefix[:verb.start()]):
                continue
            if len(verbs) > 1 and re.search(r'\bor\s*$', prefix[:verb.start()], re.I) and REFUSAL.search(prefix[:verbs[-2].start()]):
                continue
            if card_number and (LIMITED_DIGITS.search(prefix) or LIMITED_DIGITS_AFTER.match(text[match.end():])):
                continue
            if IN_PERSON.search(text) and not re.search(r'邮件|短信|发送|回复|上传|\b(?:email|send|reply|upload|text)\b', text, re.I):
                continue
            findings.append(dict(code='SENSITIVE_EMAIL_INTAKE', severity='block', scope='reply', quote=text.strip(),
                                 reason='This request permits sending a secret or a full sensitive identifier in the reply.'))
            break
    return findings


TARIFF_OUTCOME = re.compile(
    r'(?:保证|确认|确定)(?:不会|不把|不将)[^，。！？]{0,25}(?:全部|所有)[^，。！？]{0,18}(?:新价|新费率)|'
    r"\b(?:guarantee|confirm|ensure)\s+(?:that\s+)?(?:we |you )?(?:won't|will not)\b"
    r'[^.。!?]{0,45}\b(?:all (?:units|usage)|every unit)\b[^.。!?]{0,35}\b(?:new rate|new tariff|new price)\b', re.I,
)


def tariff_findings(email, reply, facts):
    if 'tariff_reconciliation' not in source_topics(email):
        return []
    authorized = {fact['conclusion'].strip().rstrip('.。') for fact in verified_facts(email, facts)
                  if fact.get('topic') == 'tariff_reconciliation'}
    scopes = nonasserted_spans(reply)
    findings = []
    for clause in re.finditer(r'[^.。!?！？;；\n]+', reply):
        if clause.group().strip() in authorized:
            continue
        for match in TARIFF_OUTCOME.finditer(clause.group()):
            if any(a <= clause.start()+match.start() and clause.start()+match.end() <= b for a, b, _ in scopes):
                continue
            if re.search(r'无法|尚未|不能|\b(?:cannot|can.t|could not)\b', clause.group()[:match.start()][-12:], re.I):
                continue
            findings.append(dict(code='SOURCE_TARIFF_ALLOCATION_UNVERIFIED', severity='review', scope='reply', quote=match.group(),
                                 reason='The task can check the allocation. The billing interval and applicable allocation method still need evidence.'))
    return findings
