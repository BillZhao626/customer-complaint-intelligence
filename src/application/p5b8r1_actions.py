"""Keep explicit feedback-routing requests even when their Issue is praise."""
from src.application.p5b8_pipeline import guided_actions as historical_actions
VERSION='p5b8r1-local-feedback-plan-1'
def guided_actions(analysis):
    result=historical_actions(analysis)
    for i in (analysis or {}).get('issues',[]):
        if i['issue_kind']=='praise' and i['business_process']=='store service issue' and i['customer_requests']:
            result.append(dict(kind='store_service_request',issue_ids=[i['issue_id']],goal='; '.join(i['customer_requests'])+' (internal pending feedback routing; no external delivery confirmed)',evidence=i['evidence'],priority='normal'))
    return result
