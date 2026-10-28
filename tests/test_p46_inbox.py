"""P4.6 offline transactional and UI journeys; no model-quality claims."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from src.application.copilot_demo import SCENARIOS, example, CopilotFake
from src.application.copilot_drafts import insert_suggestion
from src.application.product_workflow import ProductStore, Conflict
from src.application.product_analysis import ProductAnalysis
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.domain.contracts import digest


class InsertionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=ProductStore(Path(self.tmp.name)/'product.sqlite3')
        self.repo=Repository(Path(self.tmp.name)/'analysis.sqlite3')

    def case(self,n=0):
        email,_=example(SCENARIOS[n])
        return ProductAnalysis(AnalysisService(self.repo,CopilotFake(email,SCENARIOS[n])),self.db).submit(email)

    def insert(self,c,text='',mode='replace',**extra):
        return insert_suggestion(self.db,c['case_id'],expected_revision=c['revision'],editor_text=text,
            expected_editor_hash=digest(text),mode=mode,**extra)

    def approve(self,c):
        return self.db.act(c['case_id'],'approve',expected_revision=c['revision'],actor='offline_test',actor_type='demo_test',
            reason='Offline test; not human certification',checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True))

    def test_same_text_insertion_revokes_approval_with_immutable_origin(self):
        c=self.case(); original=c['draft'].copy(); c=self.approve(c)
        new=self.insert(c)
        self.assertEqual(new['state'],'pending_review')
        self.assertEqual(new['current_version'],2)
        self.assertEqual(new['drafts'][0],original)
        source=new['events'][-1]['details']['draft_source']
        self.assertEqual(source,dict(kind='copilot_suggestion',run_id=c['run'].run_id,input_hash=c['run'].input_hash,
                                    suggestion_hash=digest(original['body']),mode='replace'))
        self.assertEqual(ProductStore(self.db.path).get(c['case_id']),new)

    def test_append_preserves_unsaved_text_and_requires_explicit_mode(self):
        c=self.case();text='Operator introduction, not yet saved.'
        with self.assertRaises(Conflict): self.insert(c,text,mode=None)
        self.assertEqual(self.db.get(c['case_id'])['revision'],0)
        result=self.insert(c,text,mode='append')
        self.assertEqual(result['draft']['body'],text+'\n\n'+c['draft']['body'])
        with self.assertRaises(Conflict):
            insert_suggestion(self.db,result['case_id'],expected_revision=result['revision'],editor_text='changed',expected_editor_hash=digest(text),mode='replace')

    def test_stale_revision_and_duplicate_operation(self):
        c=self.case();result=self.insert(c,operation_id='explicit-insertion-operation')
        self.assertEqual(self.insert(c,operation_id='explicit-insertion-operation'),result)
        with self.assertRaises(Conflict):self.insert(c)
        self.assertEqual(len(self.db.get(c['case_id'])['drafts']),2)

    def test_analysis_block_and_terminal_state_remain_enforced(self):
        unsafe=self.insert(self.case(8))
        with self.assertRaises(Conflict):self.approve(unsafe)
        good=self.approve(self.insert(self.case()))
        good=self.db.act(good['case_id'],'simulate_send',expected_revision=good['revision'],actor='offline_test',actor_type='demo_test')
        with self.assertRaises(Conflict):self.insert(good)
        self.assertEqual(self.db.get(good['case_id'])['receipt'],good['receipt'])

    def test_failed_case_and_forged_suggestion_are_refused(self):
        with self.assertRaises(Conflict):self.insert(self.case(4))
        c=self.case()
        with self.assertRaises(Conflict):
            self.db.act(c['case_id'],'insert_suggestion',expected_revision=c['revision'],actor='test',actor_type='demo_test',
                        body='Invented recommendation',checks=dict(insertion_mode='replace'))
        rejected=self.db.act(c['case_id'],'reject',expected_revision=c['revision'],actor='test',actor_type='demo_test',reason='Must change this text')
        with self.assertRaises(Conflict):self.insert(rejected)
        changed=self.insert(rejected,'New operator clarification.','append')
        self.assertEqual(changed['state'],'pending_review')


class InboxUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'product.sqlite3'
        env=patch.dict(os.environ,COMPLAINT_PRODUCT_DB=str(self.path),COMPLAINT_DB_PATH=str(Path(self.tmp.name)/'legacy.sqlite3'))
        env.start();self.addCleanup(env.stop)
        from streamlit.testing.v1 import AppTest
        self.app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45).run()

    def create(self,n=0):
        app=self.app
        app.selectbox(key='p4_scenario').set_value(SCENARIOS[n]).run()
        if n==6:
            app.text_input(key='p4_subject').set_value('合成中文功能咨询')
            app.text_area(key='p4_body').set_value('请问这台设备是否支持有线连接？').run()
        app.button(key='p4_analyze').click().run()
        self.assertFalse(app.exception,[e.message for e in app.exception])
        return ProductStore(self.path).get(app.session_state['p4_case'])

    def test_case_switch_preserves_separate_unsaved_buffers_and_advice(self):
        first=self.create();self.app.button(key='p46_insert').click().run()
        first=ProductStore(self.path).get(first['case_id'])
        key=f"p4_reply_{first['case_id']}_{first['current_version']}"
        self.app.text_area(key=key).set_value('Unsaved camera reply.').run()
        second=self.create(7)
        self.assertEqual(self.app.text_area(key=f"p4_reply_{second['case_id']}_1").value,'')
        self.assertTrue(any('soaked' in t.value for t in self.app.text))
        self.app.button(key='case_'+first['case_id']).click().run()
        self.assertEqual(self.app.text_area(key=key).value,'Unsaved camera reply.')
        self.assertTrue(any('official specifications' in t.value for t in self.app.text))
        self.assertEqual(self.app.query_params['case_id'],[first['case_id']])
        self.assertNotEqual(ProductStore(self.path).get(first['case_id'])['draft']['body'],'Unsaved camera reply.')

    def test_insert_confirmation_cancel_append_and_fresh_reload(self):
        c=self.create();key=f"p4_reply_{c['case_id']}_1"
        self.app.text_area(key=key).set_value('Keep this manual introduction.').run()
        self.app.button(key='p46_insert').click().run()
        self.assertEqual(ProductStore(self.path).get(c['case_id'])['current_version'],1)
        self.app.button(key='p46_insert_cancel').click().run()
        self.assertEqual(self.app.text_area(key=key).value,'Keep this manual introduction.')
        self.app.button(key='p46_insert').click().run()
        self.app.button(key='p46_insert_confirm').click().run()
        self.assertFalse(self.app.exception,[e.message for e in self.app.exception])
        saved=ProductStore(self.path).get(c['case_id'])
        self.assertTrue(saved['draft']['body'].startswith('Keep this manual introduction.\n\n'))
        self.assertEqual(saved['state'],'pending_review')
        from streamlit.testing.v1 import AppTest
        fresh=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45)
        fresh.query_params['case_id']=c['case_id'];fresh.run()
        self.assertEqual(fresh.text_area(key=f"p4_reply_{c['case_id']}_2").value,saved['draft']['body'])
        self.assertFalse(any(b.key=='p4_simulate_send' for b in fresh.button))

    def test_filter_creation_selection_and_unknown_identity(self):
        from src.app.copilot_inbox import preview
        self.assertEqual(preview('![x](https://example.invalid/x)'),r'\!\[x\](https://example.invalid/x)')
        self.create(7)
        self.app.selectbox(key='p46_filter').set_value('已模拟发送').run()
        c=self.create(6)
        self.assertEqual(self.app.selectbox(key='p46_filter').value,'全部')
        self.assertEqual(self.app.session_state['p4_case'],c['case_id'])
        self.assertTrue(any('unknown流程占位' in x.value for x in self.app.caption))
        self.assertFalse(self.app.text_input(key='p46_question_'+c['case_id']).disabled)
        self.assertFalse(self.app.exception)

    def test_existing_approved_v1_restores_without_losing_reply(self):
        c=self.create();db=ProductStore(self.path)
        approved=db.act(c['case_id'],'approve',expected_revision=c['revision'],actor='prior_operator',actor_type='demo_test',
            reason='Existing P4 approved draft; offline fixture only',checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True))
        from streamlit.testing.v1 import AppTest
        fresh=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=45)
        fresh.query_params['case_id']=c['case_id'];fresh.run()
        self.assertEqual(fresh.text_area(key=f"p4_reply_{c['case_id']}_1").value,approved['draft']['body'])
        self.assertFalse(fresh.button(key='p4_simulate_send').disabled)
