"""Explicit offline fixtures for inbox import/review/error retention."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.app.p5b8_api import create
from src.application.p5b8_pipeline import execute
from src.domain.contracts import EmailInput
def fixture(path,failed=False):
    e=EmailInput(email_id='FIXTURE-001',subject='保修咨询',body='耳机不亮，请核实维修。')
    a=dict(version='p5b8-calibration-1',expressed_sentiment='neutral',expressed_evidence=[],experience_polarity='negative',complaint_intent='yes',complaint_evidence=['请核实维修'],urgency='medium',urgency_evidence=[],mentioned_store=None,issues=[dict(issue_id='I1',object_type='product',object_name='耳机',category='Electronics',sentiment='neutral',experience_polarity='negative',issue_kind='complaint',business_process='product issue',customer_requests=['核实维修'],evidence=['耳机不亮'],risk='none',urgency='medium',resolution='unresolved')],uncertainty=[])
    runtime=execute(e,[dict(kind='aftersales_request',issue_ids=['I1'],goal='核实维修',evidence=['耳机不亮'],priority='normal')],path/'actions.sqlite3')
    reply='已登记内部售后核实请求，具体维修条件仍需核实。';call=dict(run_id='fixture-real-transport-shape-not-api',raw=json.dumps(dict(reply=reply),ensure_ascii=False),elapsed_ms=1,metadata=dict(dispatch_at='2026-10-31T00:00:00+00:00'))
    return dict(case_id=e.email_id,email=e.model_dump(),dataset_role='OFFLINE_FIXTURE',annotation_status='NOT_GOLD',analysis=dict(data=None if failed else a,error='Fixture analysis rejected' if failed else None,call=dict(run_id='analysis-fixture')),replies=dict(A_GUIDED=dict(reply=reply,error=None,call=call,runtime=runtime)))
class ProductTests(unittest.TestCase):
    def test_import_idempotent_prepare_review_simulate_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('<p>fixture</p>');cse=fixture(root);db=root/'product.sqlite3'
            with patch('src.app.p5b8_api.cases',return_value=[cse]),TestClient(create(db,root/'web')) as c:
                h={'x-p5-token':c.get('/api/session').json()['token']};body=dict(identity='P5B8_SAVED_REAL_CHAIN')
                r=c.post('/api/b8/import',json=body,headers=h);self.assertEqual(r.status_code,200,r.text);cid=r.json()['case_ids'][0]
                self.assertEqual(c.post('/api/b8/import',json=body,headers=h).json()['case_ids'],[cid])
                d=c.get('/api/p5b5r2/cases/'+cid).json();n=len(d['local_events'])
                r=c.post('/api/p5b5r2/cases/'+cid+'/prepare',json=dict(revision=d['revision']),headers=h);self.assertEqual(r.status_code,200,r.text);self.assertEqual(n,len(r.json()['local_events']))
                for action in ('approve','simulate_send'):
                    d=c.get('/api/p5b5r2/cases/'+cid).json()
                    r=c.post('/api/cases/'+cid+'/actions',json=dict(action=action,revision=d['revision'],operation_id='fixture-'+action,checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True),reason='Offline demo_test only'),headers=h)
                    self.assertEqual(r.status_code,200,r.text)
            with TestClient(create(db,root/'web')) as c:self.assertEqual(c.get('/api/p5b5r2/cases/'+cid).json()['state'],'simulated_sent')
    def test_failed_analysis_imports_without_draft_or_action_waiver(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('<p>fixture</p>');cse=fixture(root,True)
            with patch('src.app.p5b8_api.cases',return_value=[cse]),TestClient(create(root/'product.sqlite3',root/'web')) as c:
                h={'x-p5-token':c.get('/api/session').json()['token']};r=c.post('/api/b8/import',json=dict(identity='P5B8_SAVED_REAL_CHAIN'),headers=h);self.assertEqual(r.status_code,200,r.text)
                cid=r.json()['case_ids'][0];d=c.get('/api/p5b5r2/cases/'+cid).json();self.assertEqual(d['state'],'analysis_failed');self.assertIsNone(d['draft'])
                self.assertEqual(c.post('/api/p5b5r2/cases/'+cid+'/prepare',json=dict(revision=d['revision']),headers=h).status_code,409)
    def test_new_receipt_predicates_and_safe_negation(self):
        from src.application.p5b8_guard import inspect
        e=EmailInput(email_id='fixture',subject='',body='请核实会员方案。');empty=dict(events=[])
        for text in ['我已经在内部提交了查询请求。','我已经将您的查询请求提交给相关同事进一步核实。','I have opened your case.']:
            self.assertTrue(inspect(e,text,empty)['hard_findings'],text)
        self.assertFalse(inspect(e,'尚未提交查询请求，下一步可以核实。',empty)['hard_findings'])
    def test_independent_hazard_cannot_be_waived_by_safe_reply(self):
        from src.application.p5b8_product import make_run,stored,quality
        with tempfile.TemporaryDirectory() as folder:
            c=fixture(Path(folder));text='折叠车车架锁扣失效，差点摔倒。';c['email']['body']=text
            a=c['analysis']['data'];a['complaint_evidence']=[text];i=a['issues'][0];i.update(object_name='折叠车',evidence=[text],risk='none',urgency='medium')
            reply='请不要再试骑，先暂停骑行，等待售后核实。';c['replies']['A_GUIDED']['reply']=reply;c['replies']['A_GUIDED']['call']['raw']=json.dumps(dict(reply=reply),ensure_ascii=False)
            run=make_run(c);q=quality(run,stored(run),reply,True)
            self.assertIn('potential_injury_downgrade',{f['code'] for f in q['findings']});self.assertTrue(q['safety_review_required'])
            i.update(risk='severe',urgency='high');run=make_run(c);q=quality(run,stored(run),reply,True)
            self.assertNotIn('dangerous_reproduction',{f['code'] for f in q['findings']});self.assertNotIn('potential_injury_downgrade',{f['code'] for f in q['findings']})
if __name__=='__main__':unittest.main()
