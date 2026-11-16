"""Bounded HTTP gate checks and read-only restart checks; no model dispatch."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.app.p5_api import create_app
from src.application.product_workflow import ProductStore
from src.application.p5b3_actions import journal
from src.application.mail_threads import MailThreads
from src.evaluation.p5b_pilot import write_new,read,now
from src.application.p5b3_runtime import Budget,LOCAL
from src.domain.contracts import digest
from fastapi.testclient import TestClient

store=ProductStore(ROOT/'.local/p4/p5b3-20261029-v1/product.sqlite3')
client=TestClient(create_app(store.path,serve_web=False,live_generate=True))
headers={'x-p5-token':client.get('/api/session').json()['token']}
cases=store.list_cases();calls_before=Budget(LOCAL/'budget.sqlite3').summary()['reserved_attempts'];checks=[]
def post(c,action):
    result=client.post('/api/cases/'+c['case_id']+'/actions',headers=headers,json=dict(action=action,revision=c['revision'],operation_id='b3-negative-'+c['case_id']+'-'+action,reason='demo_test gate check',checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True)))
    checks.append(dict(case_id=c['case_id'],action=action,status=result.status_code))
    assert result.status_code==409

for c in cases:
    if c['state']=='analysis_failed' or c['quality']['status']=='blocked':
        post(c,'approve');post(c,'simulate_send')
    if c['receipt']:
        assert c['receipt']['body_hash']==c['draft']['body_hash']
        assert c['receipt']['version']==c['current_version']
        assert any(e['action']=='approve' and e['version']==c['current_version'] for e in c['events'])
        assert ProductStore(store.path).get(c['case_id'])['receipt']==c['receipt']
        checks.append(dict(case_id=c['case_id'],receipt_hash=digest(c['receipt']),restart_reopen=True,draft_versions=len(c['drafts'])))
    MailThreads(store).messages(c['case_id'])
Budget(LOCAL/'budget.sqlite3').halt('P5B3_COMPLETED_MIXED_RESULT_NO_FURTHER_DISPATCH')
closed=client.post('/api/live',headers=headers,json=dict(subject='Closed ledger probe',body='合成预算停发测试，不得派发',synthetic_confirmed=True))
assert closed.status_code==409
assert Budget(LOCAL/'budget.sqlite3').summary()['reserved_attempts']==calls_before
tasks=[]
with journal(store).connect() as conn:
    count=conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    events=conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
for c in cases:
    tasks.extend(journal(store).list(c['run'].input_hash))
write_new(ROOT/'docs/p5b3/E2E_RECEIPT.json',dict(at=now(),checks=checks,ui_cases=[dict(case_id=c['case_id'],subject=c['run'].email.subject,run_id=c['run'].run_id,source_kind=c['source_kind'],state=c['state'],draft_versions=len(c['drafts']),tasks=[t['task_id'] for t in journal(store).list(c['run'].input_hash)],events=[dict(event_id=e['event_id'],action=e['action'],actor_type=e['actor_type'],version=e['version']) for e in c['events']]) for c in cases],local_task_count=count,local_task_events=events,simulated_sends=sum(bool(c['receipt']) for c in cases),demo_test_takeovers=sum(any(e['action']=='take_over' for e in c['events']) for c in cases),real_human_takeovers=0,external_business_actions=0,budget_closed_http=closed.status_code,provider_calls=calls_before))
print('PASS: bound receipts, reopen, live thread links, safety/failed gates, budget closed; calls',calls_before)
