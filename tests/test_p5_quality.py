"""P5 DEV engineering contracts; never a naturalness or real-model score."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.application import p5_quality as p5
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.application.reply_review import inspect_reply
from src.domain.contracts import digest
from src.infrastructure.repository import Repository


class P5QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.repo = Repository(Path(self.temp.name) / 'analysis.sqlite3')

    def case(self, cid='P5A-F01-M01-1'):
        email, _ = p5.example(cid)
        return ProductAnalysis(AnalysisService(self.repo, p5.P5CandidateAnalyzer(email, cid)), self.store).submit(email)

    def test_original_family_ids_splits_and_denominators_remain_separate(self):
        matrix = p5.families(); self.assertEqual(len(matrix), 48)
        self.assertEqual(len({m['parent_family_id'] for m in matrix}), 12)
        cases = p5.list_cases(); selected = {c['scenario_family'] for c in cases}
        self.assertEqual(len(cases), 48); self.assertEqual(len(selected), 16)
        self.assertEqual(sum(c['language'] == 'zh' for c in cases), 36)
        self.assertEqual(sum(c['language'] == 'en' for c in cases), 12)
        original = {m['microfamily_id']: m for m in matrix}
        for c in cases:
            self.assertEqual(original[c['scenario_family']]['split'], 'DEV')
            self.assertEqual(c['split'], 'DEV')
            self.assertEqual(c['model_call_count'], 0)
            self.assertIsNone(c['evaluation']['independent_gold'])
            self.assertIsNone(c['evaluation']['owner_signoff'])
        for fid in selected:
            self.assertEqual(sum(c['scenario_family'] == fid for c in cases), 3)

    def test_whitelisted_authored_outputs_survive_original_service_and_storage(self):
        for item in p5.list_cases():
            with self.subTest(case=item['case_id']):
                c = self.case(item['case_id'])
                self.assertTrue(c['accepted'])
                self.assertEqual(c['state'], 'pending_review')
                self.assertFalse(any(f['severity'] == 'block' for f in c['quality']['findings']))
                self.assertIsNone(c['receipt'])
                restored = ProductStore(self.store.path).get(c['case_id'])
                self.assertEqual(restored['analysis'], c['analysis'])
                self.assertIsNotNone(p5.p5_strategy(restored))
                self.assertEqual(c['run'].config.parameters['semantics'], 'developer_authored_synthetic_not_model_inference_not_human_gold')

    def test_mutated_mail_or_candidate_cannot_inherit_guidance(self):
        c = self.case(); email = c['run'].email
        with self.assertRaises(ValueError):
            p5.P5CandidateAnalyzer(email.model_copy(update={'body': email.body + ' another request'}), 'P5A-F01-M01-1')
        bad = copy.deepcopy(c); bad['analysis']['summary'] += ' wrong'
        self.assertIsNone(p5.p5_strategy(bad))
        for key in ('p5_policy_hash', 'p5_candidate_hash', 'fixture_hash', 'knowledge_snapshot_id', 'p5_case_id'):
            bad = copy.deepcopy(c)
            params = dict(c['run'].config.parameters, **{key: 'wrong'})
            bad['run'] = c['run'].model_copy(update={'config': c['run'].config.model_copy(update={'parameters': params})})
            self.assertIsNone(p5.p5_strategy(bad))
        for key in ('model_id', 'prompt_version'):
            bad = copy.deepcopy(c)
            bad['run'] = c['run'].model_copy(update={'config': c['run'].config.model_copy(update={key: 'wrong'})})
            self.assertIsNone(p5.p5_strategy(bad))

    def test_same_severe_fact_different_tone_never_downgrades_or_invites_reproduction(self):
        emotions = set()
        for n in (1, 2, 3):
            c = self.case('P5A-F05-M01-' + str(n)); strategy = p5.p5_strategy(c)
            emotions.add(strategy['customer_emotion']['primary'])
            self.assertEqual(strategy['action'], 'HARD_BLOCK')
            self.assertEqual(strategy['tier'], 'human_required')
            self.assertEqual(c['analysis']['issues'][0]['risk_level'], 'severe')
            self.assertEqual(c['analysis']['urgency'], 'high')
            self.assertTrue(c['quality']['safety_review_required'])
            self.assertIn('停止使用', c['draft']['body'])
            self.assertIn('不要骑行', c['draft']['body'])
        self.assertEqual(emotions, {'平静', '担心', '生气'})

    def test_customer_and_merchant_missing_information_do_not_collapse(self):
        camera = p5.get_case('P5A-F01-M01-1')
        self.assertEqual(camera['policy_decision']['customer_questions'], [])
        self.assertTrue(camera['policy_decision']['internal_questions'])
        wet = p5.get_case('P5A-F03-M01-1')
        self.assertEqual(wet['policy_decision']['action'], 'ASK_CLARIFICATION')
        self.assertEqual(len(wet['policy_decision']['customer_questions']), 1)
        self.assertNotIn('订单号', wet['policy_decision']['customer_questions'][0])
        complete = p5.get_case('P5A-F03-M02-1')
        self.assertEqual(complete['policy_decision']['customer_questions'], [])
        self.assertTrue(complete['policy_decision']['internal_questions'])

    def test_emotion_alone_does_not_change_p5_action(self):
        for fid in ('F01-M01', 'F03-M01', 'F04-M01', 'F12-M02'):
            values = [p5.get_case('P5A-' + fid + '-' + str(n)) for n in (1, 2, 3)]
            self.assertEqual(len({i['policy_decision']['action'] for i in values}), 1)
        self.assertEqual(p5.get_case('P5A-F10-M02-2')['policy_decision']['action'], 'ASK_HUMAN_INPUT')

    def test_multi_issue_spans_are_independent_and_order_not_customer_importance(self):
        for n in (1, 2, 3):
            _, data = p5.example('P5A-F08-M01-' + str(n))
            self.assertEqual(len(data['issues']), 3)
            self.assertEqual(len({i['evidence'][0]['quote'] for i in data['issues']}), 3)
            self.assertEqual({i['customer_importance'] for i in data['issues']}, {'unspecified'})
            self.assertEqual(data['relations'], [])
            self.assertEqual(data['issues'][2]['reason'], 'billing/invoice issue')

    def test_negated_product_failure_preserves_billing_complaint(self):
        for n in (1, 2, 3):
            _, data = p5.example('P5A-F12-M02-' + str(n))
            self.assertEqual(data['complaint_status'], 'current_unresolved')
            self.assertEqual(data['issues'][0]['reason'], 'billing/invoice issue')
            self.assertNotIn('product quality', [i['reason'] for i in data['issues']])

    def test_pending_knowledge_is_unusable_even_when_complete(self):
        for record in p5.knowledge_drafts():
            self.assertEqual(record['owner_approval'], 'OWNER_PENDING')
            self.assertEqual(record['use_in_model'], 'NO')
            self.assertTrue(record['claims'])
            self.assertIsNone(p5.approved_knowledge(retrieval_key=record['retrieval_key'], as_of='2026-10-28'))
        answer = p5.knowledge_answer()
        self.assertEqual(answer['action'], 'ASK_HUMAN_INPUT')
        self.assertIsNone(answer['answer'])

    @staticmethod
    def approved_fixture(**changes):
        value = dict(knowledge_id='TEST-ONLY-SPEC', kind='PRODUCT_SPEC', version='test-v1',
                     owner_approval='APPROVED', use_in_model='YES',
                     retrieval_key='DemoCam C200:wired_meeting', source_ref='explicit_test_fixture_not_owner_approval',
                     effective_from='2026-01-01', effective_to='2026-12-31', case_scope=None,
                     claims=dict(customer_answer='TEST ONLY: USB supports file transfer, not webcam mode.'))
        value.update(changes); return value

    def test_known_fact_counterfactual_answers_with_exact_source_only_in_explicit_fixture(self):
        record = self.approved_fixture()
        answer = p5.knowledge_answer(records=[record])
        self.assertEqual(answer['action'], 'ANSWER')
        self.assertEqual(answer['answer'], record['claims']['customer_answer'])
        self.assertEqual(answer['knowledge_refs'][0]['hash'], digest(record))
        # The fixture never changes the real draft catalog or default behaviour.
        self.assertEqual(p5.knowledge_answer()['action'], 'ASK_HUMAN_INPUT')

    def test_expired_conflicted_duplicate_and_wrong_case_knowledge_cannot_answer(self):
        for record in (self.approved_fixture(effective_to='2026-10-27'), self.approved_fixture(conflict=True),
                       self.approved_fixture(effective_from='2026-10-29'), self.approved_fixture(source_ref=None),
                       self.approved_fixture(kind='ORDER_FIXTURE', case_scope='case-A')):
            self.assertEqual(p5.knowledge_answer(records=[record], case_scope='case-B')['action'], 'ASK_HUMAN_INPUT')
        self.assertEqual(p5.knowledge_answer(records=[self.approved_fixture(), self.approved_fixture()])['action'], 'ASK_HUMAN_INPUT')

    def test_six_conversations_add_facts_without_fake_sent_or_gold(self):
        data = json.loads((p5.ROOT / 'conversations_dev.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data), 6)
        for c in data:
            self.assertNotEqual(c['turns'][0]['body'], c['turns'][2]['body'])
            self.assertEqual(c['turns'][1]['role'], 'agent_candidate_unsent')
            self.assertEqual(c['model_calls'], 0)
            self.assertIsNone(c['human_gold'])
            self.assertFalse(inspect_reply(c['turn2_customer_reply'])['findings'])

    def test_bad_case_before_is_exact_historical_source_and_after_is_candidate(self):
        from src.application.service_scenarios import example
        bad = json.loads((p5.ROOT / 'bad_cases.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(bad), 3)
        for item in bad:
            email, data = example(item['scenario'])
            self.assertEqual(item['email'], email.model_dump())
            self.assertEqual(item['input_hash'], email.input_hash)
            self.assertEqual(item['before_reply'], data['suggested_reply'])
            self.assertNotEqual(item['before_reply'], item['after_reply_candidate'])
            self.assertIsNone(item['human_scores'])
            self.assertEqual(item['quality_effect'], 'NOT_MEASURED')
            self.assertFalse(inspect_reply(item['after_reply_candidate'])['findings'])
            for phrase in ('不用再重复填写', '无需再重复说明', '您已提供型号', 'No refund or replacement has been approved here'):
                self.assertNotIn(phrase, item['after_reply_candidate'])

    def test_catalog_manifest_and_returned_copies_are_integrity_bound(self):
        manifest = json.loads((p5.ROOT / 'manifest.json').read_text(encoding='utf-8'))
        for filename, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((p5.ROOT / filename).read_bytes()).hexdigest(), expected)
        items = p5.list_cases(); original = items[0]['body']; items[0]['body'] = 'wrong'
        self.assertEqual(p5.list_cases()[0]['body'], original)


if __name__ == '__main__':
    unittest.main()
