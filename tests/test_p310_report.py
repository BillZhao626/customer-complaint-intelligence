"""Fixed denominators and unchanged raw comparison, no live provider."""
from pathlib import Path
import tempfile
import unittest
from src.application.p310_experiment import make_plan
from src.evaluation.p310_report import evaluate
from tests.test_p310_execution import inputs


class ResearchReportTests(unittest.TestCase):
    def test_missing40_per_arm_keeps_denominators(self):
        p=make_plan(inputs(40),'new40');r=evaluate(p,[])
        self.assertEqual(len(r['members']),80);self.assertEqual(len(r['pairs']),40)
        for arm in r['arms'].values():
            self.assertEqual(arm['planned'],40);self.assertEqual(arm['accepted'],0)
            self.assertEqual(arm['unattempted'],40);self.assertEqual(arm['acceptance_denominator'],40)
            self.assertEqual(arm['received'],0)
        self.assertFalse(r['quality_promotion_recommended']);self.assertIsNone(r['actual_invoice_cny'])

    def test_plan_hash_tamper_rejected(self):
        p=make_plan(inputs());p['inputs'][0]['email']['body']='changed'
        with self.assertRaises(ValueError):evaluate(p,[])

    def test_failed_raw_review_never_becomes_human_score(self):
        p=make_plan(inputs());r=evaluate(p,[])
        for m in r['members']:
            self.assertEqual(len(m['semantic_dimensions']),18)
            self.assertFalse(m['formal_accepted'])
            self.assertTrue(all(v['human_score'] is None and v['state']=='unreviewed' for v in m['semantic_dimensions'].values()))
