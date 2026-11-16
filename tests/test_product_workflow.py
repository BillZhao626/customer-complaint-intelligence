"""Vertical integration and recovery against real temporary SQLite databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from src.application.analysis_service import AnalysisService
from src.application.product_workflow import ProductStore, Conflict
from src.application.product_demo import ProductFake, example, SCENARIOS
from src.infrastructure.repository import Repository
from src.domain.contracts import digest

CHECKS = dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True)


class ProductWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.db = ProductStore(self.path / 'product.sqlite3')
        self.repo = Repository(self.path / 'analysis.sqlite3')

    def create(self, scenario=0):
        e, _ = example(SCENARIOS[scenario])
        r = AnalysisService(self.repo, ProductFake(e, SCENARIOS[scenario])).analyze(e)
        return self.db.create(r)

    def act(self, c, action, **kwargs):
        args = dict(expected_revision=c['revision'], actor='offline_acceptance_operator', actor_type='demo_test',
                    reason='Explicit engineering acceptance, not human quality rating', checks=CHECKS)
        args.update(kwargs)
        return self.db.act(c['case_id'], action, **args)

    def test_complete_inquiry_approve_simulate_restart_dashboard(self):
        c = self.create()
        self.assertEqual(c['state'], 'pending_review')
        self.assertEqual(len(c['analysis']['issues'][0]['evidence']), 1)
        c = self.act(c, 'approve')
        c = self.act(c, 'simulate_send')
        fresh = ProductStore(self.db.path).get(c['case_id'])
        self.assertEqual(fresh['receipt']['body'], fresh['draft']['body'])
        self.assertEqual(fresh['state'], 'simulated_sent')
        self.assertEqual(len(fresh['events']), 3)
        stats = self.db.dashboard()
        self.assertEqual(stats['states'], {'simulated_sent': 1})
        self.assertEqual(stats['groups'][0]['accepted'], 1)

    def test_multi_issue_evidence_order_survives_full_cycle(self):
        c = self.create(1)
        self.assertEqual([i['handling_priority'] for i in c['analysis']['issues']], [1, 2, 3])
        original = c['run'].model_dump()
        c = self.act(c, 'approve')
        c = self.act(c, 'simulate_send')
        self.assertEqual(ProductStore(self.db.path).get(c['case_id'])['run'].model_dump(), original)

    def test_severe_risk_requires_explicit_safety_review(self):
        c = self.create(2)
        self.assertTrue(c['quality']['safety_review_required'])
        with self.assertRaises(Conflict):
            self.act(c, 'approve', checks={k: v for k, v in CHECKS.items() if k != 'safety'})
        c = self.act(c, 'approve')
        self.assertEqual(self.act(c, 'simulate_send')['state'], 'simulated_sent')

    def test_failed_contract_and_provider_have_no_draft_no_statistics(self):
        for scenario in (4, 5):
            c = self.create(scenario)
            self.assertEqual(c['state'], 'analysis_failed')
            self.assertIsNone(c['draft'])
            for action in ('approve', 'simulate_send', 'save_edit'):
                with self.assertRaises(Conflict):
                    self.act(c, action, body='Please help.')
        stats = self.db.dashboard()
        self.assertEqual(sum(g['accepted'] for g in stats['groups']), 0)
        self.assertEqual(sum(g['negative'] for g in stats['groups']), 0)
        self.assertEqual(sum(g['failed'] for g in stats['groups']), 2)

    def test_blocked_promise_edit_version_diff_review_send(self):
        c = self.create(3); old = c['draft']['body']
        with self.assertRaises(Conflict):
            self.act(c, 'approve')
        c = self.act(c, 'request_changes')
        c = self.act(c, 'save_edit', body='Thank you for describing the lamp fault. Please share its model so the available support options can be verified.')
        self.assertEqual(c['state'], 'pending_review')
        self.assertEqual(c['drafts'][0]['body'], old)
        self.assertEqual(c['current_version'], 2)
        c = self.act(c, 'approve')
        c = self.act(c, 'simulate_send')
        self.assertEqual(c['receipt']['version'], 2)
        self.assertNotIn('will contact', c['receipt']['body'])

    def test_edit_after_approval_invalidates_old_approval_and_stale_page(self):
        c = self.act(self.create(), 'approve')
        stale = c
        c = self.act(c, 'save_edit', body=c['draft']['body'] + ' Please include the model label.')
        self.assertEqual(c['state'], 'pending_review')
        with self.assertRaises(Conflict):
            self.act(stale, 'simulate_send')
        with self.assertRaises(Conflict):
            self.act(c, 'simulate_send')
        c = self.act(c, 'approve')
        self.assertEqual(self.act(c, 'simulate_send')['receipt']['version'], 2)

    def test_reject_reason_return_reason_and_unauthorized_state_transition(self):
        c = self.create()
        for action in ('reject', 'request_changes', 'approve'):
            with self.assertRaises(Conflict):
                self.act(c, action, reason='')
        with self.assertRaises(Conflict):
            self.act(c, 'simulate_send')
        with self.assertRaises(Conflict):
            self.act(c, 'force_send')
        c = self.act(c, 'reject')
        for action in ('approve', 'simulate_send', 'request_changes'):
            with self.assertRaises(Conflict):
                self.act(c, action)
        c = self.act(c, 'save_edit', body=c['draft']['body'] + ' A product specialist can verify specifications.')
        self.assertEqual(c['state'], 'pending_review')

    def test_idempotent_retries_approval_simulation_and_key_collision(self):
        c = self.create(); original = c
        c = self.act(c, 'approve', operation_id='same-approve')
        retried = self.act(original, 'approve', operation_id='same-approve')
        self.assertEqual(retried['revision'], c['revision'])
        with self.assertRaises(Conflict):
            self.act(original, 'approve', operation_id='same-approve', reason='Changed request')
        self.assertEqual(self.act(c, 'approve')['revision'], c['revision'])
        approved = c
        c = self.act(c, 'simulate_send', operation_id='same-send')
        self.assertEqual(self.act(approved, 'simulate_send', operation_id='same-send')['receipt'], c['receipt'])
        self.assertEqual(self.act(c, 'simulate_send')['receipt'], c['receipt'])
        with self.assertRaises(Conflict):
            self.act(c, 'save_edit', body='Changed after send')

    def test_duplicate_source_does_not_reset_review_or_add_drafts(self):
        c = self.act(self.create(), 'approve')
        again = self.create()
        self.assertEqual(again['case_id'], c['case_id'])
        self.assertEqual(again['state'], 'approved')
        self.assertEqual(len(again['drafts']), 1)

    def test_parallel_approval_only_one_event(self):
        c = self.create()
        def approve(_):
            try:
                return self.act(c, 'approve')['state']
            except Conflict:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(approve, range(2)))
        self.assertEqual(sorted(outcomes), ['approved', 'stale'])
        self.assertEqual(len(self.db.get(c['case_id'])['events']), 2)

    def test_sqlite_failure_rolls_back_version_and_receipt(self):
        c = self.create()
        with patch.object(self.db, '_event', side_effect=sqlite3.OperationalError('injected disk failure')):
            with self.assertRaises(sqlite3.OperationalError):
                self.act(c, 'save_edit', body='A revised draft.')
        fresh = self.db.get(c['case_id'])
        self.assertEqual(fresh['revision'], c['revision'])
        self.assertEqual(len(fresh['drafts']), 1)
        c = self.act(c, 'approve')
        with patch.object(self.db, '_event', side_effect=sqlite3.OperationalError('injected disk failure')):
            with self.assertRaises(sqlite3.OperationalError):
                self.act(c, 'simulate_send')
        fresh = self.db.get(c['case_id'])
        self.assertEqual(fresh['state'], 'approved')
        self.assertIsNone(fresh['receipt'])
        self.assertEqual(self.act(fresh, 'simulate_send')['state'], 'simulated_sent')

    def test_unconfirmed_commit_retry_recovers_exact_operation(self):
        c = self.create()
        real_get = self.db.get
        calls = []
        def late_read_failure(case_id):
            calls.append(case_id)
            if len(calls) == 2:
                raise sqlite3.OperationalError('post-commit read failure')
            return real_get(case_id)
        with patch.object(self.db, 'get', side_effect=late_read_failure):
            with self.assertRaises(sqlite3.OperationalError):
                self.act(c, 'approve', operation_id='committed-but-response-lost')
        recovered = self.act(c, 'approve', operation_id='committed-but-response-lost')
        self.assertEqual(recovered['state'], 'approved')
        self.assertEqual(len(recovered['events']), 2)

    def test_immutable_versions_and_events_and_database_identity(self):
        c = self.create()
        for sql in ('UPDATE product_drafts SET body="modified"', 'DELETE FROM product_drafts', 'UPDATE product_events SET reason="modified"', 'DELETE FROM product_events'):
            with self.assertRaises(sqlite3.IntegrityError), self.db.connect() as conn:
                conn.execute(sql)
        with self.assertRaises(ValueError):
            ProductStore(self.repo.path)
        with self.assertRaises(ValueError):
            ProductStore(Path(__file__).resolve().parents[1] / '.local/p310/forbidden.sqlite3')
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_tampered_state_cannot_send_without_approval_event(self):
        c = self.create()
        with self.db.connect() as conn:
            conn.execute("UPDATE product_workflow SET state='approved' WHERE case_id=?", (c['case_id'],))
        c = self.db.get(c['case_id'])
        with self.assertRaises(Conflict):
            self.act(c, 'simulate_send')

    def test_identity_and_review_checklist_cannot_be_inherited(self):
        c = self.create()
        self.assertEqual(c['events'][0]['actor_type'], 'system')
        for args in ({'actor': ''}, {'actor_type': 'system'}, {'checks': {}}):
            with self.assertRaises(Conflict):
                self.act(c, 'approve', **args)
        self.assertTrue(all(e['action'] != 'approve' for e in self.db.get(c['case_id'])['events']))

    def test_changed_policy_after_approval_invalidates_send(self):
        c = self.act(self.create(), 'approve')
        from src.application import product_workflow as w
        old = w.inspect
        def different(*args, **kwargs):
            result = old(*args, **kwargs)
            result['version'] = 'next-guard-version'
            return result
        with patch.object(w, 'inspect', side_effect=different):
            with self.assertRaises(Conflict):
                self.act(c, 'simulate_send')

    def test_local_real_replay_accepted_unsafe_does_not_become_sendable(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / '.local/p310/FINAL_REVIEW_V2/content-review.json').exists():
            self.skipTest('Private real-model source not present')
        from src.application.product_sources import catalog, read_run
        item = next(i for i in catalog(root) if i['run_id'] == '86d85387-9dcc-49be-80a1-0ac55019af65')
        run = read_run(item['path'], item['run_id'])
        c = self.db.create(run, item['path'])
        self.assertEqual(c['source_kind'], 'real_replay')
        self.assertTrue(c['accepted'])
        self.assertEqual(c['quality']['status'], 'blocked')
        self.assertEqual(self.db.dashboard()['groups'][0]['business_denominator'], 0)
        with self.assertRaises(Conflict):
            self.act(c, 'approve')
        c = self.act(c, 'save_edit', body='Please do not ride the bike. Keep it aside and use existing photos only.')
        with self.assertRaises(Conflict):
            self.act(c, 'approve')
        c = self.act(c, 'reject')
        self.assertEqual(ProductStore(self.db.path).get(c['case_id'])['state'], 'rejected')
