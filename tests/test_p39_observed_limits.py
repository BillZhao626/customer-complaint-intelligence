"""Generalized offline counterexamples retaining the approved profile behavior.

These record observed guard limitations; they do not approve new semantics or
repair/relax model predictions after a paid failure. No actual email fixtures.
"""
import unittest
from src.application.urgency_context_v1 import signals
from src.domain.analysis_v31_context import ContextAnalysisV31
from tests.test_urgency_context import fixture


class ObservedContextLimits(unittest.TestCase):
    def test_recurrent_hardware_symptom_is_not_repeated_service_nonperformance(self):
        for body in ('The projector keeps flickering after I restart it several times.',
                     '门锁总会自己弹开，我关回去几次，过一会又开了。'):
            email,data=fixture(body,'medium','repeated_failure')
            self.assertFalse(signals(body)['repeated_failure'])
            with self.assertRaisesRegex(ValueError,'Repeated failure basis'):
                ContextAnalysisV31.model_validate(data).validate_input(email)

    def test_single_missed_service_does_not_establish_repetition(self):
        for body in ('The technician never arrived for the booked visit.',
                     '预约那天没人来，也没有接到电话。'):
            email,data=fixture(body,'medium','repeated_failure')
            with self.assertRaisesRegex(ValueError,'Repeated failure basis'):
                ContextAnalysisV31.model_validate(data).validate_input(email)

    def test_relaxed_paraphrases_remain_explicit_known_bounded_guard_limit(self):
        for body in ('There is no hurry to send the receipt.', '这个文件晚一点补也可以。'):
            email,data=fixture(body,'low','explicit_relaxed')
            self.assertFalse(signals(body)['relaxed'])
            with self.assertRaisesRegex(ValueError,'Relaxed basis'):
                ContextAnalysisV31.model_validate(data).validate_input(email)
            # A limitation of current accepted lexical vocabulary, not evidence
            # that low is semantically wrong. No validator changes here.

    def test_follow_up_together_is_not_explicit_equal_importance(self):
        email,data=fixture('Please follow up both the booking and the receipt together.','medium','other')
        issue=data['issues'][0];issue['customer_importance']='equal';issue['importance_evidence']=issue['evidence']
        with self.assertRaisesRegex(ValueError,'Together does not establish equal'):
            ContextAnalysisV31.model_validate(data).validate_input(email)
