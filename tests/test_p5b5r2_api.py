"""Explicit offline fake driver; no API key, network, or historical DB writes."""
import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from src.app.p5b5r2_api import create

class Driver:
    def __init__(self):self.calls=[]
    def status_ui(self):return dict(enabled=True,remaining_requests=300,remaining_cny=10,halted=None)
    def generate_ui(self,subject,body,operation_id):
        self.calls.append((subject,body,operation_id))
        raise RuntimeError('UNKNOWN synthetic timeout')

class FollowupDriver(Driver):
    def __init__(self,path,unknown=False):super().__init__();self.path=path;self.unknown=unknown
    def generate_followup_ui(self,parent_run,body,operation_id,*,context_messages,subject):
        self.calls.append(operation_id)
        if self.unknown:raise RuntimeError('UNKNOWN')
        from src.application.mail_threads import assemble_context
        from src.application.copilot_demo import CopilotFake,SCENARIOS
        from src.application.analysis_service import AnalysisService
        from src.application.v31_demo import pipeline_probe
        from src.infrastructure.repository import Repository
        from src.domain.contracts import EmailInput,digest
        email=EmailInput(email_id=operation_id,subject=subject,body=assemble_context(context_messages,subject,body))
        analyzer=CopilotFake(email,SCENARIOS[6],context_hash=digest(context_messages),data=pipeline_probe(email).model_dump())
        return AnalysisService(Repository(self.path/'fake-analysis.sqlite3'),analyzer).analyze(email)

