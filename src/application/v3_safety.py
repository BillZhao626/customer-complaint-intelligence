"""Conservative draft gate, not a complete semantic hallucination detector."""
import re


def check_reply(value):
    # Current application has no approval/payment/execution authority. These
    # unqualified claims cannot be emitted even if requested in customer text.
    patterns=[r'(?<!not )(?<!not been )\b(?:refund|compensation) (?:has been |is )?approved\b',
              r'\b(?:manager|we|i) (?:has |have )?approved\b',
              r'\b(?:will|guarantee(?:d)?) (?:be )?(?:paid|pay|payment|refund|arrive|deliver)\b',
              r'\b(?:we have|i have) (?:refunded|processed|sent|cancelled)\b',
              r'(?:已批准|保证明天|明日到账|已退款|已经支付|已为您安排)']
    if any(re.search(p,value.suggested_reply,re.I) for p in patterns):
        raise ValueError('Unverified commitment in unsent draft')
