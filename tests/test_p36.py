"""Offline authorization and evaluation regressions. No local research inputs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.infrastructure.p36_budget import DevelopmentBudget
from src.infrastructure.deepseek import DeepSeekAnalyzer, LiveSettings, LiveError
from src.application.v3_demo import DEMO_EMAIL, demo_result
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.evaluation.p36_report import development_comparison, diagnose_attempt, percentile
from src.evaluation.e2e_v3 import SEVEN


class P36Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.a=DeepSeekAnalyzer(LiveSettings('fixture',True,max_attempts=1),prompt_profile='multi-issue-v3')
        self.b=DevelopmentBudget.create(self.root/'budget.sqlite3',[DEMO_EMAIL.input_hash],
            {'authorization':'P3.6-40-requests-15-CNY-fictional-development-only'})
        self.b.register(self.a.config,'fixture-experiment')
    def tearDown(self):self.tmp.cleanup()

    def test_bound_config_whitelist_exclusive_create(self):
        self.b.verify_config(self.a.config)
        with self.assertRaises(LiveError):self.b.verify_config(self.a.config.model_copy(update={'prompt_hash':'wrong'}))
        with self.assertRaises(LiveError):self.b.acquire('x','not-allowed')
        with self.assertRaises(FileExistsError):DevelopmentBudget.create(self.b.path,[],{'authorization':'P3.6-40-requests-15-CNY-fictional-development-only'})
        self.assertEqual(self.b.summary()['reserved_attempts'],0)

    def test_40_including_failed_and_restart_cannot_reset(self):
        for i in range(40):
            rid=str(i);self.b.acquire(rid,DEMO_EMAIL.input_hash)
            self.b.reserve(rid,1,DEMO_EMAIL.input_hash,[],2000);self.b.release(rid)
        b=DevelopmentBudget(self.b.path)
        self.assertEqual(b.summary()['reserved_attempts'],40)
        self.assertEqual(b.summary()['halted'],'authorization_limit')
        with self.assertRaises(LiveError):b.acquire('41',DEMO_EMAIL.input_hash)

    def test_money_limit_halts_without_another_reservation(self):
        self.b.acquire('x',DEMO_EMAIL.input_hash)
        with self.b.connection() as c:
            c.execute("INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES('old',1,?,14.999,'fixture')",(DEMO_EMAIL.input_hash,))
        with self.assertRaises(LiveError):self.b.reserve('x',1,DEMO_EMAIL.input_hash,[],2000)
        self.assertEqual(self.b.summary()['reserved_attempts'],1)
        self.assertEqual(self.b.summary()['halted'],'authorization_limit')

    def test_unknown_dispatch_blocks_new_process(self):
        self.b.acquire('unknown',DEMO_EMAIL.input_hash)
        self.b.reserve('unknown',1,DEMO_EMAIL.input_hash,[],2000)
        b=DevelopmentBudget(self.b.path)
        with self.assertRaises(LiveError):b.acquire('second',DEMO_EMAIL.input_hash)
        self.assertEqual(b.summary()['pending_dispatches'],1)

    def test_real_service_path_fake_explicit_and_span_diagnostic(self):
        async def provider(*args):return demo_result().model_dump_json(),dict(input_tokens=100,output_tokens=100,total_tokens=200)
        self.a.provider=provider
        service=AnalysisService(Repository(self.root/'runs.sqlite3'),self.a,budget=self.b)
        r=service.analyze(DEMO_EMAIL)
        self.assertEqual(r.status,'succeeded')
        d=diagnose_attempt(r.attempts[0],DEMO_EMAIL)
        self.assertEqual(d['exact_spans']['valid'],d['exact_spans']['denominator'])
        data=[dict(email=DEMO_EMAIL.model_dump(),input_hash=DEMO_EMAIL.input_hash,expected={k:getattr(r.result,k) for k in SEVEN},reference_hash='fixture',exclude_clean=False)]
        self.assertEqual(development_comparison(data,[r])['all24']['field_correct'],7)
        missing=development_comparison(data,[])['all24']
        self.assertEqual((missing['field_correct'],missing['field_denominator'],missing['missing_prediction']),(0,7,1))
        self.assertEqual(service.analyze(DEMO_EMAIL).run_id,r.run_id)
        self.assertEqual(self.b.summary()['reserved_attempts'],1)

    def test_latency_small_sample(self):
        self.assertIsNone(percentile([],.95));self.assertEqual(percentile([5],.95),5)
        self.assertAlmostEqual(percentile([1,3],.95),2.9)

    def test_catalog_exact_unicode_and_immutable_old_prompt(self):
        from src.application.v3_pilot_prompt import catalog, messages, PROMPT_HASH
        from src.application.v3_prompt import PROMPT_HASH as old
        from src.domain.contracts import EmailInput
        e=EmailInput(email_id='unicode',subject='提问？',body='  烟已停。Both matter equally!\nSecond issue; last clause')
        entries=catalog(e)
        self.assertGreaterEqual(len(entries),5)
        for ev in entries:self.assertEqual(getattr(e,ev['field'])[ev['start']:ev['end']],ev['quote'])
        self.assertNotEqual(PROMPT_HASH,old)
        self.assertIn('evidence_catalog',messages(e)[1][1])

    def test_real_bad_case_executed_action_gate(self):
        from src.application.v3_safety import check_reply
        for text in ('我们已将您的问题记录并转交相关团队进行调查。','We have logged your case.'):
            with self.assertRaises(ValueError):check_reply(demo_result().model_copy(update={'suggested_reply':text}))
        for text in ('请提供订单信息，以便核实。','We can suggest checking the order record.'):
            check_reply(demo_result().model_copy(update={'suggested_reply':text}))

    def test_negation_does_not_become_unverified_commitment(self):
        from src.application.v3_safety import check_reply
        for text in ('我们无法保证明天付款。','We cannot guarantee payment tomorrow.','我们不能保证明天退款。'):
            check_reply(demo_result().model_copy(update={'suggested_reply':text}))
        for text in ('我们保证明天付款。','We guarantee payment tomorrow.',
                     '我们无法保证明天退款，但保证明天付款。','We cannot guarantee payment, but we guarantee payment tomorrow.'):
            with self.assertRaises(ValueError):check_reply(demo_result().model_copy(update={'suggested_reply':text}))

    def test_pilot_output_limit_does_not_expand_p2(self):
        from src.infrastructure.v3_live_settings import V3PilotSettings
        with self.assertRaises(LiveError):LiveSettings('fixture',True,max_tokens=4000).validate()
        V3PilotSettings('fixture',True,max_tokens=4000).validate()
        with self.assertRaises(LiveError):V3PilotSettings('fixture',True,max_tokens=6001).validate()

    def test_actual_ui_opt_in_submit_reopen_and_pending_review(self):
        from streamlit.testing.v1 import AppTest
        import os
        space=self.root/'.local/p36';exp=space/'fixture'
        exp.mkdir(parents=True)
        (exp/'manifest.json').write_text(json.dumps(dict(config=self.a.config.model_dump())),encoding='utf8')
        (space/'inputs-v1.json').write_text(json.dumps(dict(inputs=[dict(input_hash=DEMO_EMAIL.input_hash,
            email=DEMO_EMAIL.model_dump(),expected=None)])),encoding='utf8')
        b=DevelopmentBudget.create(space/'budget.sqlite3',[DEMO_EMAIL.input_hash],
            {'authorization':'P3.6-40-requests-15-CNY-fictional-development-only'})
        b.register(self.a.config,'ui-fixture')
        calls=[]
        async def provider(*args):
            calls.append(1);return demo_result().model_dump_json(),dict(input_tokens=10,output_tokens=20,total_tokens=30)
        self.a.provider=provider
        service=AnalysisService(Repository(exp/'runs.sqlite3'),self.a,budget=b)
        source=f"from pathlib import Path\nfrom src.app.v3_view import render_v3_live\nrender_v3_live(Path({str(self.root.as_posix())!r}))"
        with patch.dict(os.environ,{'COMPLAINT_ENABLE_LIVE':'true','COMPLAINT_P36_EXPERIMENT':'fixture'}),patch('scripts.p36.frozen_service',return_value=service):
            app=AppTest.from_string(source,default_timeout=30).run()
            self.assertFalse(app.exception);self.assertFalse(app.checkbox(key='p36_enable').value)
            self.assertTrue(app.button(key='p36_analyze').disabled);self.assertEqual(calls,[])
            app.text_input(key='p36_email_id').set_value(DEMO_EMAIL.email_id)
            app.text_input(key='p36_subject').set_value(DEMO_EMAIL.subject)
            app.text_area(key='p36_body').set_value(DEMO_EMAIL.body)
            app.checkbox(key='p36_enable').set_value(True).run()
            self.assertFalse(app.button(key='p36_analyze').disabled);self.assertEqual(calls,[])
            app.button(key='p36_analyze').click().run();self.assertFalse(app.exception)
            self.assertEqual(len(calls),1)
            app.button(key='p36_analyze').click().run();self.assertEqual(len(calls),1)
            run=service.repository.list_runs()[0]
            fresh=AppTest.from_string(source,default_timeout=30).run()
            fresh.text_input(key='p36_lookup').set_value(run.run_id)
            fresh.button(key='p36_load').click().run()
            self.assertFalse(fresh.exception);self.assertEqual(len(calls),1)
            self.assertTrue(any('Unreviewed reply' in w.value for w in fresh.warning))
            self.assertEqual(len(fresh.get('download_button')),1)
