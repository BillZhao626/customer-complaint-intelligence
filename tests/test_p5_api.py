"""P5 thin API tests: real services, temporary SQLite, no provider/network."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from src.app.p5_api import create_app
from src.application.service_scenarios import SCENARIOS


class P5ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'product.sqlite3'
        self.app = create_app(self.path,serve_web=False)
        self.client = TestClient(self.app)
        self.headers = {'x-p5-token':self.client.get('/api/session').json()['token']}

    def tearDown(self): self.client.close(); self.temp.cleanup()

    def post(self,path,body): return self.client.post(path,json=body,headers=self.headers)

    def demo(self,scenario=None):
        r = self.post('/api/demo',dict(scenario=scenario or 'p47:'+SCENARIOS[0]))
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def act(self,c,action,**fields):
        return self.post('/api/cases/'+c['case_id']+'/actions',dict(action=action,revision=c['revision'],operation_id=str(uuid4()),**fields))

    def test_loopback_origin_and_session_protect_writes(self):
        self.assertEqual(self.client.post('/api/demo',json={'scenario':'blocked'}).status_code,403)
        self.assertEqual(self.client.get('/api/session',headers={'host':'attacker.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/session',headers={'origin':'https://attacker.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/cases').json(),{'cases':[]})

    def test_serialization_provenance_and_idempotent_import(self):
        c=self.demo(); again=self.demo()
        self.assertEqual(c['case_id'],again['case_id'])
        self.assertEqual(len(c['messages']),1)
        self.assertTrue(c['simulation_only']); self.assertEqual(c['source_kind'],'offline_fake')
        self.assertEqual(len(self.client.get('/api/cases').json()['cases']),1)
        self.assertTrue(self.client.get('/api/cases/'+c['case_id']+'/sources').json()['sources'])

    def test_quick_confirmation_receipt_retry_and_restart(self):
        c=self.demo()
        self.assertNotEqual(self.act(c,'quick_confirm',confirmed=False).status_code,200)
        command=dict(action='quick_confirm',revision=c['revision'],operation_id=str(uuid4()),confirmed=True)
        path='/api/cases/'+c['case_id']+'/actions'
        r=self.post(path,command); self.assertEqual(r.status_code,200,r.text)
        c=r.json(); self.assertEqual(c['state'],'simulated_sent')
        self.assertEqual(len(c['messages']),2)
        again=self.post(path,command).json(); self.assertEqual(c['receipt'],again['receipt'])
        with TestClient(create_app(self.path,serve_web=False)) as client:
            restored=client.get('/api/cases/'+c['case_id']).json()
            self.assertEqual(c['receipt'],restored['receipt'])

    def test_edit_retracts_approval_and_stale_write_conflicts(self):
        c=self.demo()
        checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True)
        approved=self.act(c,'approve',checks=checks,reason='本地开发操作确认').json()
        self.assertEqual(approved['state'],'approved')
        edited=self.act(approved,'save_edit',body=c['draft']['body']+' 请保留商品页面。').json()
        self.assertEqual(edited['state'],'pending_review')
        self.assertEqual(self.act(approved,'save_edit',body='旧页覆盖').status_code,409)
        self.assertEqual(self.act(edited,'simulate_send').status_code,409)

    def test_takeover_required_for_safety_and_no_checkbox_bypass(self):
        c=self.demo('p47:'+SCENARIOS[4])
        checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True)
        self.assertEqual(self.act(c,'approve',checks=checks,reason='人工确认').status_code,409)
        c=self.act(c,'take_over',reason='本地操作者接管安全问题').json()
        self.assertEqual(self.act(c,'approve',checks={},reason='遗漏核对').status_code,409)
        r=self.act(c,'approve',checks=checks,reason='逐项确认安全与权限')
        self.assertEqual(r.status_code,200,r.text)

    def test_bad_analysis_cannot_be_cleared_by_rewriting(self):
        c=self.demo('blocked'); self.assertEqual(c['quality']['status'],'blocked')
        c=self.act(c,'take_over',reason='检查阻断反例').json()
        c=self.act(c,'save_edit',body='Please do not ride the bicycle. A qualified human safety assessment is needed.').json()
        self.assertEqual(c['quality']['status'],'blocked')
        self.assertEqual(self.act(c,'approve',checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True),reason='不可豁免').status_code,409)

    def test_followup_is_single_thread_and_blank_error_is_chinese(self):
        c=self.demo(); c=self.act(c,'quick_confirm',confirmed=True).json()
        path='/api/cases/'+c['case_id']+'/followup'
        blank=self.post(path,dict(body='  ',revision=c['revision'],operation_id='blank'))
        self.assertEqual(blank.status_code,422)
        self.assertIn('请填写',blank.json()['message']); self.assertNotIn('input',blank.text)
        command=dict(body='电脑是USB-C接口，请先核实商品协议。',revision=c['revision'],operation_id='followup')
        r=self.post(path,command); self.assertEqual(r.status_code,200,r.text)
        child=r.json(); self.assertEqual(len(child['messages']),3)
        self.assertEqual(child['triage']['level'],'human_required')
        self.assertEqual(self.post(path,command).json()['case_id'],child['case_id'])
        rows=self.client.get('/api/cases').json()['cases']
        self.assertEqual([x['case_id'] for x in rows],[child['case_id']])
        self.assertEqual(rows[0]['preview'],command['body'])
        self.assertEqual(child['preview'],command['body'])

    def test_validation_does_not_echo_raw_input(self):
        c=self.demo()
        r=self.post('/api/cases/'+c['case_id']+'/actions',dict(action='save_edit',revision='wrong',operation_id='x',body='PRIVATE_SENTINEL'))
        self.assertEqual(r.status_code,422); self.assertNotIn('PRIVATE_SENTINEL',r.text)
        self.assertEqual(self.client.get('/api/cases/absent').status_code,404)

    def test_knowledge_tasks_are_case_scoped_pending_idempotent_and_durable(self):
        c=self.demo(); other=self.demo('blocked')
        path='/api/cases/'+c['case_id']+'/knowledge-notes'
        command=dict(revision=c['revision'],operation_id='knowledge-1',kind='request',body='请商品资料负责人核实 C200 的 UVC 协议。')
        first=self.post(path,command); self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(len(self.post(path,command).json()['knowledge_tasks']),1)
        command['kind']='note'; command['body']='候选补充：待研究者核验来源后再决定。'
        self.assertEqual(self.post(path,command).status_code,409)
        command['operation_id']='knowledge-2'
        after=self.post(path,command).json()
        self.assertEqual(after['draft'],c['draft'])
        self.assertEqual(after['revision'],c['revision'])
        self.assertTrue(all(n['owner_status']=='OWNER_PENDING' and n['use_in_model'] is False for n in after['knowledge_tasks']))
        self.assertEqual(self.client.get('/api/cases/'+other['case_id']).json()['knowledge_tasks'],[])
        with TestClient(create_app(self.path,serve_web=False)) as client:
            self.assertEqual(len(client.get('/api/cases/'+c['case_id']).json()['knowledge_tasks']),2)

    def test_p5_bound_guidance_no_emotion_only_handoff_and_safety_guard(self):
        from src.application.p5_quality import load_cases
        rows=load_cases()
        ordinary=[]; severe=[]
        for item in rows:
            c=self.demo('p5:'+item['case_id'])
            self.assertEqual(c['pilot']['case_id'],item['case_id'])
            self.assertNotIn('strong_emotion',c['triage']['reason_codes'])
            self.assertNotIn('quick_confirm',c['allowed_actions'])
            if c['quality']['safety_review_required']: severe.append(c)
            if c['triage']['level']=='human_confirm': ordinary.append(c)
        self.assertTrue(ordinary); self.assertGreaterEqual(len(severe),3)
        c=severe[0]
        checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True)
        self.assertEqual(self.act(c,'approve',checks=checks,reason='尚未接管').status_code,409)
        c=self.act(c,'take_over',reason='本地接管').json()
        self.assertNotIn('take_over',c['allowed_actions'])
        self.assertEqual(self.act(c,'approve',checks=checks,reason='核对安全与权限').status_code,200)

    def test_reopening_existing_product_and_sidecars_never_changes_file_bytes(self):
        from src.application.product_workflow import ProductStore
        from src.application.mail_threads import MailThreads
        from src.infrastructure.copilot_repository import CopilotRepository
        c=self.demo()
        threads=MailThreads(self.app.state.store); qa=CopilotRepository(self.path)
        paths=[self.path,threads.path,qa.path]
        before={str(p):p.read_bytes() for p in paths}
        for _ in range(3):
            store=ProductStore(self.path)
            self.assertEqual(store.get(c['case_id'])['case_id'],c['case_id'])
            self.assertEqual(len(MailThreads(store).messages(c['case_id'])),1)
            self.assertEqual(CopilotRepository(self.path).history(c['case_id']),[])
        self.assertEqual(before,{str(p):p.read_bytes() for p in paths})

    def test_unbound_candidate_identity_never_displays_another_pilot_plan(self):
        import copy
        from unittest.mock import patch
        from src.app.p5_api import detail
        from src.application.p5_quality import load_cases
        rows=load_cases(); original=self.demo('p5:'+rows[0]['case_id'])
        case=copy.deepcopy(self.app.state.store.get(original['case_id']))
        params=dict(case['run'].config.parameters,p5_case_id=rows[3]['case_id'])
        case['run']=case['run'].model_copy(update={'config':case['run'].config.model_copy(update={'parameters':params})})
        with patch.object(self.app.state.store,'get',return_value=case):
            result=detail(self.app.state.store,case['case_id'])
        self.assertIn('unbound_strategy',result['triage']['reason_codes'])
        self.assertNotIn('pilot',result)
        self.assertNotIn('missing_facts',result['ai'])
        self.assertEqual(result['ai']['next_step'],result['triage']['next_step'])


if __name__=='__main__': unittest.main()
