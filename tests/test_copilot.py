"""Offline P4.5 acceptance: authored scenarios are not model quality scores."""
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from src.application.copilot_demo import SCENARIOS, FOLLOWUP, FOLLOWUP_SUBJECT, example, CopilotFake
from src.application.mail_threads import MailThreads
from src.application.product_workflow import ProductStore, Conflict
from src.application.product_analysis import ProductAnalysis
from src.application.analysis_service import AnalysisService
from src.application.copilot_statistics import summarize
from src.infrastructure.repository import Repository
from src.domain.contracts import digest


class CopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.repo = Repository(Path(self.temp.name) / 'analysis.sqlite3')
        self.threads = MailThreads(self.db)

    def case(self, n):
        e, _ = example(SCENARIOS[n])
        return ProductAnalysis(AnalysisService(self.repo, CopilotFake(e, SCENARIOS[n])), self.db).submit(e)

    def act(self, c, action, **kwargs):
        return self.db.act(c['case_id'], action, expected_revision=c['revision'], actor='offline_acceptance', actor_type='demo_test',
            reason='P45 offline test; not human semantic scoring', checks=dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True),
            operation_id=str(uuid4()), **kwargs)

    def sent(self, c):
        return self.act(self.act(c, 'approve'), 'simulate_send')

    def test_scenario_contracts_and_business_boundaries(self):
        cases = [self.case(n) for n in range(9)]
        self.assertEqual([c['accepted'] for c in cases], [True]*4 + [False, False] + [True]*3)
        inquiry, multi, safety, _, _, _, unknown, rain, unsafe = cases
        self.assertEqual(inquiry['analysis']['complaint_status'], 'no_complaint')
        self.assertIn('official specifications', inquiry['draft']['body'])
        self.assertEqual(len(multi['analysis']['issues']), 3)
        for word in ('drawer', 'collection', 'invoice'): self.assertIn(word, multi['draft']['body'])
        self.assertEqual(safety['analysis']['issues'][0]['risk_level'], 'severe')
        self.assertEqual(safety['analysis']['urgency'], 'high')
        self.assertEqual(rain['analysis']['issues'][0]['reason'], 'other')
        self.assertEqual(rain['analysis']['issues'][0]['business_process'], 'delivery/logistics issue')
        self.assertEqual(unknown['analysis']['sentiment'], 'unknown')
        self.assertTrue(any(f['code'] == 'potential_injury_downgrade' for f in unsafe['quality']['findings']))
        edited = self.act(unsafe, 'save_edit', body='Please do not ride the bicycle. A qualified safety assessment is needed.')
        with self.assertRaises(Conflict): self.act(edited, 'approve')
        with self.assertRaises(Conflict): self.threads.follow_up(edited['case_id'], 'Follow-up', FOLLOWUP)

    def test_modified_fixture_cannot_claim_authored_identity(self):
        e, _ = example(SCENARIOS[0])
        with self.assertRaises(ValueError): CopilotFake(e.model_copy(update={'body': 'This camera is broken.'}), SCENARIOS[0])

    def test_changed_followup_subject_is_unknown_and_foreign_db_refused(self):
        parent = self.sent(self.case(0))
        child = self.threads.follow_up(parent['case_id'], 'The camera caught fire', FOLLOWUP)
        self.assertEqual(child['analysis']['sentiment'], 'unknown')
        other = ProductStore(Path(self.temp.name) / 'other.sqlite3')
        path = other.path.with_name('other-threads.sqlite3')
        with closing(sqlite3.connect(path)) as conn:
            with conn:
                conn.execute('CREATE TABLE unrelated(value TEXT)')
        before = path.read_bytes()
        with self.assertRaises(Conflict): MailThreads(other)
        self.assertEqual(path.read_bytes(), before)

    def test_thread_rejects_corrupted_link_identity(self):
        parent = self.sent(self.case(0))
        child = self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)
        # Test an externally altered sidecar, without touching production data.
        with self.threads.connect() as conn:
            conn.execute('DROP TRIGGER immutable_links_update')
            conn.execute("UPDATE thread_links SET parent_receipt_hash='wrong'")
        with self.assertRaises(Conflict): self.threads.messages(child['case_id'])

    def test_thread_context_immutability_idempotency_and_restart(self):
        parent = self.case(0)
        with self.assertRaises(Conflict): self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)
        parent = self.sent(parent)
        before = self.db.get(parent['case_id'])
        child = self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)
        self.assertEqual(child['state'], 'pending_review')
        self.assertEqual(self.db.get(parent['case_id']), before)
        self.assertEqual(child['analysis']['complaint_status'], 'no_complaint')
        self.assertIn('DemoCam C200', child['draft']['body'])
        self.assertIn('cannot confirm', child['draft']['body'])
        self.assertNotIn('Which camera model', child['draft']['body'])
        self.assertEqual(self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)['case_id'], child['case_id'])
        with self.assertRaises(Conflict): self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, 'Different input')
        reopened = MailThreads(ProductStore(self.db.path))
        messages = reopened.messages(child['case_id'])
        self.assertEqual([m['role'] for m in messages], ['customer', 'assistant_simulation', 'customer'])
        self.assertEqual(messages[1]['body'], parent['receipt']['body'])
        self.assertEqual(child['run'].config.parameters['context_hash'], digest(reopened.link(child['case_id'])['context']))
        self.assertIn(parent['receipt']['body'], child['run'].email.body)
        for e in child['analysis']['issues'][0]['evidence']:
            self.assertEqual(child['run'].email.body[e['start']:e['end']], FOLLOWUP)
        with reopened.connect() as conn:
            with self.assertRaises(sqlite3.IntegrityError): conn.execute('UPDATE thread_links SET current_json=?', ('{}',))
            with self.assertRaises(sqlite3.IntegrityError): conn.execute('DELETE FROM thread_links')
        # Third turn preserves outgoing edited text, rather than old fixture text.
        child = self.act(child, 'save_edit', body='Thank you. The official specifications still need verification for DemoCam C200.')
        child = self.sent(child)
        third = reopened.follow_up(child['case_id'], 'Re: additional context', 'Here is another question about the adapter.')
        self.assertEqual(third['analysis']['sentiment'], 'unknown')
        self.assertEqual(len(reopened.messages(third['case_id'])), 5)
        self.assertEqual(reopened.messages(third['case_id'])[-2]['body'], child['receipt']['body'])

    def test_link_failure_retry_reuses_analysis_and_product(self):
        parent = self.sent(self.case(0))
        original = self.threads.connect
        count = 0
        def fail_last():
            nonlocal count
            count += 1
            if count == 3: raise OSError('link unavailable')
            return original()
        with patch.object(self.threads, 'connect', side_effect=fail_last):
            with self.assertRaises(OSError): self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)
        self.assertEqual(len(self.db.list_cases()), 2)
        child = self.threads.follow_up(parent['case_id'], FOLLOWUP_SUBJECT, FOLLOWUP)
        self.assertEqual(len(self.db.list_cases()), 2)
        self.assertEqual(self.threads.child(parent['case_id']), child['case_id'])

    def test_statistics_deduplicate_and_preserve_unknown(self):
        multi, unknown, failed, unsafe = [self.case(n) for n in (1, 6, 4, 8)]
        rows = summarize([multi, unknown, failed, unsafe], '情绪')
        self.assertEqual({r['name']: r['total'] for r in rows}, {'negative': 1, 'unknown': 1})
        self.assertEqual(next(r for r in rows if r['name'] == 'negative')['complaints'], 1)
        self.assertEqual(sum(r['total'] for r in summarize([multi], '日期')), 1)
        for dimension in ('日期', '门店'):
            self.assertEqual(sum(r['unresolved'] for r in summarize([multi], dimension)), 1)


