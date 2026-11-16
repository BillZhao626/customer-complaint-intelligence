"""Real SDK + controlled HTTP + application/SQLite/review; zero network."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx

from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis, ProductAuthorization, SnapshotPending
from src.application.product_demo import example, SCENARIOS
from src.application.product_workflow import ProductStore, Conflict
from src.domain.contracts import digest
from src.infrastructure.deepseek import DeepSeekAnalyzer, LiveSettings
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.repository import Repository


class ProductAnalysisTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.email, self.output = example(SCENARIOS[0])
        self.requests = []
        self.repo = Repository(self.root / 'analysis.sqlite3')
        self.store = ProductStore(self.root / 'product.sqlite3')
        self.analyzer = DeepSeekAnalyzer(LiveSettings('offline-test-only', True, max_attempts=1),
            prompt_profile='multi-issue-v31-B', mock_http_transport=httpx.MockTransport(self.http))
        self.budget = PilotBudget.create(self.root / 'new-product-budget.sqlite3', [self.email.input_hash],
            dict(product_authorization_id='product-offline-test', config=self.analyzer.config.model_dump()))
        self.service = AnalysisService(self.repo, self.analyzer, budget=self.budget)
        self.auth = ProductAuthorization('product-offline-test', digest(self.analyzer.config.model_dump()),
            frozenset([self.email.input_hash]), str(self.budget.path), '2099-01-01T00:00:00+00:00', 'offline_mock_http')
        self.app = ProductAnalysis(self.service, self.store, authorization=self.auth)

    def http(self, request):
        self.requests.append(json.loads(request.content))
        saved = self.repo.list_runs()[0]
        self.assertEqual(saved.status, 'running')
        self.assertEqual(saved.attempts[-1].metadata['dispatch'], 'started_or_unknown')
        return httpx.Response(200, headers={'x-request-id': 'controlled-http-fixture'}, json={
            'id': 'completion-fixture', 'object': 'chat.completion', 'created': 1, 'model': 'deepseek-flash',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(self.output)}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 100, 'total_tokens': 200}})

    def test_http_to_review_simulation_reload_and_idempotency(self):
        case = self.app.submit(self.email)
        self.assertEqual(case['run'].status, 'succeeded')
        self.assertEqual(case['source_kind'], 'offline_mock_http')
        self.assertEqual(case['run'].attempts[0].metadata['request_id'], 'controlled-http-fixture')
        self.assertEqual(case['case_id'], self.app.submit(self.email)['case_id'])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]['model'], 'deepseek-flash')
        self.assertEqual(self.requests[0]['max_tokens'], 1800)
        actor = dict(actor='offline_acceptance', actor_type='demo_test', reason='Engineering fixture only')
        case = self.store.act(case['case_id'], 'approve', expected_revision=0,
            checks=dict(facts_evidence=True, authority_privacy=True, all_issues=True), **actor)
        case = self.store.act(case['case_id'], 'simulate_send', expected_revision=1, **actor)
        self.assertEqual(case['state'], 'simulated_sent')
        self.assertEqual(ProductStore(self.store.path).get(case['case_id']), case)
        self.assertEqual(self.budget.summary()['reserved_attempts'], 1)

    def test_product_commit_failure_recovers_after_expiry_without_provider(self):
        with patch.object(self.store, 'create', side_effect=OSError('injected disk fault')):
            with self.assertRaises(SnapshotPending) as caught:
                self.app.submit(self.email)
        run_id = caught.exception.run_id
        self.assertEqual(Repository(self.repo.path).get(run_id).status, 'succeeded')
        self.budget.halt('offline_fixture_exhausted')
        restarted = ProductAnalysis(AnalysisService(Repository(self.repo.path), self.analyzer), ProductStore(self.store.path))
        with patch.object(self.analyzer, 'request', side_effect=AssertionError('must not dispatch')):
            case = restarted.recover(run_id)
            self.assertEqual(restarted.recover(run_id)['case_id'], case['case_id'])
        self.assertEqual(len(self.requests), 1)

    def test_model_failure_has_no_draft_or_send(self):
        self.output = {'invalid': True}
        case = self.app.submit(self.email)
        self.assertEqual(case['state'], 'analysis_failed'); self.assertIsNone(case['draft'])
        with self.assertRaises(Conflict):
            self.store.act(case['case_id'], 'simulate_send', expected_revision=0, actor='test', actor_type='demo_test')

    def test_evidence_not_bypassed(self):
        self.output['issues'][0]['evidence'][0]['quote'] = 'not present in original'
        case = self.app.submit(self.email)
        self.assertEqual(case['state'], 'analysis_failed'); self.assertIsNone(case['draft'])

    def test_authorization_rejected_before_any_call(self):
        variants = [None, replace(self.auth, expires_at='2000-01-01T00:00:00+00:00'),
            replace(self.auth, config_hash='wrong'), replace(self.auth, input_hashes=frozenset()),
            replace(self.auth, budget_path=str(self.root / 'old-budget.db')),
            replace(self.auth, authorization_id='P3.10'), replace(self.auth, mode='live')]
        for authorization in variants:
            with self.subTest(auth=authorization), self.assertRaises(ValueError):
                ProductAnalysis(self.service, self.store, authorization=authorization).submit(self.email)
        self.assertEqual(self.requests, []); self.assertEqual(self.repo.list_runs(), [])
        with self.budget.connection() as conn:
            conn.execute('UPDATE policy SET manifest=?', (json.dumps({'config': self.analyzer.config.model_dump()}),))
        with self.assertRaises(ValueError): self.app.submit(self.email)
        self.assertEqual(self.requests, [])

    def test_live_server_disabled_even_with_bound_new_ledger(self):
        analyzer = DeepSeekAnalyzer(LiveSettings('unused-test-key', True), prompt_profile='multi-issue-v31-B')
        service = AnalysisService(self.repo, analyzer, budget=self.budget)
        auth = replace(self.auth, mode='live', config_hash=digest(analyzer.config.model_dump()))
        with self.assertRaises(ValueError):
            ProductAnalysis(service, self.store, authorization=auth).submit(self.email)
        self.assertEqual(self.repo.list_runs(), [])

    def test_mock_label_cannot_replace_real_transport_gate(self):
        self.analyzer.mock_http_transport = None
        with self.assertRaises(ValueError): self.app.submit(self.email)
        self.assertEqual(self.requests, []); self.assertEqual(self.repo.list_runs(), [])

    def test_accepted_unsafe_analysis_remains_blocked_after_reply_edit(self):
        email, output = example(SCENARIOS[2])
        self.email, self.output = email, output
        issue = self.output['issues'][0]
        issue.update(risk_level='minor', urgency='medium', urgency_basis='other')
        self.output['urgency'] = 'medium'
        self.budget = PilotBudget.create(self.root / 'safety-test-budget.sqlite3', [email.input_hash],
            dict(product_authorization_id='product-offline-test', config=self.analyzer.config.model_dump()))
        self.service = AnalysisService(self.repo, self.analyzer, budget=self.budget)
        self.auth = replace(self.auth, input_hashes=frozenset([email.input_hash]), budget_path=str(self.budget.path))
        case = ProductAnalysis(self.service, self.store, authorization=self.auth).submit(email)
        self.assertTrue(case['accepted'])
        self.assertTrue(any(f['code']=='potential_injury_downgrade' for f in case['quality']['findings']))
        actor = dict(actor='offline_test', actor_type='demo_test', reason='Known unsafe fixture')
        case = self.store.act(case['case_id'], 'save_edit', expected_revision=0,
            body='Please stop using the tray and do not reproduce the failure. Keep it aside for qualified assessment.', **actor)
        with self.assertRaises(Conflict):
            self.store.act(case['case_id'], 'approve', expected_revision=1,
                checks=dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True), **actor)

    def test_batch_explicit_coordinator_retains_row_failures(self):
        result = self.app.submit_many([self.email, self.email.model_copy(update={'body': 'not whitelisted'})])
        self.assertEqual([r['state'] for r in result], ['pending_review', 'input_or_authorization_rejected'])
        self.assertEqual(len(self.requests), 1)
