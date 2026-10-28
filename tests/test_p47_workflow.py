"""Local P4.7 routing and recovery; authored fixtures are not quality scores."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.application.analysis_service import AnalysisService
from src.application.copilot_demo import CopilotFake, SCENARIOS as LEGACY_SCENARIOS, example as legacy_example
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore, Conflict
from src.application.service_scenarios import SCENARIOS, CUSTOM_SCENARIO, ServiceCopilotFake, example
from src.application.service_triage import (
    triage, explicit_human_request, request_handoff, take_over, quick_confirm_and_simulate, is_p47_case,
)
from src.domain.contracts import EmailInput
from src.infrastructure.repository import Repository


CHECKS = dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True)


class ServiceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.db = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.repo = Repository(Path(self.temp.name) / 'analysis.sqlite3')

    def case(self, scenario=None):
        name = scenario or SCENARIOS[0]
        email, _ = example(name)
        return ProductAnalysis(AnalysisService(self.repo, ServiceCopilotFake(email, name)), self.db).submit(email)

    def legacy(self, n=0):
        email, _ = legacy_example(LEGACY_SCENARIOS[n])
        return ProductAnalysis(AnalysisService(self.repo, CopilotFake(email, LEGACY_SCENARIOS[n])), self.db).submit(email)

    def custom(self, body):
        email = EmailInput(email_id='manual-p47-fixture', subject='客户补充来信', body=body)
        return ProductAnalysis(AnalysisService(self.repo, ServiceCopilotFake(email, CUSTOM_SCENARIO)), self.db).submit(email)

    def v2_case(self, scenario):
        from src.application.service_scenarios_v2 import example as v2_example, ServiceCopilotFake as V2Fake
        email, _ = v2_example(scenario)
        return ProductAnalysis(AnalysisService(self.repo, V2Fake(email, scenario)), self.db).submit(email)

    def act(self, case, action, **kwargs):
        args = dict(expected_revision=case['revision'], actor='offline_operator', actor_type='demo_test',
                    reason='Offline workflow acceptance; not independent human evaluation', checks=CHECKS)
        args.update(kwargs)
        return self.db.act(case['case_id'], action, **args)

    def quick(self, case, **kwargs):
        args = dict(expected_revision=case['revision'], actor='offline_operator', actor_type='demo_test',
                    confirmed=True, operation_id='quick-' + case['case_id'])
        args.update(kwargs)
        return quick_confirm_and_simulate(self.db, case['case_id'], **args)

    def test_routine_uses_explicit_confirmation_and_original_receipt_gates(self):
        case = self.case(); route = triage(case)
        self.assertEqual(route['level'], 'ai_assist')
        self.assertTrue(route['can_quick_confirm'])
        with self.assertRaises(Conflict): self.quick(case, confirmed=False)
        self.assertEqual(self.db.get(case['case_id'])['revision'], 0)
        sent = self.quick(case)
        self.assertEqual([e['action'] for e in sent['events']], ['created', 'approve', 'simulate_send'])
        self.assertTrue(sent['events'][1]['details']['checks']['quick_confirmation']['confirmed'])
        self.assertEqual(sent['receipt']['body_hash'], sent['draft']['body_hash'])
        self.assertEqual(sent['receipt']['mode'], 'simulation_only')

    def test_confirmation_retry_recovers_both_committed_transactions(self):
        case = self.case(); sent = self.quick(case)
        retried = self.quick(case)
        self.assertEqual(sent, retried)
        self.assertEqual(len(retried['events']), 3)
        with self.assertRaises(Conflict): self.quick(case, actor='different_operator')
        with self.assertRaises(Conflict): self.quick(case, expected_revision=case['revision'] + 1)

    def test_send_failure_preserves_approval_and_explicit_retry_resumes(self):
        case = self.case(); original = self.db._event
        def fail_send(*args, **kwargs):
            if args[4] == 'simulate_send':
                raise sqlite3.OperationalError('Injected send-event disk failure')
            return original(*args, **kwargs)
        with patch.object(self.db, '_event', side_effect=fail_send):
            with self.assertRaises(sqlite3.OperationalError): self.quick(case)
        restored = ProductStore(self.db.path).get(case['case_id'])
        self.assertEqual(restored['state'], 'approved')
        self.assertIsNone(restored['receipt'])
        self.assertEqual([e['action'] for e in restored['events']], ['created', 'approve'])
        sent = self.quick(case)
        self.assertEqual(sent['state'], 'simulated_sent')
        self.assertEqual(len(sent['events']), 3)

    def test_lost_approval_response_is_not_automatically_retried(self):
        case = self.case(); original = self.db.get
        def lost_response(case_id):
            result = original(case_id)
            if result and result['state'] == 'approved':
                raise sqlite3.OperationalError('Injected lost committed approval response')
            return result
        with patch.object(self.db, 'get', side_effect=lost_response):
            with self.assertRaises(sqlite3.OperationalError): self.quick(case)
        self.assertEqual(self.db.get(case['case_id'])['state'], 'approved')
        self.assertEqual(self.quick(case)['state'], 'simulated_sent')

    def test_lost_send_response_recovers_existing_receipt_without_duplicate_event(self):
        case = self.case(); original = self.db.get
        def lost_response(case_id):
            result = original(case_id)
            if result and result['state'] == 'simulated_sent':
                raise sqlite3.OperationalError('Injected lost committed receipt response')
            return result
        with patch.object(self.db, 'get', side_effect=lost_response):
            with self.assertRaises(sqlite3.OperationalError): self.quick(case)
        receipt = self.db.get(case['case_id'])['receipt']
        recovered = self.quick(case)
        self.assertEqual(recovered['receipt'], receipt)
        self.assertEqual(len(recovered['events']), 3)

    def test_new_draft_or_intervening_handoff_cannot_resume_stale_confirmation(self):
        case = self.case(); original = self.db._event
        def fail_send(*args, **kwargs):
            if args[4] == 'simulate_send': raise sqlite3.OperationalError('Injected failure')
            return original(*args, **kwargs)
        with patch.object(self.db, '_event', side_effect=fail_send):
            with self.assertRaises(sqlite3.OperationalError): self.quick(case)
        current = self.db.get(case['case_id'])
        changed = self.act(current, 'save_edit', body=current['draft']['body'] + '\n补充说明：型号仍需核实。')
        with self.assertRaises(Conflict): self.quick(case)
        self.assertEqual(self.db.get(case['case_id']), changed)

    def test_intervening_handoff_cannot_resume_stale_confirmation(self):
        case = self.case(); original = self.db._event
        def fail_send(*args, **kwargs):
            if args[4] == 'simulate_send': raise sqlite3.OperationalError('Injected failure')
            return original(*args, **kwargs)
        with patch.object(self.db, '_event', side_effect=fail_send):
            with self.assertRaises(sqlite3.OperationalError): self.quick(case)
        current = self.db.get(case['case_id'])
        requested = self.act(current, 'request_handoff')
        with self.assertRaises(Conflict): self.quick(case)
        self.assertEqual(self.db.get(case['case_id']), requested)

    def test_manual_handoff_and_takeover_are_persisted_without_changing_draft(self):
        case = self.case()
        request = dict(expected_revision=case['revision'], actor='offline_operator', actor_type='demo_test',
                       reason='客户希望有人继续跟进；本地演示', operation_id='handoff-request')
        requested = request_handoff(self.db, case['case_id'], **request)
        self.assertEqual(request_handoff(self.db, case['case_id'], **request), requested)
        self.assertEqual(triage(requested)['handoff'], 'requested')
        self.assertFalse(triage(requested)['can_quick_confirm'])
        self.assertEqual(requested['state'], case['state'])
        self.assertEqual(requested['drafts'], case['drafts'])
        detail = requested['events'][-1]['details']['handoff']
        self.assertEqual(detail['run_id'], case['run'].run_id)
        self.assertEqual(detail['input_hash'], case['run'].input_hash)
        self.assertEqual(detail['body_hash'], case['draft']['body_hash'])
        with self.assertRaises(Conflict): self.act(case, 'take_over')
        owned = take_over(self.db, case['case_id'], expected_revision=requested['revision'],
                          actor='offline_operator', actor_type='demo_test', reason='本地接管并阅读原文', operation_id='takeover')
        self.assertTrue(triage(owned)['takeover_complete'])
        self.assertEqual(triage(owned)['owner'], 'offline_operator')
        self.assertEqual(ProductStore(self.db.path).get(case['case_id']), owned)
        self.assertEqual(owned['drafts'], case['drafts'])

    def test_customer_human_request_is_atomic_idempotent_system_request_not_takeover(self):
        case = self.custom('之前的回答没有说明白，请转人工客服，我想和真人确认。')
        self.assertEqual([e['action'] for e in case['events']], ['created', 'request_handoff'])
        self.assertEqual(case['events'][-1]['actor_type'], 'system')
        self.assertEqual(triage(case)['handoff'], 'requested')
        self.assertFalse(triage(case)['takeover_complete'])
        self.assertIn('customer_requested', triage(case)['reason_codes'])
        self.assertEqual(self.db.create(case['run']), case)
        with self.assertRaises(Conflict): self.act(case, 'approve')

    def test_customer_request_event_failure_rolls_back_entire_product_case(self):
        email = EmailInput(email_id='atomic-customer-handoff', subject='希望人工处理', body='请转人工客服，我有信息要核对。')
        run = AnalysisService(self.repo, ServiceCopilotFake(email, CUSTOM_SCENARIO)).analyze(email)
        original = self.db._event
        def fail_handoff(*args, **kwargs):
            if args[4] == 'request_handoff': raise sqlite3.OperationalError('Injected handoff-event failure')
            return original(*args, **kwargs)
        with patch.object(self.db, '_event', side_effect=fail_handoff):
            with self.assertRaises(sqlite3.OperationalError): self.db.create(run)
        self.assertEqual(self.db.list_cases(), [])
        recovered = self.db.create(self.repo.get(run.run_id))
        self.assertEqual([e['action'] for e in recovered['events']], ['created', 'request_handoff'])
        self.assertEqual(recovered['run'].run_id, run.run_id)

    def test_human_request_negative_and_customer_content_are_bounded(self):
        for text in ('不用转人工客服，只要说明型号在哪里。', '我不需要人工客服。', "I do not need a human agent."):
            self.assertFalse(explicit_human_request(text), text)
        for text in ('请转人工客服。', 'I would like a human agent.', '不用解释了，但是请转人工。'):
            self.assertTrue(explicit_human_request(text), text)
        case = self.custom('不要转人工客服，我只是想知道怎么找到型号。')
        self.assertEqual([e['action'] for e in case['events']], ['created'])
        self.assertEqual(triage(case)['level'], 'human_required')  # unknown stays unknown

    def test_high_safety_requires_takeover_and_original_safety_check(self):
        case = self.case(SCENARIOS[4])
        self.assertTrue(case['accepted'])
        self.assertNotEqual(case['quality']['status'], 'blocked')
        self.assertEqual(triage(case)['level'], 'human_required')
        with self.assertRaises(Conflict): self.act(case, 'approve')
        with self.assertRaises(Conflict): self.quick(case)
        owned = self.act(case, 'take_over')
        with self.assertRaises(Conflict): self.act(owned, 'approve', checks={k: v for k, v in CHECKS.items() if k != 'safety'})
        approved = self.act(owned, 'approve')
        self.assertEqual(self.act(approved, 'simulate_send')['state'], 'simulated_sent')

    def test_blocked_analysis_remains_blocked_after_takeover_and_reply_edit(self):
        case = self.legacy(8)
        requested = self.act(case, 'request_handoff')
        owned = self.act(requested, 'take_over')
        changed = self.act(owned, 'save_edit', body='Please do not ride the bicycle or reproduce the failure. Existing photos and the order reference would help a safety review.')
        self.assertTrue(triage(changed)['takeover_complete'])
        for action in ('approve', 'simulate_send'):
            with self.assertRaises(Conflict): self.act(changed, action)
        self.assertIsNone(self.db.get(case['case_id'])['receipt'])

    def test_failed_analysis_allows_handoff_but_never_gains_a_draft(self):
        case = self.legacy(4)
        self.assertEqual(case['state'], 'analysis_failed')
        owned = self.act(self.act(case, 'request_handoff'), 'take_over')
        self.assertEqual(owned['state'], 'analysis_failed')
        self.assertEqual(owned['drafts'], [])
        self.assertIsNone(owned['draft'])
        self.assertTrue(triage(owned)['takeover_complete'])
        for action in ('approve', 'save_edit', 'simulate_send'):
            with self.assertRaises(Conflict): self.act(owned, action, body='Human text cannot create an accepted analysis')

    def test_handoff_requires_reason_and_rolls_back_with_event_failure(self):
        case = self.case()
        for action in ('request_handoff', 'take_over'):
            with self.assertRaises(Conflict): self.act(case, action, reason='')
        with patch.object(self.db, '_event', side_effect=sqlite3.OperationalError('Injected disk failure')):
            with self.assertRaises(sqlite3.OperationalError): self.act(case, 'request_handoff')
        self.assertEqual(self.db.get(case['case_id']), case)
        sent = self.quick(case)
        with self.assertRaises(Conflict): self.act(sent, 'request_handoff')

    def test_reply_block_and_unknown_never_use_quick_confirmation(self):
        case = self.act(self.case(), 'save_edit', body='我们会为您退款，保证明天到账。')
        self.assertEqual(case['quality']['status'], 'blocked')
        with self.assertRaises(Conflict): self.quick(case)
        unknown = self.custom('好的，那个事情还是上次说的那样。')
        self.assertIn('unknown_intent', triage(unknown)['reason_codes'])
        with self.assertRaises(Conflict): self.quick(unknown)
        self.assertIsNone(self.db.get(unknown['case_id'])['receipt'])

    def test_rejected_draft_cannot_offer_quick_confirmation_before_real_edit(self):
        case = self.act(self.case(), 'reject')
        self.assertFalse(triage(case)['can_quick_confirm'])
        with self.assertRaises(Conflict): self.quick(case)
        changed = self.act(case, 'save_edit', body=case['draft']['body'] + '\n请先确认设备标签上的型号。')
        self.assertEqual(changed['state'], 'pending_review')
        self.assertTrue(triage(changed)['can_quick_confirm'])

    def test_p47_returned_draft_requires_real_edit_while_legacy_remains_compatible(self):
        returned = self.act(self.case(), 'request_changes')
        self.assertFalse(triage(returned)['can_quick_confirm'])
        with self.assertRaises(Conflict): self.quick(returned)
        with self.assertRaises(Conflict): self.act(returned, 'approve')
        unchanged = self.act(returned, 'save_edit', body=returned['draft']['body'])
        self.assertEqual(unchanged['state'], 'changes_requested')
        changed = self.act(returned, 'save_edit', body=returned['draft']['body'] + '\n型号可以在机身标签上查看。')
        self.assertEqual(changed['state'], 'pending_review')
        self.assertTrue(triage(changed)['can_quick_confirm'])
        legacy_returned = self.act(self.legacy(), 'request_changes')
        self.assertEqual(self.act(legacy_returned, 'approve')['state'], 'approved')

    def test_legacy_review_compatibility_and_database_schema_are_unchanged(self):
        case = self.legacy(2)  # existing safety path has no new ownership precondition
        self.assertEqual(triage(case)['level'], 'human_required')
        approved = self.act(case, 'approve')
        self.assertEqual(self.act(approved, 'simulate_send')['state'], 'simulated_sent')
        with self.db.connect() as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_v2_safety_emotions_keep_severe_high_and_require_takeover(self):
        from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, POLICY_VERSION, POLICY_HASH
        hashes = []
        for name in V2_SCENARIOS[:3]:
            with self.subTest(scenario=name):
                case = self.v2_case(name)
                self.assertTrue(is_p47_case(case))
                self.assertTrue(case['accepted'])
                self.assertNotEqual(case['quality']['status'], 'blocked')
                self.assertEqual(case['analysis']['urgency'], 'high')
                self.assertEqual(case['analysis']['issues'][0]['risk_level'], 'severe')
                self.assertEqual(case['analysis']['issues'][0]['urgency'], 'high')
                self.assertEqual(case['run'].config.parameters['service_policy_version'], POLICY_VERSION)
                self.assertEqual(case['run'].config.parameters['service_policy_hash'], POLICY_HASH)
                hashes.append(case['run'].input_hash)
                route = triage(case)
                self.assertEqual(route['level'], 'human_required')
                self.assertTrue(route['requires_takeover'])
                self.assertIn('safety', route['reason_codes'])
                self.assertNotIn('unbound_strategy', route['reason_codes'])
                self.assertFalse(route['can_quick_confirm'])
                with self.assertRaises(Conflict): self.act(case, 'approve')
                with self.assertRaises(Conflict): self.quick(case)
                owned = self.act(case, 'take_over')
                with self.assertRaises(Conflict):
                    self.act(owned, 'approve', checks={k: v for k, v in CHECKS.items() if k != 'safety'})
                approved = self.act(owned, 'approve')
                self.assertEqual(self.act(approved, 'simulate_send')['state'], 'simulated_sent')
        self.assertEqual(len(set(hashes)), 3)

    def test_v2_delivery_uses_human_confirmation_and_same_source_bound_policy(self):
        from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, POLICY_VERSION, POLICY_HASH
        case = self.v2_case(V2_SCENARIOS[3])
        self.assertTrue(is_p47_case(case))
        self.assertTrue(case['accepted'])
        self.assertNotEqual(case['quality']['status'], 'blocked')
        self.assertEqual(case['run'].config.parameters['service_policy_version'], POLICY_VERSION)
        self.assertEqual(case['run'].config.parameters['service_policy_hash'], POLICY_HASH)
        route = triage(case)
        self.assertEqual(route['level'], 'human_confirm')
        self.assertFalse(route['requires_takeover'])
        self.assertFalse(route['can_quick_confirm'])
        self.assertNotIn('unbound_strategy', route['reason_codes'])
        with self.assertRaises(Conflict): self.quick(case)
        self.assertEqual(self.act(self.act(case, 'approve'), 'simulate_send')['state'], 'simulated_sent')

    def test_v1_and_v2_strategies_are_never_rebound_across_policy_versions(self):
        from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS
        case = self.case()
        self.assertTrue(triage(case)['can_quick_confirm'])
        run = case['run']
        params = dict(run.config.parameters, service_policy_version='p47-service-reply-policy-v2')
        wrong = dict(case, run=run.model_copy(update=dict(config=run.config.model_copy(update=dict(parameters=params)))))
        self.assertEqual(triage(wrong)['level'], 'human_required')
        self.assertIn('unbound_strategy', triage(wrong)['reason_codes'])
        v2 = self.v2_case(V2_SCENARIOS[1])
        self.assertEqual(v2['analysis']['issues'][0]['risk_level'], 'severe')
        self.assertEqual(triage(v2)['level'], 'human_required')
        self.assertTrue(triage(self.db.get(case['case_id']))['can_quick_confirm'])


if __name__ == '__main__':
    unittest.main()
