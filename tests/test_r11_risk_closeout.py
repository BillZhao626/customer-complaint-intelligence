"""Offline release checks with invented examples and temporary task receipts."""
import unittest

from src.application.service_response import audit_reply, composition_brief, reconcile_plan
from src.domain.contracts import EmailInput


SYNC_EN = 'Does deleting a file from cloud sync remove the remote copy? I need to clear space.'
SYNC_ZH = '电脑上删文件会不会一起删掉云端副本？我想清理空间。'
CARD_EN = 'My gift card shows used. Can you verify the activation and transactions?'
CARD_ZH = '礼品卡首次使用就提示已兑换，请核对激活记录。'
NEUTRAL = 'Please verify the number on my invoice.'
PAGES_EN = 'The manual skips from page 18 to 25. Could you check the printing?'
PAGES_ZH = '说明书从第１８页跳到第２５页了，能核对一下吗？'
TARIFF_ZH = '抄表区间和费率变更日期不一致，能先核对分段读数吗？'
SYNC = 'UNVERIFIED_SYNC_MUTATION'
SECRET = 'SENSITIVE_EMAIL_INTAKE'
PAGE = 'SOURCE_PAGE_RANGE_CONFLICT'
TARIFF = 'SOURCE_TARIFF_ALLOCATION_UNVERIFIED'

RISK_CHECKS = (
    ('sync_direct_move', SYNC_EN, 'You could move the original to another folder now.', SYNC),
    ('sync_alternative', SYNC_EN, 'Keep the original in place, or move it to a different folder until we check.', SYNC),
    ('sync_mixed', SYNC_EN, "Don't delete the file yet, but move the file out of the synced folder.", SYNC),
    ('sync_irrelevant_condition', SYNC_EN, 'Once you have checked the app version, drag the file to the desktop.', SYNC),
    ('sync_gerund_directive', SYNC_EN, 'We recommend moving the original away from the cloud folder for now.', SYNC),
    ('sync_false_guarantee', SYNC_EN, "Deleting the local copy won't affect your cloud copy.", SYNC),
    ('sync_zh_move', SYNC_ZH, '建议先保留一份，或者将文件移出同步目录。', SYNC),
    ('sync_zh_guarantee', SYNC_ZH, '删除本地文件不会影响云端副本。', SYNC),
    ('sync_copy', SYNC_EN, 'Copy the file to independent storage, open the copy and keep the original in place.', None),
    ('sync_gerund_explanation', SYNC_EN, 'Moving the file can change what appears in the synced folder.', None),
    ('sync_negative', SYNC_EN, "Don't delete the file or move it while the setting is unknown.", None),
    ('sync_zh_negative', SYNC_ZH, '请勿删除文件或把原件移出同步目录。可以先复制并验证能否恢复。', None),
    ('sync_qualified', SYNC_EN, 'Only after official support confirms sync behavior and you verify an independent copy can be restored, move the original.', None),
    ('sync_open_question', SYNC_EN, "We will check whether deleting the local copy won't affect the synced copy.", None),
    ('sync_quote', SYNC_EN, 'The earlier message said “move the original”, which we will check.', None),
    ('unrelated_file', NEUTRAL, 'Move the original to your records folder.', None),
    ('pin_parenthesis', NEUTRAL, 'Reply with the account reference (not a password or PIN).', None),
    ('pin_parenthesis_zh', NEUTRAL, '请回复账单编号（请勿提供密码或PIN）。', None),
    ('pin_negative_without', NEUTRAL, 'Reply with the invoice number without including your PIN.', None),
    ('pin_explicit_no_need', NEUTRAL, 'Please reply with the invoice number (no password or PIN is needed).', None),
    ('pin_positive_parenthesis', NEUTRAL, 'Reply with the details (your password or PIN).', SECRET),
    ('pin_after_refusal', NEUTRAL, 'Please reply with the account reference (not a password or PIN) and email the PIN separately.', SECRET),
    ('pin_positive_alternative', NEUTRAL, 'Please reply with your reference, or your PIN.', SECRET),
    ('pin_negative_coordinated', NEUTRAL, 'Do not email your password or send your PIN.', None),
    ('pin_after_refusal_zh', NEUTRAL, '请回复账单编号（不要发送密码），并提供PIN码。', SECRET),
    ('pin_through_mail_zh', NEUTRAL, '请通过邮箱提供PIN码。', SECRET),
    ('pin_counter_pretext', NEUTRAL, 'Please email your PIN to the agent at the counter.', SECRET),
    ('password_reset', NEUTRAL, 'Please share the password reset ticket number.', None),
    ('card_ambiguous', CARD_ZH, '请提供卡号（可以只提供部分号码）或小票参考号。', SECRET),
    ('card_full', CARD_EN, 'Please reply with the complete gift card number.', SECRET),
    ('card_whole_as_digits', CARD_EN, 'Please reply with the last 16 digits of your gift card number.', SECRET),
    ('card_limited', CARD_EN, 'Please share the last four digits of your gift card number.', None),
    ('card_limited_zh', CARD_ZH, '请提供卡号末四位或小票交易参考号。', None),
    ('card_last_few_zh', CARD_ZH, '请提供以下任一项：卡号后几位或交易凭证。', None),
    ('card_refuse_back_zh', CARD_ZH, '请提供小票或付款金额（无需提供完整卡密、卡背或密码）。', None),
    ('card_receipt', CARD_EN, 'Please use the receipt reference, rather than the gift card number or PIN.', None),
    ('page_range', PAGES_EN, 'The manual is missing pages 18–25.', PAGE),
    ('page_range_zh', PAGES_ZH, '说明书缺少第１８到第２５页。', PAGE),
    ('page_range_intersect', PAGES_EN, 'Pages 17–19 are missing.', PAGE),
    ('page_range_report', PAGES_EN, 'You said the book is missing pages 18 to 25.', PAGE),
    ('page_range_inside', PAGES_EN, 'Pages 19–24 appear absent given the jump you reported.', None),
    ('page_range_question', PAGES_EN, 'We need to check whether pages 18–25 are missing.', None),
    ('page_range_literal', PAGES_ZH, '您反映说明书从第１８页跳到第２５页。', None),
    ('tariff_precommit', TARIFF_ZH, '我们将确认不会把全部用量按新价计算。', TARIFF),
    ('tariff_open', TARIFF_ZH, '先查清生效日、分段读数和适用计费办法，目前无法确认费用如何分配。', None),
)


