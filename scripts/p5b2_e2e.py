"""Controlled HTTP assertions against saved real runs. No model dispatch."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b2 import DOC,LOCAL,read,write_new,now
from src.application.product_workflow import ProductStore
from src.app.p5_api import create_app
from fastapi.testclient import TestClient

WORK=ROOT/'.local/p4/p5-b2-20261029-v1/product.sqlite3'
app=create_app(WORK,serve_web=False);client=TestClient(app)
token=client.get('/api/session').json()['token'];headers={'X-P5-Token':token}
rows=read(DOC/'PRODUCT_CASES.json');byturn={r['turn_id']:r for r in rows};evidence=[]
def detail(tid):return client.get('/api/cases/'+byturn[tid]['case_id']).json()
def attempt(tid,action,extra=None):
    d=detail(tid);payload=dict(action=action,revision=d['revision'],operation_id='p5b2-e2e:'+tid+':'+action,
        checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True),reason='P5-B2 demo_test negative gate assertion')
    payload.update(extra or {})
    response=client.post('/api/cases/'+d['case_id']+'/actions',json=payload,headers=headers)
    evidence.append(dict(turn_id=tid,action=action,http_status=response.status_code,response=response.json()))
    return response

# Browser-generated receipts must bind unchanged B output, approval and version.
for tid in ('P5A-F01-M01-1','P5A-F07-M01-3'):
    d=detail(tid);assert d['state']=='simulated_sent' and d['receipt']['mode']=='simulation_only'
    r=read(LOCAL/'formal/turns'/tid/'run.json');body=r['result']['suggested_reply']
    assert d['receipt']['body']==body and d['draft']['body']==body
    actions=[e['action'] for e in d['events']]
    assert 'approve' in actions and 'simulate_send' in actions
    if tid.endswith('M01-3'):assert 'take_over' in actions
    evidence.append(dict(turn_id=tid,checks='browser receipt/raw/approval/version exact',detail=d))
    receipt=dict(d['receipt'])
    reopened=ProductStore(WORK).get(d['case_id']);assert reopened['receipt']==receipt
    evidence.append(dict(turn_id=tid,reopen_verified=True,event_ids=[e['event_id'] for e in reopened['events']]))

# Real accepted safety draft cannot be approved or sent before takeover.
safety='P5A-F05-M01-3';assert detail(safety)['triage']['requires_takeover']
assert attempt(safety,'approve').status_code==409
assert attempt(safety,'simulate_send').status_code==409
assert detail(safety)['state']=='pending_review'

# Invalid real three-issue raw never gets a draft or approval, even after takeover.
bad='P5A-F08-M01-1';assert detail(bad)['draft'] is None
assert '紧急程度' in detail(bad)['validation_reason']
assert attempt(bad,'approve').status_code==409
assert attempt(bad,'take_over').status_code==200
assert attempt(bad,'save_edit',dict(body='替换文案也不能修复原分析')).status_code==409
assert attempt(bad,'simulate_send').status_code==409
assert detail(bad)['draft'] is None

# Explicit human request is application evidence, never an accepted external transfer.
h=detail('P5A-F10-M01-2');assert h['triage']['handoff']=='requested' and 'approve' not in h['allowed_actions']
assert attempt('P5A-F10-M01-2','approve').status_code==409

store=ProductStore(WORK);cases=store.list_cases()
write_new(DOC/'PRODUCT_E2E_RECEIPT.json',dict(at=now(),identity='DEMO_TEST_NOT_HUMAN_REVIEW',checks=evidence,
    summary=dict(cases=len(cases),simulations=sum(bool(c['receipt']) for c in cases),
        local_requests=sum(any(e['action']=='request_handoff' for e in c['events']) for c in cases),
        demo_takeovers=sum(any(e['action']=='take_over' for e in c['events']) for c in cases),
        real_human_takeovers=0,external_sends=0,external_business_actions=0)))
print('PASS: browser receipts; reopen; safety takeover gate; rejected raw/edit/send gates; explicit human request')
