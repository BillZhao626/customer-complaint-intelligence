"""Source lineage and freeze enforcement; no independence claim from similarity."""
import unittest
from tests.test_p310_execution import inputs
from src.evaluation.p310_leakage import screen


class LeakageTests(unittest.TestCase):
    def test_freeze_and_exact_overlap_are_explicit(self):
        rows=[dict(r,semantic_family='fixture-family',template_group=str(n),translation_source=None) for n,r in enumerate(inputs(40))]
        with self.assertRaises(ValueError):screen(rows,inputs(2),{})
        r=screen(rows,inputs(2),{'candidate_frozen_before_new_data':True})
        self.assertEqual(r['exact_old_duplicates'],2);self.assertFalse(r['independence_claim'])
        self.assertTrue(all(x['independent_human_holdout'] is False for x in r['records']))
        self.assertEqual(r['new_count'],40)

    def test_duplicates_and_wrong_denominator_rejected(self):
        with self.assertRaises(ValueError):screen(inputs(39),inputs(1),{'candidate_frozen_before_new_data':True})
        rows=inputs(40);rows[-1]=rows[0]
        with self.assertRaises(ValueError):screen(rows,inputs(1),{'candidate_frozen_before_new_data':True})
