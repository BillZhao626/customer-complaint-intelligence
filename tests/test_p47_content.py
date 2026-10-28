"""P4.7 offline content identity and workflow compatibility, not quality scores."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.application.service_scenarios import (
    SCENARIOS, CUSTOM_SCENARIO, VERSION, POLICY_VERSION, POLICY_HASH, example, ServiceCopilotFake, strategy,
)
from src.domain.analysis_v31 import AnalysisV31
from src.domain.contracts import EmailInput, digest
from src.infrastructure.repository import Repository


class ServiceContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.repo = Repository(Path(self.temp.name) / 'analysis.sqlite3')

    def case(self, index, email=None):
        name = SCENARIOS[index]
        email = email or example(name)[0]
        return ProductAnalysis(AnalysisService(self.repo, ServiceCopilotFake(email, name)), self.db).submit(email)

    def test_all_new_inputs_have_contract_evidence_and_saved_policy_identity(self):
        from src.application.copilot_demo import SCENARIOS as OLD, example as old_example
        old_inputs = {old_example(s)[0].input_hash for s in OLD}
        inputs = []
        for n, name in enumerate(SCENARIOS):
            email, data = example(name)
            AnalysisV31.model_validate(data).validate_input(email)
            c = self.case(n)
            self.assertTrue(c['accepted'], name)
            self.assertNotEqual(c['quality']['status'], 'blocked', name)
            self.assertEqual(c['analysis'], data)
            self.assertEqual(c['run'].config.parameters['service_policy_hash'], POLICY_HASH)
            self.assertEqual(c['run'].config.parameters['fixture_hash'], digest({email.input_hash: data}))
            self.assertIsNotNone(strategy(ProductStore(self.db.path).get(c['case_id'])))
            self.assertNotIn(email.input_hash, old_inputs)
            inputs.append(email.input_hash)
        self.assertEqual(len(set(inputs)), len(SCENARIOS))

    def test_safety_case_does_not_downgrade_no_injury_and_old_bad_analysis_remains(self):
        from src.application.copilot_demo import SCENARIOS as OLD, example as old_example, CopilotFake
        c = self.case(4)
        self.assertEqual(c['analysis']['urgency'], 'high')
        self.assertEqual(c['analysis']['issues'][0]['risk_level'], 'severe')
        self.assertTrue(c['quality']['safety_review_required'])
        self.assertEqual(strategy(c)['tier'], 'human_required')
        email, _ = old_example(OLD[8])
        old = ProductAnalysis(AnalysisService(self.repo, CopilotFake(email, OLD[8])), self.db).submit(email)
        self.assertEqual(old['analysis']['issues'][0]['risk_level'], 'minor')
        self.assertTrue(any(f['code'] == 'potential_injury_downgrade' for f in old['quality']['findings']))
        self.assertIsNone(strategy(old))

    def test_multi_issue_spans_routes_and_business_order_remain_distinct(self):
        data = self.case(3)['analysis']
        issues = data['issues']
        self.assertEqual(len(issues), 3)
        self.assertEqual([i['handling_priority'] for i in issues], [1, 2, 3])
        self.assertEqual([i['customer_importance'] for i in issues], ['unspecified'] * 3)
        self.assertEqual(len({digest(i['evidence']) for i in issues}), 3)
        self.assertEqual(issues[2]['reason'], 'billing/invoice issue')
        self.assertEqual(issues[2]['routing_team'], 'customer_support')

    def test_customer_requests_are_separate_from_merchant_verification(self):
        consultation, delivery, refund = self.case(0), self.case(1), self.case(6)
        guide = strategy(consultation)
        self.assertEqual(guide['tier'], 'ai_assist')
        self.assertIn('DemoCam C200 官方连接说明', guide['internal_verification'])
        self.assertNotIn('具体型号', guide['customer_info'])
        self.assertEqual(strategy(delivery)['tier'], 'human_confirm')
        self.assertEqual(strategy(refund)['tier'], 'human_required')
        self.assertIn('运费承担及处理权限', strategy(refund)['internal_verification'])

    def test_modified_authored_input_cannot_inherit_scenario_or_policy(self):
        email = example(SCENARIOS[0])[0]
        changed = email.model_copy(update={'body': 'This is a broken bicycle.'})
        with self.assertRaises(ValueError):
            ServiceCopilotFake(changed, SCENARIOS[0])
        c = self.case(0)
        bad = copy.copy(c)
        params = dict(c['run'].config.parameters, fixture_hash='tampered')
        bad['run'] = c['run'].model_copy(update={'config': c['run'].config.model_copy(update={'parameters': params})})
        self.assertIsNone(strategy(bad))
        bad = copy.deepcopy(c)
        bad['analysis']['issues'][0]['risk_level'] = 'severe'
        self.assertIsNone(strategy(bad))

    def test_custom_input_stays_unknown_with_language_and_bounded_safety(self):
        for body, language, risk in [
            ('My parcel is missing. What should I do?', 'en', 'unknown'),
            ('我想问下订单现在什么情况。', 'zh', 'unknown'),
            ('水壶使用时插座冒火花。', 'zh', 'severe'),
        ]:
            email = EmailInput(email_id='custom-' + digest(body)[:12], subject='New customer mail', body=body)
            c = self.case(SCENARIOS.index(CUSTOM_SCENARIO), email)
            self.assertTrue(c['accepted'])
            self.assertEqual(c['analysis']['complaint_status'], 'unknown')
            self.assertEqual(c['analysis']['reply_language'], language)
            self.assertEqual(c['analysis']['issues'][0]['risk_level'], risk)
            self.assertEqual(strategy(c)['tier'], 'human_required')
            self.assertEqual(c['run'].config.parameters['semantics'], 'authored_synthetic_or_unknown_not_model_inference')

    def test_demo_manifest_is_exclusive_and_preserves_version_hashes(self):
        from scripts.p47_demo import main
        out = Path(self.temp.name) / 'exclusive-p47'
        rows = main(out)
        manifest = json.loads((out / 'demo-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[-1]['scenario'],SCENARIOS[0])
        self.assertEqual(len({r['input_hash'] for r in rows}),11)
        self.assertTrue(manifest['demo_aftersales_policy_hash'])
        self.assertEqual(manifest['version'], VERSION)
        self.assertEqual(manifest['policy_version'], POLICY_VERSION)
        self.assertEqual(manifest['policy_hash'], POLICY_HASH)
        self.assertEqual(manifest['model_calls'], 0)
        self.assertTrue(all(r['input_hash'] and r['output_hash'] and r['scenario_hash'] for r in rows))
        before = (out / 'demo-manifest.json').read_bytes()
        with self.assertRaises(FileExistsError): main(out)
        self.assertEqual((out / 'demo-manifest.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
