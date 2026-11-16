"""Offline API acceptance with explicit fake, temp storage and durable evidence."""
from pathlib import Path
import sys,tempfile,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.app.p5_api import create_app
from src.application.service_scenarios import SCENARIOS
from fastapi.testclient import TestClient
from src.evaluation.p5b4 import write,digest,now

def main():
    result=dict(at=now(),identity='OFFLINE_FAKE_API_E2E_DEMO_TEST_NOT_HUMAN',new_provider_calls=0,external_sends=0,checks=[])
    with tempfile.TemporaryDirectory(prefix='p5b4_e2e_') as t:
        db=Path(t)/'product.db'
        with TestClient(create_app(db,serve_web=False,local_origin_port=8768)) as client:
            headers={'x-p5-token':client.get('/api/session').json()['token']}
            def post(url,body,expected=200):
                r=client.post(url,json=body,headers=headers);assert r.status_code==expected,r.text
                return r.json()
            c=post('/api/demo',dict(scenario='p47:'+SCENARIOS[0]))
            original=c['draft']['body']; original_id=c['case_id']; initial_version=c['draft']['version']
            def act(case,action,**kw): return post('/api/cases/'+case['case_id']+'/actions',dict(action=action,revision=case['revision'],operation_id=action+'-b4',reason='Offline engineering acceptance only; actor demo_test',checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True),**kw))
            edited=act(c,'save_draft',body=original+' 如有新的问题，可在当前会话补充。')
            assert edited['draft']['version']==initial_version+1
            approved=act(edited,'approve');sent=act(approved,'simulate_send')
            assert sent['state']=='simulated_sent' and sent['receipt']['body_hash']==sent['draft']['body_hash']
            again=act(approved,'simulate_send');assert again['receipt']==sent['receipt']
            result['checks'].append(dict(case_id=original_id,edit_version=sent['draft']['version'],receipt=sent['receipt'],idempotent=True,actor_type='demo_test',state=sent['state']))
            bad=post('/api/demo',dict(scenario='blocked'))
            for action in ['approve','simulate_send']:
                post('/api/cases/'+bad['case_id']+'/actions',dict(action=action,revision=bad['revision'],operation_id='negative-'+action,reason='must reject'),409)
            post('/api/live',dict(subject='offline',body='No dispatch allowed',synthetic_confirmed=True),422)
            result['checks'].append(dict(blocked_case_id=bad['case_id'],approve_and_simulate_http=409,live_disabled_http=422))
        with TestClient(create_app(db,serve_web=False,local_origin_port=8768)) as fresh:
            restored=fresh.get('/api/cases/'+original_id).json()
            assert restored['receipt']==sent['receipt'] and restored['draft']==sent['draft']
            result['checks'].append(dict(fresh_app_restores_receipt_and_draft=True,receipt_hash=digest(restored['receipt'])))
    write(ROOT/'.local/p5b4/e2e-api-receipt.json',result)
    print('PASS: input/fake -> draft/edit -> review/demo_test -> local simulation -> new-app restore; blocked & live negative checks')

if __name__=='__main__':main()