class CopilotUITests(unittest.TestCase):
    def test_dashboard_member_identity_after_new_cohort_and_filter(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, COMPLAINT_PRODUCT_DB=str(Path(d)/'product.sqlite3'), COMPLAINT_DB_PATH=str(Path(d)/'legacy.sqlite3')):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=45).run()
            app.button(key='p4_analyze').click().run()
            first = app.session_state['p4_case']
            cohort = app.selectbox(key='business_cohort').value
            app.selectbox(key='p4_scenario').set_value(SCENARIOS[8]).run()
            app.button(key='p4_analyze').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key='business_cohort').value, cohort)
            member = next(s for s in app.selectbox if s.key and s.key.startswith('business_member_'))
            self.assertEqual(member.value.split(':')[0], first)
            self.assertIn('相机是否支持有线连接', member.options[0])
            current = ProductStore(Path(d)/'product.sqlite3').get(app.session_state['p4_case'])
            app.selectbox(key='business_cohort').set_value('offline_fake:' + current['run'].cohort_id).run()
            app.selectbox(key='business_state').set_value('需人工介入').run()
            member = next(s for s in app.selectbox if s.key and s.key.startswith('business_member_'))
            self.assertIn('折叠车锁扣脱开', member.options[0])
            self.assertFalse(app.exception)

    def test_preview_custom_mail_thread_and_navigation(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, COMPLAINT_PRODUCT_DB=str(Path(d)/'product.sqlite3'), COMPLAINT_DB_PATH=str(Path(d)/'legacy.sqlite3')):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=45).run()
            self.assertFalse(app.exception)
            self.assertEqual([t.label for t in app.tabs][:3], ['智能接待', '业务分析', '研究与开发者工具'])
            self.assertTrue(any('official specifications' in t.value for t in app.text))
            app.button(key='p4_analyze').click().run()
            db = ProductStore(Path(d)/'product.sqlite3')
            c = db.get(app.session_state['p4_case'])
            for key in ('facts', 'authority', 'issues'): app.checkbox(key=f"p4_{key}_{c['case_id']}_1").check()
            app.text_area(key=f"p4_reason_{c['case_id']}").set_value('Offline acceptance only')
            app.button(key='p4_approve').click().run()
            app.button(key='p4_simulate_send').click().run()
            app.button(key='thread_submit').click().run()
            self.assertFalse(app.exception)
            child = db.get(app.session_state['p4_case'])
            self.assertEqual(child['state'], 'pending_review')
            self.assertIn('DemoCam C200', child['draft']['body'])
            app.selectbox(key='p4_scenario').set_value(SCENARIOS[6]).run()
            app.text_input(key='p4_subject').set_value('产品咨询')
            app.text_area(key='p4_body').set_value('这个设备支持有线连接吗？')
            app.button(key='p4_analyze').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('unknown流程占位' in c.value for c in app.caption))
            case_id = app.session_state['p4_case']
            app.button(key='p4_analyze').click().run()
            self.assertEqual(app.session_state['p4_case'], case_id)
