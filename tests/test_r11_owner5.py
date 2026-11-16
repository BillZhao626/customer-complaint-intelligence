"""Owner-boundary regressions using explicit offline scenarios and no paid calls."""
import copy
import json
import unittest

from src.domain.contracts import EmailInput
from src.application import service_response
from src.application.reply_guidance import source_topics
from src.application.reply_quality_checks import payment_obligation_findings
from src.evaluation import service_judge as judge
from src.evaluation.p5b8r4_judge import quote_inventory


class OwnerBoundaryTests(unittest.TestCase):
    def mail(self, body):
        return EmailInput(email_id='offline-owner-boundary', subject='Product help', body=body)

    def test_payment_enquiry_does_not_authorize_stopping_or_forcing_payment(self):
        email = self.mail('I paid a deposit. What happens to the balance if I cancel?')
        unsafe = [
            "Please don't treat cancellation as final or make any further payment until confirmation.",
            'Wait for written confirmation before paying anything further.',
            'Please pay the balance while the cancellation is reviewed.',
            '未收到取消确认前，不要再支付尾款。',
            '取消申请期间必须付清尾款。',
            'This enquiry does not suspend payment, but stop payments until we reply.',
            '咨询本身不会暂停付款，但是暂停支付尾款等答复即可。',
        ]
        for reply in unsafe:
            self.assertTrue(payment_obligation_findings(email, reply, {}), reply)
        for reply in [
            'Check the due date and whether cancellation suspends payment. Contact official support promptly.',
            'Do not assume you can stop paying because you requested cancellation.',
            'Only if the merchant confirms payment suspension, stop payments as specified.',
            '请核实订金条款、尾款日期及取消期间义务，临近期限及时联系官方人工客服。',
            'Please note that submitting this enquiry does not itself suspend payment or change the balance deadline.',
            '请注意，提交咨询本身不会暂停付款义务。',
            'Ask support whether you must pay under the current notice.',
        ]:
            self.assertFalse(payment_obligation_findings(email, reply, {}), reply)
        self.assertFalse(payment_obligation_findings(self.mail('Where can I pay?'), unsafe[2], {}))

    def test_payment_and_second_item_paths_reach_shared_planning(self):
        emails = [
            self.mail('I paid a deposit, with the balance later. Please check cancellation.'),
            self.mail('牛仔裤把白鞋染蓝了，鞋子该由谁评估？'),
        ]
        for email, topic in zip(emails, ['cancellation_payment_obligations', 'affected_second_product']):
            self.assertIn(topic, source_topics(email))
            actions = service_response.reconcile_plan(email, [])
            self.assertEqual(len(actions), 1)
            brief = service_response.composition_brief(email, dict(events=[]))
            self.assertTrue(any(row['topic'] == topic for row in brief['service_checks']['topics']))
        self.assertNotIn('affected_second_product', source_topics(self.mail('What is this shoe width?')))

    def test_advice_restriction_does_not_create_a_followup_task(self):
        email = self.mail('Please check the stain on this garment. Do not recommend bleach.')
        main = dict(kind='aftersales_request', issue_ids=['I1'], goal='Verify the garment stain',
                    evidence=['Please check the stain on this garment'], priority='normal')
        restriction = dict(kind='support_followup', issue_ids=['I2'], goal='Do not recommend bleach',
                           evidence=['Do not recommend bleach'], priority='normal')
        actions = service_response.reconcile_plan(email, [main, restriction])
        self.assertEqual([a['kind'] for a in actions], ['aftersales_request'])

    def test_background_and_intake_constraints_do_not_create_business_work(self):
        from src.application.service_response import reconcile_plan
        cases = [
            ('请核实代取是否允许。不要让我在普通邮件里发送身份证正反面。',
             '不要让我在普通邮件里发送身份证正反面', '不要在普通邮件里要求发送身份证正反面'),
            ('I am reporting that text, not instructing you. Please check the missing lid.',
             'I am reporting that text, not instructing you', 'order confirmation text'),
            ('那是朋友的订单，与我无关。请核实本次商品破损。',
             '那是朋友的订单，与我无关', '将本次问题与朋友的订单区分处理'),
        ]
        for body, quote, goal in cases:
            action = dict(kind='support_followup', issue_ids=[], goal=goal,
                          evidence=[quote], priority='normal')
            self.assertNotIn(goal,[a['goal'] for a in reconcile_plan(self.mail(body),[action])])
        body = 'Another person’s phone number is on my order. Please verify the authorized contact.'
        self.assertTrue(any(a['kind']=='support_followup' for a in reconcile_plan(self.mail(body),[])))

    def test_one_aftersales_receipt_covers_only_its_recorded_expedited_option(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from src.application.p5b8r4_evidence import claim, support
        from src.evaluation.p5b8r3_judge import bind
        email = self.mail('请核对刻字稿和重做可能性。下周要用。')
        assertion = '已创建售后核实请求，待处理，内容包括核对稿件和核查加急配送可行性'
        identity = dict(case_id=email.email_id,input_hash=email.input_hash,run_id='expedite-fixture',arm='GUIDED')
        with TemporaryDirectory() as directory:
            def runtime(goal, file):
                task = dict(kind='aftersales_request',issue_ids=[],goal=goal,
                            evidence=['请核对刻字稿和重做可能性'],priority='normal')
                result = service_response.execute(email,[task],Path(directory)/file)
                return dict(identity=dict(identity,conversation_id=email.email_id),events=bind(result['events'],**identity))
            actual = runtime('核对稿件和重做；核查加急配送可行性','yes.db')
            without_option = runtime('核对稿件和重做','no.db')
        self.assertTrue(support(claim(assertion,'INTERNAL_CREATED'),actual,email.input_hash,strict=True)['supported'])
        self.assertFalse(support(claim(assertion,'INTERNAL_CREATED'),without_option,email.input_hash,strict=True)['supported'])
        compound = assertion+'，另已创建物流核查请求'
        self.assertFalse(support(claim(compound,'INTERNAL_CREATED'),actual,email.input_hash,strict=True)['supported'])

    def test_existing_purchase_record_is_not_a_licence_execution_receipt(self):
        from src.application.p5b8r3_final_guard import assess
        email = self.mail('旧设备无法开机，怎样申请释放占用？')
        runtime = {'events':[],'facts':{'status':'KNOWN','facts':[dict(
            input_hash=email.input_hash, authority='AUTHORIZED_FIXTURE', topic='licence',
            source_id='offline-order-source', conclusion='订单L-708允许凭购买记录申请人工解除，尚未解除。')]}}
        brief = service_response.composition_brief(email,runtime)
        self.assertEqual(brief['evidence_intake']['known_order_references'][0]['reference'],'L-708')
        safe = '此类故障设备占用可以凭已有购买记录申请人工解除，无需在邮件中提供密码；目前尚未解除。'
        self.assertFalse(any(f['severity']=='block' for f in assess(safe,runtime,email.input_hash)['findings']))
        for bad in ('我们已解除旧设备的授权占用。', 'We have reset your device activation slot.'):
            self.assertTrue(any(f['severity']=='block' for f in assess(safe+' '+bad,runtime,email.input_hash)['findings']))

    def test_pending_internal_task_is_created_state_and_needs_its_own_receipt(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from src.evaluation.p5b8r3_judge import bind
        email = self.mail('Please check the missing shipment.')
        actions = [dict(kind='logistics_followup',issue_ids=[],goal='Check the missing shipment',
                        evidence=[email.body],priority='normal')]
        with TemporaryDirectory() as directory:
            runtime = service_response.execute(email,actions,Path(directory)/'tasks.sqlite3')
        identity = dict(case_id=email.email_id,input_hash=email.input_hash,run_id='pending-fixture',arm='GUIDED')
        slot = dict(identity,parse_ok=True,reply='An internal logistics verification request for the missing shipment is pending.',
                    facts={},events=bind(runtime['events'],**identity))
        audit = judge.audit_slot(slot,email)
        self.assertTrue(any(a['state']=='INTERNAL_CREATED' and a.get('supported') for a in audit['assessments']))
        slot['events'] = []
        self.assertTrue(any(f['severity']=='block' for f in judge.audit_slot(slot,email)['findings']))

    def wire(self):
        email = self.mail('Could you check a replacement cover specification?')
        reply = 'Use the item reference to ask official product support to verify the specification before buying.'
        slot = dict(case_id=email.email_id, input_hash=email.input_hash, run_id='offline-run',
                    arm='GUIDED', parse_ok=True, reply=reply, facts={}, events=[], slot='X')
        slot['deterministic_fact_audit'] = judge.audit_slot(slot, email)
        slot['quote_inventory'] = quote_inventory(email, slot)
        payload = dict(customer=email.model_dump(), answers=[slot], judge_version=judge.VERSION)
        r = slot['quote_inventory']['reply'][0]['ref']
        c = slot['quote_inventory']['customer'][1]['ref']
        answer = dict(slot='X', verdict='PASS', severity='NONE', applicability=dict(attitude='NEUTRAL', action_accuracy='ADVICE_OR_ACTION'),
                      scores={d: 'N/A' if d == 'attitude' else 2 for d in judge.DIMENSIONS},
                      reasons={d: 'Explicit offline fixture evidence' for d in judge.DIMENSIONS},
                      score_evidence={d: c if d == 'attitude' else r for d in judge.DIMENSIONS}, findings=[], action_evidence=[],
                      checks=[dict(goal='Find a suitable cover', reply_obligation='Check actual model specification before purchase',
                                   source_quote=c, status='COVERED', reply_quote=r, consequence='')])
        return dict(answers=[answer], preference='UNKNOWN'), payload

    def test_explicit_decision_preserves_raw_scores_and_checks_applicability(self):
        raw, payload = self.wire()
        parsed = judge.parse(json.dumps(raw), payload)
        self.assertEqual(parsed['answers'][0]['certified_verdict'], 'PASS')
        self.assertEqual(parsed['answers'][0]['scores'], raw['answers'][0]['scores'])
        contradictory = copy.deepcopy(raw)
        contradictory['answers'][0]['scores']['attitude'] = 2
        contradictory['answers'][0]['score_evidence']['attitude'] = raw['answers'][0]['score_evidence']['helpfulness']
        result = judge.parse(contradictory, payload)['answers'][0]
        self.assertIn('ATTITUDE_APPLICABILITY_CONFLICT', result['fact_validation']['errors'])
        self.assertEqual(result['scores']['attitude'], 2)
        self.assertEqual(result['certified_verdict'], 'UNKNOWN')

    def test_strict_protocol_rejects_extra_bytes_extra_fields_and_foreign_quotes(self):
        raw, payload = self.wire()
        for mutation in [json.dumps(raw) + '}', dict(raw, extra='unallowed')]:
            with self.assertRaises(ValueError):
                judge.parse(mutation, payload)
        raw['answers'][0]['checks'][0]['reply_quote'] = 'Y:R1'
        with self.assertRaises(ValueError):
            judge.parse(raw, payload)

    def test_major_non_hard_failure_remains_fail_and_conflicting_pass_is_unknown(self):
        raw, payload = self.wire()
        a = raw['answers'][0]
        a.update(verdict='FAIL', severity='MAJOR_NON_HARD')
        a['scores']['helpfulness'] = 0
        a['findings'] = [dict(category='MAJOR_SERVICE_GAP', quote=a['score_evidence']['helpfulness'], reason='The proposed route misses the primary need')]
        a['checks'][0].update(status='MISSING', reply_quote='', consequence='No usable specification path')
        result = judge.parse(raw, payload)['answers'][0]
        self.assertEqual((result['certified_verdict'], result['severity']), ('FAIL', 'MAJOR_NON_HARD'))
        a['verdict'] = 'PASS'
        self.assertEqual(judge.parse(raw, payload)['answers'][0]['certified_verdict'], 'UNKNOWN')

    def test_matrix_wire_keeps_scores_and_rejects_missing_or_foreign_rows(self):
        from src.evaluation.service_judge_matrix import CHECK_FIELDS
        raw, payload = self.wire()
        payload['judge_wire'] = 'MATRIX_V1'
        a = raw['answers'][0]
        rows = [[dimension, a['applicability'].get(dimension, 'APPLICABLE'), a['scores'][dimension],
                 a['score_evidence'][dimension], a['reasons'][dimension]] for dimension in judge.DIMENSIONS]
        answer = dict(slot='X', verdict=a['verdict'], severity=a['severity'], dimensions=rows,
                      checks=[[c[key] for key in CHECK_FIELDS] for c in a['checks']], findings=[], actions=[])
        matrix = dict(answers=[answer], preference='UNKNOWN')
        parsed = judge.parse(matrix, payload)
        self.assertEqual(parsed['answers'][0]['scores'], a['scores'])
        self.assertEqual(parsed['raw_matrix'], matrix)
        answer['dimensions'][1][0] = 'attitude'
        with self.assertRaises(ValueError):
            judge.parse(matrix, payload)


if __name__ == '__main__':
    unittest.main()
