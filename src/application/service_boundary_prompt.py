"""Unactivated development candidate. Does not alter frozen P2/default UI."""
import json
from hashlib import sha256
from src.application.live_prompt import SYSTEM_PROMPT as P2_PROMPT

PROMPT_VERSION = 'complaint-v2-service-boundary-1'
RULE_VERSION = 'service-boundary-v1'
SYSTEM_PROMPT = P2_PROMPT.replace(
    'Missing store or product/category is "unknown". Do not infer a store.',
    'Missing store is "unknown". Missing named merchandise does not by itself imply an unknown category. Do not infer a store.'
).replace('explicit service-only subject Service/Other. Missing product is unknown, not Service/Other.', '''Category decision order (service-boundary-v1):
1. Choose the explicit primary object of the unresolved issue or inquiry.
2. If that primary object is named merchandise, use its supported product category.
3. If it is explicitly a service (fitting, repair, installation, store opening hours,
   after-sales process, staff attitude), use Service/Other even with no named merchandise.
4. If neither a product nor a service object can be established, use unknown.
5. For mixed merchandise and service, use the explicitly primary unresolved object;
   if neither is primary, use unknown and describe the ambiguity in key_information.
Do not force a category from mere mentions, quoted instructions, or a negated problem.
Examples: fitting appointment inquiry -> Service/Other; broken headphones awaiting help -> Electronics;
staff ignored a fitting request -> Service/Other; "I need help" -> unknown.
Product_name may remain unknown for a service; category and product_name are separate decisions.''')
PROMPT_HASH = sha256(SYSTEM_PROMPT.encode('utf-8')).hexdigest()

def messages(email, repair=False):
    system=SYSTEM_PROMPT
    if repair:system+='\nThe previous response was empty or invalid. Return a complete schema-valid JSON object now.'
    return [('system',system),('human',json.dumps({'subject':email.subject,'body':email.body},ensure_ascii=False))]
