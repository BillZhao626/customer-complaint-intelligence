"""Offline authored regressions plus optional local immutable raw replay."""
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.evaluation.p39r3_causal import replay, read_saved, source_identity
from src.domain.analysis_v3 import to_v2
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.application.p39_v2 import ContextOfflineService
from src.application.v31_demo import ReplayV31
from src.infrastructure.context_repository import ContextRepository, ReadOnlyContextRepository
from tests.test_urgency_context import fixture

ROOT = Path(__file__).resolve().parents[1]


class CausalReplayTests(unittest.TestCase):
    def run_case(self, body, urgency, basis):
        email, data = fixture(body, urgency, basis)
        raw = json.dumps(data, ensure_ascii=False)
        original = copy.deepcopy(data)
        results = {p: replay(raw, email, p) for p in
                   ('v31-policy-v2-gate3', 'v31-context-v1-gate3')}
        self.assertEqual(data, original)
        self.assertTrue(all(r['raw_text_sha256'] == sha256(raw.encode()).hexdigest() for r in results.values()))
        return email, data, results

    def test_original_bad_basis_is_still_rejected_by_both(self):
        for body in ('Does this keyboard have wireless mode?', '请问这台吸尘器支持预约启动吗？'):
            _, _, rows = self.run_case(body, 'low', 'general_help')
            self.assertTrue(all(not r['accepted'] for r in rows.values()))

    def test_correct_specific_inquiry_is_preserved_in_both(self):
        for body in ('What is the capacity of this rice cooker?', '请问周末几点开门？'):
            _, _, rows = self.run_case(body, 'low', 'other')
            self.assertTrue(all(r['accepted'] for r in rows.values()))

    def test_introduced_explicit_relaxed_lexical_limit_is_distinct_from_wrong_low(self):
        for body in ('There is no hurry to send the receipt.', '这个文件晚一点补也可以。'):
            _, _, rows = self.run_case(body, 'low', 'explicit_relaxed')
            self.assertTrue(rows['v31-policy-v2-gate3']['accepted'])
            self.assertFalse(rows['v31-context-v1-gate3']['accepted'])
            self.assertEqual(rows['v31-context-v1-gate3']['failed_stage'], 'source_and_policy_validation')

    def test_new_context_rejects_single_service_or_recurring_product_basis(self):
        for body in ('The repair technician missed the booked visit.',
                     'The monitor flickers after I restart it several times.',
                     '预约那天没人来，也没有给我打电话。'):
            _, _, rows = self.run_case(body, 'medium', 'repeated_failure')
            self.assertTrue(rows['v31-policy-v2-gate3']['accepted'])
            self.assertFalse(rows['v31-context-v1-gate3']['accepted'])

    def test_actual_repetition_and_resolved_history_counterexamples(self):
        for body in ('Three callbacks were promised and none arrived.', '多次承诺回电但一直未兑现。'):
            _, _, rows = self.run_case(body, 'medium', 'repeated_failure')
            self.assertTrue(rows['v31-context-v1-gate3']['accepted'])
        _, _, rows = self.run_case('My appointment was cancelled twice but it is now resolved.', 'low', 'other')
        self.assertTrue(rows['v31-context-v1-gate3']['accepted'])

    def test_quoted_current_contrast_and_deadline_new_old_differential(self):
        cases = [('A quoted notice says "ASAP". What time does the shop open?', 'low', 'other'),
                 ('They missed the promised reply twice. A response before closing today is essential.', 'high', 'repeated_failure')]
        for body, u, basis in cases:
            _, _, rows = self.run_case(body, u, basis)
            self.assertFalse(rows['v31-policy-v2-gate3']['accepted'])
            self.assertTrue(rows['v31-context-v1-gate3']['accepted'])
        _, _, rows = self.run_case('I did not ask for ASAP, but please process it as soon as possible.', 'high', 'explicit_urgent')
        self.assertTrue(rows['v31-context-v1-gate3']['accepted'])

    def test_historical_negation_false_rejection_has_exact_same_raw(self):
        email, data = fixture('Please check the refund request.', 'medium', 'other')
        data.pop('policy_version'); data.pop('reply_language')
        data['schema_version'] = 'analysis-v3'; data['taxonomy_version'] = 'complaint-issues-v3'
        for issue in data['issues']:
            for key in ('risk_level', 'risk_evidence', 'risk_rationale', 'urgency_basis', 'urgency_evidence'):
                issue.pop(key)
        data['suggested_reply'] = '无法保证明天付款，请提供申请编号以便核查。'
        raw = json.dumps(data, ensure_ascii=False)
        self.assertFalse(replay(raw, email, 'v3-gate1-historical-reconstruction')['accepted'])
        for profile in ('v3-gate2', 'v3-gate3'):
            self.assertTrue(replay(raw, email, profile)['accepted'])
        data['suggested_reply'] += '但是保证明天付款。'
        raw = json.dumps(data, ensure_ascii=False)
        for profile in ('v3-gate1-historical-reconstruction', 'v3-gate2', 'v3-gate3'):
            self.assertFalse(replay(raw, email, profile)['accepted'])

    def test_no_false_safety_success_or_customer_equal_inference(self):
        email, data = fixture('Please follow up the repair and booking together.', 'medium', 'other')
        data['issues'][0].update(customer_importance='equal', importance_evidence=data['issues'][0]['evidence'])
        raw = json.dumps(data)
        self.assertFalse(replay(raw, email, 'v31-context-v1-gate3')['accepted'])
        email, data = fixture('No rush. The battery is swollen and smoking.', 'low', 'other')
        self.assertFalse(replay(json.dumps(data), email, 'v31-context-v1-gate3')['accepted'])

    def test_parse_errors_redact_customer_text(self):
        email, _ = fixture('Does the router support guest access?', 'low', 'other')
        raw = 'PRIVATE_CUSTOMER_DATA_INVALID_JSON'
        row = replay(raw, email, 'v31-context-v1-gate3')
        self.assertEqual(row['failed_stage'], 'parsing')
        self.assertNotIn(raw, json.dumps(row))
        with self.assertRaises(ValueError):
            replay(raw, email, 'implicit-latest')

    def test_identity_and_temp_sqlite_integration_no_network(self):
        email, data = fixture('Does this clock display two time zones?', 'low', 'other')
        analyzer = ReplayV31({email.input_hash: data})
        from src.application.urgency_context_v1 import PROFILE
        from src.domain.contracts import RunConfigV31
        config = analyzer.config.model_dump()
        config['parameters']['urgency_validation_profile'] = PROFILE
        analyzer.config = RunConfigV31.model_validate(config)
        with tempfile.TemporaryDirectory() as td, patch('socket.socket', side_effect=AssertionError('offline only')):
            repo = ContextRepository(Path(td) / 'temporary.sqlite3')
            original = ContextOfflineService(repo, analyzer).analyze(email)
            saved = ReadOnlyContextRepository(Path(td) / 'temporary.sqlite3').get(original.run_id)
            self.assertEqual(original, saved)
            self.assertEqual(saved.status, 'succeeded')
            self.assertEqual(replay(saved.attempts[-1].raw_output, saved.email, 'v31-context-v1-gate3')['accepted'], True)
            self.assertEqual(ContextOfflineService(repo, analyzer).analyze(email).run_id, saved.run_id)

    def test_saved_historical_raw_optional_read_only(self):
        paths = list((ROOT / '.local/p39/runtime-v1').glob('run-*.json'))
        paths += list((ROOT / '.local/p39/v2/live-delivery-v1/runtime').glob('run-*.json'))
        if not paths:
            self.skipTest('Local historical artifacts intentionally excluded from public checkout')
        with patch('socket.socket', side_effect=AssertionError('offline only')):
            for path in paths:
                before = path.read_bytes()
                report = read_saved(path)
                self.assertEqual(before, path.read_bytes())
                self.assertEqual(report['original_status'], json.loads(before)['status'])
                self.assertFalse(report['historical_result_modified'])
                self.assertEqual(report['new_provider_calls'], 0)
        self.assertTrue(source_identity(ROOT)['source_identity_hash'])

    def test_actual_commitment_raw_remains_failed_but_negation_diagnostic_improves(self):
        path = ROOT / '.local/p36/draft-v3/run-4e3497ac-f667-4b0c-8b37-a0e6a3743b97.json'
        if not path.exists():
            self.skipTest('Local research raw is not included in public checkout')
        before = path.read_bytes()
        row = read_saved(path)
        results = {r['profile']: r for r in row['diagnostic_results']}
        self.assertEqual(row['original_status'], 'failed')
        self.assertFalse(results['v3-gate1-historical-reconstruction']['accepted'])
        self.assertTrue(results['v3-gate2']['accepted'])
        self.assertTrue(results['v3-gate3']['accepted'])
        self.assertEqual(before, path.read_bytes())

    def test_actual_context_failure_preexists_but_earliest_guard_changes(self):
        path = ROOT / '.local/p39/v2/live-delivery-v1/runtime/run-524455eb-b0b7-4826-be59-1fe866eea3cb.json'
        if not path.exists():
            self.skipTest('Local research raw is not included in public checkout')
        before = path.read_bytes()
        row = read_saved(path)
        results = {r['profile']: r for r in row['diagnostic_results']}
        self.assertFalse(results['v31-policy-v2-gate3']['accepted'])
        self.assertFalse(results['v31-context-v1-gate3']['accepted'])
        self.assertIn('equal', json.dumps(results['v31-policy-v2-gate3']['errors']).lower())
        self.assertIn('Repeated failure', json.dumps(results['v31-context-v1-gate3']['errors']))
        self.assertEqual(row['original_status'], 'failed')
        self.assertEqual(before, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
