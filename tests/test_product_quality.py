"""Mechanism-level counterexamples; authored fixtures, no semantic accuracy claim."""
import copy
import json
from pathlib import Path
import unittest
from src.application.product_quality import inspect, load_failure, POLICY_HASH
from src.application.product_demo import example, SCENARIOS
from src.domain.contracts import EmailInput


def candidate(body, **changes):
    e, d = example(SCENARIOS[0])
    e = EmailInput(email_id='renamed-mechanism-fixture', subject='', body=body)
    ev = dict(field='body', start=0, end=len(body), quote=body)
    i = d['issues'][0]
    i.update(evidence=[ev], urgency_evidence=[ev], risk_evidence=[], **changes)
    return e, d


def codes(e, d, reply=None):
    return {f['code'] for f in inspect(e, d, reply, True)['findings']}


class ProductQualityTests(unittest.TestCase):
    def test_load_bearing_cross_product_language_and_no_injury(self):
        bodies = ["The bicycle frame latch opened while I lifted it. Nobody fell.",
                  'The pan handle detached when lifted. It was cold and empty.',
                  'The load-bearing chair leg broke. Nobody was injured.',
                  '烤盘一侧承重把手整块脱开。无人受伤。',
                  '自行车车架锁扣自行打开，尚未骑行。']
        for body in bodies:
            e, d = candidate(body, risk_level='minor', urgency='medium')
            with self.subTest(body=body):
                self.assertIn('potential_injury_downgrade', codes(e, d))

    def test_decorative_negative_quoted_hypothetical_and_negation(self):
        bodies = ['The decorative pan handle cover came off.',
                  'The bicycle frame latch has not opened.',
                  'The manual says "The bicycle frame latch opened".',
                  'If the bicycle frame latch opened, would it be unsafe?',
                  '烤盘承重把手没有脱开，我只询问尺寸。',
                  'The camera plastic cover detached.']
        for body in bodies:
            with self.subTest(body=body):
                self.assertIsNone(load_failure(body))

    def test_safe_field_and_reply_alignment_no_automatic_approval(self):
        e, d = example(SCENARIOS[2])
        q = inspect(e, d)
        self.assertEqual(q['status'], 'review_required')
        self.assertTrue(q['safety_review_required'])
        self.assertFalse(q['human_approved'])
        d['issues'][0]['urgency'] = 'medium'
        self.assertIn('risk_urgency_conflict', codes(e, d))

    def test_dangerous_reproduction_and_negated_coordination_contrast(self):
        e, d = example(SCENARIOS[2])
        for reply in ('Please do not use it. Try to reproduce the failure.',
                      'Stop using it. 请通电再次拍摄故障视频。',
                      'Do not reproduce the failure, but record a powered video.'):
            with self.subTest(reply=reply):
                self.assertIn('dangerous_reproduction', codes(e, d, reply))
        for reply in ('Please do not use the tray or reproduce the failure.',
                      'Stop using it. Do not repeat the failure; existing photos are enough.'):
            with self.subTest(reply=reply):
                self.assertNotIn('dangerous_reproduction', codes(e, d, reply))
        self.assertIn('missing_stop_use_advice', codes(e, d, 'Thank you for the report.'))

    def test_rain_without_timing_is_not_delay_and_explicit_delay_retained(self):
        for text in ('The delivery arrived but the packaging was soaked by rain.', '配送已完成，包装雨淋受潮。'):
            e, d = candidate(text, reason='delivery delay')
            with self.subTest(text=text):
                self.assertIn('unsupported_delivery_delay', codes(e, d))
                d['issues'][0]['reason'] = 'other'
                d['issues'][0]['business_process'] = 'delivery/logistics issue'
                self.assertNotIn('unsupported_delivery_delay', codes(e, d))
        for text in ('The delivery was overdue and the bag was soaked.', '配送超过约定时间，包装雨淋受潮。'):
            e, d = candidate(text, reason='delivery delay')
            self.assertNotIn('unsupported_delivery_delay', codes(e, d))

    def test_delay_quoted_denied_or_missing_keeps_review(self):
        for text in ('The delivery was not delayed. Its location is unknown.', 'The message said "delayed". I only ask about delivery.', 'The package location is unknown.'):
            e, d = candidate(text, reason='delivery delay')
            self.assertIn('unsupported_delivery_delay', codes(e, d))
        e, d = candidate('The packaging was left in the rain.', reason='product quality')
        self.assertIn('unsupported_manufacturing_cause', codes(e, d))

    def test_booking_cancellation_vs_other_complaint_denial(self):
        for text in ('My appointment was cancelled twice. I am not complaining about treatment.',
                     'The clinic cancelled my appointment and then the replacement was cancelled.',
                     '预约连续两次取消，我想确认可用时段。'):
            e, d = candidate(text)
            self.assertIn('booking_complaint_erasure', codes(e, d))
            d.update(complaint_status='current_unresolved')
            d['issues'][0].update(issue_kind='complaint', resolution='unresolved')
            self.assertNotIn('booking_complaint_erasure', codes(e, d))

    def test_booking_information_resolved_quoted_and_denied(self):
        for text in ('What appointment times are available?',
                     'My appointment was not cancelled twice.',
                     'The manual says "My appointment was cancelled twice".',
                     'My appointment was cancelled twice but it is now resolved.'):
            e, d = candidate(text)
            with self.subTest(text=text):
                self.assertNotIn('booking_complaint_erasure', codes(e, d))

    def test_customer_importance_does_not_come_from_workflow(self):
        e, d = candidate('Please reply to both issues together. I did not say equal importance.', customer_importance='equal')
        self.assertIn('denied_equal_importance', codes(e, d))
        d['issues'][0]['customer_importance'] = 'unspecified'
        self.assertNotIn('denied_equal_importance', codes(e, d))
        e, d = candidate('Both issues are equally important.', customer_importance='equal')
        self.assertNotIn('denied_equal_importance', codes(e, d))
        self.assertIn('importance_scope_review', codes(e, d))

    def test_document_provider_and_future_capabilities_negation_contrast(self):
        e, d = example(SCENARIOS[0])
        for reply in ('请您下周整理后提供保修说明。', 'Please provide the warranty manual.',
                      '两件事会在同一封邮件中分别答复。', 'We will contact you tomorrow.',
                      'We cannot send it, but we will arrange a replacement.', '请发送到 service@example.test。'):
            with self.subTest(reply=reply):
                self.assertEqual(inspect(e, d, reply)['status'], 'blocked')
        for reply in ('We cannot confirm that a refund is approved.',
                      'Please provide the model number so the merchant can identify its warranty documentation.',
                      '您无需提供保修说明。',
                      '不需要您提供说明书。',
                      'You do not need to provide the warranty manual.',
                      '我们不会发送保修说明，请先核对型号。'):
            with self.subTest(reply=reply):
                self.assertNotEqual(inspect(e, d, reply)['status'], 'blocked')

    def test_span_overflow_and_same_prediction_not_mutated(self):
        e, d = example(SCENARIOS[0]); before = copy.deepcopy(d)
        inspect(e, d)
        self.assertEqual(before, d)
        d['issues'][0]['evidence'][0]['end'] += 20
        self.assertIn('evidence_mismatch', codes(e, d))

    def test_arbitrary_invalid_raw_is_diagnostic_not_a_crash(self):
        e, _ = example(SCENARIOS[0])
        for d in (None, [], 1, {}, {'issues': [None, 1]},
                  {'issues': [{'evidence': None, 'risk_evidence': [1]}], 'suggested_reply': 42}):
            with self.subTest(raw=d):
                q = inspect(e, d, accepted=False)
                self.assertEqual(q['status'], 'blocked')

    def test_local_owner_packet_and_fourteen_sources(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / '.local/p311/adjudication/SHA256_MANIFEST.json').exists():
            self.skipTest('Private researcher attachment unavailable in portable checkout')
        from scripts.p311_audit import build
        report = build(root, root / '.local/p311/adjudication')
        self.assertEqual(len(report['records']), 14)
        self.assertEqual(len(report['not_attempted']), 1)
        self.assertEqual(len(report['same_raw_differential']), 244)
        self.assertEqual(report['policy_hash'], POLICY_HASH)
        self.assertTrue(all(r['human_score'] is None for r in report['records']))
        self.assertFalse(report['natural_variant']['independent_holdout'])
        self.assertEqual(sum(r['formal_accepted_but_owner_policy_violation'] for r in report['records']), 5)
