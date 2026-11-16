"""Keep evidenced relay requests across resolved/praise/mixed Issue boundaries."""
import re
from src.application.p5b8r1_actions import guided_actions as previous

VERSION='p5b8r4-explicit-local-relay-1'

def guided_actions(analysis):
    actions=previous(analysis)
    for issue in (analysis or {}).get('issues',[]):
        requests=issue.get('customer_requests',[]);evidence=issue.get('evidence',[])
        relay=re.compile(r'转达|转交|pass.{0,20}thanks|relay.{0,20}thanks',re.I)
        if not any(relay.search(x) for x in requests) or not any(relay.search(x) for x in evidence):continue
        if any(a['kind']=='store_service_request' and issue['issue_id'] in a['issue_ids'] for a in actions):continue
        actions.append(dict(kind='store_service_request',issue_ids=[issue['issue_id']],goal='; '.join(x for x in requests if relay.search(x)),evidence=evidence,priority='normal'))
    return actions
