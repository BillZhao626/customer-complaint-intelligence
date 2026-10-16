"""Conservative draft gate, not a complete semantic hallucination detector."""
import re

GATE_VERSION='v3-draft-gate-2-negation'


def check_reply(value,version=None):
    if version not in (None,GATE_VERSION):
        from src.application.reply_review import VERSION,check
        if version!=VERSION:raise ValueError('Unknown reply gate version')
        return check(value)
    # Current application has no approval/payment/execution authority. These
    # unqualified claims cannot be emitted even if requested in customer text.
    patterns=[r'(?<!not )(?<!not been )\b(?:refund|compensation) (?:has been |is )?approved\b',
              r'\b(?:manager|we|i) (?:has |have )?approved\b',
              r'\b(?:will|guarantee(?:d)?) (?:be )?(?:paid|pay|payment|refund|arrive|deliver)\b',
              r'\b(?:we have|i have) (?:refunded|processed|sent|cancelled)\b',
              r'(?:已批准|保证明天|明日到账|已退款|已经支付|已为您安排)',
              r'(?:我们|我方)(?:已|已经).{0,35}(?:转交|记录|升级处理)',
              r'\b(?:we have|i have) (?:logged|recorded|escalated|forwarded)\b']
    for pattern in patterns:
        for match in re.finditer(pattern,value.suggested_reply,re.I):
            # Only an immediately scoped, explicit negation can suppress a match.
            # "无法保证明天付款，但保证明天付款" still rejects the second clause.
            prefix=value.suggested_reply[:match.start()]
            if re.search(r'(?:无法|不能|不会|尚未|并未|没有|未|不)$|\b(?:cannot|can not|will not|could not|do not|did not|not|never)\s+$',prefix,re.I):
                continue
            raise ValueError('Unverified commitment in unsent draft')
