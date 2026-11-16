"""Observed R6 failures and counterexamples, offline explicit fixtures only."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from src.application import service_response as service
from src.domain.contracts import EmailInput

FIXTURES=json.loads((Path(__file__).parent/'fixtures/service_response_r6_regressions.json').read_text('utf8'))
def case(key):
    r=copy.deepcopy(FIXTURES[key])
    return EmailInput.model_validate(r['email']),r['analysis']

class SourceAndBriefRepairs(unittest.TestCase):
    def test_fee_exemption_needs_policy_fact_not_billing_query(self):
        from src.application.p5b8r3_final_guard import assess
        text="You're under no obligation to pay anything further while this is being looked into."
        runtime=dict(events=[],facts=dict(status='UNKNOWN'))
        self.assertIn('UNVERIFIED_FEE_POLICY',{f['code'] for f in assess(text,runtime,'a'*64)['findings']})
        self.assertNotIn('UNVERIFIED_FEE_POLICY',{f['code'] for f in assess('I cannot confirm '+text,runtime,'a'*64)['findings']})
        quote=text.rstrip('.')
        runtime['facts']=dict(status='KNOWN',facts=[dict(input_hash='a'*64,source_id='fixture-policy',authority='AUTHORIZED_FIXTURE',conclusion=quote)])
        self.assertNotIn('UNVERIFIED_FEE_POLICY',{f['code'] for f in assess(text,runtime,'a'*64)['findings']})
    def test_reasonable_future_intent_is_soft_but_rigid_callback_is_blocked(self):
        from src.application.p5b8r3_final_guard import assess
        from src.application.p5b8r1_guard import calibrate
        runtime=dict(events=[],future_intent_policy='owner-nonrigid-v1')
        for text in ["We'll follow up once the checks are complete.",'有结果后，我们会根据情况告知您。']:
            out=assess(text,runtime,'a'*64)
            self.assertFalse(any(f['severity']=='block' for f in out['findings']),text)
            prior=dict(findings=[dict(code='H03',quote=out['assessments'][0]['quote'],severity='block')])
            self.assertFalse(any(f['severity']=='block' for f in calibrate(prior,text,runtime,'a'*64,action_audit=out)['findings']))
        for text in ["We'll contact you tomorrow.",'我们保证今天下午回复您。']:
            self.assertTrue(any(f['severity']=='block' for f in assess(text,runtime,'a'*64)['findings']),text)
    def test_product_prepare_uses_source_mapper_and_current_quality(self):
        from fastapi.testclient import TestClient
        from src.app.p5b8r5_api import create
        from src.application.p5b8_product import make_run
        from src.domain.contracts import idempotency_key
        e,a=case('B7-036')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'web').mkdir();(root/'web/index.html').write_text('<p>offline fixture</p>')
            # Old raw remains a fixture; action preparation creates no reply.
            text='Fixture draft for offline integration only.'
            call=dict(run_id='r6-offline-fixture',raw=json.dumps(dict(reply=text)),elapsed_ms=1,metadata=dict(dispatch_at='2026-11-04T00:00:00Z'))
            cse=dict(email=e.model_dump(),analysis=dict(data=a,call=dict(run_id='fixture-analysis')),replies=dict(A_GUIDED=dict(reply=text,error=None,runtime=dict(events=[],facts={}),call=call)),dataset_role='OFFLINE_FIXTURE',annotation_status='NOT_GOLD')
            run=make_run(cse);config=run.config.model_copy(update=dict(parameters=dict(run.config.parameters,experiment='p5b8r6',arm='GUIDED')))
            run=run.model_copy(update=dict(config=config,idempotency_key=idempotency_key(e,config),cohort_id=config.cohort_id))
            with TestClient(create(root/'product.sqlite3',root/'web')) as client:
                saved=client.app.state.store.create(run);cid=saved['case_id'];headers={'x-p5-token':client.get('/api/session').json()['token']}
                d=client.get('/api/p5b5r2/cases/'+cid).json()
                with patch.object(service,'plan_actions',wraps=service.plan_actions) as planner:
                    response=client.post('/api/p5b5r2/cases/'+cid+'/prepare',json=dict(revision=d['revision']),headers=headers)
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(planner.call_args.kwargs['email'],e)
                result=response.json();kinds={x['kind'] for x in result['local_events'] if x['status']=='created'}
                self.assertTrue({'aftersales_request','logistics_followup'}<=kinds)
                event_ids={x['event_id'] for x in result['local_events']}
                again=client.post('/api/p5b5r2/cases/'+cid+'/prepare',json=dict(revision=d['revision']),headers=headers)
                self.assertEqual({x['event_id'] for x in again.json()['local_events']},event_ids)
                self.assertEqual(client.get('/api/p5b5r2/inbox').json()['cases'][0]['analysis_experiment'],'p5b8r6')
                self.assertEqual(client.app.state.store.get(cid)['run'].metadata['runtime']['events'],[])
                self.assertEqual(client.app.state.store.get(cid)['draft']['body'],text)

    def test_run_arm_scope_prevents_cross_arm_reuse_in_shared_store(self):
        e,a=case('B7-036');planned=service.plan_actions(a,email=e)
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'shared.sqlite3';direct=service.execute(e,planned,path,execution_scope=dict(run_id='direct',arm='DIRECT'))
            guided=service.execute(e,planned,path,execution_scope=dict(run_id='guided',arm='GUIDED'))
            self.assertFalse({x['event_id'] for x in direct['events']}&{x['event_id'] for x in guided['events']})
            self.assertFalse(service.missing_actions(e,planned,guided['events']))

    def test_typed_generic_request_is_supported_but_wrong_goal_is_not(self):
        from src.application.p5b8r4_evidence import claim,support
        e=EmailInput(email_id='pan-inquiry',subject='Pan',body='Can you identify the pan?')
        event=dict(event_id='event',input_hash=e.input_hash,kind='human_input_request',status='created',payload=dict(action=dict(goal='Identify the pan and check induction compatibility')))
        runtime=dict(events=[event])
        self.assertTrue(support(claim("I've created an internal product inquiry request",'INTERNAL_CREATED'),runtime,e.input_hash)['supported'])
        self.assertFalse(support(claim("I've created a praise relay request",'INTERNAL_CREATED'),runtime,e.input_hash)['supported'])
        self.assertFalse(support(claim('已创建售后核实和表扬转达请求','INTERNAL_CREATED'),runtime,e.input_hash)['supported'])

    def test_original_relay_survives_analysis_omission_and_negation(self):
        e,a=case('B7-009')
        for i in a['issues']:i['customer_requests']=[]
        actions=service.plan_actions(a,email=e)
        self.assertTrue(any(x['kind']=='store_service_request' for x in actions))
        e=EmailInput(email_id='no-relay',subject='Thanks',body='The staff helped me. Please do not pass my thanks along; no follow-up is needed.')
        result=service.reconcile_plan(e,[dict(kind='store_service_request',issue_ids=[],goal='pass my thanks along',evidence=['The staff helped me.'],priority='normal')])
        self.assertFalse(result)

    def test_merge_damage_source_and_no_expedite_for_safety_alone(self):
        e,a=case('B7-036')
        self.assertEqual(len(a['issues']),1)
        actions=service.plan_actions(a,email=e)
        self.assertTrue({'aftersales_request','logistics_followup'}<={x['kind'] for x in actions})
        a['issues'][0].update(risk='severe',urgency='high')
        a['urgency_evidence']=[]
        self.assertFalse(any('替代方案' in x['goal'] for x in service.plan_actions(a,email=e)))

    def test_water_brief_has_apology_and_completed_vs_remaining_checks(self):
        e,a=case('B7-084')
        with tempfile.TemporaryDirectory() as t:
            runtime=service.execute(e,service.plan_actions(a),Path(t)/'actions.db')
            b=service.brief(e,runtime,a)
        self.assertTrue(any(x['kind']=='apology_for_current_inconvenience' for x in b['acknowledgements']))
        checks=b['knowledge'][0]['checks']
        self.assertEqual(next(c['status'] for c in checks if c['key']=='tank_seating'),'ALREADY_REPORTED_DONE')
        self.assertEqual(next(c['status'] for c in checks if c['key']=='seal_cleaning'),'ALREADY_REPORTED_DONE')
        self.assertEqual(next(c['status'] for c in checks if c['key']=='visible_seal_damage'),'REMAINING_VISUAL_CHECK')

    def test_brief_excludes_foreign_receipts_and_does_not_invent_non_acceptance(self):
        e,a=case('B7-084')
        with tempfile.TemporaryDirectory() as t:
            runtime=service.execute(e,service.plan_actions(a),Path(t)/'actions.db')
        foreign=next(x for x in runtime['events'] if x['status']=='created')
        foreign['input_hash']='f'*64
        b=service.brief(e,runtime,a)
        self.assertNotIn(foreign['event_id'],{p['event_id'] for p in b['pending_progress']})
        self.assertNotIn('No staff has accepted',json.dumps(b))

    def test_praise_and_billing_do_not_get_unrequested_relay(self):
        e,a=case('B7-085')
        actions=service.plan_actions(a,email=e)
        self.assertNotIn('store_service_request',[x['kind'] for x in actions])
        with tempfile.TemporaryDirectory() as t:
            b=service.brief(e,service.execute(e,actions,Path(t)/'a.db'),a)
        self.assertEqual(b['feedback_relay']['requested'],False)
