"""Local research evidence only. Excluded from portable CI; never calls provider."""
import json
from pathlib import Path
import unittest
from src.evaluation.p37_replay import audit_p36
from src.evaluation.semantic_review import validate_review
from src.application.v3_remediation import verify_derived
from src.domain.contracts import digest
from src.evaluation.e2e_v3 import validate_candidates,Candidate,dataset_hash

ROOT=Path(__file__).resolve().parents[1]


class P37LocalAssets(unittest.TestCase):
    def test_all40_replay_and_original_metrics_are_frozen(self):
        audit,groups=audit_p36(ROOT/'.local/p36')
        self.assertEqual((audit['runs'],audit['budget_requests'],audit['new_model_requests']),(40,40,0))
        self.assertEqual((audit['frozen_all24']['field_correct'],audit['frozen_all24']['all_correct']),(143,17))
        self.assertEqual((audit['frozen_final_succeeded'],audit['frozen_final_attempted']),(29,32))

    def test_unsigned24_and_candidate32_keep_source_quality_and_hashes(self):
        audit,groups=audit_p36(ROOT/'.local/p36');runs={r.run_id:r for r in groups['draft-v3']}
        packets=json.loads((ROOT/'.local/p37/review-v1/semantic-review24.json').read_text(encoding='utf8'))
        self.assertEqual(len(packets),24);self.assertEqual(sum(p['source_status']=='succeeded' for p in packets),22)
        for p in packets:validate_review(runs[p['run_id']],p)
        root=ROOT/'.local/p37/dataset-review-v1'
        reviews=json.loads((root/'review32.json').read_text(encoding='utf8'))
        self.assertEqual(len(reviews),32);self.assertEqual(len({r['naturalness'] for r in reviews}),32)
        rows=validate_candidates(json.loads((ROOT/'.local/p35/dataset-candidate-v2/candidates.json').read_text(encoding='utf8')))
        overlay=json.loads((root/'source-quality-overlay172.json').read_text(encoding='utf8'))
        self.assertEqual(overlay['parent_dataset_hash'],dataset_hash(rows))
        self.assertEqual([x['source_record'] for x in overlay['records']],[r.model_dump() for r in rows])
        self.assertEqual(sum(not r.exclusion_reason for r in rows),160)
        proposals=json.loads((root/'revision-proposals.json').read_text(encoding='utf8'))
        self.assertEqual(len(proposals),11)
        for p in proposals:
            c=Candidate.model_validate(p['candidate']);self.assertNotEqual(c.input_hash,p['parent_input_hash'])
            self.assertEqual(c.input_hash,p['new_input_hash']);self.assertFalse(p['active_dataset'])
            self.assertIsNone(c.reference);self.assertIsNone(p['human_approval'])

    def test_all87_derived_packets_trace_to29_successes(self):
        audit,groups=audit_p36(ROOT/'.local/p36');runs={r.run_id:r for r in groups['draft-v3']}
        packets=json.loads((ROOT/'.local/p37/replay-v2/derived-views.json').read_text(encoding='utf8'))
        self.assertEqual(len(packets),87);self.assertEqual(len({p['derived_id'] for p in packets}),87)
        self.assertEqual(len({p['parent_run_id'] for p in packets}),29)
        for p in packets:verify_derived(runs[p['parent_run_id']],p)
