"""Local research assets stay local; public portable suite excludes this module."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from src.domain.contracts import digest

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))


class LocalP38Assets(unittest.TestCase):
    def test_adoption_is_reproducible_and_preserves_all_approved_texts(self):
        from src.dataset.adoption_v3 import build
        source=load('.local/p35/dataset-candidate-v2/candidates.json');reviews=load('.local/p37/dataset-review-v1/review32.json');proposals=load('.local/p37/dataset-review-v1/revision-proposals.json')
        m=build(source,reviews,proposals)
        self.assertEqual(m['counts']['natural_candidates'],159);self.assertEqual(len(m['receipts']),32)
        index={r['record_id']:r for r in m['records']}
        for p in proposals:self.assertEqual(index[p['candidate']['sample_id']]['source_record'],p['candidate'])
        for r in source:self.assertEqual(index[r['sample_id']]['source_record'],r)

    def test_v2_rubric_22_success_two_failure_unsigned_and_tamper_rejected(self):
        from src.evaluation.p37_replay import audit_p36
        from src.evaluation.semantic_review_v2 import build_review,validate_review,MAPPING
        _,groups=audit_p36(ROOT/'.local/p36');runs={r.run_id:r for r in groups['draft-v3']}
        parents=load('.local/p37/review-v1/semantic-review24.json');self.assertEqual(len(parents),24)
        succeeded=0
        for p in parents:
            run=runs[p['run_id']];packet=build_review(run,p);validate_review(run,p,packet)
            self.assertEqual(len(packet['dimensions']),18);succeeded+=bool(run.result)
            self.assertTrue(all(d['human_score'] is None and d['human_critical_error'] is None for d in packet['dimensions'].values()))
            bad=copy.deepcopy(packet);bad['human_reviewer']='invented';bad.pop('packet_hash');bad['packet_hash']=digest(bad)
            with self.assertRaises(ValueError):validate_review(run,p,bad)
        self.assertEqual(succeeded,22)

    def test_p36_all_40_locked_budget_and_frozen_scores(self):
        from src.evaluation.p37_replay import audit_p36
        audit,_=audit_p36(ROOT/'.local/p36')
        self.assertEqual(audit['runs'],40);self.assertEqual(audit['budget_halted'],'authorization_limit')
        self.assertEqual((audit['frozen_final_succeeded'],audit['frozen_final_attempted']),(29,32))
        self.assertEqual(audit['new_model_requests'],0)

    def test_preparation_cli_produces_zero_budget_pending_evaluation(self):
        from scripts.p38 import prepare
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'prepared';receipt=prepare(path)
            self.assertFalse(receipt['ab']['paid_dispatch_allowed']);self.assertEqual(receipt['ab']['inputs'],32)
            report=json.loads((path/'paired-evaluation-pending.json').read_text(encoding='utf8'))
            self.assertEqual(report['arms']['A']['old_seven_consistency']['denominator'],168)
            self.assertEqual(report['arms']['B']['input_denominator'],32)
            with self.assertRaises(FileExistsError):prepare(path)