def mail(body):
    return EmailInput(email_id='development-risk-fixture', subject='Service enquiry', body=body)


class ReplyRiskTests(unittest.TestCase):
    def test_bounded_risk_decisions(self):
        for name, source, reply, expected in RISK_CHECKS:
            with self.subTest(name=name):
                findings = audit_reply(mail(source), reply, {})['findings']
                self.assertEqual({f['code'] for f in findings}, {expected} if expected else set())
                for finding in findings:
                    self.assertIn(finding['quote'], reply)
                    self.assertEqual(finding['severity'], 'review' if expected in (PAGE, TARIFF) else 'block')

    def test_source_specific_composition_checks(self):
        tariff = 'The tariff change date falls inside the meter reading interval. Please check the split.'
        for text, topic in ((SYNC_EN, 'sync_file_recovery'), (CARD_EN, 'gift_card_intake'),
                            (tariff, 'tariff_reconciliation')):
            guidance = composition_brief(mail(text), {})
            self.assertIn(topic, {check['topic'] for check in guidance['service_checks']['topics']})
            self.assertFalse(reconcile_plan(mail(text), []))
        jump = composition_brief(mail(PAGES_EN), {})['source_page_observations']['jumps'][0]
        self.assertEqual((jump['first_observed_page'], jump['next_observed_page']), (18, 25))


