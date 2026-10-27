"""Actual app.py AppTest journeys. Browser testing is recorded separately."""
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from src.application.product_demo import SCENARIOS
from src.application.product_workflow import ProductStore

ROOT = Path(__file__).resolve().parents[1]


class ProductUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / 'product.sqlite3'
        env = patch.dict(os.environ, COMPLAINT_PRODUCT_DB=str(self.db_path), COMPLAINT_DB_PATH=str(Path(self.temp.name) / 'legacy.sqlite3'), COMPLAINT_ENABLE_LIVE='true')
        env.start()
        self.addCleanup(env.stop)

    def app(self):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=45).run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(os.environ['COMPLAINT_ENABLE_LIVE'], 'false')
        return app

    def current(self, app):
        return ProductStore(self.db_path).get(app.session_state['p4_case'])

    def analyze(self, app, scenario=0):
        if app.selectbox(key='p4_scenario').value != SCENARIOS[scenario]:
            app.selectbox(key='p4_scenario').set_value(SCENARIOS[scenario]).run()
        app.button(key='p4_analyze').click().run()
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertEqual(app.selectbox(key='p4_history').value.split(':')[0], self.current(app)['case_id'])
        return self.current(app)

    def approve(self, app):
        c = self.current(app)
        for key in ('facts', 'authority', 'issues'):
            app.checkbox(key=f"p4_{key}_{c['case_id']}_{c['current_version']}").check()
        if c['quality']['safety_review_required']:
            app.checkbox(key=f"p4_safety_{c['case_id']}_{c['current_version']}").check()
        app.text_area(key=f"p4_reason_{c['case_id']}").set_value('Automated UI acceptance; not an independent human quality score.')
        app.button(key='p4_approve').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.current(app)['state'], 'approved')

    def test_inquiry_full_ui_send_reopen_new_session_dashboard(self):
        app = self.app(); c = self.analyze(app)
        self.assertTrue(app.button(key='p4_simulate_send').disabled)
        self.assertTrue(any('Evidence' in e.label for e in app.expander))
        self.approve(app)
        app.button(key='p4_simulate_send').click().run()
        self.assertEqual(self.current(app)['state'], 'simulated_sent')
        fresh = self.app()
        fresh.selectbox(key='p4_history').set_value(c['case_id'] + ':2')
        fresh.button(key='p4_open').click().run()
        self.assertTrue(any('模拟发送已完成' in x.value for x in fresh.success))
        self.assertTrue(fresh.button(key='p4_save_edit').disabled)
        self.assertTrue(any('审核状态' in json.loads(m.value) for m in fresh.json))

    def test_edit_return_save_approve_new_version_and_simulate(self):
        app = self.app(); c = self.analyze(app, 3)
        self.assertTrue(app.button(key='p4_approve').disabled)
        app.text_area(key=f"p4_reason_{c['case_id']}").set_value('Remove unsupported follow-up promise.')
        app.button(key='p4_request_changes').click().run()
        self.assertEqual(self.current(app)['state'], 'changes_requested')
        reply_key = f"p4_reply_{c['case_id']}_1"
        app.text_area(key=reply_key).set_value('Thank you for describing the lamp problem. Please share the model to help identify available support options.')
        app.button(key='p4_save_edit').click().run()
        self.assertEqual(self.current(app)['current_version'], 2)
        self.assertTrue(any('v1' in t.value and 'v2' in t.value for t in app.code))
        self.approve(app)
        # A browser rerun after editing must disable send while text is dirty.
        app.text_area(key=f"p4_reply_{c['case_id']}_2").set_value('An unsaved new reply.').run()
        self.assertTrue(app.button(key='p4_simulate_send').disabled)
        app.text_area(key=f"p4_reply_{c['case_id']}_2").set_value(self.current(app)['draft']['body']).run()
        app.button(key='p4_simulate_send').click().run()
        self.assertEqual(self.current(app)['receipt']['version'], 2)

    def test_multi_and_severe_safety_review_actual_widgets(self):
        app = self.app(); c = self.analyze(app, 1)
        self.assertEqual(len(c['analysis']['issues']), 3)
        self.approve(app)
        app.button(key='p4_simulate_send').click().run()
        c = self.analyze(app, 2)
        self.assertTrue(c['quality']['safety_review_required'])
        self.approve(app)
        app.button(key='p4_simulate_send').click().run()
        self.assertEqual(self.current(app)['state'], 'simulated_sent')

    def test_contract_failure_and_reject_actual_ui(self):
        app = self.app(); c = self.analyze(app, 4)
        self.assertIsNone(c['draft'])
        self.assertFalse(any(b.key == 'p4_approve' for b in app.button))
        c = self.analyze(app, 0)
        app.text_area(key=f"p4_reason_{c['case_id']}").set_value('Reject this demo draft for manual investigation.')
        app.button(key='p4_reject').click().run()
        self.assertEqual(self.current(app)['state'], 'rejected')
        self.assertTrue(app.button(key='p4_simulate_send').disabled)
        self.assertTrue(app.button(key='p4_approve').disabled)

    def test_local_real_unsafe_replay_ui_block_preserves_original(self):
        if not (ROOT / '.local/p310/FINAL_REVIEW_V2/content-review.json').exists():
            self.skipTest('Private real-model replay source unavailable')
        app = self.app()
        app.radio(key='p4_mode').set_value('真实历史run / 只读重放').run()
        item = next(i for i in app.selectbox(key='p4_source_run').options if '86d85387-9dcc-49be-80a1-0ac55019af65' in i)
        # AppTest options are formatted labels; actual value is the source dictionary.
        from src.application.product_sources import catalog
        source = next(i for i in catalog(ROOT) if i['run_id'] == '86d85387-9dcc-49be-80a1-0ac55019af65')
        app.selectbox(key='p4_source_run').set_value(source).run()
        app.button(key='p4_replay').click().run()
        self.assertFalse(app.exception)
        c = self.current(app)
        self.assertEqual(c['source_kind'], 'real_replay')
        self.assertTrue(c['accepted'])
        self.assertTrue(app.button(key='p4_approve').disabled)
        self.assertTrue(app.button(key='p4_simulate_send').disabled)
