"""Offline v2 safety communication, demo-policy binding and v1 preservation."""
import copy
from pathlib import Path
import tempfile
import unittest

from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.application import service_scenarios as v1
from src.application import service_scenarios_v2 as v2
from src.domain.contracts import digest
from src.infrastructure.repository import Repository


class ServiceContentV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.repo = Repository(Path(self.temp.name) / 'analysis.sqlite3')

    def case(self, index):
        name = v2.SCENARIOS[index]
        email, _ = v2.example(name)
        return ProductAnalysis(AnalysisService(self.repo, v2.ServiceCopilotFake(email, name)), self.db).submit(email)

    def test_same_safety_fact_with_different_emotions_retains_severe_high(self):
        results = [self.case(n) for n in range(3)]
        self.assertEqual({v2.strategy(c)['customer_emotion'] for c in results}, {'担忧', '平静', '生气'})
        evidence = []
        for c in results:
            self.assertTrue(c['accepted'])
            self.assertNotEqual(c['quality']['status'], 'blocked')
            self.assertTrue(c['quality']['safety_review_required'])
            self.assertEqual(c['analysis']['urgency'], 'high')
            self.assertEqual(c['analysis']['issues'][0]['risk_level'], 'severe')
            self.assertEqual(v2.strategy(c)['tier'], 'human_required')
            evidence.append(c['analysis']['issues'][0]['risk_evidence'][0]['quote'])
            for phrase in ('无人受伤', '没人受伤', '没有受伤', '幸好没摔倒'):
                self.assertNotIn(phrase, c['run'].email.body)
            reply = c['draft']['body']
            self.assertIn('停止使用', reply)
            self.assertIn('不要骑行', reply)
            self.assertIn('维修、更换或退货申请', reply)
        self.assertEqual(len(set(evidence)), 1)
        self.assertEqual(len({c['run'].input_hash for c in results}), 3)
        self.assertNotIn('害怕', results[1]['draft']['body'])
        self.assertNotIn('生气', results[1]['draft']['body'])

    def test_demo_policy_is_source_bound_durable_and_never_claims_approval(self):
        for n in range(len(v2.SCENARIOS)):
            c = self.case(n)
            restored = ProductStore(self.db.path).get(c['case_id'])
            guide = v2.strategy(restored)
            self.assertIsNotNone(guide)
            self.assertEqual(guide['demo_aftersales_policy_hash'], digest(guide['demo_aftersales_policy']))
            self.assertEqual(c['run'].config.parameters['demo_aftersales_policy_hash'], v2.DEMO_AFTERSALES_POLICY_HASH)
            policy = guide['demo_aftersales_policy']
            self.assertTrue(policy['simulation_only'])
            self.assertIn('演示', policy['title'])
            self.assertEqual(policy['options'], ['维修申请', '更换申请', '退货申请'])
            self.assertIn('不等于', policy['approval_boundary'])
            self.assertEqual(c['state'], 'pending_review')
            self.assertIsNone(c['receipt'])
            self.assertEqual([e['action'] for e in c['events']], ['created'])
            self.assertFalse(any(f['severity'] == 'block' for f in c['quality']['findings']))

    def test_wet_package_preserves_known_info_and_keeps_damage_uncertain(self):
        c = self.case(3)
        guide = v2.strategy(c)
        issue = c['analysis']['issues'][0]
        self.assertEqual(guide['tier'], 'human_confirm')
        self.assertEqual(issue['business_process'], 'delivery/logistics issue')
        self.assertEqual(issue['reason'], 'other')
        self.assertEqual(issue['risk_level'], 'none')
        self.assertIn('DEMO-24031', c['draft']['body'])
        self.assertIn('不用再重复填写或重新拍摄', c['draft']['body'])
        self.assertNotIn('订单编号', guide['customer_info'])
        self.assertIn('若商品或插头有受潮迹象，请不要通电', c['draft']['body'])
        self.assertIn('提出申请不代表已经获批', c['draft']['body'])
        self.assertIn('是否', guide['customer_info'][0])

    def test_policy_or_input_tampering_cannot_inherit_v2_guidance(self):
        c = self.case(0)
        bad = copy.deepcopy(c)
        params = dict(c['run'].config.parameters, demo_aftersales_policy_hash='wrong')
        bad['run'] = c['run'].model_copy(update={'config': c['run'].config.model_copy(update={'parameters': params})})
        self.assertIsNone(v2.strategy(bad))
        bad = copy.deepcopy(c)
        bad['analysis']['issues'][0]['risk_level'] = 'minor'
        self.assertIsNone(v2.strategy(bad))
        email, _ = v2.example(v2.SCENARIOS[0])
        with self.assertRaises(ValueError):
            v2.ServiceCopilotFake(email.model_copy(update={'body': email.body + ' 另一段来信。'}), v2.SCENARIOS[0])

    def test_v1_snapshots_and_guidance_survive_v2_example_creation(self):
        before = {name: digest(dict(email=v1.example(name)[0].model_dump(), analysis=v1.example(name)[1])) for name in v1.SCENARIOS}
        name = v1.SCENARIOS[4]
        email, data = v1.example(name)
        c = ProductAnalysis(AnalysisService(self.repo, v1.ServiceCopilotFake(email, name)), self.db).submit(email)
        old_guide = v1.strategy(c)
        self.assertEqual(old_guide['version'], 'p47-service-reply-policy-v1')
        self.assertIsNone(v2.strategy(c))
        for n in range(len(v2.SCENARIOS)):
            new = self.case(n)
            self.assertIsNone(v1.strategy(new))
        after = {name: digest(dict(email=v1.example(name)[0].model_dump(), analysis=v1.example(name)[1])) for name in v1.SCENARIOS}
        self.assertEqual(before, after)
        self.assertEqual(v1.strategy(ProductStore(self.db.path).get(c['case_id'])), old_guide)
        self.assertIn('幸好没摔倒', email.body)
        self.assertEqual(data, c['analysis'])


if __name__ == '__main__':
    unittest.main()
