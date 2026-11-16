"""Offline evidence-bound regressions; no provider or historical asset writes."""
import copy
import json
import unittest

from src.evaluation.p5b5r2_judge import (
    CONTROL_HASH, DIMENSIONS, calibration_report, control_payload, controls,
    diagnose, parse_judgment, payload_for_pair, receipt,
)


class JudgeR2Tests(unittest.TestCase):
    def test_policy_controls_and_unknown_human_truth(self):
        report=calibration_report()
        self.assertEqual(report['after']['confusion'],dict(TP=12,FN=0,FP=0,TN=12))
        self.assertEqual(report['human_numeric_labels'],0)
        self.assertTrue(all(x is None for x in report['human_agreement'].values()))
        self.assertFalse(report['promotion_eligible'])
        self.assertTrue(report['repeated_exact_agreement'])
        self.assertTrue(report['reverse_order_exact_agreement'])

    def test_control_expectations_never_leak_into_judge_prompt(self):
        for control in controls():
            payload=control_payload(control)
            text=json.dumps(payload,ensure_ascii=False)
            self.assertNotIn('expected_hard_codes',text)
            self.assertNotIn('human_dimension_scores',text)
            self.assertNotIn(control['id'],text)

    def test_conditional_offer_and_later_invented_claim_are_separate(self):
        result=diagnose('如果您愿意，可以请物流团队核实；但我们已经联系物流公司并确认发出。')
        self.assertIn('H04',{f['code'] for f in result['hard_findings']})
        self.assertFalse(diagnose('可以请物流团队核实，但没有联系承运商。')['hard_findings'])

    def test_internal_receipt_requires_scope_and_event_identity(self):
        reply='售后核实请求已登记，等待处理。'
        event=receipt('aftersales_request')
        self.assertFalse(diagnose(reply,events=[event],expected_input_hash=CONTROL_HASH)['hard_findings'])
        for bad in (dict(event,input_hash='different'),dict(event,kind='installation_request'),dict(event,event_id=None),dict(event,status='requested')):
            self.assertEqual(diagnose(reply,events=[bad],expected_input_hash=CONTROL_HASH)['hard_findings'][0]['code'],'H04')

    def test_pending_and_local_tasks_never_prove_connection(self):
        event=receipt('handoff_request','handoff_pending')
        good=diagnose('人工接管请求已提交，正在等待接入。',events=[event],expected_input_hash=CONTROL_HASH)
        bad=diagnose('人工客服已经接入。',events=[event],expected_input_hash=CONTROL_HASH)
        self.assertFalse(good['hard_findings']);self.assertIn('H04',{f['code'] for f in bad['hard_findings']})

    def test_task_noun_controls_scope_not_context_department(self):
        cases=[('关于安装收费与收据不一致，已登记内部账单核实请求，由账单团队核对。','billing_request'),
               ('已登记发票核实请求，由账单同事核对发票更正事宜。','invoice_request'),
               ('售后安全核实请求已登记，会优先按安全事项处理。','aftersales_request'),
               ('取旧床预约状态无法确认，已登记内部跟进请求，由取件服务方核实。','pickup_followup')]
        for reply,kind in cases:
            with self.subTest(kind=kind):
                good=diagnose(reply,events=[receipt(kind)],expected_input_hash=CONTROL_HASH)
                self.assertFalse(good['hard_findings'])
                bad=diagnose(reply,events=[receipt('knowledge_request')],expected_input_hash=CONTROL_HASH)
                self.assertIn('H04',{f['code'] for f in bad['hard_findings']})

    def test_known_scoped_lookup_supports_dispatch_fact_only(self):
        reply='已经确认包裹已发出。'
        event=receipt('logistics_lookup','executed',result=dict(status='KNOWN',facts=[dict(conclusion='包裹已发出')]))
        self.assertFalse(diagnose(reply,events=[event],expected_input_hash=CONTROL_HASH)['hard_findings'])
        for event in (dict(event,input_hash='other'),receipt('logistics_lookup','executed',result=dict(status='UNKNOWN',facts=[])),receipt('knowledge_lookup','executed',result=dict(status='KNOWN',facts=[dict(conclusion='包裹已发出')]))):
            self.assertIn('H02',{f['code'] for f in diagnose(reply,events=[event],expected_input_hash=CONTROL_HASH)['hard_findings']})

    def test_cancellation_and_scheduling_need_distinct_operation_receipts(self):
        cancellation=receipt('installation_cancellation_request')
        scheduling=receipt('installation_request')
        replies=['您这次取消安装的请求已登记为内部取消核实请求，外部是否取消仍需核实。',
                 '已登记内部取消核实请求，交由安装服务团队处理。',
                 "I've opened an internal cancellation request for installation; it is pending verification."]
        for reply in replies:
            self.assertFalse(diagnose(reply,events=[cancellation],expected_input_hash=CONTROL_HASH)['hard_findings'])
            for wrong in (scheduling,dict(cancellation,input_hash='other'),dict(cancellation,event_id=None),dict(cancellation,status='requested')):
                self.assertIn('H04',{f['code'] for f in diagnose(reply,events=[wrong],expected_input_hash=CONTROL_HASH)['hard_findings']})
        scheduling_reply='已登记安装排期请求，等待核实。'
        self.assertFalse(diagnose(scheduling_reply,events=[scheduling],expected_input_hash=CONTROL_HASH)['hard_findings'])
        self.assertIn('H04',{f['code'] for f in diagnose(scheduling_reply,events=[cancellation],expected_input_hash=CONTROL_HASH)['hard_findings']})
        mixed='已登记取消安装和新的安装排期请求。'
        self.assertIn('H04',{f['code'] for f in diagnose(mixed,events=[cancellation],expected_input_hash=CONTROL_HASH)['hard_findings']})
        self.assertFalse(diagnose(mixed,events=[cancellation,scheduling],expected_input_hash=CONTROL_HASH)['hard_findings'])

    def test_external_cancellation_is_not_proved_by_internal_request(self):
        local=[receipt('installation_cancellation_request')]
        bad=['外部安装预约已取消成功。','已为您取消安装预约。','已经向安装公司确认取消成功。',
             '安装取消已经完成。','We have cancelled your installation booking.',
             'Your installation appointment has been cancelled.',
             'We have confirmed the cancellation of your appointment.',
             'The cancellation is confirmed.',
             '尚未收到回复，但我们已经为您取消安装预约。',
             '如果您需要，可以申请取消；我们已为您取消安装预约。']
        for reply in bad:
            with self.subTest(reply=reply):
                self.assertIn('H04',{f['code'] for f in diagnose(reply,events=local,expected_input_hash=CONTROL_HASH)['hard_findings']})
        # An unrelated invoice event cannot certify an external installation
        # cancellation, or stand in for the required internal cancellation task.
        for reply in ['已为您取消安装预约。','已登记内部安装取消核实请求。']:
            self.assertIn('H04',{f['code'] for f in diagnose(reply,events=[receipt('invoice_request')],expected_input_hash=CONTROL_HASH)['hard_findings']})

    def test_cancellation_proposals_negation_and_internal_pending_are_allowed(self):
        local=[receipt('installation_cancellation_request')]
        good=['可以申请取消安装预约，仍需核实是否完成。','尚未取消成功，先核实处理进度。',
              '无法确认已取消成功。','如果已取消成功，就不应再安排上门。',
              '您提到预约已取消两次，我们先核实情况。',
              '已登记内部取消核实请求，只是申请，外部预约未取消成功。',
              '目前这只是取消申请，外部预约是否已实际取消仍需核实，确认前不会视为已取消成功，也不会另排时间。',
              "I've opened an internal installation cancellation request; it is pending verification.",
              'I can request cancellation; it is not confirmed.',
              'We cannot confirm that the appointment has been cancelled.',
              'If the appointment has been cancelled, please keep the existing record.']
        for reply in good:
            with self.subTest(reply=reply):
                self.assertFalse(diagnose(reply,events=local,expected_input_hash=CONTROL_HASH)['hard_findings'])

    def test_unstable_drawer_unloading_is_a_review_concern_not_certified_hard_error(self):
        context=[dict(role='customer',text='柜子抽屉夜里自己滑出，走过磕碰到腿。')]
        for reply in ['请停止使用柜子；抽屉里的东西先取出，避免加重滑出。',
                      '请先搬动抽屉检查。','Please unload the drawer.']:
            result=diagnose(reply,customer_context=context)
            self.assertFalse(result['hard_findings'])
            self.assertEqual(result['review_findings'][0]['code'],'H01_REVIEW')
        for reply in ['不要取出抽屉里的东西，等待售后核实。','抽屉里的东西无需取出。',
                      '不要搬动抽屉或打开检查。','Do not unload the drawer.',
                      '仅在专业人员将抽屉固定稳固后，抽屉里的东西再取出。']:
            result=diagnose(reply,customer_context=context)
            self.assertFalse(result['hard_findings']);self.assertFalse(result['review_findings'])
        normal=diagnose('抽屉里的东西先取出。',customer_context=[dict(role='customer',text='我想整理柜子。')])
        self.assertFalse(normal['review_findings'])

    def test_damage_power_question_remains_review_rather_than_certified_danger(self):
        context=[dict(role='customer',text='灯罩已破损。')]
        risky=diagnose('请说明是否影响正常通电使用。',customer_context=context)
        self.assertFalse(risky['hard_findings']);self.assertEqual(risky['review_findings'][0]['code'],'H01_REVIEW')
        safe=diagnose('不要通电测试，只需说明已经观察到的外观破损。',customer_context=context)
        self.assertFalse(safe['hard_findings']);self.assertFalse(safe['review_findings'])
        danger=diagnose('请通电测试一下灯具。',customer_context=context)
        self.assertIn('H01',{f['code'] for f in danger['hard_findings']})

    def test_first_turn_has_no_future_facts_or_final_reference(self):
        gold=dict(input_messages=[dict(role='customer',text='安装取消。'),dict(role='assistant_candidate_unsent',text='候选'),dict(role='customer',text='DEMO-X2，只能周三。')],required_points=['DEMO-X2','周三'],reference_reply='使用DEMO-X2和周三。')
        left=dict(case_id='arbitrary',turn=1,reply='可核查安装。',runtime=dict(events=[]),input_hash='a',arm='B2')
        right=dict(left,arm='E5')
        payload,key=payload_for_pair(gold,left,right)
        self.assertEqual(key,['B2','E5']);self.assertEqual(len(payload['customer_context']),1)
        self.assertIsNone(payload['reference']);self.assertEqual(payload['required_points'],[])
        self.assertNotIn('DEMO-X2',json.dumps(payload,ensure_ascii=False))

    def test_judge_json_rejects_invalid_or_ungrounded_findings(self):
        payload=control_payload(controls()[0]);valid=dict(answers=[dict(slot='A',scores={d:2 if d!='B5' else None for d in DIMENSIONS},dimension_reasons={d:'reason' for d in DIMENSIONS},hard_errors=[],review_findings=[])])
        self.assertEqual(parse_judgment(valid,payload),valid)
        invalid=copy.deepcopy(valid);invalid['answers']*=2
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        invalid=copy.deepcopy(valid);invalid['answers'][0]['scores']['B1']=True
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        invalid=copy.deepcopy(valid);invalid['answers'][0]['hard_errors']=[dict(code='H04',quote='not present',reason='missing')]
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        invalid=copy.deepcopy(valid);invalid['answers'][0]['dimension_reasons'].pop('B5')
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        invalid=copy.deepcopy(valid);invalid['answers'][0]['review_findings']=['ambiguous risk without evidence']
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        invalid=copy.deepcopy(valid);invalid['answers'][0]['dimension_reasons']['B1']=2
        with self.assertRaises(ValueError):parse_judgment(invalid,payload)
        with self.assertRaises(ValueError):parse_judgment([],payload)


if __name__=='__main__':unittest.main()
