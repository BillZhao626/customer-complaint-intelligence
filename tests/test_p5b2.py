"""P5-B2 explicit fixtures, temporary stores, real SDK over mock HTTP only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import httpx
from src.domain.analysis_v32 import adapt,validate,stored_analysis,SCHEMA
from src.domain.contracts import EmailInput
from src.evaluation.p5b2 import Analyzer,Budget,messages
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.application.p5_quality import example
from src.application.urgency_context_v2 import signals

class P5B2Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.p=Path(self.t.name)
        self.email,self.old=example('P5A-F10-M01-2')
        self.data,_=adapt(self.old,legacy=True)
        self.data['mentioned_store']=None;self.data['store_verification']='unknown'
        self.settings=V3PilotSettings(api_key='offline-fixture',enabled=True,max_tokens=4000,max_attempts=1)
    def test_optional_store_and_legacy_are_explicit(self):
        old=copy.deepcopy(self.old);old.update(mentioned_store='',store_verification='unknown')
        converted,changes=adapt(old,legacy=True)
        self.assertIsNone(converted['mentioned_store']);self.assertEqual(old['mentioned_store'],'')
        self.assertIn('legacy_missing_store_sentinel_to_null',changes)
    def test_native_empty_store_rejected(self):
        self.data['mentioned_store']=''
        with self.assertRaises(ValueError):validate(self.data,self.email)
    def test_named_store_needs_source(self):
        self.data.update(mentioned_store='虚构门店',store_verification='mentioned_only')
        with self.assertRaisesRegex(ValueError,'source'):validate(self.data,self.email)
    def test_runtime_fields_and_conflicts(self):
        self.data.pop('policy_version');self.data.pop('reply_language')
        value,_,changes,_=validate(self.data,self.email)
        self.assertIn('runtime_policy_version',changes);self.assertEqual(value.reply_language,'zh')
        self.data['policy_version']='invented'
        with self.assertRaises(ValueError):validate(self.data,self.email)
    def test_deadline_and_negated_quoted_counterexamples(self):
        self.assertTrue(signals('礼物明天要送人')['deadline'])
        self.assertFalse(signals('礼物不是明天要送人')['deadline'])
        self.assertFalse(signals('“礼物明天要送人”是例句')['deadline'])
        self.assertFalse(signals('如果明天要送人')['deadline'])
        self.assertFalse(signals('明天是星期五')['deadline'])
    def test_report_not_verified_ticket_fact(self):
        self.assertTrue(signals('前面已经说得很清楚，还是没人看')['repeated_failure'])
        self.assertFalse(signals('前面的问题现在已解决')['repeated_failure'])
        self.assertFalse(signals('不要转人工，我不方便等')['relaxed'])
    def test_language_not_hidden_by_label(self):
        email=EmailInput(email_id='english',subject=self.email.subject,body=self.email.body+' Please reply in English.')
        with self.assertRaisesRegex(ValueError,'language'):validate(self.data,email)
    def test_forged_span_rejected(self):
        self.data['issues'][0]['evidence'][0]['start']+=1
        with self.assertRaises(ValueError):validate(self.data,self.email)
    def test_claims_guard_retained(self):
        self.data['suggested_reply']='我们已为您退款。'
        with self.assertRaises(ValueError):validate(self.data,self.email)
    def make_budget(self):
        b=Budget.create(self.p/'budget.sqlite3',[],{'pricing':dict(price_source='fixture',prices_verified_at='fixture',prices={})})
        with b.connection() as c:c.execute('CREATE TABLE stage_reservations(run_id TEXT PRIMARY KEY,stage TEXT NOT NULL)')
        return b
    def test_sdk_service_persistence_and_product(self):
        from src.application.analysis_service import AnalysisService
        from src.infrastructure.repository import Repository
        from src.application.product_workflow import ProductStore
        d=copy.deepcopy(self.data);d.pop('policy_version');d.pop('reply_language');calls=[]
        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json=dict(id='fixture',object='chat.completion',created=1,model='deepseek-flash',
                choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(d,ensure_ascii=False)))],
                usage=dict(prompt_tokens=100,completion_tokens=200,total_tokens=300)))
        a=Analyzer(self.settings,self.p/'ev',mock_http_transport=httpx.MockTransport(handle));b=self.make_budget();b.bind(self.email,a.config,'explore')
        service=AnalysisService(Repository(self.p/'runs.sqlite3'),a,budget=b);r=service.analyze(self.email)
        self.assertEqual(r.status,'succeeded',r.model_dump());stored_analysis(r)
        self.assertEqual(service.analyze(self.email).run_id,r.run_id);self.assertEqual(len(calls),1)
        case=ProductStore(self.p/'product.sqlite3').create(r,origin='new_analysis')
        self.assertEqual(case['draft']['body'],d['suggested_reply'])
        bad=r.model_copy(update={'metadata':dict(r.metadata,analysis_v32_hash='tampered')})
        with self.assertRaises(ValueError):stored_analysis(bad)
    def test_budget_limits_and_unknown(self):
        a=Analyzer(self.settings,self.p/'ev');b=self.make_budget();b.bind(self.email,a.config,'explore');b.acquire('run',self.email.input_hash)
        with b.connection() as c:
            for n in range(6):c.execute('INSERT INTO stage_reservations VALUES(?,?)',(str(n),'explore'))
        with self.assertRaises(Exception):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)
        self.assertIsNone(b.estimate_cost({}));self.assertEqual(b.summary()['halted'],'UNKNOWN_BILLING')
    def test_prompt_no_reference_answers(self):
        from src.application.p5b2_prompt import system
        self.assertNotIn('改写为“感谢您说明',system())
        self.assertNotIn('DEMO-P5035',system())
        self.assertNotIn('R04',system())

    def test_safety_prohibition_scope_and_contrast(self):
        from src.application.product_quality import dangerous_instruction
        self.assertIsNone(dangerous_instruction('不要再次上路测试锁扣。'))
        self.assertIsNone(dangerous_instruction('Do not reproduce the failure.'))
        self.assertTrue(dangerous_instruction('不要再次上路测试锁扣，但请重新试骑拍视频。'))
        self.assertTrue(dangerous_instruction('Please reproduce the failure.'))

    def test_new_budget_five_cny_is_cumulative(self):
        a=Analyzer(self.settings,self.p/'ev');b=self.make_budget();b.bind(self.email,a.config,'formal');b.acquire('run',self.email.input_hash)
        with b.connection() as c:
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',('prior',1,'other',4.999,'fixture'))
        with self.assertRaises(Exception):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)

    def test_new_budget_40_and_formal_18_hard_stops(self):
        a=Analyzer(self.settings,self.p/'ev');b=self.make_budget();b.bind(self.email,a.config,'formal');b.acquire('run',self.email.input_hash)
        with b.connection() as c:
            for n in range(40):
                c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(str(n),1,'other',.001,'fixture'))
        with self.assertRaises(Exception):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)
        with b.connection() as c:
            c.execute('DELETE FROM reservations')
            for n in range(18):c.execute('INSERT INTO stage_reservations VALUES(?,?)',(str(n),'formal'))
        with self.assertRaises(Exception):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)

    def test_new_budget_no_retry_and_exclusive_lease(self):
        a=Analyzer(self.settings,self.p/'ev');b=self.make_budget();b.bind(self.email,a.config,'explore');b.acquire('run',self.email.input_hash)
        with self.assertRaises(Exception):b.reserve('run',2,self.email.input_hash,messages(self.email),4000)
        with self.assertRaises(Exception):b.acquire('second',self.email.input_hash)

    def test_legacy_quality_version_is_unchanged(self):
        from src.application.product_quality import inspect
        q=inspect(self.email,self.old,self.old['suggested_reply'],True)
        self.assertEqual(q['version'],'product-quality-guard-v1')

if __name__=='__main__':unittest.main()
