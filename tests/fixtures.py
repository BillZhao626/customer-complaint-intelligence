"""Expectations are hand-written, independent of the fake's implementation."""
from src.domain.contracts import EmailInput

EMAILS = [
    EmailInput(email_id='fixture-a-negative',subject='Synthetic A complaint',body='[store:A] [negative] Synthetic: headphones broke.'),
    EmailInput(email_id='fixture-a-positive',subject='Synthetic A thanks',body='[store:A] [positive] Synthetic: thank you.'),
    EmailInput(email_id='fixture-b-neutral',subject='Synthetic B inquiry',body='[store:B] [neutral] Synthetic: opening hours?'),
    EmailInput(email_id='fixture-unknown',subject='Synthetic unknown store',body='[neutral] Synthetic: inquiry without store.'),
]
EXPECTED = [('A','negative',True),('A','positive',False),('B','neutral',False),('unknown','neutral',False)]
VALID = dict(store_location='A',product_name='headphones',product_category='Electronics',sentiment='negative',urgency='medium',
    is_complaint=True,complaint_reason='product quality',source_attribution='product issue',key_information=['synthetic'],
    summary='Broken headphones.',suggested_reply='Thank you for contacting us.',confidence=0.8)
