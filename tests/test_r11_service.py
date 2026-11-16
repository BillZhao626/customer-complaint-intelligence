"""Offline semantic boundaries use explicit fixtures, not model-generated Gold."""
import unittest
import json
from pathlib import Path
import tempfile
from src.domain.contracts import EmailInput
from src.application.service_response import brief, audit_reply
from src.application.reply_guidance import service_checks

class ServicePathTests(unittest.TestCase):
    def mail(self,body):return EmailInput(email_id='fixture',subject='Service enquiry',body=body)
    def test_negative_secret_clause_keeps_independent_request(self):
        mail=self.mail('Please check my voucher. It has no time zone.')
        for reply in ('Please share the reference, no PIN or password needed.',
                      'Please share the reference. No PIN is needed.',
                      '请提供订单编号，无需PIN。'):
            self.assertNotIn('SENSITIVE_EMAIL_INTAKE',[f['code'] for f in audit_reply(mail,reply,dict(events=[]))['findings']])
        for reply in ('Please send your PIN.', 'No password is needed, but please send your PIN.'):
            self.assertIn('SENSITIVE_EMAIL_INTAKE',[f['code'] for f in audit_reply(mail,reply,dict(events=[]))['findings']])
    def test_water_visual_checks_do_not_erase_service_path(self):
        mail=self.mail('My water tank leaks. I already reseated it and cleaned the seal.')
        data=brief(mail,dict(events=[]))
        self.assertIsInstance(data['service_checks'],dict)
        checks=data['knowledge'][0]['checks']
        self.assertEqual(next(c for c in checks if c['key']=='tank_seating')['status'],'ALREADY_REPORTED_DONE')
        self.assertIn('path_requirements',data['service_checks'])
    def test_verified_fact_is_current_input_only(self):
        mail=self.mail('What is the outside depth?')
        base=dict(status='KNOWN',facts=[dict(source_id='catalogue',conclusion='Depth 40 cm',authority='AUTHORIZED_FIXTURE',input_hash='foreign')])
        self.assertEqual(service_checks(mail,dict(facts=base))['verified_facts'],[])
    def test_dimensional_arithmetic_preserves_two_axes(self):
        from src.application.service_plan import dimension_comparison
        data=dimension_comparison(self.mail('被套220×240，被芯200×230。'))
        self.assertEqual(data['axis_differences'],['20','10'])
        self.assertEqual(data['centered_margin_per_side'],['10','5'])
    def test_attachment_prerequisite_and_later_assertion_are_separate(self):
        from src.application.source_facts import attachment_claim_audit
        mail=self.mail('Can you help with the cardigan?')
        for reply in ('Avoid heat until the label details have been reviewed. You can reply with the photo.',
                      'Avoid heat until the photo has been reviewed.'):
            self.assertFalse(attachment_claim_audit(reply,mail)['findings'])
        self.assertTrue(attachment_claim_audit('Avoid heat until the photo has been reviewed. We have seen your photo.',mail)['findings'])
    def test_real_orchestrator_passes_validated_service_goals_to_composer(self):
        from src.application.r6u0_workflow import generate
        from src.application import service_response
        fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/service_response_r6_regressions.json').read_text('utf8'))['B7-036']
        email=EmailInput.model_validate(fixture['email']);analysis=fixture['analysis'];calls=[]
        actions=service_response.plan_actions(analysis,email=email)
        plan=dict(goals=[dict(goal='Check the reported damage',source_quote=email.body,
                  response_points=['Check inspection and shipment handling'],preserve_constraints=[],minimum_lookup=['Missing order reference'],interim_options=['Do not power damaged electrical equipment'],decision_dependencies=dict(scope=[],timing=[],cost=[],authorization=[],source=[]))],actions=actions,customer_reported_fact_ids=['S2'],internal_constraints=[])
        def invoke(stage,messages,payload):
            calls.append((stage,messages))
            raw=json.dumps(analysis) if stage=='ANALYSIS' else json.dumps(plan) if stage=='GUIDED-PLAN' else '{"reply":"很抱歉商品受损，请先不要通电。"}'
            return dict(raw=raw,run_id=stage,metadata=dict(finish_reason='stop'))
        with tempfile.TemporaryDirectory() as tmp:
            record=generate(fixture['email'],invoke,tmp,arms=('GUIDED',),semantic_planning=True)['GUIDED']
            self.assertEqual([s for s,m in calls],['ANALYSIS','GUIDED-PLAN','GUIDED-REPLY'])
            payload=json.loads(calls[-1][1][1][1])
            self.assertEqual(payload['service_brief']['service_goals'],[{k:v for k,v in g.items() if k!='preserve_constraints'} for g in plan['goals']])
            self.assertEqual(record['service_brief'],payload['service_brief'])
            self.assertIsNone(record['plan_error'])
            self.assertEqual(record['runtime']['service_plan']['customer_reported_fact_ids'],['S2'])
            self.assertTrue(all(q in email.subject+'\n'+email.body for q in record['runtime']['service_plan']['customer_reported_facts']))
            self.assertTrue(any(e['status']=='created' for e in record['runtime']['events']))
    def test_lookup_prerequisite_is_not_a_second_task_for_same_issue(self):
        from src.application.service_response import reconcile_plan
        email=self.mail('The stool is uneven. Please check the purchase record and available remedy.')
        base=dict(issue_ids=['I1'],evidence=[email.body],priority='normal')
        actions=[dict(base,kind='aftersales_request',goal='Check purchase and remedy'),dict(base,kind='clarification_request',goal='Obtain missing lookup reference')]
        final=reconcile_plan(email,actions)
        self.assertEqual(len(final),1)
        self.assertEqual(final[0]['kind'],'aftersales_request')
    def test_praise_only_goal_cannot_authorize_an_unsolicited_relay(self):
        from src.application.service_plan import enforce_scope
        email=self.mail('Your colleague was helpful. The stool is uneven.')
        value=dict(goals=[dict(source_quote='Your colleague was helpful.',goal='Relay praise'),dict(source_quote='The stool is uneven.',goal='Check stool')],actions=[])
        analysis=dict(issues=[dict(issue_kind='praise',evidence=['Your colleague was helpful.']),dict(issue_kind='complaint',evidence=['The stool is uneven.'])])
        result,exclusions=enforce_scope(value,email,analysis)
        self.assertEqual([g['goal'] for g in result['goals']],['Check stool'])
        self.assertEqual(len(exclusions),1)
    def test_relay_authorization_is_independent_of_proposed_task_kind(self):
        from src.application.service_response import reconcile_plan
        email=self.mail('Your colleague was helpful. The stool is uneven.')
        a=dict(kind='support_followup',issue_ids=['I2'],goal="Pass along the customer's praise to the staff",evidence=['Your colleague was helpful.'],priority='normal')
        self.assertEqual(reconcile_plan(email,[a]),[])
        requested=self.mail('Please pass my thanks to the staff.')
        a.update(evidence=[requested.body])
        self.assertEqual(reconcile_plan(requested,[a])[0]['kind'],'store_service_request')
    def test_business_record_noun_does_not_make_conditional_check_a_callback(self):
        from src.application.p5b8r3_final_guard import assess
        runtime=dict(events=[],future_intent_policy='owner-nonrigid-v1')
        plain='收到订单号后，我们会据此核对官方结算记录，再告知适用币种。'
        self.assertFalse(any(f['code']=='H03' and f['severity']=='block' for f in assess(plain,runtime,'h')['findings']))
        hard='我们会核对官方结算记录，保证明天回复您。'
        self.assertTrue(any(f['code']=='H03' and f['severity']=='block' for f in assess(hard,runtime,'h')['findings']))
        mixed=plain+'我们已经退款。'
        self.assertTrue(any(f['severity']=='block' for f in assess(mixed,runtime,'h')['findings']))
    def test_open_questions_denials_and_reports_do_not_hide_later_execution(self):
        from src.application.p5b8r3_final_guard import assess
        runtime=dict(events=[],future_intent_policy='owner-nonrigid-v1')
        good=['核对结果会明确退款是否已发起以及目前所处环节。',
              '我们不会据此认定退款已完成。',
              '这句话不作为已联系门店的执行记录。',
              '您反馈的情况我们已收到：台灯已送达，灯泡尚未收到。',
              'We will check whether the refund has been completed.']
        for reply in good:
            self.assertFalse(any(f['severity']=='block' for f in assess(reply,runtime,'h')['findings']),reply)
        for reply in (good[0]+'但我们已经退款。',good[1]+'我们已经退款。',
                      '您反馈台灯已到货，但我们已经退款。',
                      'This is not proof that a refund was completed, but we have refunded you.'):
            self.assertTrue(any(f['severity']=='block' for f in assess(reply,runtime,'h')['findings']),reply)
    def test_task_creation_scope_excludes_recording_and_customer_context(self):
        from src.application.p5b8r3_final_guard import assess
        event=lambda key,kind:dict(event_id=key,input_hash='h',kind=kind,status='created',payload=dict(action=dict(goal='核实暂停订阅规则与扣款日期')))
        rt=dict(events=[event('support','support_followup'),event('bill','billing_request')],future_intent_policy='owner-nonrigid-v1')
        reply='您希望暂停一次配送，这个需求我已记录，并已创建内部核实请求和收费核查请求，均待处理。'
        self.assertFalse(any(f['severity']=='block' for f in assess(reply,rt,'h')['findings']))
        self.assertTrue(any(f['severity']=='block' for f in assess(reply,dict(events=[]),'h')['findings']))
    def test_one_subscription_goal_has_one_billing_owner(self):
        from src.application.service_response import reconcile_plan
        email=self.mail('咖啡豆定期配送想暂停下个月一次，不想取消后面所有月份。下一次扣款日期还不清楚，请先核对暂停规则和生效范围。')
        action=dict(kind='support_followup',issue_ids=['I1'],goal='核实订阅暂停规则和下一次扣款日期',evidence=[email.body],priority='normal')
        final=reconcile_plan(email,[action])
        self.assertEqual(len(final),1);self.assertEqual(final[0]['kind'],'billing_request')
    def test_planned_customer_fact_reference_preserves_original_and_rejects_unknown_id(self):
        from src.application.service_plan import parse,source_units
        email=self.mail('The item arrived green. Could you exchange it?')
        units=source_units(email)
        value=dict(goals=[],actions=[],customer_reported_fact_ids=[units[1]['id']],internal_constraints=[])
        result=parse(json.dumps(value),email,dict(issues=[]))
        self.assertEqual(result['customer_reported_facts'],[units[1]['quote']])
        self.assertIn(result['customer_reported_facts'][0],email.body)
        value['customer_reported_fact_ids']=['S999']
        with self.assertRaises(ValueError):parse(json.dumps(value),email,dict(issues=[]))
    def test_invalid_service_plan_is_not_a_successful_product_run(self):
        from src.application.r6u0_workflow import generate,product_run
        fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/service_response_r6_regressions.json').read_text('utf8'))['B7-036']
        def invoke(stage,messages,payload):
            return dict(raw=json.dumps(fixture['analysis']) if stage=='ANALYSIS' else '{"actions":[]}' if stage=='GUIDED-PLAN' else '{"reply":"很抱歉，请暂停使用。"}',run_id=stage,elapsed_ms=1,metadata=dict(finish_reason='stop',dispatch_at='2026-11-09T10:00:00+00:00'))
        with tempfile.TemporaryDirectory() as tmp:
            r=generate(fixture['email'],invoke,tmp,arms=('GUIDED',),semantic_planning=True)['GUIDED']
            self.assertTrue(r['plan_error'])
            self.assertNotEqual(product_run(r).status,'succeeded')
            self.assertTrue(any(e['status']=='created' for e in r['runtime']['events']))
            self.assertEqual(r['runtime']['planning_fallback'],'DETERMINISTIC_SOURCE_BOUND_REVIEW_REQUIRED')

if __name__=='__main__':unittest.main()