class R2APITest(unittest.TestCase):
    def parent(self,client):
        from src.application.product_demo import SCENARIOS,ProductFake,example
        from src.application.analysis_service import AnalysisService
        from src.infrastructure.repository import Repository
        h={'x-p5-token':client.get('/api/session').json()['token']}
        email,_=example(SCENARIOS[6]);email=email.model_copy(update=dict(body='C200的USB接口能否连接电脑？'));store=client.app.state.store
        run=AnalysisService(Repository(store.path.with_name('fixture-parent-analysis.sqlite3')),ProductFake(email,SCENARIOS[6])).analyze(email)
        created=store.create(run);c=client.get('/api/cases/'+created['case_id']).json()
        checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True)
        for action in ('approve','simulate_send'):
            r=client.post('/api/cases/'+c['case_id']+'/actions',json=dict(action=action,revision=c['revision'],operation_id='fixture-'+action,checks=checks,reason='offline UI fixture, not human rating'),headers=h)
            self.assertEqual(r.status_code,200,r.text);c=r.json()
        return c,h

    def test_new_live_route_requires_csrf_and_explicit_source(self):
        with tempfile.TemporaryDirectory() as t:
            d=Driver()
            with TestClient(create(Path(t)/'product.sqlite3',live_driver=d)) as c:
                p=dict(subject='合成试验',body='请查物流',operation_id='operation-fixture',synthetic_confirmed=True)
                self.assertEqual(c.post('/api/p5b5r2/live',json=p).status_code,403)
                h={'x-p5-token':c.get('/api/session').json()['token']}
                self.assertEqual(c.post('/api/p5b5r2/live',json=dict(p,synthetic_confirmed=False),headers=h).status_code,422)
                self.assertEqual(d.calls,[])
                self.assertTrue(c.get('/api/p5b5r2/live/status').json()['enabled'])
                # The one requested attempt fails: no internal retry or new identity.
                r=c.post('/api/p5b5r2/live',json=p,headers=h)
                self.assertEqual(r.status_code,409);self.assertEqual(len(d.calls),1)
                self.assertEqual(d.calls[0][2],'operation-fixture')
                self.assertEqual(r.json()['code'],'dispatch_unconfirmed')
                # The inherited historical paid route remains closed.
                self.assertEqual(c.post('/api/live',json={k:v for k,v in p.items() if k!='operation_id'},headers=h).status_code,422)

    def test_review_is_hash_bound_append_only_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);package=root/'package.json';package.write_text(json.dumps(dict(items=[dict(id='review-fixture',source='SYNTHETIC_DEV')],human_signed=False)),encoding='utf-8')
            db=root/'product.sqlite3'
            with TestClient(create(db,live_driver=Driver(),review_package=package)) as c:
                p=c.get('/api/p5b5r2/review').json();h={'x-p5-token':c.get('/api/session').json()['token']}
                body=dict(item_id='review-fixture',decision='unable',reviewer='offline_test_not_human',comment='fixture only',package_hash=p['package_hash'],operation_id='review-operation-fixture')
                self.assertEqual(c.post('/api/p5b5r2/review',json=dict(body,package_hash='0'*64),headers=h).status_code,409)
                r=c.post('/api/p5b5r2/review',json=body,headers=h)
                self.assertEqual(r.status_code,200);self.assertEqual(c.post('/api/p5b5r2/review',json=body,headers=h).json(),r.json())
                self.assertEqual(len(c.get('/api/p5b5r2/review').json()['decisions']),1)
            with TestClient(create(db,live_driver=Driver(),review_package=package)) as c:
                saved=c.get('/api/p5b5r2/review').json();self.assertEqual(saved['decisions'][0]['decision'],'unable')
                self.assertFalse(saved['human_signed']);self.assertEqual(len(saved['decisions']),1)

    def test_uninitialized_budget_and_absent_result_are_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            with TestClient(create(Path(t)/'product.sqlite3',evidence=Path(t)/'none.json',review_package=Path(t)/'missing-review.json',live_driver=Driver())) as c:
                # No quality endpoint call here: historical private fixtures are optional.
                self.assertEqual(c.get('/api/p5b5r2/review').json()['status'],'PREPARING')

    def test_real_followup_contract_preserves_edited_receipt_and_link_on_restart(self):
        from src.application.mail_threads import MailThreads
        from src.application.product_workflow import ProductStore
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=root/'product.sqlite3';driver=FollowupDriver(root)
            with TestClient(create(db,live_driver=driver)) as client:
                parent,h=self.parent(client)
                client.post('/api/p5b5r2/cases/'+parent['case_id']+'/prepare',json=dict(revision=parent['revision']),headers=h)
                payload=dict(subject='Re: fixture',body='The correct model is DEMO-C230. Please keep this conversation with the AI.',revision=parent['revision'],synthetic_confirmed=True,operation_id='followup-known-fixture')
                path='/api/p5b5r2/cases/'+parent['case_id']+'/followup'
                first=client.post(path,json=payload,headers=h);self.assertEqual(first.status_code,200,first.text)
                again=client.post(path,json=payload,headers=h);self.assertEqual(again.json()['case_id'],first.json()['case_id']);self.assertEqual(len(driver.calls),1)
                child_id=first.json()['case_id']
                historical=client.get('/api/p5b5r2/cases/'+parent['case_id']).json()['local_events']
                self.assertTrue(any(e['status']=='superseded' for e in historical))
                self.assertTrue(any(e.get('operational_status')=='superseded' for e in historical))
                self.assertTrue(any(e['status']=='superseded' for e in first.json()['local_events']))
            fresh=ProductStore(db);link=MailThreads(fresh).link(child_id)
            self.assertEqual(link['current']['body'],payload['body'])
            self.assertTrue(any(m['source']=='simulation_only' for m in link['context']))
            self.assertEqual(fresh.get(child_id)['run'].config.parameters['context_hash'],link['context_hash'])

    def test_unknown_followup_cannot_redispatch_even_after_restart(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);db=root/'product.sqlite3';driver=FollowupDriver(root,unknown=True)
            with TestClient(create(db,live_driver=driver)) as client:
                parent,h=self.parent(client);payload=dict(subject='Re: fixture',body='Please verify the model.',revision=parent['revision'],synthetic_confirmed=True,operation_id='followup-unknown-fixture')
                path='/api/p5b5r2/cases/'+parent['case_id']+'/followup'
                self.assertEqual(client.post(path,json=payload,headers=h).status_code,409)
            with TestClient(create(db,live_driver=driver)) as client:
                h={'x-p5-token':client.get('/api/session').json()['token']}
                self.assertEqual(client.post(path,json=payload,headers=h).json()['code'],'followup_unknown')
                self.assertEqual(len(driver.calls),1)

    def test_optional_human_scores_are_blank_scoped_and_preserve_zero(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);package=root/'package.json'
            package.write_text(json.dumps(dict(items=[dict(id='reply-fixture',score_target='R3')],human_signed=False)),encoding='utf-8')
            with TestClient(create(root/'product.sqlite3',live_driver=Driver(),review_package=package)) as c:
                p=c.get('/api/p5b5r2/review').json();h={'x-p5-token':c.get('/api/session').json()['token']}
                self.assertEqual(p['decisions'],[]);self.assertFalse(p['human_signed'])
                body=dict(item_id='reply-fixture',decision='modify',reviewer='offline_fixture_not_human',comment='temporary test only',
                    package_hash=p['package_hash'],operation_id='score-fixture-operation',score_target='R3',scores=dict(B1=0,B2=1,B3=2,B4=None,B5=None))
                self.assertEqual(c.post('/api/p5b5r2/review',json=dict(body,score_target='FINAL'),headers=h).status_code,422)
                self.assertEqual(c.post('/api/p5b5r2/review',json=dict(body,scores=dict(B1=3)),headers=h).status_code,422)
                saved=c.post('/api/p5b5r2/review',json=body,headers=h)
                self.assertEqual(saved.status_code,200,saved.text);self.assertEqual(saved.json()['scores']['B1'],0)
                self.assertIsNone(saved.json()['scores']['B4']);self.assertEqual(saved.json()['score_target'],'R3')
                self.assertFalse(c.get('/api/p5b5r2/review').json()['human_signed'])
                self.assertEqual(c.get('/api/p5b5r2/media/unregistered-file').status_code,404)

if __name__=='__main__':unittest.main()
