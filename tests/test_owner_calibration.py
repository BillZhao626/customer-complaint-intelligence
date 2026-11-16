"""Behavioral controls for the shared production chain and calibrated intake."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.application import service_response as service
from src.application.reply_guidance import source_topics
from src.domain.contracts import EmailInput
from src.evaluation import owner_calibrated_judge as judge


def email(body):
    return EmailInput(email_id='synthetic-control', subject='Question', body=body)


def slot(mail, arm, reply, runtime):
    identity = dict(case_id=mail.email_id, run_id='fixture-' + arm, arm=arm, input_hash=mail.input_hash)
    return dict(identity, parse_ok=True, reply=reply, facts=runtime.get('facts', {}),
                events=judge.bind(runtime.get('events', []), **identity))


# The first reply in each family is the primary hard-error sentinel. Related
# good/middle/bad replies and position repeats are not independent samples.
CONTROLS = [
    ('voucher_en', 'My coupon expires Friday. Which time zone does it use?',
     ('As a safeguard, please pay before Friday in your local time.',
      'If the merchant confirms the cutoff uses your local time and which payment timestamp qualifies, please follow those terms when paying. Share the promotion reference so billing can check.',
      'I am not sure. Please share the promotion reference.'), (True, False, False)),
    ('voucher_zh', '折扣码周一到期，我该按哪个时区付款？',
     ('规则暂未核实，但建议在当地时间周一之前付款，比较稳妥。',
      '请提供活动编号，账务可以核实条款中的时区和有效付款时间戳。请勿按当地时间下单来保证优惠。',
      '可以查看优惠条款。'), (True, False, False)),
    ('ordinary_deadline', 'I am travelling. When can I buy a replacement part?',
     ('Please call the store before it closes in your local time.',
      'Check the branch opening hours before travelling.', 'Please contact the store.'), (False, False, False)),
    ('unsupported_refund', 'The mat has a strong smell and I have stopped using it.',
     ('We have refunded the payment.', 'Keep it out of use while we check the label and available return options.',
      'Please check the care label.'), (True, False, False)),
    ('fit_depth', 'The fitted sheet fits the length and width but does not reach under the mattress.',
     ('Could you send the order reference and a photo of the size label and receipt?',
      'Check the pocket depth against the mattress height. A deeper pocket with the same footprint may fit.',
      'Please check the label dimensions.'), (False, False, False)),
    ('pickup', 'Can a friend pick up my reserved blender?',
     ('Email your pickup code to us.', 'Please do not send the pickup code. Share the reservation reference if we do not have it so we can check the store’s rules.',
      'Please contact the branch for its collection policy.'), (True, False, False)),
    ('praise_intent', 'The shop assistant was great. My table still wobbles.',
     ('We will pass on your praise. Could you share your order reference?',
      'Sorry the table wobbles, and thank you for the kind words about the assistant. We can check whether a return or exchange is available.',
      'Please share the order reference so we can look into the table.'), (False, False, False)),
    ('loan', 'Can I borrow a unit while mine is being repaired? I am only asking.',
     ('Please share the repair reference so we can check whether a compatible unit is available.',
      'We can check availability at your repair location and confirm the terms if a unit is available.',
      'Please share the repair location.'), (False, False, False)),
]


def control_audits():
    rows = []
    for family, source, replies, expected in CONTROLS:
        mail = email(source)
        answers = [slot(mail, arm, reply, {}) for arm, reply in zip('ABC', replies)]
        runs = []
        for left, right, reverse in ((0, 1, False), (0, 1, True), (0, 1, False), (1, 2, False)):
            payload, key = judge.blind_pair(mail, [answers[left], answers[right]], reverse=reverse)
            runs.append({
                key[item['slot']]['arm']: sorted(f['code'] for f in item['deterministic_fact_audit']['findings']
                                               if f['severity'] == 'block')
                for item in payload['answers']
            })
        rows.append(dict(family=family, expected=list(expected), AB=runs[0], BA=runs[1],
                         REPEAT=runs[2], BC=runs[3]))
    return rows


def fake_judgment(mail, payload):
    answers = []
    for slot_data in payload['answers']:
        quote = slot_data['reply']
        answers.append(dict(slot=slot_data['slot'], scores=dict.fromkeys(judge.DIMENSIONS, 2),
                            reasons=dict.fromkeys(judge.DIMENSIONS, 'Synthetic maximum-score control'),
                            findings=[], action_evidence=[], score_evidence=dict.fromkeys(judge.DIMENSIONS, quote),
                            customer_goals=[dict(goal='customer request', quote=mail.body)],
                            issue_coverage=[dict(issue='customer request', reply_quote=quote, status='COVERED')]))
    return dict(answers=answers, preference='TIE')


class OwnerCalibrationTests(unittest.TestCase):
    def test_controls_with_swap_and_repeat(self):
        for row in control_audits():
            with self.subTest(family=row['family']):
                self.assertEqual(row['AB'], row['BA'])
                self.assertEqual(row['AB'], row['REPEAT'])
                actual = [bool(row['AB']['A']), bool(row['AB']['B']), bool(row['BC']['C'])]
                self.assertEqual(actual, row['expected'])

    def test_multi_issue_plan_and_visible_pending_status(self):
        mail = email("The order notice has someone else's phone number. My shipment never arrived.")
        planned = service.plan_actions(None, email=mail)
        self.assertEqual({item['kind'] for item in planned}, {'support_followup', 'logistics_followup'})
        self.assertEqual(service.reconcile_plan(mail, planned), planned)
        with TemporaryDirectory() as tmp:
            runtime = service.execute(mail, planned, Path(tmp) / 'db.sqlite3')
        draft = "I've created an internal privacy verification request. I've also created a logistics verification request."
        audit = judge.audit_slot(slot(mail, 'A', draft, runtime), mail)
        self.assertFalse([f for f in audit['findings'] if f['severity'] == 'block'], audit)
        self.assertEqual(sum(a['state'] == 'INTERNAL_CREATED' and a['supported'] for a in audit['assessments']), 2)
        self.assertEqual([c['status'] for c in audit['service_review']['customer_informed_of_actions']],
                         ['DISCLOSED', 'DISCLOSED'])
        merged = 'A verification request covering privacy and delivery has been created and is pending.'
        bad = judge.audit_slot(slot(mail, 'A', merged, runtime), mail)
        self.assertEqual([c['status'] for c in bad['service_review']['customer_informed_of_actions']],
                         ['MERGED', 'MERGED'])
        self.assertFalse([f for f in bad['findings'] if f['severity'] == 'block'])
        denial = "We have not created a privacy verification request. A logistics request could be opened."
        undisclosed = judge.audit_slot(slot(mail, 'A', denial, runtime), mail)
        self.assertEqual([c['status'] for c in undisclosed['service_review']['customer_informed_of_actions']],
                         ['NOT_EXPLICITLY_DISCLOSED', 'NOT_EXPLICITLY_DISCLOSED'])
        pair, _ = judge.blind_pair(mail, [slot(mail, 'A', merged, runtime), slot(mail, 'B', draft, {})])
        checked = judge.parse(fake_judgment(mail, pair), pair)
        self.assertIn('CREATED_WORK_DISCLOSURE_GAP', checked['answers'][0]['fact_validation']['errors'])
        foreign = dict(runtime, events=[dict(e, input_hash='f' * 64) for e in runtime['events']])
        self.assertEqual([c['status'] for c in service.audit_reply(mail, draft, foreign)['customer_informed_of_actions']],
                         ['NO_PENDING_RECEIPT', 'NO_PENDING_RECEIPT'])
        self.assertTrue(any(f['severity'] == 'block' for f in judge.audit_slot(slot(mail, 'A', draft, {}), mail)['findings']))

    def test_unrelated_and_resolved_topics_do_not_create_work(self):
        for text in ('I typed the wrong order number.', 'They delivered the wrong phone model.',
                     'The parcel was missing. The parcel has arrived.',
                     'The mat had a strong smell but the smell has gone.',
                     'Can I borrow a book?', 'I do not need a loaner while the device is being repaired.',
                     'I want to cancel my subscription.'):
            self.assertEqual(service.reconcile_plan(email(text), []), [], text)

    def test_facts_must_be_current_and_authorized(self):
        mail = email('优惠券周末到期，付款用哪个时区？')
        reply = '请在当地时间周六之前付款'
        fact = dict(conclusion=reply, topic='promotion_deadline', authority='AUTHORIZED_FIXTURE',
                    source_id='policy-fixture', input_hash=mail.input_hash)
        rt = dict(facts=dict(status='KNOWN', facts=[fact]))
        self.assertFalse(service.audit_reply(mail, reply, rt)['findings'])
        fact['input_hash'] = 'f' * 64
        self.assertTrue(service.audit_reply(mail, reply, rt)['findings'])
        self.assertEqual(service.brief(mail, rt)['service_checks']['verified_facts'], [])
        en = email('The coupon expiry has no time zone. Which payment timestamp counts?')
        unclear = 'If the merchant confirms the cutoff uses your local time, please pay before Friday.'
        self.assertTrue(service.audit_reply(en, unclear, {})['findings'])

    def test_judge_cannot_average_away_unsupported_advice(self):
        mail = email(CONTROLS[0][1])
        a, b, _ = CONTROLS[0][2]
        payload, _ = judge.blind_pair(mail, [slot(mail, 'A', a, {}), slot(mail, 'B', b, {})])
        raw = fake_judgment(mail, payload)
        checked = judge.parse(json.dumps(raw), payload)
        self.assertEqual(checked['answers'][0]['scores'], raw['answers'][0]['scores'])
        self.assertEqual(checked['validation']['validated_preference'], 'UNKNOWN')
        self.assertIn('JUDGE_HARD_ERROR_OMISSION', checked['answers'][0]['fact_validation']['errors'])
        self.assertTrue(checked['answers'][1]['fact_validation']['certifiable'])

    def test_operational_inquiries_and_care_keep_correct_scope(self):
        cases = [
            ('能暂停一周的定期配送吗？不想终止。', 'subscription_skip', 'billing_request', 'benefits'),
            ('Can my neighbour collect on my behalf?', 'delegate_pickup', 'store_service_request', 'minimum proof'),
            ('检修期间能借一台备用机吗？', 'service_loan', 'store_service_request', 'no booking'),
            ('地垫刺鼻，已经不用了。', 'uncomfortable_odor', 'aftersales_request', 'return, exchange or refund'),
        ]
        for source, topic, kind, advice in cases:
            mail = email(source)
            self.assertIn(topic, source_topics(mail))
            self.assertEqual([a['kind'] for a in service.plan_actions(None, email=mail)], [kind])
            self.assertIn(advice, service.brief(mail, {})['service_checks']['topics'][0]['possible_solutions'])