class PendingReceiptTests(unittest.TestCase):
    def setUp(self):
        from src.evaluation.service_judge import bind

        self.email = mail('Can my friend collect my store order instead? Please also trace the missing shipment.')
        self.identity = dict(case_id=self.email.email_id, run_id='fixture-run', arm='GUIDED', input_hash=self.email.input_hash)
        self.delivery = dict(event_id='delivery', kind='logistics_followup', status='created', conversation_id=self.email.email_id,
                             input_hash=self.email.input_hash, business_goal='Trace the missing shipment with logistics')
        self.store = dict(event_id='store', kind='store_service_request', status='created', conversation_id=self.email.email_id,
                          input_hash=self.email.input_hash, business_goal='Verify delegate collection and the store hold period')
        self.bind = bind
        self.reply = ('您提到的两项需求已分别创建内部请求，均待处理：一项为物流核查，'
                      '一项为门店服务核实（代取授权、最少凭证及保留时间）')

    def runtime(self, events):
        return dict(identity=dict(self.identity, conversation_id=self.email.email_id),
                    events=self.bind(events, **self.identity), strict_identity=True)

    def support(self, quote, runtime):
        from src.application.p5b8r4_evidence import claim, support

        return support(claim(quote, 'INTERNAL_CREATED'), runtime, self.email.input_hash, strict=True)

    def test_distinct_pending_tasks_need_own_receipts(self):
        both = self.runtime([self.delivery, self.store])
        self.assertEqual(self.support(self.reply, both)['event_ids'], ['delivery', 'store'])
        english = ('Two separate internal requests have been created and are pending: '
                   'one for logistics verification, and another for delegate collection.')
        self.assertEqual(self.support(english, both)['event_ids'], ['delivery', 'store'])
        family_pickup = dict(self.store, business_goal='Check whether the customer’s sister can collect the reserved bag instead')
        self.assertEqual(self.support(english, self.runtime([self.delivery, family_pickup]))['event_ids'], ['delivery', 'store'])
        for events in ([self.delivery], [self.store], [self.delivery, dict(self.store, status='requested')],
                       [self.delivery, dict(self.store, status='completed')],
                       [self.delivery, dict(self.store, business_goal='Store service appointment')]):
            self.assertFalse(self.support(self.reply, self.runtime(events))['supported'])
        self.assertFalse(self.support(self.reply.replace('两项', '三项'), both)['supported'])
        duplicate = self.reply.replace('门店服务核实（代取授权、最少凭证及保留时间）', '物流核查')
        self.assertFalse(self.support(duplicate, both)['supported'])
        foreign = self.bind([self.store], **dict(self.identity, arm='DIRECT'))[0]
        self.assertFalse(self.support(self.reply, dict(both, events=[both['events'][0], foreign]))['supported'])

    def test_generic_status_needs_a_unique_actual_pending_task(self):
        text = '目前内部核查请求已创建，尚待处理，核查结果和完成时间尚未确定'
        one = self.runtime([self.delivery])
        self.assertEqual(self.support(text, one)['event_ids'], ['delivery'])
        both = self.runtime([self.delivery, self.store])
        self.assertFalse(self.support(text, dict(one, receipt_inventory=both['events']))['supported'])
        self.assertFalse(self.support(text, self.runtime([dict(self.delivery, status='completed')]))['supported'])
        self.assertFalse(self.support(text + '，也已经安排退款', one)['supported'])

    def test_guard_checks_app_predicate_and_separate_external_assertion(self):
        from src.application.p5b8r3_final_guard import assess

        runtime = self.runtime([self.delivery, self.store])
        checked = assess(self.reply + '。我们已联系承运商核实进度。', runtime, self.email.input_hash)
        self.assertTrue(any(a['state']=='INTERNAL_CREATED' and a['supported'] for a in checked['assessments']))
        self.assertTrue(any(f['severity']=='block' and '联系承运商' in f['quote'] for f in checked['findings']))
        reported = self.reply.replace('您提到的', '您提到')
        self.assertFalse(assess(reported, self.runtime([]), self.email.input_hash)['findings'])

    def test_delegate_route_keeps_independent_shipment_work(self):
        source = '朋友愿意代取。能否核对授权或延期选择？另一个包裹还没收到，请核对运单。'
        email = mail(source)
        base = dict(priority='normal')
        out = reconcile_plan(email, [
            dict(base, kind='logistics_followup', issue_ids=['delegate'], goal='核对授权或延期选择', evidence=['能否核对授权或延期选择']),
            dict(base, kind='logistics_followup', issue_ids=['shipment'], goal='请核对运单', evidence=['另一个包裹还没收到，请核对运单']),
        ])
        self.assertEqual([a['kind'] for a in out], ['store_service_request', 'logistics_followup'])
        self.assertEqual([a['issue_ids'] for a in out], [['delegate'], ['shipment']])


class LayeredReviewTests(unittest.TestCase):
    def test_numeric_diagnostic_does_not_rewrite_consistent_service_verdict(self):
        from src.evaluation.risk_review import assess

        answer = dict(verdict='PASS', severity='NONE', required_coverage=[dict(status='COVERED')],
                      findings=[], scores=dict(attitude=1, reliability=2),
                      fact_validation=dict(errors=['ATTITUDE_APPLICABILITY_CONFLICT']))
        output = assess(dict(findings=[]), answer)
        self.assertEqual(output['review']['verdict'], 'PASS')
        self.assertEqual(output['numeric']['scores'], answer['scores'])
        self.assertEqual(output['numeric']['diagnostics'], ['ATTITUDE_APPLICABILITY_CONFLICT'])
        for changed in (dict(answer, required_coverage=[dict(status='MISSING')]),
                        dict(answer, fact_validation=dict(errors=['JUDGE_EVIDENCE_MISMATCH']))):
            self.assertEqual(assess(dict(findings=[]), changed)['review']['verdict'], 'UNKNOWN')

    def test_hard_suspicion_and_protocol_failure_retain_review_route(self):
        from src.evaluation.risk_review import assess

        clean = dict(findings=[])
        result = assess(clean, protocol_error='Incomplete wire')
        self.assertEqual(result['review'], dict(verdict='UNKNOWN', reason='JUDGE_PROTOCOL_ERROR', route='HUMAN_REVIEW'))
        held = assess(clean, dict(verdict='FAIL', severity='HARD', findings=[dict(category='HARD_ERROR')]))
        self.assertEqual(held['review']['route'], 'BLOCK_DRAFT')
        self.assertEqual(held['review']['verdict'], 'UNKNOWN')
        blocked = assess(dict(findings=[dict(severity='block', code=SYNC)]), protocol_error='Incomplete wire')
        self.assertEqual(blocked['review']['verdict'], 'FAIL')
        self.assertEqual(blocked['review']['route'], 'BLOCK_DRAFT')


if __name__ == '__main__':
    unittest.main()
