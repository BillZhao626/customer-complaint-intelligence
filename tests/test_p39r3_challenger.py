"""Prompt identity/payload engineering tests; these do not score LLM semantics."""
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from src.application.p39_v2 import system as champion_system, messages as champion_messages
from src.application.p39r3_challenger import system, messages, candidate_identity, PARENT_B_SHA256
from src.domain.contracts import EmailInput, digest


class ChallengerPromptTests(unittest.TestCase):
    def test_independent_identity_and_champion_unchanged(self):
        before = {arm: champion_system(arm) for arm in ('A', 'B')}
        row = candidate_identity()
        self.assertEqual(row['parent_prompt_sha256'], PARENT_B_SHA256)
        self.assertNotEqual(row['prompt_sha256'], PARENT_B_SHA256)
        self.assertTrue(system().startswith(before['B']))
        self.assertEqual(before, {arm: champion_system(arm) for arm in ('A', 'B')})
        body = dict(row); claimed = body.pop('candidate_hash')
        self.assertEqual(digest(body), claimed)
        self.assertFalse(row['semantic_acceptance_changed'])
        self.assertFalse(row['model_improvement_proven'])

    def test_exact_payload_catalog_with_renamed_multilingual_inputs(self):
        for identifier, body in [('invented-kettle', 'Please check the booking and the receipt together.'),
                                 ('invented-printer', '预约那天没人来，这个文件晚一点补也可以。')]:
            email = EmailInput(email_id=identifier, subject='Authored counterexample', body=body)
            result = messages(email)
            self.assertEqual(result[1], champion_messages(email, 'B')[1])
            payload = json.loads(result[1][1])
            self.assertEqual(set(payload), {'email_id', 'subject', 'body', 'input_hash', 'evidence_catalog'})
            self.assertEqual(payload['body'], body)
            self.assertNotIn(identifier, result[0][1])
            for forbidden in ('P35-171', 'p25-product', 'p25-uncertain', 'human_score', 'expected_label'):
                self.assertNotIn(forbidden, result[0][1])

    def test_drift_fails_closed(self):
        with patch('src.application.p39r3_challenger.champion_system', return_value='changed parent'):
            with self.assertRaisesRegex(ValueError, 'identity drift'):
                system()

    def test_existing_schema_and_evidence_requirements_are_inherited(self):
        from src.application.p39r3_challenger import RULES
        self.assertEqual(sha256(champion_system('B').encode()).hexdigest(), PARENT_B_SHA256)
        self.assertIn('only the schema JSON', RULES)
        self.assertIn('responsibility remains unverified', RULES)
        self.assertIn('keep severe/high', RULES)
        self.assertIn('never invent an address', RULES)
        self.assertIn('not repeated service non-performance', RULES)


if __name__ == '__main__':
    unittest.main()
