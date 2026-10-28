"""Explicit P4.7 journeys through the real UI; temporary offline stores only."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.application.service_scenarios import SCENARIOS, CUSTOM_SCENARIO
from src.application.product_workflow import ProductStore
from src.application.service_triage import triage

class ServiceInboxUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'product.sqlite3'
        env=patch.dict(os.environ,COMPLAINT_PRODUCT_DB=str(self.path),COMPLAINT_DB_PATH=str(Path(self.tmp.name)/'legacy.sqlite3'))
        env.start();self.addCleanup(env.stop)
        from streamlit.testing.v1 import AppTest
        self.app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45).run()
    def create(self,index=0):
        self.app.selectbox(key='p4_scenario').set_value(SCENARIOS[index]).run()
        self.app.button(key='p4_analyze').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        return ProductStore(self.path).get(self.app.session_state['p4_case'])
    def test_routine_prefill_explicit_confirmation_and_receipt_recovery(self):
        c=self.create();key=f"p4_reply_{c['case_id']}_1"
        self.assertEqual(self.app.text_area(key=key).value,c['draft']['body'])
        self.assertTrue(self.app.button(key='p47_quick_send').disabled)
        self.app.checkbox(key=f"p47_quick_check_{c['case_id']}_1").check().run()
        self.app.button(key='p47_quick_send').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        saved=ProductStore(self.path).get(c['case_id'])
        self.assertEqual(saved['state'],'simulated_sent')
        self.assertTrue(any(e['action']=='approve' and e['actor_type']=='demo_test' for e in saved['events']))
        from streamlit.testing.v1 import AppTest
        fresh=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45)
        fresh.query_params['case_id']=c['case_id'];fresh.run()
        self.assertTrue(any('模拟发送已完成' in e.value for e in fresh.success))
    def test_manual_handoff_changes_owner_without_approving_draft(self):
        c=self.create();self.app.button(key='p47_handoff').click().run()
        saved=ProductStore(self.path).get(c['case_id'])
        self.assertEqual(triage(saved)['handoff'],'requested')
        self.assertEqual(saved['state'],'pending_review')
        self.assertFalse(any(b.key=='p47_quick_send' for b in self.app.button))
        self.app.button(key='p47_take_over').click().run()
        self.assertEqual(triage(ProductStore(self.path).get(c['case_id']))['handoff'],'taken_over')
        self.assertFalse(self.app.exception)
    def test_unsaved_edit_is_case_scoped_and_does_not_confirm(self):
        c=self.create();key=f"p4_reply_{c['case_id']}_1"
        self.app.text_area(key=key).set_value('另存前的客服手稿').run()
        other=self.create(1)
        self.app.button(key='case_'+c['case_id']).click().run()
        self.assertEqual(self.app.text_area(key=key).value,'另存前的客服手稿')
        self.assertNotEqual(ProductStore(self.path).get(c['case_id'])['draft']['body'],'另存前的客服手稿')
        self.assertFalse(any(b.key=='p47_quick_send' for b in self.app.button))
    def test_custom_human_request_is_saved_as_local_handoff(self):
        self.app.selectbox(key='p4_scenario').set_value(CUSTOM_SCENARIO).run()
        self.app.text_input(key='p4_subject').set_value('想找客服')
        self.app.text_area(key='p4_body').set_value('请转人工客服，我想说明一下我的情况。').run()
        self.app.button(key='p4_analyze').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        c=ProductStore(self.path).get(self.app.session_state['p4_case'])
        self.assertEqual(triage(c)['handoff'],'requested')
        self.assertFalse(any(b.key=='p47_quick_send' for b in self.app.button))

    def test_safety_takeover_review_and_approval_are_separate(self):
        c=self.create(4)
        self.assertTrue(self.app.button(key='p46_review_open').disabled)
        self.assertFalse(any(b.key=='p47_quick_send' for b in self.app.button))
        self.app.button(key='p47_take_over').click().run()
        self.app.button(key='p46_review_open').click().run()
        self.app.checkbox(key=f"p47_confirm_{c['case_id']}_1").check().run()
        self.assertTrue(self.app.button(key='p4_approve').disabled)
        self.app.checkbox(key=f"p47_safety_{c['case_id']}_1").check().run()
        self.app.button(key='p4_approve').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        saved=ProductStore(self.path).get(c['case_id'])
        self.assertEqual(saved['state'],'approved')
        self.assertIsNone(saved['receipt'])
        self.app.button(key='p4_simulate_send').click().run()
        self.assertEqual(ProductStore(self.path).get(c['case_id'])['state'],'simulated_sent')

    def test_v2_delivery_selection_preserves_unsaved_draft_through_handoff_and_confirmation(self):
        from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, POLICY_VERSION
        self.app.selectbox(key='p4_scenario').set_value(V2_SCENARIOS[3]).run()
        self.app.button(key='p4_analyze').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        db=ProductStore(self.path);c=db.get(self.app.session_state['p4_case'])
        self.assertEqual(c['run'].config.parameters['service_policy_version'],POLICY_VERSION)
        self.assertEqual(c['run'].config.parameters['service_scenario'],V2_SCENARIOS[3])
        self.assertNotIn('unbound_strategy',triage(c)['reason_codes'])
        key=f"p4_reply_{c['case_id']}_1"
        edited=c['draft']['body']+'\n请您保留现有资料，后续处理方式仍需人工确认。'
        self.app.text_area(key=key).set_value(edited).run()
        self.app.button(key='p47_handoff').click().run()
        self.assertEqual(self.app.text_area(key=key).value,edited)
        self.assertNotEqual(db.get(c['case_id'])['draft']['body'],edited)
        self.app.button(key='p47_take_over').click().run()
        self.assertEqual(self.app.text_area(key=key).value,edited)
        self.app.button(key='p4_save_edit').click().run()
        saved=db.get(c['case_id'])
        self.assertEqual(saved['current_version'],2)
        self.assertEqual(saved['draft']['body'],edited)
        self.assertEqual(triage(saved)['handoff'],'taken_over')
        self.app.button(key='p46_review_open').click().run()
        self.app.checkbox(key=f"p47_confirm_{c['case_id']}_2").check().run()
        self.app.button(key='p4_approve').click().run()
        self.assertEqual(db.get(c['case_id'])['state'],'approved')
        self.assertIsNone(db.get(c['case_id'])['receipt'])
        self.app.button(key='p4_simulate_send').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        receipt=db.get(c['case_id'])['receipt']
        self.assertEqual(receipt['version'],2)
        self.assertEqual(receipt['body'],edited)


class ServiceStatusTests(unittest.TestCase):
    def test_approved_case_handoff_remains_visible_as_waiting_for_human(self):
        from src.application.analysis_service import AnalysisService
        from src.application.product_analysis import ProductAnalysis
        from src.application.service_scenarios import example, ServiceCopilotFake
        from src.infrastructure.repository import Repository
        from src.app.copilot_inbox import status
        with tempfile.TemporaryDirectory() as directory:
            db=ProductStore(Path(directory)/'product.sqlite3')
            email,_=example(SCENARIOS[0])
            c=ProductAnalysis(AnalysisService(Repository(Path(directory)/'analysis.sqlite3'),
                              ServiceCopilotFake(email,SCENARIOS[0])),db).submit(email)
            c=db.act(c['case_id'],'approve',expected_revision=c['revision'],actor='offline_operator',
                     actor_type='demo_test',reason='Offline status regression only',
                     checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True))
            self.assertEqual(status(c),'审核通过')
            c=db.act(c['case_id'],'request_handoff',expected_revision=c['revision'],actor='offline_operator',
                     actor_type='demo_test',reason='Explicit local handoff after approval')
            self.assertEqual(c['state'],'approved')
            self.assertEqual(triage(c)['handoff'],'requested')
            self.assertEqual(status(c),'等待人工')
            self.assertIsNone(c['receipt'])
