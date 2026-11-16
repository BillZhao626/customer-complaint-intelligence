"""Offline pairwise guard regressions; synthetic fixtures, temporary journals."""
import copy, tempfile, unittest
from pathlib import Path
from src.application.p5b3_actions import TaskJournal
from src.application.p5b4_guard import lexical, receipts, inspect
from src.domain.contracts import EmailInput
from src.evaluation.p5b4 import calibration, freeze_config, preflight

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.path=Path(self.t.name)/'actions.db';self.j=TaskJournal(self.path)
        self.e=EmailInput(email_id='fixture',subject='售后',body='包裹破损，需售后核实。')
        self.j.prepare(self.e)
        self.reply='已记录内部售后请求待核实。'
    def blocked(self,text,rs=()): return any(f['severity']=='block' for f in lexical(text,rs,event_guard=True))
    def test_local_record_requires_receipt(self):
        self.assertTrue(self.blocked(self.reply))
        self.assertFalse(self.blocked(self.reply,receipts(self.path,self.e.input_hash)))
    def test_wrong_input_never_authorizes(self):
        self.assertTrue(self.blocked(self.reply,receipts(self.path,'other')))
    def test_wrong_owner_never_authorizes(self):
        j=TaskJournal(Path(self.t.name)/'bad.db')
        with j.connect() as c:
            c.execute("INSERT INTO tasks VALUES('x',?,?)",(self.e.input_hash,'{"kind":"aftersales_followup","owner":"logistics"}'))
            c.execute("INSERT INTO events VALUES('e','x','task_created','{\"status\":\"PENDING\",\"local_only\":true}','now','op')")
        self.assertEqual(receipts(j.path,self.e.input_hash),[])
    def test_terminal_or_external_claim_stays_blocked(self):
        rs=receipts(self.path,self.e.input_hash)
        for text in ['已记录内部售后请求待核实，已退款。','我们已经批准退款。','We have already sent your refund.','已记录内部售后请求待核实且已完成。']:
            with self.subTest(text=text):self.assertTrue(self.blocked(text,rs))
    def test_no_broad_record_exemption(self):
        rs=receipts(self.path,self.e.input_hash)
        for text in ['已记录售后请求。','已记录内部知识请求待核实。','已记录内部售后请求并安排退款。']:
            with self.subTest(text=text):self.assertTrue(self.blocked(text,rs))
    def test_negation_does_not_authorize_next_clause(self):
        self.assertFalse(self.blocked('我们尚未批准退款。'))
        self.assertTrue(self.blocked('我们尚未批准退款，但是我们已经批准退款。'))
    def test_attachment_report_is_not_receipt(self):
        for text,blocked in [('照片我们已经收到。',True),('We have received the photos.',True),('您提到已经发送照片。',False),('我们尚未收到照片。',False),('We have a question.',False)]:
            result=inspect(self.e,{'suggested_reply':text,'issues':[]},structured_ok=True,attachment_guard=True)
            self.assertEqual(any(f['code']=='attachment_receipt_without_manifest' for f in result['findings']),blocked,text)
    def test_safety_synonym_not_dangerous_reproduction(self):
        e=self.e.model_copy(update={'body':'电器冒烟。'})
        data={'schema_version':'analysis-v3.2','issues':[{'risk_level':'severe','urgency':'high'}],'suggested_reply':'保持断电，勿触碰。'}
        old=inspect(e,data,structured_ok=True); new=inspect(e,data,structured_ok=True,safety_synonyms=True)
        self.assertTrue(any(f['code']=='missing_stop_use_advice' for f in old['findings']))
        self.assertFalse(any(f['code']=='missing_stop_use_advice' for f in new['findings']))
        data['suggested_reply']+='重新通电测试故障。'
        self.assertTrue(any(f['code']=='dangerous_reproduction' for f in inspect(e,data,structured_ok=True,safety_synonyms=True)['findings']))
    def test_structure_rejection_cannot_be_waived(self):
        r=inspect(self.e,{'suggested_reply':self.reply,'issues':[]},structured_ok=False,journal_path=self.path,event_guard=True)
        self.assertEqual(r['status'],'blocked')
    def test_receipt_read_does_not_change_database(self):
        before=self.path.read_bytes();receipts(self.path,self.e.input_hash)
        self.assertEqual(before,self.path.read_bytes())

class HarnessTests(unittest.TestCase):
    def test_langchain_fact_boundary_and_callbacks_are_executed_offline(self):
        import json
        from src.application.p5b4_structured import offline_extract,dry_requests
        e=EmailInput(email_id='lang',subject='Question',body='I sent photos. Does C200 support USB meetings?')
        raw=dict(customer_claims=[dict(field='body',start=0,end=14,quote='I sent photos.')],unresolved_questions=['C200 USB meetings capability'])
        result=offline_extract(e,json.dumps(raw),expected_language='en')
        self.assertEqual(result['context']['verified_facts'],[])
        self.assertEqual(result['context']['expected_language'],'en')
        self.assertTrue(any(x['event']=='start' for x in result['trace']))
        with self.assertRaises(ValueError):offline_extract(e,json.dumps(raw)[:-1],expected_language='en')
        raw['verified_facts']=['photos received']
        with self.assertRaises(ValueError):offline_extract(e,json.dumps(raw),expected_language='en')
        raw.pop('verified_facts');raw['customer_claims'][0]['quote']='photos received'
        with self.assertRaises(ValueError):offline_extract(e,json.dumps(raw),expected_language='en')
        self.assertTrue(dry_requests()['strict_mode']['local_incompatibilities'])
    def test_explicit_local_preview_origin_keeps_write_token_and_external_boundary(self):
        from src.app.p5_api import create_app
        from fastapi.testclient import TestClient
        with tempfile.TemporaryDirectory() as t:
            with TestClient(create_app(Path(t)/'product.db',serve_web=False,local_origin_port=8768)) as client:
                self.assertEqual(client.get('/api/session',headers={'origin':'http://127.0.0.1:8768'}).status_code,200)
                self.assertEqual(client.get('/api/session',headers={'origin':'https://attacker.example'}).status_code,403)
                self.assertEqual(client.post('/api/demo',json={'scenario':'blocked'},headers={'origin':'http://127.0.0.1:8768'}).status_code,403)
            with self.assertRaises(ValueError): create_app(Path(t)/'other.db',local_origin_port='8768')
    def test_calibration_abstentions_and_disputes(self):
        r=calibration({'a':'PASS','b':'FAIL','c':'PASS','d':'FAIL','e':'DISPUTED'}, {'a':'FAIL','b':'PASS','c':'PASS','d':'ABSTAIN','e':'FAIL'})
        self.assertEqual((r['false_positive'],r['false_negative'],r['judge_abstained'],r['needs_human_review'],r['agreement']),(1,1,1,1,1/3))
        self.assertIsNone(calibration({}, {})['agreement'])
    def test_preflight_checks_budget_schema_and_missing_provenance(self):
        if not (Path(__file__).resolve().parents[1]/'.local/p5b3-20261029-v1').is_dir():self.skipTest('Private historical raw unavailable')
        c=freeze_config()
        for field,value in [('authorized_new_api_budget_rmb',1),('schema_hash','forged'),('max_iterations',9),('dataset_hash','forged')]:
            bad=copy.deepcopy(c);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):preflight(bad)

if __name__=='__main__':unittest.main()
