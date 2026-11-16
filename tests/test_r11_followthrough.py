"""Explicit offline fixtures for follow-through; never writes historical assets."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import sqlite3
from contextlib import closing

from src.domain.contracts import EmailInput,digest
from src.application import service_response as service
from src.application.service_plan import transport_schema,parse as parse_plan
from src.evaluation import service_judge as judge
from src.infrastructure.p5b8r3_execution import Dispatcher

def mail(body):return EmailInput(email_id='independent-fixture',subject='Service question',body=body)
def slot(email,text,runtime):
    identity=dict(case_id=email.email_id,run_id='test',arm='GUIDED',input_hash=email.input_hash)
    return dict(identity,parse_ok=True,reply=text,facts={},events=judge.bind(runtime.get('events',[]),**identity))

class FollowthroughTests(unittest.TestCase):
    def test_request_only_requires_explicit_waiver_and_enforces_cap(self):
        plan=dict(authorization_scope='FIXTURE',planned_requests=1,proposed_cny_cap=None,budget_mode='REQUEST_ONLY',allowed_call_ids=['one','two'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
        auth=dict(scope='FIXTURE',provider_requests=1,cny=None,budget_mode='REQUEST_ONLY',monetary_cap_explicitly_waived=True,plan_hash=digest(plan),user_approval_verbatim='Explicit fixture approval')
        provider=lambda m,f,p:('{}',dict(input_tokens=1,output_tokens=1,total_tokens=2))
        with TemporaryDirectory() as t:
            d=Dispatcher(t,plan,authorization=auth,provider=provider,mode='LIVE')
            d.call('one',[('human','fixture')]);self.assertEqual(d.summary()['paid_requests'],1)
            with self.assertRaisesRegex(RuntimeError,'cap exceeded'):d.call('two',[('human','fixture')])
        with TemporaryDirectory() as t:
            with self.assertRaises(PermissionError):Dispatcher(t,plan,authorization=dict(auth,monetary_cap_explicitly_waived=False),mode='LIVE')

    def test_linked_extension_is_append_only_and_keeps_prior_request_count(self):
        plan=dict(authorization_scope='EXTENSION_FIXTURE',planned_requests=1,proposed_cny_cap=None,budget_mode='REQUEST_ONLY',allowed_call_ids=['one','two','three'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
        auth=dict(scope='EXTENSION_FIXTURE',provider_requests=1,cny=None,budget_mode='REQUEST_ONLY',monetary_cap_explicitly_waived=True,plan_hash=digest(plan),user_approval_verbatim='Original explicit fixture')
        calls=[]
        def provider(m,f,p):calls.append(1);return '{}',dict(input_tokens=1,output_tokens=1,total_tokens=2)
        extended=dict(plan,planned_requests=2)
        approved=dict(auth,provider_requests=2,plan_hash=digest(extended),extends_authorization_hash=digest(auth),extends_plan_hash=auth['plan_hash'],user_approval_verbatim='Explicit extension fixture')
        with TemporaryDirectory() as t:
            original=Dispatcher(t,plan,authorization=auth,provider=provider,mode='LIVE');original.call('one',[('human','fixture')])
            with closing(sqlite3.connect(original.db)) as db:before=db.execute('SELECT identity FROM policy').fetchone()[0]
            with self.assertRaises(ValueError):Dispatcher(t,extended,authorization=dict(approved,extends_authorization_hash='unrelated'),provider=provider,mode='LIVE')
            newer=Dispatcher(t,extended,authorization=approved,provider=provider,mode='LIVE');newer.call('two',[('human','fixture')])
            with self.assertRaisesRegex(RuntimeError,'cap exceeded'):newer.call('three',[('human','fixture')])
            self.assertEqual(len(calls),2);self.assertEqual(newer.summary()['paid_requests'],2)
            with closing(sqlite3.connect(newer.db)) as db:
                self.assertEqual(db.execute('SELECT identity FROM policy').fetchone()[0],before)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM policy_extensions').fetchone()[0],1)
            Dispatcher(t,extended,authorization=approved,provider=provider,mode='LIVE')

    def test_diagnosed_unknown_stays_counted_and_original_cannot_replay(self):
        plan=dict(authorization_scope='NETWORK_FIXTURE',planned_requests=2,proposed_cny_cap=None,budget_mode='REQUEST_ONLY',allowed_call_ids=['one','two','three'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
        auth=dict(scope='NETWORK_FIXTURE',provider_requests=2,cny=None,budget_mode='REQUEST_ONLY',monetary_cap_explicitly_waived=True,plan_hash=digest(plan),user_approval_verbatim='Explicit fixture cap')
        def failed(m,f,p):raise ConnectionError('Explicit offline DNS fixture')
        with TemporaryDirectory() as t:
            d=Dispatcher(t,plan,authorization=auth,provider=failed,mode='LIVE')
            with self.assertRaises(ConnectionError):d.call('one',[('human','fixture')])
            d.acknowledge_unknown_transport('one',reason='Diagnosed fixture, no assertion of no charge',evidence={'offline_fixture':True})
            with self.assertRaisesRegex(RuntimeError,'UNKNOWN_DO_NOT_RETRY'):d.call('one',[('human','fixture')])
            d.provider=lambda m,f,p:('{}',dict(input_tokens=1,output_tokens=1,total_tokens=2))
            d.call('two',[('human','different explicit assessment')])
            self.assertEqual(d.summary()['states'],{'COMPLETED':1,'UNKNOWN_COUNTED_NO_REPLAY':1})
            with self.assertRaisesRegex(RuntimeError,'cap exceeded'):d.call('three',[('human','fixture')])
    def test_planner_transport_does_not_permit_catalogue_as_customer_evidence(self):
        e=mail('Please cancel the installation service, keeping Friday delivery.')
        schema=transport_schema(e,dict(issues=[dict(issue_id='I1')]))
        self.assertEqual(schema['properties']['goals']['items']['items']['type'],'string')
        raw=dict(goals=[['S2','Check removal','Check fee status','','order reference','','','','','','']],actions=[],customer_reported_fact_ids=[],internal_constraints=[])
        restored=parse_plan(json.dumps(raw),e,dict(issues=[dict(issue_id='I1')]))
        self.assertEqual(restored['goals'][0]['source_quote'],e.body)
        raw['goals'][0][0]='CATALOGUE1'
        with self.assertRaisesRegex(ValueError,'Foreign goal'):parse_plan(json.dumps(raw),e,dict(issues=[]))
    def test_optional_service_fee_work_is_real_plan_content(self):
        for body in ['I did not select assembly. Can it be removed without changing delivery?', '请取消安装服务，但保留原配送日。']:
            e=mail(body);actions=service.reconcile_plan(e,[])
            self.assertTrue(any('已收款退费' in a['goal'] and '未收款' in a['goal'] for a in actions))
            brief=service.composition_brief(e,dict(events=[]))
            profile=next(t for t in brief['service_checks']['topics'] if t['topic']=='optional_service_removal')
            self.assertIn('refund/credit',profile['possible_solutions'])
        self.assertEqual(service.reconcile_plan(mail('How long does assembly take?'),[]),[])
    def test_contact_assertion_is_not_supported_by_local_creation(self):
        e=mail('Please ask the repair desk whether my removed part can be returned.')
        actions=[dict(kind='aftersales_request',issue_ids=[],goal='Verify repair removed part return',evidence=[e.body],priority='normal')]
        with TemporaryDirectory() as t:runtime=service.execute(e,actions,Path(t)/'actions.sqlite3')
        for text in ['We have asked the repair desk to return your removed part.', '已向维修台咨询旧件退回。']:
            audit=judge.audit_slot(slot(e,text,runtime),e)
            self.assertTrue(any(f['severity']=='block' for f in audit['findings']),audit)
        for text in ['We have not asked the repair desk yet.', 'If we have asked the repair desk, its answer would still need verification.', 'An internal aftersales verification request has been created and is pending.']:
            audit=judge.audit_slot(slot(e,text,runtime),e)
            self.assertFalse([f for f in audit['findings'] if f['severity']=='block'],audit)
    def test_two_named_checks_in_one_sentence_are_distinct(self):
        e=mail("The notice includes someone else's phone number. My parcel is missing.")
        with TemporaryDirectory() as t:runtime=service.execute(e,service.plan_actions(None,email=e),Path(t)/'actions.sqlite3')
        text='Both matters have been logged internally and are pending: one for the privacy review and one for the logistics check.'
        checks=service.audit_reply(e,text,runtime)['customer_informed_of_actions']
        self.assertEqual([c['status'] for c in checks],['DISCLOSED','DISCLOSED'])
        checks=service.audit_reply(e,'One request covering privacy and logistics has been created.',runtime)['customer_informed_of_actions']
        self.assertEqual([c['status'] for c in checks],['MERGED','MERGED'])
        text='An internal privacy verification request and an internal logistics verification request have both been created and are pending.'
        self.assertEqual([c['status'] for c in service.audit_reply(e,text,runtime)['customer_informed_of_actions']],['DISCLOSED','DISCLOSED'])
        text='I have recorded the privacy concern and the missing-parcel check as two separate internal verification requests, both currently pending.'
        self.assertEqual([c['status'] for c in service.audit_reply(e,text,runtime)['customer_informed_of_actions']],['DISCLOSED','DISCLOSED'])
        from src.application.p5b8r4_evidence import claim,support
        full=slot(e,text,runtime);self.assertTrue(support(claim(text,'INTERNAL_CREATED'),dict(events=full['events']),e.input_hash)['supported'])
        incomplete=[x for x in full['events'] if x['kind']!='logistics_followup']
        self.assertFalse(support(claim(text,'INTERNAL_CREATED'),dict(events=incomplete),e.input_hash)['supported'])
    def test_record_verification_does_not_hide_later_real_contact(self):
        e=mail('我昨天给门店发送了确认图，想核查记录。')
        for text in ['为核查已确认的方案和门店记录，请提供订单号。', '此前已发送的记录我们不会要求您重复说明。']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'])
        audit=judge.audit_slot(slot(e,'为核查已确认的方案和门店记录，请提供订单号。我们已联系门店。',{}),e)
        self.assertTrue(any(f['severity']=='block' for f in audit['findings']))
    def test_default_shared_chain_uses_actual_source_bound_tasks(self):
        from src.application.r6u0_workflow import generate
        fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/service_response_r6_regressions.json').read_text('utf8'))['B7-036']
        stages=[]
        def invoke(stage,messages,payload):
            stages.append(stage)
            return dict(raw=json.dumps(fixture['analysis']) if stage=='ANALYSIS' else '{"reply":"很抱歉商品受损，请先不要通电。"}',run_id=stage,metadata=dict(finish_reason='stop'))
        with TemporaryDirectory() as t:
            result=generate(fixture['email'],invoke,t,arms=('GUIDED',))['GUIDED']
            self.assertEqual(stages,['ANALYSIS','GUIDED-REPLY'])
            self.assertIsNone(result['plan_error'])
            self.assertTrue(any(e['status']=='created' for e in result['runtime']['events']))
    def test_interrogative_denial_and_modal_photo_keep_independent_assertion(self):
        e=mail('灯泡还没收到，另请核查商品。')
        for text in ['灯泡是否已有独立运单，需核实。','尚不代表已有人员受理、联系门店。','Keep any photos you may have taken.']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        for text in ['灯泡是否已有独立运单，需核实。我们已联系门店。','不代表已退款，但是我们已联系门店。','Keep any photos you may have taken. We have viewed your photos.']:
            self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
    def test_generic_creation_needs_unique_bound_current_task(self):
        e=mail('Please check the subscription skip rules.')
        actions=[dict(kind='billing_request',issue_ids=[],goal='Verify subscription billing and charge date',evidence=[e.body],priority='normal')]
        with TemporaryDirectory() as t:runtime=service.execute(e,actions,Path(t)/'tasks.sqlite3')
        text='已创建一项内部核查请求'
        self.assertFalse([f for f in judge.audit_slot(slot(e,text,runtime),e)['findings'] if f['severity']=='block'])
        self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'])
        extra=dict(runtime['events'][-1],event_id='other',operation_id='different')
        ambiguous=dict(runtime,events=runtime['events']+[extra])
        self.assertTrue([f for f in judge.audit_slot(slot(e,text,ambiguous),e)['findings'] if f['severity']=='block'])

    def test_negative_secret_and_optional_photo_keep_later_assertions(self):
        e=mail('Please verify this missing item and the payment record.')
        for text in ['Nothing has been dispatched or collected at this stage.','Keep any photos you have taken of the damage.','Share the last four characters there—not the full PIN.']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        for text in ['Nothing has been dispatched, but we have refunded the payment.','Keep any photos you have taken. We have reviewed them and your photos.','I am not certain; send the full PIN by email.']:
            self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)

    def test_creation_scope_excludes_future_questions_and_preservation(self):
        from src.application.p5b8r4_evidence import claim,support
        e=mail('Please link my guest order and keep delivery details unchanged.')
        actions=[dict(kind='support_followup',issue_ids=[],goal='Verify account link and receipt access',evidence=[e.body],priority='normal')]
        with TemporaryDirectory() as t:runtime=service.execute(e,actions,Path(t)/'tasks.sqlite3')
        bound=slot(e,'',runtime)
        text='An internal verification request to link the order, while keeping delivery details as they are, has been created.'
        identity=dict({k:bound[k] for k in ('case_id','run_id','arm','input_hash')},conversation_id=bound['events'][0]['conversation_id'])
        self.assertTrue(support(claim(text,'INTERNAL_CREATED'),dict(events=bound['events'],identity=identity),e.input_hash,strict=True)['supported'])
        self.assertFalse(support(claim('An internal verification request and a delivery have been created.','INTERNAL_CREATED'),dict(events=bound['events']),e.input_hash)['supported'])

    def test_promotion_wording_and_disclaimer_do_not_hide_unsafe_timing(self):
        from src.application.reply_quality_checks import policy_findings
        e=mail('促销页只写周日截止。我想知道以付款授权还是扣款时间为准。')
        self.assertTrue(policy_findings(e,'我无法确认条款，但请在您的所在地时间周日之前下单付款，这样比较保险。',{}))
        self.assertFalse(policy_findings(e,'请先核实截止时区和有效付款事件，不要按当地时间付款来保证折扣。',{}))

    def test_open_whether_and_photo_offer_are_not_completed_facts(self):
        e=mail('我可以拍页码，但还没拍。 Please check the second parcel.')
        for text in ['The check can focus on whether a second parcel was dispatched and what its tracking details are.','您愿意拍摄页码照片会很有帮助。']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        for text in ['The check can focus on whether a parcel was dispatched, but we have refunded it.','您愿意拍摄页码照片。我们已查看照片。']:
            self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)

    def test_generic_registered_task_still_needs_unique_current_receipt(self):
        e=mail('请核实礼品卡的激活和消费记录。')
        with TemporaryDirectory() as t:runtime=service.execute(e,service.reconcile_plan(e,[dict(kind='billing_request',issue_ids=[],goal='核实激活和消费记录',evidence=[e.body],priority='normal')]),Path(t)/'tasks.sqlite3')
        text='任务已登记'
        self.assertFalse([f for f in judge.audit_slot(slot(e,text,runtime),e)['findings'] if f['severity']=='block'])
        self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'])

    def test_pending_adverb_and_no_duplicate_constraint_reach_actual_task(self):
        e=mail("Another person's phone number appears. My parcel is missing.")
        with TemporaryDirectory() as t:runtime=service.execute(e,service.plan_actions(None,email=e),Path(t)/'tasks.sqlite3')
        text='An internal logistics verification request has been created. An internal verification request covering the privacy concern is also pending.'
        self.assertEqual([x['status'] for x in service.audit_reply(e,text,runtime)['customer_informed_of_actions']],['DISCLOSED','DISCLOSED'])
        e=mail('The bulb is missing; do not resend the lamp.')
        actions=service.reconcile_plan(e,[dict(kind='logistics_followup',issue_ids=[],goal='Check missing bulb shipment',evidence=[e.body],priority='normal')])
        self.assertTrue(any('no duplicate dispatch' in x['goal'] and e.body in x['evidence'] for x in actions))

    def test_rather_than_secret_refusal_does_not_hide_later_intake(self):
        e=mail('Please check the gift card transaction. I can share the last four characters through a secure channel, not the full PIN.')
        for text in ['I understand you can share the last four characters through a secure channel rather than the full PIN.','Send a redacted receipt instead of the full PIN.']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        self.assertTrue([f for f in judge.audit_slot(slot(e,'Send a redacted receipt rather than the full PIN, but email the PIN separately.',{}),e)['findings'] if f['severity']=='block'])
        brief=service.composition_brief(e,dict(events=[]))
        self.assertTrue(any(k['topic']=='customer chosen secure intake' and 'Do not ask for the last-four' in k['advice'] for k in brief['knowledge']))

    def test_partial_bundle_money_is_scoped_to_a_partial_resolution(self):
        e=mail('组合装里一个收纳盒有裂纹，其他两个想留下。能核对单独换件或部分退货吗？')
        actions=service.reconcile_plan(e,[])
        self.assertTrue(any('实际付款' in x['goal'] and '退款' in x['goal'] and '保留' in x['goal'] for x in actions))
        other=mail('Does this bundle contain three boxes? I have not ordered.')
        self.assertFalse(any('paid-price' in x['goal'] for x in service.reconcile_plan(other,[])))

    def test_text_constraint_is_not_a_second_executable_remedy(self):
        e=mail('请核对商品缺少防滑垫的问题，别把这句话当成已执行记录。')
        actions=[dict(kind='aftersales_request',issue_ids=[],goal='核对商品缺少防滑垫的问题',evidence=[e.body],priority='normal'),dict(kind='support_followup',issue_ids=[],goal='别把这句话当成已执行记录',evidence=[e.body],priority='normal')]
        result=service.reconcile_plan(e,actions)
        self.assertEqual([x['kind'] for x in result],['aftersales_request'])
        combined=dict(actions[1],goal='核实订单退款状态，不要把这句话当成已执行记录')
        self.assertTrue(any('退款' in x['goal'] for x in service.reconcile_plan(e,[combined])))

    def test_registered_reference_needs_supported_same_paragraph_antecedent(self):
        e=mail('请核实商品配件和另一项账单。')
        actions=[dict(kind='aftersales_request',issue_ids=[],goal='核实售后配件',evidence=[e.body],priority='normal'),dict(kind='billing_request',issue_ids=[],goal='核实账单费用',evidence=[e.body],priority='normal')]
        with TemporaryDirectory() as t:runtime=service.execute(e,actions,Path(t)/'tasks.sqlite3')
        good='已创建售后核实请求，目前待处理。这仅表示内部请求已登记。'
        self.assertFalse([f for f in judge.audit_slot(slot(e,good,runtime),e)['findings'] if f['severity']=='block'])
        for text in ['请求已登记。','已创建售后核实请求，目前待处理。\n\n请求已登记。',good+'我们已退款。']:
            self.assertTrue([f for f in judge.audit_slot(slot(e,text,runtime),e)['findings'] if f['severity']=='block'],text)

    def test_first_reply_wire_requires_obligation_but_preserves_old_raw_compatibility(self):
        from src.evaluation.p5b8r4_judge import quote_inventory
        import copy
        e=mail('Could you verify the product label?');s=dict(slot(e,'Please provide the product reference so the official label can be checked.',{}),slot='X')
        s['deterministic_fact_audit']=judge.audit_slot(s,e);s['quote_inventory']=quote_inventory(e,s)
        payload=dict(customer=e.model_dump(),answers=[s],judge_version=judge.LEGACY_VERSION)
        rq=s['quote_inventory']['reply'][0]['ref'];cq=s['quote_inventory']['customer'][1]['ref']
        answer=dict(scores={d:2 for d in judge.DIMENSIONS},reasons={d:'Explicit fixture reason' for d in judge.DIMENSIONS},findings=[],action_evidence=[],score_evidence={d:rq for d in judge.DIMENSIONS},checks=[dict(goal='Verify product label',source_quote=cq,status='COVERED',reply_quote=rq,consequence='Obtain one missing product reference before checking the actual label')])
        wire=dict(X=answer,preference='UNKNOWN')
        with self.assertRaisesRegex(ValueError,'first-reply obligation'):judge.parse(copy.deepcopy(wire),payload)
        old=dict(payload,judge_version='old-compact-fixture')
        self.assertEqual(judge.parse(copy.deepcopy(wire),old)['answers'][0]['scores']['helpfulness'],2)
        wire['X']['checks'][0]['reply_obligation']='Request the missing model reference and verify its official label without inventing the result'
        parsed=judge.parse(wire,payload)
        self.assertIn('missing model',parsed['answers'][0]['service_contract']['required_points'][0]['point'])

    def test_property_queries_and_preservation_are_not_other_business_kinds(self):
        from src.application.p5b8r4_evidence import claim,support,domains
        self.assertNotIn('store',domains('preservation of the retained lamp'))
        self.assertIn('store',domains('verify the reservation'))
        for body,kind,goal,text in [
            ('请核对徒步鞋尺码和试穿建议。','human_input_request','提供尺码依据和试穿建议','关于尺码依据与试穿建议的内部咨询请求已创建，待处理。'),
            ('Please check a partial return and price allocation.','aftersales_request','核实费用与退款分配 / verify charge and refund allocation','An internal aftersales verification request covering the charge, refund allocation and preservation of the retained item has been created.')]:
            e=mail(body)
            with TemporaryDirectory() as t:runtime=service.execute(e,[dict(kind=kind,issue_ids=[],goal=goal,evidence=[body],priority='normal')],Path(t)/'tasks.sqlite3')
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,runtime),e)['findings'] if f['severity']=='block'],text)
            self.assertTrue([f for f in judge.audit_slot(slot(e,'We have refunded the payment.',runtime),e)['findings'] if f['severity']=='block'])

    def test_indefinite_relative_photos_and_non_equivalence_preserve_real_claims(self):
        e=mail('No photo has been supplied. 请核查退货。')
        for text in ["You can share any photos you've already taken.",'运单已生成并不等于每个包裹都已获得授权。']:
            self.assertFalse([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        for text in ["We have viewed any photos you've already taken.",'运单已生成并不等于每个包裹都已获得授权，但是我们已退款。']:
            self.assertTrue([f for f in judge.audit_slot(slot(e,text,{}),e)['findings'] if f['severity']=='block'],text)
        for body in ['灯杆和底座退回能各装一箱吗？','Can I return the pole and base, each in its own box?']:
            e=mail(body);actions=service.reconcile_plan(e,[])
            self.assertTrue(any('EACH return parcel' in a['goal'] for a in actions),body)

if __name__=='__main__':unittest.main()
