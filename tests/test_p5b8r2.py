"""Explicit offline fixtures: cross-arm contamination, failure denominators and fairness."""
import copy
import json
import unittest
from src.domain.contracts import EmailInput, digest
from src.evaluation.p5b8r2_judge import bind_events, validate_events, parse, deterministic, blind_pair, DIMENSIONS
from src.application.p5b8r2_reply import paired_messages, chain_messages
from src.application.p5b8r1_experiment import pair_invariant
from src.application.p5b8r1_actions import guided_actions
from src.application.p5b8r2_guard import assess

def fixture():
    e=EmailInput(email_id='unseen-fixture-relay',subject='谢谢',body='请转达我对城北店店员的谢意。')
    event=dict(event_id='fixture-event',input_hash=e.input_hash,kind='store_service_request',status='created',payload=dict(external_execution=False))
    slot=dict(slot='X',case_id=e.email_id,run_id='fixture-run',arm='DIRECT',input_hash=e.input_hash,parse_ok=True,reply='已创建内部转达请求。')
    slot['events']=bind_events([event],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
    answer=dict(slot='X',scores={k:2 for k in DIMENSIONS},reasons={k:'OFFLINE parser fixture, not observed quality' for k in DIMENSIONS},findings=[],action_evidence=[dict(quote=slot['reply'],state='INTERNAL_CREATED',event_ids=['fixture-event'],missing_evidence='')])
    return e,slot,dict(answers=[answer],preference='TIE')

class R2Evidence(unittest.TestCase):
    def test_blind_order_maps_to_own_evidence_without_version_leak(self):
        e,a,_=fixture();b=copy.deepcopy(a);b.update(run_id='second-run',arm='GUIDED',events=[])
        payload,key=blind_pair(e,[a,b]);reverse,rkey=blind_pair(e,[a,b],reverse=True)
        self.assertNotIn('DIRECT',json.dumps(payload));self.assertNotIn('GUIDED',json.dumps(payload))
        self.assertEqual(key['X'],rkey['Y']);self.assertEqual(len(payload['answers'][0]['events']),1)
        self.assertEqual(reverse['answers'][0]['events'],[])
        for slot in payload['answers']+reverse['answers']:validate_events(slot)
    def test_same_hash_different_case_run_or_arm_rejected(self):
        _,slot,j=fixture(); parse(j,dict(answers=[slot]))
        for key in ('case_id','run_id','arm','input_hash'):
            other=copy.deepcopy(slot);other[key]='foreign'
            with self.assertRaises(ValueError):parse(j,dict(answers=[other]))
        for key in ('status','kind','payload'):
            other=copy.deepcopy(slot);other['events'][0][key]='mutated'
            with self.assertRaises(ValueError):validate_events(other)

    def test_foreign_event_ids_and_completion_cannot_use_local_ticket(self):
        _,slot,j=fixture();j['answers'][0]['action_evidence'][0]['event_ids']=['other-arm']
        with self.assertRaises(ValueError):parse(j,dict(answers=[slot]))
        j['answers'][0]['action_evidence'][0].update(event_ids=['fixture-event'],state='EXTERNAL_COMPLETED')
        with self.assertRaises(ValueError):parse(j,dict(answers=[slot]))

    def test_bad_structure_separate_from_semantic_zero(self):
        _,slot,j=fixture();slot.update(parse_ok=False,reply='')
        self.assertEqual(deterministic(slot,{})['category'],'ENGINEERING_FAILURE')
        self.assertIsNone(deterministic(slot,{})['scores'])
        with self.assertRaisesRegex(ValueError,'ENGINEERING'):parse(j,dict(answers=[slot]))

    def test_no_fake_numeric_or_incomplete_scores(self):
        _,slot,j=fixture();j['answers'][0]['scores']['attitude']=True
        with self.assertRaises(ValueError):parse(j,dict(answers=[slot]))
        j['answers'][0]['scores']['attitude']='N/A';parse(j,dict(answers=[slot]))
        j['answers'][0]['reasons'].pop('helpfulness')
        with self.assertRaises(ValueError):parse(j,dict(answers=[slot]))

    def test_arms_share_all_except_actual_predicted_emotion(self):
        from tests.test_p5b8r1 import analysis
        e,_,_=fixture();a=analysis();r=dict(facts=dict(status='UNKNOWN'),events=[])
        m=paired_messages(e,a,r);self.assertTrue(pair_invariant(m)['equal_common'])
        self.assertEqual(chain_messages(e,r)[0],chain_messages(e,r,a)[0])
        self.assertNotIn('B7-',m['ISSUES_NO_SENTIMENT'][0][1])

    def test_different_ids_same_semantics_get_same_local_relay(self):
        from tests.test_p5b8r1 import analysis
        a=analysis();i=a['issues'][0];i.update(issue_kind='praise',business_process='store service issue',resolution='resolved',customer_requests=['请转达谢意'])
        self.assertEqual(guided_actions(a)[0]['kind'],'store_service_request')
        i['customer_requests']=[];self.assertEqual(guided_actions(a),[])

    def test_proposal_negation_and_forged_completion_stay_distinct(self):
        e,slot,_=fixture();r=dict(events=slot['events'])
        def codes(t):return {f['code'] for f in assess(t,r,e.input_hash)['findings']}
        self.assertNotIn('H04',codes('可以请门店核实。'))
        self.assertNotIn('H04',codes('尚未转达谢意。'))
        self.assertIn('H04',codes('已转达谢意。'))
        self.assertNotIn('H04',codes('已创建内部转达请求。'))
        self.assertIn('H04',codes('已创建内部转达请求，并已转达谢意。'))

if __name__=='__main__':unittest.main()
