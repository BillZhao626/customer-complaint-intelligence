from tests.archive_support import requires_archive
"""Offline regression of observed R3 failures; fixtures are not human scores."""
import copy
import json
import unittest
from pathlib import Path
from src.application.p5b8r3_final_guard import assess

ROOT = Path(__file__).resolve().parents[1]

class ObservedFailure(unittest.TestCase):
    @requires_archive('docs/p5b8r3/JUDGE_OBSERVED_COUNTEREXAMPLES.json')
    def test_actual_relay_claim_cannot_use_product_consultation(self):
        row = json.loads((ROOT/'docs/p5b8r3/JUDGE_OBSERVED_COUNTEREXAMPLES.json').read_text('utf-8'))[0]
        out = assess(row['reply'], {'events': row['actual_events']}, row['actual_events'][0]['input_hash'])
        claim = next(a for a in out['assessments'] if '内部转达请求' in a['quote'])
        self.assertFalse(claim['supported'])
        self.assertTrue(any(f['code']=='H04' and f['quote']==claim['quote'] for f in out['findings']))
        self.assertFalse(any(a['supported'] and any(f['quote']==a['quote'] and f['severity']=='block' for f in out['findings']) for a in out['assessments']))

from src.application.p5b8r4_evidence import claim,support
from src.evaluation import p5b8r4_judge as judge
from src.domain.contracts import EmailInput,digest

def fixture(kind='store_service_request',status='created',goal='转达表扬谢意',reply='已创建内部表扬转达请求。',arm='ONE'):
    email=EmailInput(email_id='fixture-current',subject='反馈',body='请转达谢意。')
    identity=dict(case_id=email.email_id,run_id='run-'+arm,arm=arm,input_hash=email.input_hash)
    e=dict(event_id='event-'+arm,conversation_id=email.email_id,input_hash=email.input_hash,kind=kind,status=status,
           created_at='2026-11-02T00:00:00Z',payload=dict(action=dict(goal=goal),external_execution=False))
    slot=dict(identity,parse_ok=True,reply=reply,events=judge.previous.bind([e],**identity))
    return email,slot

