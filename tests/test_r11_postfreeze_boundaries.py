"""Newly exposed transfer regressions: offline mapping, no provider or saved-data writes."""
import unittest
from src.domain.contracts import EmailInput
from src.application.reply_guidance import source_topics,strengthen_plan,service_checks

class PostFreezeBoundaries(unittest.TestCase):
    def mail(self,body):return EmailInput(email_id='offline-fixture',subject='Product question',body=body)
    def test_manufacturing_cover_does_not_create_paid_service_task(self):
        for text in ['The care leaflet says not to remove the cover. Is the zip only for assembly?',
                     'My order has a zip for manufacturing assembly. May I remove the cover?',
                     '床垫拉链用于生产装配，不要拆套清洗。能核实吗？',
                     'The assembly instructions say remove the protective cover, not cancel a service.']:
            mail=self.mail(text)
            self.assertNotIn('optional_service_removal',source_topics(mail))
            self.assertFalse(any(a['kind']=='aftersales_request' for a in strengthen_plan(mail,[])))
    def test_actual_optional_fee_removal_keeps_financial_scope(self):
        for text in ['The delivery confirmation includes assembly, which I did not select. Can assembly be removed on its own?',
                     '订单含组装服务，但我没选择。可以单独取消并保留配送日吗？',
                     'The cover is for manufacturing assembly. Separately, cancel my paid assembly service and check its fee.']:
            actions=strengthen_plan(self.mail(text),[])
            fee=[a for a in actions if a['kind']=='aftersales_request']
            self.assertEqual(len(fee),1)
            self.assertIn('refund or billing adjustment if paid',fee[0]['goal'])
    def test_load_profile_reaches_real_verification_task_bilingually(self):
        for text in ['Can a 2300 W extension lead power an 1800 W kettle and 1500 W heater together?',
                     '插线板标2300W，水壶1800W、取暖器1500W，能一起用吗？']:
            mail=self.mail(text);actions=strengthen_plan(mail,[])
            self.assertEqual([a['kind'] for a in actions],['human_input_request'])
            self.assertEqual(set(source_topics(mail)),{'electrical_load_boundary'})
    def test_filter_profile_requires_a_joint_limit_not_any_filter_question(self):
        for text in ['Filter: six months or600litres, whichever comes first; usage uncertain.',
                     '滤芯六个月或600升，以先到者为准，用量未知。']:
            actions=strengthen_plan(self.mail(text),[])
            self.assertEqual(len(actions),1)
            self.assertIn('unknown usage',actions[0]['goal'])
        self.assertFalse(strengthen_plan(self.mail('Can you check the filter colour?'),[]))

    def test_dual_limit_guidance_reuses_current_task_with_omitted_product_noun(self):
        email = self.mail('滤芯六个月或600升，以先到者为准。能解释要跟踪哪个限制吗？')
        initial = dict(kind='human_input_request', goal='核实六个月与600升如何跟踪', issue_ids=['I1'],
                       evidence=['能解释要跟踪哪个限制吗'], priority='normal')
        actions = strengthen_plan(email, [initial])
        self.assertEqual(len(actions), 1)
        self.assertIn('用量未知时不能用最长日历期限代替', actions[0]['goal'])
        self.assertIn('滤芯六个月或600升，以先到者为准', actions[0]['evidence'])
    def test_unrelated_assembly_and_filter_work_do_not_trigger_boundary_checks(self):
        self.assertFalse(source_topics(self.mail('I need assembly instructions and a replacement filter.')))

    def check(self,text):
        from src.application.p5b8r3_final_guard import assess
        return assess(text,dict(events=[]),'offline-input-hash')

    def test_active_and_passive_completed_refund_need_real_receipts(self):
        for text in ['We have completed your refund.','Your refund has been completed.',
                     'We have just processed the refund.','The refund is now complete.']:
            self.assertTrue(any(f['severity']=='block' for f in self.check(text)['findings']),text)
    def test_refund_negation_question_and_internal_request_are_not_completion(self):
        for text in ['We have not completed your refund.','Has your refund been completed?',
                     'If your refund has been completed, please check the bank record.',
                     'We have completed your refund check, with no refund made.',
                     'Your refund request has been completed internally; no payment was made.']:
            self.assertFalse(any(a['state']=='EXTERNAL_COMPLETED' and a.get('supported') is False for a in self.check(text)['assessments']),text)
    def test_quote_or_negative_does_not_hide_later_real_refund_completion(self):
        for text in ['The note says "Your refund has been completed". We have completed your refund.',
                     'We have not contacted the store. Your refund has been completed.']:
            self.assertTrue(any(f['severity']=='block' for f in self.check(text)['findings']),text)

    def test_optional_photo_alternative_preserves_affirmative_media_checks(self):
        from src.application.source_facts import attachment_claim_audit

        email = self.mail('涂料标重750克，页面按每升计覆盖面积。请核实密度。')
        offer = '如产品页面另有规格说明或您已拍摄的标签照片，也可一并提供，以便对照。'
        self.assertEqual(attachment_claim_audit(offer, email)['findings'], [])
        alternate = '如商品页面上列有用量说明或者你已经拍下的铭牌图片，可以补充提供。'
        self.assertEqual(attachment_claim_audit(alternate, email)['findings'], [])

        for reply, expected in (
            ('您已拍摄标签照片。', 'TAKEN'),
            (offer + '我们已查看照片。', 'VIEWED'),
            ('如产品页面另有规格说明或您已拍摄的标签照片，我们已收到照片。', 'RECEIVED'),
        ):
            with self.subTest(reply=reply):
                findings = attachment_claim_audit(reply, email)['findings']
                self.assertIn(expected, {finding['asserted_level'] for finding in findings})

    def test_locker_fee_and_separate_constraint_require_matching_distinct_receipts(self):
        from src.application.p5b8r4_evidence import claim, support
        from src.evaluation.p5b8r3_judge import bind

        email = self.mail('Can you reissue the locker code before collection expires? Do not mark it collected.')
        identity = dict(case_id=email.email_id, conversation_id=email.email_id, run_id='offline-run', arm='GUIDED', input_hash=email.input_hash)

        def event(event_id, goal, status='created', kind='logistics_followup'):
            return dict(event_id=event_id, conversation_id=email.email_id, input_hash=email.input_hash,
                        kind=kind, status=status, payload={'action': {'goal': goal}})

        def check(events, assertion):
            bound = bind(events, **{k: v for k, v in identity.items() if k != 'conversation_id'})
            return support(claim(assertion, 'INTERNAL_CREATED'), dict(identity=identity, events=bound), email.input_hash, strict=True)

        main = event('primary', 'Verify code reissue, extension, charges and approved alternatives before the collection expiry, and do not mark it collected')
        constraint = event('constraint', 'Do not mark the parcel as collected')
        pending = 'An internal logistics verification request covering code reissue, extension, charges and approved alternatives is pending'
        both = pending + ', and a separate pending check records that the parcel must not be marked as collected.'
        self.assertEqual(set(check([main, constraint], both)['event_ids']), {'primary', 'constraint'})
        unrelated = event('unrelated', 'Verify another parcel tracking number')
        self.assertEqual(set(check([main, constraint, unrelated], both)['event_ids']), {'primary', 'constraint'})
        self.assertEqual(check([main], pending)['event_ids'], ['primary'])
        self.assertFalse(check([main], both)['supported'])
        self.assertFalse(check([event('primary', 'Check code reissue and extension'), constraint], both)['supported'])
        self.assertFalse(check([main, event('constraint', 'Do not mark it collected', status='requested')], both)['supported'])
        self.assertFalse(check([main, constraint], pending + ', and a separate billing request covers your outstanding balance')['supported'])
        self.assertFalse(check([main, constraint], pending.replace('charges', 'fees already paid'))['supported'])

    def test_bounded_safety_vetoes_keep_verified_and_negative_phrasing(self):
        from src.application.reply_quality_checks import unresolved_risk_findings

        power = self.mail('插线板额定2300 W。取暖器和热水壶能一起用吗？')
        filter_email = self.mail('滤芯到六个月或600升时更换，以先到者为准。我无法确认升数。')
        currency = self.mail('商品页写港币，购物车变成人民币符号。付款以哪个为准？')
        examples = (
            (power, '不要同时使用。若必须同时使用，请分别接入不同回路或插座。', 'UNVERIFIED_ELECTRIC_WORKAROUND'),
            (power, 'Running the two units one at a time or on separate sockets avoids the overload.', 'UNVERIFIED_ELECTRIC_WORKAROUND'),
            (power, 'Until a qualified electrician confirms the capacity, please use separate sockets.', 'UNVERIFIED_ELECTRIC_WORKAROUND'),
            (power, 'Do not use that lead, and you can run the units on separate sockets.', 'UNVERIFIED_ELECTRIC_WORKAROUND'),
            (filter_email, '若用水量难以统计，则以安装满六个月作为兜底节点。', 'UNVERIFIED_USAGE_FALLBACK'),
            (currency, '建议您以结算页面最终显示的币种和金额为准。', 'UNVERIFIED_CURRENCY_BASIS'),
        )
        for email, reply, code in examples:
            with self.subTest(reply=reply):
                self.assertIn(code, {f['code'] for f in unresolved_risk_findings(email, reply, {})})

        safe = (
            (power, 'Do not use separate sockets as a workaround. Ask a qualified electrician to verify the circuits.'),
            (power, 'Only after a qualified electrician confirms the capacity, you can use separate sockets as specified.'),
            (filter_email, '如果无法确定用水量，请核实累计升数，不能仅以六个月作为兜底。'),
            (currency, '不能以结算页面最终显示的币种为准。请先核实实际结算币种。'),
            (currency, '您提到：“请以结算页面显示的币种为准”。这个说法仍待核实。'),
            (self.mail('Where can I find the checkout currency?'), 'Please rely on the checkout currency for payment.'),
        )
        for email, reply in safe:
            with self.subTest(reply=reply):
                self.assertEqual(unresolved_risk_findings(email, reply, {}), [])

if __name__=='__main__':unittest.main()
