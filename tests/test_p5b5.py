"""Explicit offline fixtures, new temporary storage, no provider construction."""
import json
from pathlib import Path
import tempfile
import unittest
from src.application.p5b5_pipeline import ConversationState,ActionStore,LocalFacts,plan,candidate_messages,dispatch_disabled,runnable
from src.domain.contracts import EmailInput
from src.evaluation.p5b5 import agreement,diagnose,calibration,read,ROOT

class P5B5Tests(unittest.TestCase):
    def state(self,*texts):
        s=ConversationState('fixture-thread')
        for t in texts:s.update('customer',t)
        return s
    def test_latest_constraints_and_no_assistant_fact(self):
        s=self.state('订单DEMO-OLD，下周一上午安装。')
        s.update('assistant','已批准订单DEMO-FAKE，已预约。')
        s.update('customer','号码写错，更正为DEMO-NEW。只有周三下午在家。')
        self.assertNotIn('DEMO-OLD',s.identifiers);self.assertNotIn('DEMO-FAKE',s.identifiers)
        self.assertIn('周三下午',s.availability)
    def test_undecided_return_exchange_not_a_preference(self):
        from src.application.p5b5_state_v3 import ConversationState
        s=ConversationState('fixture');s.update('customer','我现在也说不准想退还是想换。')
        self.assertIsNone(s.preferred_outcome)
        s.update('customer','订单DEMO-D505，F20车型。我现在更想退掉，不想修。')
        self.assertEqual(s.preferred_outcome,'return')
        s.update('customer','要修还是换我都想先了解，特别是邮费。')
        self.assertIsNone(s.preferred_outcome)
        s.update('customer','不想退货，只想了解换货条件。')
        self.assertIsNone(s.preferred_outcome)
    def test_refusal_means_background_input(self):
        s=self.state('不要转人工，C200能一根线开会吗？');ctx,actions=plan(s)
        self.assertTrue(ctx['refuses_handoff']);self.assertIn('human_input_request',[x['kind'] for x in actions])
        self.assertNotIn('handoff_request',[x['kind'] for x in actions])
    def test_service_complaint_handoff(self):
        ctx,actions=plan(self.state('别再自动回复了，我要人工客服，没人看。'))
        self.assertTrue(ctx['service_complaint']);self.assertIn('handoff_request',[x['kind'] for x in actions])
    def test_installation_not_carrier(self):
        ctx,actions=plan(self.state('安装两次取消。','DEMO-S5096。只有周三下午在家。'))
        self.assertIn('installer_schedule_lookup',[x['kind'] for x in actions]);self.assertNotIn('logistics_lookup',[x['kind'] for x in actions])
    def test_routine_fault_not_safety(self):
        ctx,a=plan(self.state('台灯又不亮了，我想寄回或到店。'))
        self.assertNotIn('safety',[x['kind'] for x in ctx['issues']]);self.assertNotIn('handoff_request',[x['kind'] for x in a])
    def test_multi_issue_has_linked_work(self):
        s=self.state('抽屉会滑出来磕腿，周六取旧床没人来，DEMO-P5081发票漏项。')
        _,a=plan(s);k={x['kind'] for x in a}
        self.assertTrue({'pickup_lookup','invoice_request','aftersales_request','handoff_request'}<=k)
    def test_billing_does_not_request_repair_or_booking(self):
        _,a=plan(self.state('产品正常，别给我安排维修。安装时多收钱，收据对不上。'))
        self.assertEqual({x['kind'] for x in a},{'billing_request'})
    def test_unknown_lookup_creates_durable_followup_idempotently(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'actions.db';s=self.state('查DEMO-P5022物流揽收进度。')
            a=ActionStore(path).execute(s,'input-1');b=ActionStore(path).execute(s,'input-1')
            self.assertEqual(a,b)
            self.assertTrue(any(e['kind']=='logistics_followup' and e['status']=='created' for e in a['events']))
            lookup=next(e for e in a['events'] if e['status']=='executed');self.assertEqual(lookup['payload']['result']['status'],'UNKNOWN')
            self.assertEqual(ActionStore(path).list('other-input'),[])
    def test_lookup_failure_never_says_executed(self):
        class Failed:
            def lookup(self,*args):raise TimeoutError()
        with tempfile.TemporaryDirectory() as t:
            r=ActionStore(Path(t)/'a.db').execute(self.state('查物流'),'x',facts=Failed())
            self.assertIn('failed',[e['status'] for e in r['events']]);self.assertNotIn('executed',[e['status'] for e in r['events']])
    def test_facts_reject_cross_customer_and_incomplete_provenance(self):
        a=dict(kind='knowledge_lookup');f=dict(kind='knowledge_lookup',input_hash='other',quote='secret')
        self.assertEqual(LocalFacts([f]).lookup(a,'mine')['status'],'UNKNOWN')
        f['input_hash']='mine'
        with self.assertRaises(ValueError):LocalFacts([f]).lookup(a,'mine')
    def test_original_b2_messages_unchanged(self):
        from src.application.p5b2_prompt import messages
        e=EmailInput(email_id='fixture',subject='咨询',body='C200怎么接电脑？')
        old=messages(e);runtime=dict(context={},events=[])
        for experiment in ('E1','E2','E3'):
            new=candidate_messages(e,runtime,experiment);self.assertEqual(new[0],old[0]);self.assertEqual(new[2:],old[1:])
    def test_actual_runnable_with_explicit_offline_sink(self):
        from langchain_core.runnables import RunnableLambda
        with tempfile.TemporaryDirectory() as t:
            chain=runnable(RunnableLambda(lambda msgs:dict(identity='OFFLINE_SINK_NOT_MODEL',messages=msgs)),ActionStore(Path(t)/'a.db'))
            r=chain.invoke(dict(email=EmailInput(email_id='x',subject='物流',body='查物流'),state=self.state('查物流')))
            self.assertEqual(r['identity'],'OFFLINE_SINK_NOT_MODEL');self.assertIn('action_receipts',r['messages'][1][1])
    def test_dispatch_closed(self):
        with self.assertRaises(PermissionError):dispatch_disabled()
    def test_new_budget_preflight_limits_and_unknown_stop(self):
        import os
        before_env=dict(os.environ)
        import scripts.p5b5_live as live
        from src.domain.contracts import RunConfig
        from src.infrastructure.deepseek import LiveError
        old=live.LOCAL
        try:
            with tempfile.TemporaryDirectory() as t:
                live.LOCAL=Path(t)/'new';policy=Path(t)/'synthetic-policy.json';policy.write_text('[]',encoding='utf-8');live.init(dataset_policy=policy)
                b=live.Budget(live.LOCAL/'budget.sqlite3');e=EmailInput(email_id='budget-fixture',subject='fixture',body='synthetic')
                config=RunConfig(backend='deepseek_live',model_id='deepseek-flash');msgs=[('system','fixture'),('human','synthetic')]
                b.bind(e,config,msgs,'TEST');b.verify_config(config);b.acquire('run-1',e.input_hash)
                bound=b.reserve('run-1',1,e.input_hash,msgs,4000);self.assertLess(bound,5)
                with self.assertRaises(LiveError):b.reserve('run-1',2,e.input_hash,msgs,4000)
                b.halt('UNKNOWN');b.release('run-1')
                with self.assertRaises(LiveError):b.acquire('run-2',e.input_hash)
                with self.assertRaises(FileExistsError):live.init()
        finally:
            live.LOCAL=old
            os.environ.clear();os.environ.update(before_env)
    def test_e3_reconciles_only_k0_not_gold_or_safety(self):
        import os
        before_env=dict(os.environ)
        try:
            from scripts.p5b5_e3 import messages
            e=EmailInput(email_id='fixture',subject='咨询',body='C200接口')
            result=messages(e,dict(context={},events=[]),'E3')
            self.assertIn('This candidate HAS persisted local runtime actions',result[0][1])
            self.assertIn('Load-bearing failures need severe/high',result[0][1])
            self.assertNotIn('reference_reply',result[0][1])
        finally:
            os.environ.clear();os.environ.update(before_env)
    def test_new_api_reuses_gate_and_restores_local_receipts(self):
        from fastapi.testclient import TestClient
        from src.app.p5b5_api import create
        from src.application.service_scenarios import SCENARIOS
        with tempfile.TemporaryDirectory() as t:
            db=Path(t)/'product.sqlite3'
            with TestClient(create(db)) as client:
                headers={'x-p5-token':client.get('/api/session').json()['token']}
                c=client.post('/api/demo',json=dict(scenario='p47:'+SCENARIOS[0]),headers=headers).json();cid=c['case_id']
                path='/api/p5b5/cases/'+cid+'/prepare'
                self.assertEqual(client.post(path,json=dict(revision=c['revision'])).status_code,403)
                self.assertEqual(client.post(path,json=dict(revision=c['revision']+1),headers=headers).status_code,409)
                result=client.post(path,json=dict(revision=c['revision']),headers=headers)
                self.assertEqual(result.status_code,200);events=result.json()['local_events'];self.assertTrue(events)
                self.assertEqual(client.post('/api/live',headers=headers,json=dict(subject='offline',body='synthetic',synthetic_confirmed=True)).status_code,422)
            with TestClient(create(db)) as fresh:
                c=fresh.get('/api/p5b5/cases/'+cid).json();self.assertEqual(c['local_events'],events)
    def test_no_human_scores_no_agreement(self):
        a=agreement({'case':dict(B1=None)},{'case':dict(B1=2)})
        self.assertEqual(a['B1']['n_eligible'],0);self.assertIsNone(a['B1']['agreement'])
    def test_controls_do_not_claim_semantic_pass(self):
        r=diagnose('如果政策允许，可申请审核。')
        self.assertEqual(r['disposition'],'NEEDS_SEMANTIC_REVIEW');self.assertTrue(all(v is None for v in r['dimensions'].values()))
    def test_immutable_evidence_controls_and_anchors(self):
        out=ROOT/'.local/p5b5/evidence-v1'
        if not out.exists():self.skipTest('private local owner evidence not bundled')
        g=read(out/'owner-policy-overlay.json');cal=calibration(g)
        self.assertEqual(cal['new_controls']['missed'],0);self.assertEqual(cal['new_controls']['false_reject'],0)
        self.assertEqual(sum(x['user_verbatim_signature'] for x in g),3)
        self.assertTrue(all(x['dataset_role']==['DEV_REGRESSION','CALIBRATION'] for x in g))

if __name__=='__main__':unittest.main()
