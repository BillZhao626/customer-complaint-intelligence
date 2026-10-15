"""Local-only frozen owner decisions and candidate assets; excluded from portable CI."""
import json
from pathlib import Path
import unittest
from src.evaluation.calibration import verify_snapshot,freeze_owner_supplement
from src.evaluation.e2e_v3 import validate_candidates,dataset_hash

ROOT=Path(__file__).resolve().parents[1]


class P35LocalAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=ROOT/'.local/p35/calibration-decision-v1.1/snapshot.json'
        cls.snapshot=verify_snapshot(cls.path,ROOT/'.local/p3/calibration-v1')
        cls.items={r['sample_id']:r['decision'] for r in cls.snapshot['records']}

    def test_complete_final_owner_freeze_no_fabricated_gold(self):
        self.assertEqual(len(self.items),24)
        self.assertFalse(self.snapshot['independent_expert_forms_received']);self.assertIsNone(self.snapshot['kappa'])
        self.assertEqual(self.snapshot['kind'],'RESEARCH_OWNER_CALIBRATION_DECISION')
        previous=verify_snapshot(ROOT/'.local/p35/calibration-decision-v1/snapshot.json')
        self.assertEqual(self.snapshot['previous_payload_hash'],previous['payload_hash'])

    def test_cannot_overwrite_frozen_snapshot(self):
        before=self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            freeze_owner_supplement(ROOT/'.local/p3/calibration-v1',ROOT/'.local/p35/supplement-original',
                ROOT/'.local/p35/calibration-decision-v1/snapshot.json',self.path)
        self.assertEqual(self.path.read_bytes(),before)

    def test_02_04_05_versioned_boundary_decisions(self):
        self.assertEqual(self.items['p25-hours']['owner_confirmed']['product_category'],'unknown')
        self.assertEqual(self.items['p25-repair']['owner_confirmed']['source_attribution'],'store service issue')
        self.assertEqual(self.items['p25-after_sales']['owner_confirmed']['source_attribution'],'customer service response issue')
        self.assertEqual(self.items['p25-repair']['owner_confirmed']['urgency'],'medium')

    def test_10_lossy_reference_is_preserved_not_relabelled(self):
        from src.application.v3_demo import demo_result
        from src.domain.analysis_v3 import to_v2
        self.assertEqual(self.items['p25-mixed_ambiguous']['owner_confirmed']['product_category'],'Clothing')
        result=demo_result();projection,diagnostics=to_v2(result)
        self.assertEqual(projection.product_category,'unknown')
        self.assertEqual([i.customer_importance for i in result.issues],['equal','equal'])
        self.assertTrue(any('No unique' in d for d in diagnostics))
        owner_projection,diag=to_v2(result,'owner-operational-v1')
        self.assertEqual(owner_projection.product_category,'Clothing')
        self.assertEqual(owner_projection.complaint_reason,'product quality')
        self.assertTrue(any('NOT customer' in d for d in diag))

    def test_15_16_17_19_21_and_safety(self):
        a=self.items['p25-commitment']['owner_confirmed'];self.assertEqual((a['sentiment'],a['is_complaint']),('neutral',True))
        self.assertFalse(self.items['p25-resolved']['owner_confirmed']['is_complaint'])
        self.assertEqual(self.items['p25-uncertain']['owner_confirmed']['source_attribution'],'unclear')
        self.assertEqual(self.items['p25-typo']['owner_confirmed']['complaint_reason'],'other')
        self.assertEqual(self.items['p25-typo']['owner_confirmed']['store_location'],'unknown')
        self.assertTrue(self.items['F176']['exclude_clean_semantic'])
        self.assertEqual(self.items['p25-chinese']['owner_confirmed']['urgency'],'high')

    def test_candidates_hash_audit_and_pending_references(self):
        path=ROOT/'.local/p35/dataset-candidate-v1'
        rows=validate_candidates(json.loads((path/'candidates.json').read_text(encoding='utf-8')))
        audit=json.loads((path/'audit.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows),160);self.assertEqual(dataset_hash(rows),audit['dataset_hash'])
        self.assertTrue(all(r.reference is None and r.review_status=='pending' for r in rows))
        self.assertEqual(audit['exact_normalized_body_duplicates'],[])
        self.assertEqual(audit['near_duplicates'],[]);self.assertEqual(audit['historical_near_matches'],[])
        self.assertGreaterEqual(audit['historical_checked'],400)

    def test_candidate_v2_quarantine_and_replacements_preserve_v1(self):
        path=ROOT/'.local/p35/dataset-candidate-v2'
        rows=validate_candidates(json.loads((path/'candidates.json').read_text(encoding='utf-8')))
        audit=json.loads((path/'audit.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows),172);self.assertEqual(sum(not r.exclusion_reason for r in rows),160)
        self.assertEqual(sum(r.split=='quarantine' for r in rows),12)
        self.assertEqual(dataset_hash(rows),audit['dataset_hash'])
        old=json.loads((ROOT/'.local/p35/dataset-candidate-v1/candidates.json').read_text(encoding='utf-8'))
        for a,b in zip(old,rows):self.assertEqual((a['subject'],a['body'],a['input_hash']),(b.subject,b.body,b.input_hash))
        self.assertEqual(audit['near_duplicates'],[]);self.assertEqual(audit['historical_near_matches'],[])
