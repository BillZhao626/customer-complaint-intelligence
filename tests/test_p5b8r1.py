"""R1 offline positive/negative controls, never synthetic human numerical Gold."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from src.application.p5b8r1_contracts import parse_outcome,paired_messages,build_judge_pair,analysis_system
from src.application.p5b8r1_experiment import pair_invariant,run_pair,ARMS
from src.application.p5b8r1_guard import assess,calibrate
from src.evaluation.p5b8r1_judge import parse as parse_judge
from src.domain.contracts import EmailInput

H='a'*64
def receipt(kind='aftersales_request',status='created',h=H,**payload):
    return dict(event_id='event-'+kind,input_hash=h,kind=kind,status=status,payload=payload)
def runtime(*events,**kw):return dict(events=list(events),facts=dict(status='UNKNOWN'),**kw)
def codes(text,r):return {f['code'] for f in assess(text,r,H)['findings']}
def analysis():
    return dict(version='p5b8-calibration-1',expressed_sentiment='neutral',expressed_evidence=[],experience_polarity='negative',complaint_intent='yes',complaint_evidence=['请核实维修'],urgency='medium',urgency_evidence=[],mentioned_store=None,issues=[dict(issue_id='I1',object_type='product',object_name='耳机',category='Electronics',sentiment='neutral',experience_polarity='negative',issue_kind='complaint',business_process='product issue',customer_requests=['核实维修'],evidence=['耳机不亮'],risk='none',urgency='medium',resolution='unresolved')],uncertainty=['No dissatisfaction expressed'])

class Contracts(unittest.TestCase):
    def test_missing_uncertainty_is_rejected_not_defaulted(self):
        e=EmailInput(email_id='fixture',subject='',body='耳机不亮，请核实维修。');a=analysis()
        self.assertEqual(parse_outcome(json.dumps(a),email=e)['status'],'accepted')
        del a['uncertainty'];out=parse_outcome(json.dumps(a),email=e)
        self.assertEqual(out['status'],'rejected');self.assertIn('uncertainty',out['error']);self.assertIn('Always include uncertainty',analysis_system())
    def test_reply_missing_brace_extra_key_empty_and_length_fail(self):
        for raw,meta in [(' {"reply":"Complete body."',{}),('{"reply":"ok","extra":1}',{}),('{"reply":"   "}',{}),('{"reply":"ok"}',{'finish_reason':'length'})]:
            with self.subTest(raw=raw):self.assertFalse(parse_outcome(raw,metadata=meta)['semantic_eligible'])
        self.assertTrue(parse_outcome(json.dumps(dict(reply='Say "hello".\n下一行。')))['semantic_eligible'])
    def test_failed_structure_not_zero_semantic_emotion(self):
        out=build_judge_pair(EmailInput(email_id='f',subject='',body='x'),[dict(parse_ok=False,reply=''),dict(parse_ok=True,reply='ok')])
        self.assertEqual(out['status'],'NOT_ASSESSABLE_STRUCTURE');self.assertIsNone(out['payload']);self.assertIsNone(out['emotion_delta'])
    def test_strict_pair_only_explicit_emotion_diff(self):
        e=EmailInput(email_id='f',subject='',body='耳机不亮，请核实维修。');a=analysis();r=runtime(receipt())
        original=copy.deepcopy(a);msgs=paired_messages(e,a,r);proof=pair_invariant(msgs)
        self.assertTrue(proof['equal_common']);self.assertEqual(original,a)
        no=json.loads(msgs[ARMS[0]][1][1]);self.assertEqual(no['structured_issues']['issues'][0]['customer_requests'],['核实维修']);self.assertNotIn('uncertainty',no['structured_issues'])
        with_payload=json.loads(msgs[ARMS[1]][1][1]);with_payload['action_receipts']=[]
        msgs[ARMS[1]][1]=('human',json.dumps(with_payload))
        with self.assertRaises(ValueError):pair_invariant(msgs)
    def test_first_response_saved_before_rejection_and_no_rerun(self):
        e=EmailInput(email_id='f',subject='',body='耳机不亮，请核实维修。');p=dict(case_id='f',order=list(ARMS),messages=paired_messages(e,analysis(),runtime()))
        with tempfile.TemporaryDirectory() as d:
            invoke=Mock(return_value=('{"reply":"incomplete"',{'finish_reason':'stop'}));out=run_pair(p,invoke,d)
            self.assertEqual(invoke.call_count,2)
            self.assertTrue((Path(d)/ARMS[0]/'response.json').is_file());self.assertEqual(out[ARMS[0]]['parse']['status'],'rejected')
            with self.assertRaises(FileExistsError):run_pair(p,invoke,d)
            self.assertEqual(invoke.call_count,2)
    def test_unknown_transport_not_retried(self):
        e=EmailInput(email_id='f',subject='',body='耳机不亮，请核实维修。');p=dict(case_id='f',order=list(ARMS),messages=paired_messages(e,analysis(),runtime()))
        with tempfile.TemporaryDirectory() as d:
            invoke=Mock(side_effect=TimeoutError())
            with self.assertRaises(TimeoutError):run_pair(p,invoke,d)
            self.assertEqual(invoke.call_count,1);self.assertEqual(json.loads((Path(d)/ARMS[0]/'error.json').read_text())['status'],'UNKNOWN_DO_NOT_RETRY')
    def test_live_rejected_before_invoking_any_transport(self):
        invoke=Mock()
        with self.assertRaises(PermissionError):run_pair({},invoke,Path('unused'),mode='LIVE')
        invoke.assert_not_called()

class ActionStates(unittest.TestCase):
    def test_task_requires_current_hash_kind_and_created_state(self):
        t='已提交内部售后请求。'
        self.assertNotIn('H04',codes(t,runtime(receipt())))
        for e in [None,receipt(h='b'*64),receipt(status='requested'),receipt(status='UNKNOWN'),receipt(kind='knowledge_lookup',status='executed'),receipt(kind='logistics_followup')]:
            with self.subTest(e=e):self.assertIn('H04',codes(t,runtime(*([e] if e else []))))
    def test_creation_not_external_completion(self):
        for t in ['已与门店沟通。','已记录并转交门店。',"I've passed your thanks along."]:
            self.assertIn('H04',codes(t,runtime(receipt(kind='store_service_request'))),t)
    def test_external_completion_requires_actual_success_fixture(self):
        e=receipt(kind='feedback_relay',status='completed',external_execution=True,result=dict(status='SUCCEEDED',authority='AUTHORIZED_FIXTURE',source_id='offline-control'))
        self.assertNotIn('H04',codes('已转达您的谢意。',runtime(e)))
        for field,val in [('status','created'),('input_hash','other')]:
            b=copy.deepcopy(e);b[field]=val;self.assertIn('H04',codes('已转达您的谢意。',runtime(b)))
        b=copy.deepcopy(e);b['payload']['result']['status']='UNKNOWN';self.assertIn('H04',codes('已转达您的谢意。',runtime(b)))
    def test_future_relay_not_completed_claim(self):
        for t in ["I'll pass your thanks along to the store.",'会在内部转交门店跟进。']:
            c=codes(t,runtime());self.assertNotIn('H04',c);self.assertIn('FUTURE_INTENT_REVIEW',c)
    def test_delivery_query_object_is_not_delivered_predicate(self):
        text='我们已就您的物流查询和本周送达确认提交了内部跟进。'
        self.assertNotIn('H04',codes(text,runtime(receipt(kind='logistics_followup'))))
        self.assertIn('H04',codes('已送达门店。',runtime()))
    def test_team_callback_and_implicit_chinese_followup_need_schedule(self):
        for text in ['The team will review the case and contact you.','后续有查询结果会尽快同步给您。','待有明确信息后会再与您联系。']:
            self.assertIn('H03',codes(text,runtime()),text)
    def test_promised_callback_requires_authorized_schedule_owner_deadline(self):
        text='我们会尽快回复。';self.assertIn('H03',codes(text,runtime(receipt(kind='support_followup'))))
        cap=dict(customer_reply=dict(enabled=True,authorized=True,executor='offline-test'))
        e=receipt(kind='support_followup',status='scheduled',action=dict(owner='support',deadline='2026-11-01',executor='offline-test'),result=dict(status='SCHEDULED',authority='AUTHORIZED_FIXTURE'))
        self.assertNotIn('H03',codes(text,runtime(e,capabilities=cap)))
        for missing in ['owner','deadline','executor']:
            b=copy.deepcopy(e);del b['payload']['action'][missing];self.assertIn('H03',codes(text,runtime(b,capabilities=cap)))
        self.assertIn('H03',codes(text,runtime(e)))
    def test_recording_input_not_task_or_forward(self):
        r=runtime(audit_records=[dict(record_id='saved-input',input_hash=H,artifact_sha256='c'*64,phase='before_provider')])
        self.assertFalse(codes('我们已记录您的表扬。',r))
        self.assertFalse(codes('已将您的情况记录，并提交给产品支持核实。',r))
        self.assertIn('H04',codes('已创建门店服务任务。',r));self.assertIn('H04',codes('我们已记录并转达您的表扬。',r))
    def test_attachments_received_and_viewed_are_distinct(self):
        text='已看到照片。';r=runtime(attachment_manifest=[dict(attachment_id='f',input_hash=H,status='received')])
        self.assertIn('H04',codes(text,r));self.assertNotIn('H04',codes('已收到照片。',r));self.assertIn('H04',codes('已收到照片。',runtime()))
        r['attachment_manifest'][0]['status']='viewed';self.assertNotIn('H04',codes(text,r))
    def test_proposal_and_negative_claim_are_not_completed(self):
        for t in ['尚未提交查询请求，下一步可以请售后核实。','I can ask whether this can be relayed.','没有已创建的工单。']:
            self.assertNotIn('H04',codes(t,runtime()))
    def test_waiver_does_not_remove_separate_unsupported_predicate_or_safety(self):
        r=runtime(audit_records=[dict(record_id='r',input_hash=H,artifact_sha256='a'*64,phase='before_provider')])
        text='已记录并转达您的表扬。';prior=dict(findings=[dict(code='H04',quote=text,reason='x',severity='block'),dict(code='potential_injury_downgrade',quote='',reason='hazard',severity='block')])
        out=calibrate(prior,text,r,H);self.assertEqual(out['status'],'blocked');self.assertIn('H04',{f['code'] for f in out['findings']});self.assertIn('potential_injury_downgrade',{f['code'] for f in out['findings']})
    def test_no_length_reward_from_deterministic_action_gate(self):
        r=runtime(receipt());short='已提交内部售后请求。';long='感谢您详细告知情况。'+short+'具体条件仍需核实。感谢您的耐心。'
        self.assertEqual(codes(short,r),codes(long,r))

class JudgeIntake(unittest.TestCase):
    def test_foreign_slot_receipt_and_ungrounded_quote_rejected(self):
        payload=dict(answers=[dict(slot='A',reply='已创建内部任务。',events=[receipt()],expected_input_hash=H),dict(slot='B',reply='尚未创建内部任务。',events=[],expected_input_hash=H)])
        def ans(s):return dict(slot=s,scores={k:2 for k in ['B1','B2','B3','B4','B5']},dimension_reasons={k:'fixture only' for k in ['B1','B2','B3','B4','B5']},hard_errors=[],review_findings=[],action_evidence=[])
        j=dict(answers=[ans('A'),ans('B')],preference='TIE');parse_judge(j,payload)
        j['answers'][1]['action_evidence']=[dict(quote='尚未创建内部任务',state='PENDING_EXECUTION',event_ids=['event-aftersales_request'],missing_evidence='')]
        with self.assertRaisesRegex(ValueError,'Foreign-slot'):parse_judge(j,payload)
        j['answers'][1]['action_evidence'][0].update(event_ids=[],quote='different text')
        with self.assertRaisesRegex(ValueError,'exact slot'):parse_judge(j,payload)

class ProductSafety(unittest.TestCase):
    def test_explicit_praise_routing_creates_pending_task_not_external_delivery(self):
        from src.application.p5b8r1_actions import guided_actions
        from src.application.p5b8_pipeline import execute
        a=analysis();i=a['issues'][0];i.update(issue_kind='praise',business_process='store service issue',customer_requests=['Please pass my thanks to the team'],evidence=['Please pass my thanks to the team'],resolution='not_applicable')
        actions=guided_actions(a);self.assertEqual(len(actions),1);self.assertEqual(actions[0]['kind'],'store_service_request')
        with tempfile.TemporaryDirectory() as folder:
            e=EmailInput(email_id='praise-fixture',subject='',body='Please pass my thanks to the team');p=Path(folder)/'actions.sqlite3';r=execute(e,actions,p);again=execute(e,actions,p)
            self.assertEqual(r['events'],again['events']);created=[x for x in r['events'] if x['status']=='created'];self.assertEqual(len(created),1);self.assertFalse(created[0]['payload']['external_execution']);self.assertEqual(r['external_actions'],0)
        i['customer_requests']=[];self.assertEqual(guided_actions(a),[])
    def test_r1_api_reuses_inbox_and_read_only_case_evidence(self):
        from tests.test_p5b8_product import fixture
        from src.app.p5b8r1_api import create
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'web').mkdir();(root/'web/index.html').write_text('R1 fixture');cse=fixture(root)
            with patch('src.app.p5b8_api.cases',return_value=[cse]),patch('src.app.p5b8r1_api.cases',return_value=[cse]),TestClient(create(root/'product.sqlite3',root/'web')) as client:
                token=client.get('/api/session').json()['token'];r=client.post('/api/b8/import',json=dict(identity='P5B8_SAVED_REAL_CHAIN'),headers={'x-p5-token':token});self.assertEqual(r.status_code,200,r.text)
                detail=client.get('/api/b8r1/cases/FIXTURE-001');self.assertEqual(detail.status_code,200,detail.text)
                self.assertIsNone(detail.json()['new_judge_scores']);self.assertEqual(detail.json()['r1_ablation_status'],'AUTHORIZATION_BLOCKED');self.assertEqual(detail.json()['r1_gate']['status'],'review_required')
                self.assertEqual(client.get('/').status_code,200)
    def test_safe_negation_does_not_waive_downgraded_hazard(self):
        from tests.test_p5b8_product import fixture
        from src.application.p5b8_product import make_run,stored
        from src.application.p5b8r1_guard import quality
        with tempfile.TemporaryDirectory() as folder:
            c=fixture(Path(folder));text='折叠车车架锁扣失效，差点摔倒。';c['email']['body']=text;a=c['analysis']['data'];a['complaint_evidence']=[text];i=a['issues'][0];i.update(object_name='折叠车',evidence=[text],risk='none',urgency='medium');reply='请不要再试骑，先暂停骑行，等待售后核实。';c['replies']['A_GUIDED']['reply']=reply;c['replies']['A_GUIDED']['call']['raw']=json.dumps(dict(reply=reply),ensure_ascii=False)
            run=make_run(c);q=quality(run,stored(run),reply,True);self.assertIn('potential_injury_downgrade',{f['code'] for f in q['findings']});self.assertTrue(q['safety_review_required'])
            i.update(risk='severe',urgency='high');run=make_run(c);q=quality(run,stored(run),reply,True);self.assertNotIn('dangerous_reproduction',{f['code'] for f in q['findings']})

if __name__=='__main__':unittest.main()
