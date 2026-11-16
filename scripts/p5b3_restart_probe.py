"""GET-only server restart verification, including hidden thread parents."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from src.application.product_workflow import ProductStore
from src.application.p5b3_runtime import Budget,LOCAL
from src.evaluation.p5b_pilot import read,write_new,now
from src.domain.contracts import digest
store=ProductStore(ROOT/'.local/p4/p5b3-20261029-v1/product.sqlite3')
with httpx.Client(base_url='http://127.0.0.1:8767',trust_env=False,timeout=15) as c:
    rows={}
    for case in store.list_cases():
        r=c.get('/api/cases/'+case['case_id']);r.raise_for_status();d=r.json()
        rows[case['case_id']]=dict(run_id=d['run_trace']['run_id'],state=d['state'],drafts_hash=digest(d['drafts']),receipt_hash=digest(d['receipt']),events_hash=digest(d['events']),tasks_hash=digest(d['business_tasks']),messages_hash=digest(d['messages']))
if sys.argv[1]=='before':
    write_new(LOCAL/'restart-before.json',rows)
else:
    assert rows==read(LOCAL/'restart-before.json')
    b=Budget(LOCAL/'budget.sqlite3').summary();assert b['reserved_attempts']==77 and b['halted']
    write_new(ROOT/'docs/p5b3/RESTART_RECEIPT.json',dict(at=now(),identity='REAL_SERVER_PROCESS_RESTART_GET_VERIFIED',cases=rows,provider_calls_unchanged=77,budget=b))
    print('PASS: actual HTTP server restart restored',len(rows),'cases with exact drafts/events/tasks/messages/receipts; calls77')
