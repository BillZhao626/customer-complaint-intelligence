"""Versioned lexical review gate; no match is not semantic or human approval."""
import re

VERSION='v3-draft-gate-3-scoped-review'

# Split contrast before evaluating negation so a denied first clause cannot
# authorize a commitment after "but". Quote boundaries do not confer authority.
BOUNDARY=re.compile(r'[。！？!?;；\n，,]|\b(?:but|however|nevertheless|yet)\b|但是|不过|然而|可是|但',re.I)
RULES=(
    ('executed_action', 'block', r'\b(?:we|i)\s+(?:have\s+|already\s+|have\s+already\s+)(?:approved|refunded|processed|sent|cancelled|logged|recorded|escalated|forwarded|arranged)\b'),
    ('executed_action', 'block', r'(?:我们|我方)?(?:已经|已)(?:为您|给您|将|把)?[^。！？;；\n，,]{0,25}(?:批准|退款|支付|转交|记录|安排|升级处理)'),
    ('approval_claim', 'block', r'\b(?:refund|compensation)\s+(?:(?:has|have)\s+been\s+|is\s+|was\s+)?approved\b|\b(?:manager|we|i)\s+(?:has\s+|have\s+)?approved\b'),
    ('executed_action', 'block', r'\b(?:refund|payment|compensation|case)\s+has\s+been\s+(?:processed|sent|logged|recorded|forwarded)\b'),
    ('material_commitment', 'block', r'\b(?:will|guarantee(?:d)?)\s+(?:be\s+)?(?:paid|pay|payment|refund|arrive|deliver)\b'),
    ('material_commitment', 'block', r'\bwill\s+(?:process|issue|approve|provide|send)\s+(?:(?:your|a|the)\s+)?(?:refund|compensation|payment|replacement)\b'),
    ('material_commitment', 'block', r'(?:保证|确保|一定|必定|肯定|承诺)[^。！？;；\n，,]{0,18}(?:到账|付款|退款|赔偿|送达)|(?:明天|明日|今天|今日|\d+天内)[^。！？;；\n，,]{0,10}(?:到账|退款|付款|送达)'),
    ('material_commitment', 'block', r'(?:我们|我方|本店)(?:将|会)(?:为您|尽快|尽早){0,2}(?:办理)?(?:退款|赔偿|付款|发货)'),
    ('vague_material_promise', 'review', r'\b(?:may|might|should|expect(?:ed)?\s+to|hope\s+to|aim\s+to|likely\s+to)\s+(?:be\s+able\s+to\s+|be\s+)?(?:refund(?:ed)?|pay|paid|processed|deliver(?:ed)?|arrive|(?:offer|provide|issue)\s+(?:a\s+)?(?:refund|compensation))\b'),
    ('vague_material_promise', 'review', r'(?:预计|应该|争取|尽量|可能|大概)[^。！？;；\n，,]{0,18}(?:到账|退款|付款|赔偿|送达)'),
)


def negated(prefix):
    # Bounded predicates, not an arbitrary "not" anywhere in the sentence.
    # "cannot confirm that a manager approved" is a denial of certification.
    english=r'\b(?:cannot|can\s+not|will\s+not|could\s+not|do\s+not|did\s+not|not|never)\s+(?:(?:guarantee|confirm|state|say|promise|claim|assure)\s+(?:that\s+)?(?:a\s+|the\s+)?)?$'
    chinese=r'(?:无法|不能|不会|未能|尚未|并未|没有|未|不)(?:(?:保证|确认|承诺|声称|表示)(?:已经|已|会|能够)?)?$'
    return bool(re.search(english,prefix,re.I) or re.search(chinese,prefix))


def inspect_reply(text):
    findings=[];cursor=0
    pieces=[]
    for match in BOUNDARY.finditer(text):
        pieces.append((cursor,text[cursor:match.start()]));cursor=match.end()
    pieces.append((cursor,text[cursor:]))
    for offset,clause in pieces:
        for kind,severity,pattern in RULES:
            for match in re.finditer(pattern,clause,re.I):
                prefix=clause[:match.start()]
                if negated(prefix):continue
                # Conditionals and reported speech require a person; they are not
                # asserted approval, and also cannot silently authorize payment.
                reported=bool(re.search(r'\b(?:you\s+(?:said|report(?:ed)?)|according\s+to|if\s+approved)\b|您(?:提到|说)|如果.{0,8}批准',prefix,re.I))
                hedged_deadline=(kind=='material_commitment' and bool(re.match(r'(?:明天|明日|今天|今日|\d+天内)',match.group()))
                    and bool(re.search(r'(?:预计|应该|争取|尽量|可能|大概)[^。！？;；\n，,]{0,8}$',prefix))
                    and not re.search(r'保证|确保|一定|必定|肯定|承诺',prefix))
                findings.append(dict(kind=kind,severity='review' if reported or hedged_deadline else severity,
                    start=offset+match.start(),end=offset+match.end(),quote=match.group(),
                    reason='reported/conditional statement requires contextual review' if reported else kind))
    # Multiple patterns can describe one claim. Preserve evidence, avoid duplicate UI alerts.
    unique={(f['start'],f['end'],f['kind']):f for f in findings}
    findings=sorted(unique.values(),key=lambda f:(f['start'],f['end'],f['kind']))
    status='blocked' if any(f['severity']=='block' for f in findings) else 'review_required' if findings else 'no_lexical_signal'
    return dict(version=VERSION,status=status,findings=findings,human_approved=False,
                caveat='Lexical screening only; absence of a signal is not semantic correctness or approval')


def check(value):
    result=inspect_reply(value.suggested_reply)
    if result['findings']:raise ValueError('Unverified claim or material promise requires review')
