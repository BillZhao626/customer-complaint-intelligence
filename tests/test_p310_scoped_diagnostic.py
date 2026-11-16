"""A discovered v2 false accept is retained, then rejected in new v3 profile."""
import unittest
from tests.test_urgency_context import fixture,CASES
from src.domain.analysis_v31_recovery import RecoveryAnalysisV31
from src.domain.analysis_v31_recovery_scoped import ScopedRecoveryAnalysisV31,scoped_repetition


class ScopedDiagnosticTests(unittest.TestCase):
    def test_answered_messages_cannot_borrow_one_cancelled_appointment(self):
        body='Several support messages were answered, then one appointment was cancelled.'
        e,d=fixture(body,'medium','repeated_failure')
        RecoveryAnalysisV31.model_validate(d).validate_input(e)
        with self.assertRaisesRegex(ValueError,'different service event'):
            ScopedRecoveryAnalysisV31.model_validate(d).validate_input(e)
        self.assertFalse(scoped_repetition(body))

    def test_positive_paraphrases_and_existing_cases_still_work(self):
        for body in ('Three promised replies, zero answers.','No reply after several support messages.','多次承诺回电但一直未兑现。'):
            e,d=fixture(body,'medium','repeated_failure')
            ScopedRecoveryAnalysisV31.model_validate(d).validate_input(e)
        for _,body,u,basis,risk in CASES:
            e,d=fixture(body,u,basis,risk)
            with self.subTest(body=body):ScopedRecoveryAnalysisV31.model_validate(d).validate_input(e)

    def test_mixed_product_service_opposite_and_quote_scope(self):
        for body in ('I operated the switch twice, then one appointment was cancelled.',
                     'Three promised replies arrived, although one appointment was cancelled.',
                     'The visits were not cancelled twice.',
                     'The manual says "three promised replies, zero answers".'):
            with self.subTest(body=body):self.assertFalse(scoped_repetition(body))
        import copy
        e,d=fixture('Can this compass show the heading?','low','other')
        d['issues'][0]['evidence']=copy.deepcopy(d['issues'][0]['evidence'])
        d['issues'][0]['evidence'][0]['end']+=1000
        RecoveryAnalysisV31.model_validate(d).validate_input(e)
        with self.assertRaisesRegex(ValueError,'bounds'):
            ScopedRecoveryAnalysisV31.model_validate(d).validate_input(e)
