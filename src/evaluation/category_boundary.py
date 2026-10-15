"""Decision table on REVIEWED evidence, not a keyword NLP classifier or output patch."""
from src.domain.contracts import PRODUCT_CATEGORIES

RULE_VERSION = 'service-boundary-v1'
SERVICES = ('fitting service','repair service','installation service','opening hours','after-sales service','staff attitude')

def decide_category(product_category, service_object, primary):
    if product_category is not None and product_category not in PRODUCT_CATEGORIES:
        raise ValueError('Unsupported product category')
    if primary not in ('product','service','unknown','ambiguous'):
        raise ValueError('Explicit primary-object assessment required')
    if primary=='service' and service_object and service_object.strip():return 'Service/Other'
    if primary=='product' and product_category:return product_category
    return 'unknown'