class ScopedEvidence(unittest.TestCase):
    def check(self,reply,e=None,strict=True):
        email,slot=fixture(reply=reply)
        if e is not None:slot['events']=e
        return judge.audit_slot(slot) if strict else assess(reply,dict(events=slot['events']),email.input_hash)
    def test_status_matrix(self):
        for state in ('requested','created','assigned','executed','completed','failed','unknown'):
            email,s=fixture(status=state)
            out=judge.audit_slot(s)
            self.assertEqual(any(a['supported'] for a in out['assessments']),state in ('created','assigned','executed','completed'),state)
        email,s=fixture(status='created',reply='已转达您的谢意。')
        self.assertTrue(judge.audit_slot(s)['findings'])
    def test_goal_mismatch_same_kind_and_object_target_mismatch(self):
        for goal in ('核实水箱渗水原因','转达耳机表扬给乙店'):
            email,s=fixture(goal=goal,reply='已创建向甲店转达咖啡机表扬的请求。')
            self.assertFalse(judge.audit_slot(s)['assessments'][0]['supported'])
    def test_queries_do_not_prove_arrival_or_refund(self):
        for text in ('包裹已到货。','已为您退款。','We have refunded your payment.'):
            email,s=fixture(kind='knowledge_lookup',status='executed',goal='查询物流或退款',reply=text)
            self.assertTrue(judge.audit_slot(s)['findings'],text)
    def test_current_task_is_supported_and_own_identity_is_required(self):
        email,s=fixture();self.assertFalse(judge.audit_slot(s)['findings'])
        for field in ('case_id','run_id','arm','input_hash'):
            t=copy.deepcopy(s);t[field]='foreign'
            with self.assertRaises(ValueError):judge.blind_pair(email,[t,fixture(arm='TWO')[1]])
    def test_foreign_empty_slot_and_event_mutation_rejected(self):
        email,s=fixture();s['events']=[]
        for field in ('case_id','input_hash'):
            t=copy.deepcopy(s);t[field]='foreign'
            with self.assertRaises(ValueError):judge.blind_pair(email,[t,fixture(arm='TWO')[1]])
        s=fixture()[1];s['events'][0]['payload']['action']['goal']='changed'
        with self.assertRaises(ValueError):judge.blind_pair(email,[s,fixture(arm='TWO')[1]])
    def test_same_raw_receipt_cannot_be_bound_twice_as_independent_arms(self):
        email,a=fixture();b=fixture(arm='TWO')[1]
        raw={k:v for k,v in a['events'][0].items() if k!='_binding'}
        b['events']=judge.previous.bind([raw],**{k:b[k] for k in ('case_id','run_id','arm','input_hash')})
        with self.assertRaisesRegex(ValueError,'Shared receipt'):judge.blind_pair(email,[a,b])
    def test_matching_external_receipt_but_not_created_refund(self):
        email,s=fixture(kind='refund_request',goal='退款',status='completed',reply='已为您退款。')
        event={k:v for k,v in s['events'][0].items() if k!='_binding'}
        event['payload'].update(external_execution=True,result=dict(status='SUCCEEDED',authority='AUTHORIZED_FIXTURE',source_id='refund-fixture'))
        s['events']=judge.previous.bind([event],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')})
        self.assertFalse(judge.audit_slot(s)['findings'])
        event['status']='created';s['events']=judge.previous.bind([event],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')})
        self.assertTrue(judge.audit_slot(s)['findings'])
    def test_attachment_taken_sent_received_viewed_are_separate(self):
        for text,blocked in [('请提供已拍好的照片。',False),('您说已发送照片，可以先核实接收情况。',False),('我们已收到照片。',True),('我们已查看照片。',True)]:
            self.assertEqual(bool(self.check(text,[])['findings']),blocked,text)
        email,s=fixture(reply='我们已收到照片。');s['events']=[]
        s['attachment_manifest']=[dict(attachment_id='file',input_hash=email.input_hash,status='received')]
        self.assertFalse(judge.audit_slot(s)['findings'])
        s['reply']='我们已查看照片。';self.assertTrue(judge.audit_slot(s)['findings'])
    def test_conditionals_negations_and_second_conjunct(self):
        for text in ('如果需要，可以请售后核实退款条件。','尚未退款。','If needed, we can request a refund review.','请保留照片，不要通电。'):
            self.assertFalse(self.check(text,[])['findings'],text)
        self.assertTrue(self.check('尚未转达，但已为您退款。',[])['findings'])
    def test_executable_callback_and_future_intent_are_not_false_completion(self):
        email,s=fixture(kind='support_followup',status='scheduled',goal='回复客户',reply='我们会尽快回复。')
        e={k:v for k,v in s['events'][0].items() if k!='_binding'}
        e['payload']['action'].update(owner='support',deadline='2026-11-03',executor='fixture-executor')
        e['payload']['result']=dict(status='SCHEDULED',authority='AUTHORIZED_FIXTURE')
        s['events']=judge.previous.bind([e],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')})
        s['capabilities']=dict(customer_reply=dict(enabled=True,authorized=True,executor='fixture-executor'))
        self.assertFalse(judge.audit_slot(s)['findings'])
        p,k=judge.blind_pair(email,[s,fixture(arm='TWO')[1]])
        q,l=judge.blind_pair(email,[s,fixture(arm='TWO')[1]],reverse=True)
        self.assertFalse(p['answers'][0]['deterministic_fact_audit']['findings'])
        self.assertFalse(q['answers'][1]['deterministic_fact_audit']['findings'])
        self.assertEqual(q['answers'][0]['capabilities'],{})
        out=self.check('我们会向门店转达谢意。',[])
        self.assertFalse(any(f['code']=='H04' for f in out['findings']))
    def test_composer_fairness_and_planner_local_event_idempotence(self):
        from src.application.p5b8r4_reply import paired_messages,chain_messages
        from src.application.p5b8r4_actions import guided_actions
        from src.application.p5b8_pipeline import execute
        from tests.test_p5b8r1 import analysis
        from src.application.p5b8r1_experiment import pair_invariant
        import tempfile
        a=analysis();i=a['issues'][0];i.update(issue_kind='praise',resolution='resolved',customer_requests=['请转达谢意'],evidence=['请转达谢意'])
        email,s=fixture();rt=dict(events=[],facts={'status':'UNKNOWN'})
        self.assertTrue(pair_invariant(paired_messages(email,a,rt))['equal_common'])
        self.assertEqual(chain_messages(email,rt)[0],chain_messages(email,rt,a)[0])
        actions=guided_actions(a);self.assertEqual(len(actions),1)
        with tempfile.TemporaryDirectory() as d:
            r=execute(email,actions,Path(d)/'actions.sqlite3');t=execute(email,actions,Path(d)/'actions.sqlite3')
            self.assertEqual(r['events'],t['events']);self.assertEqual(r['external_actions'],0)
            self.assertEqual(sum(e['kind']=='store_service_request' and e['status']=='created' for e in r['events']),1)

class ContractAndJudge(unittest.TestCase):
    def test_first_failure_stays_failure_recovery_is_secondary(self):
        from src.application.p5b8r4_contracts import parse_reply
        r=parse_reply('{"reply":"complete"',{'finish_reason':'stop'})
        self.assertEqual(r['first']['status'],'rejected');self.assertIsNotNone(r['recovery'])
        for raw in ('{"reply":"ok","type":"json_object"}','{"reply":"ok"}extra','{"reply":"  "}','{"reply":"ok","reply":"other"}'):
            r=parse_reply(raw);self.assertEqual(r['first']['status'],'rejected');self.assertIsNone(r['recovery'])
    def test_guard_veto_preserves_raw_scores_but_denies_certification(self):
        email,a=fixture(kind='human_input_request',goal='水箱咨询');b=fixture(arm='TWO')[1]
        payload,key=judge.blind_pair(email,[a,b])
        raw=dict(answers=[dict(slot=s['slot'],scores={d:2 for d in judge.DIMENSIONS},reasons={d:'fixture-only numeric values, not human scores' for d in judge.DIMENSIONS},findings=[],action_evidence=[],customer_goals=[dict(goal='relay',quote='请转达谢意')],issue_coverage=[dict(issue='relay',reply_quote=s['reply'],status='COVERED')],score_evidence={d:s['reply'] for d in judge.DIMENSIONS}) for s in payload['answers']],preference='X')
        result=judge.parse(raw,payload)
        self.assertEqual(result['validation']['status'],'UNCERTIFIED')
        self.assertEqual(result['validation']['validated_preference'],'UNKNOWN')
        self.assertEqual(result['answers'][0]['scores'],raw['answers'][0]['scores'])
        self.assertIn('JUDGE_INTERNAL_CONTRADICTION',result['answers'][0]['fact_validation']['errors'])
    def test_ab_ba_keeps_source_event_mapping(self):
        email,a=fixture();b=fixture(arm='TWO')[1]
        ab,k=judge.blind_pair(email,[a,b]);ba,l=judge.blind_pair(email,[a,b],reverse=True)
        self.assertEqual(k['X'],l['Y']);self.assertEqual(ab['answers'][0]['events'],ba['answers'][1]['events'])
        self.assertFalse(ab['answers'][0]['deterministic_fact_audit']['findings'])
        self.assertFalse(ba['answers'][1]['deterministic_fact_audit']['findings'])

    @requires_archive('docs/p5b8r4/evidence/prepared-plan.json')
    def test_r4_live_denied_before_provider_and_full_mock_uses_existing_ledger(self):
        import tempfile
        from unittest.mock import patch
        from scripts.p5b8r4 import live,run_plan
        from src.infrastructure.p5b8r3_execution import Dispatcher
        with patch('src.infrastructure.p5b8r3_execution.LangChainProvider') as provider:
            with self.assertRaisesRegex(PermissionError,'AUTHORIZATION_BLOCKED'):live(None)
            provider.assert_not_called()
        plan=json.loads((ROOT/'docs/p5b8r4/evidence/prepared-plan.json').read_text('utf-8'))
        def fake(messages,folder,payload):
            data=json.loads(messages[1][1])
            if payload and payload.get('stage')=='PLAN':
                from src.application.p5b8r3_experiment import mock_provider
                return mock_provider(messages,folder,payload)
            if payload and 'blind_payload' in payload:
                answers=[]
                for s in data['answers']:
                    answers.append(dict(slot=s['slot'],scores={d:1 for d in judge.DIMENSIONS},reasons={d:'Explicit offline fake, no quality observation' for d in judge.DIMENSIONS},findings=[],action_evidence=[],
                                        customer_goals=[dict(goal='fixture',quote=data['customer']['body'][:4])],issue_coverage=[dict(issue='fixture',reply_quote=s['reply'],status='COVERED')],score_evidence={d:s['reply'] for d in judge.DIMENSIONS}))
                out=dict(answers=answers,preference='TIE')
            else:out=dict(reply='如果需要，可以请同事进一步核实。')
            return json.dumps(out,ensure_ascii=False),dict(input_tokens=100,output_tokens=100,total_tokens=200,finish_reason='stop')
        with tempfile.TemporaryDirectory() as directory:
            d=Dispatcher(directory,plan,provider=fake)
            run_plan(plan,d)
            self.assertEqual(d.summary()['states'],{'COMPLETED':72})
            self.assertEqual(d.summary()['paid_requests'],0)
            self.assertEqual(len(list((Path(directory)/'results').glob('*.json'))),12)
            self.assertEqual(len(list((Path(directory)/'judgments').glob('*.json'))),48)
            stores=list((Path(directory)/'state').glob('*/actions.sqlite3'))
            self.assertEqual(len(stores),12)

if __name__ == '__main__': unittest.main()
