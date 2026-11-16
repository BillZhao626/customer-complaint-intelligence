import tempfile
import unittest
from tests.test_p39_continuity import setup,schema_bad
from tests.test_p39_context_live import fake
from tests.test_p38 import fixture_references
from src.application.p39_continuity import run_fixed,load_runs
from src.evaluation.p39_continuity_report import evaluate,export,attach_semantic_reviews
from pathlib import Path
from unittest.mock import patch
from hashlib import sha256
import copy


class ContinuityReportTests(unittest.TestCase):
    def test_missing_failed_and_accepted_have_fixed_denominators_and_unsigned_18(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            run_fixed(rt,b,s,schema_bad,limit=1)
            run_fixed(rt,b,s,fake,limit=2)
            refs=fixture_references(rt['candidate'])
            report=evaluate(rt,load_runs(rt),refs,b.summary())
            self.assertEqual(report['actual_requests'],2);self.assertEqual(report['unattempted'],62)
            self.assertEqual(report['model_quality_rejected'],1);self.assertEqual(report['complete_attempted_pairs'],1)
            self.assertEqual(report['failed_predictions'],1);self.assertEqual(report['formally_accepted_outputs'],1)
            for a in ('A','B'):
                self.assertEqual(report['arms'][a]['seven_denominator'],168)
                self.assertEqual(report['arms'][a]['contract_acceptance_denominator'],32)
            for member in report['members']:
                self.assertEqual(len(member['review']['dimensions']),18)
                self.assertTrue(all(d['human_score'] is None for d in member['review']['dimensions'].values()))
            self.assertIsNone(report['actual_invoice_cny'])
            export(rt,b,Path(td)/'report',refs)
            self.assertIn('未审核', (Path(td)/'report/REVIEW.html').read_text(encoding='utf8'))

    def test_arbitrary_json_quality_failures_are_exportable(self):
        for raw in ('[1]','"text"','42','{"issues":null}','{"suggested_reply":7}','{"summary":[1],"issues":[null]}'):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as td:
                rt,b,s=setup(td)
                async def bad(msgs,remaining):
                    _,meta=await fake(msgs,remaining);return raw,meta
                run_fixed(rt,b,s,bad,limit=2)
                report=export(rt,b,Path(td)/'report',fixture_references(rt['candidate']))
                self.assertEqual(report['model_quality_rejected'],2)
                self.assertEqual(report['failed_predictions'],2)

    def test_prepared_but_not_sent_does_not_count_as_actual_request(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            with patch.object(b,'reserve',side_effect=PermissionError('offline pre-send failure')):
                with self.assertRaises(PermissionError):run_fixed(rt,b,s,fake)
            report=evaluate(rt,load_runs(rt),fixture_references(rt['candidate']),b.summary())
            self.assertEqual(report['actual_requests'],0)
            self.assertEqual(report['unattempted'],64)
            self.assertEqual(report['infrastructure_blocked'],1)
            self.assertEqual(report['prepared_not_sent'],1)
            self.assertEqual(report['failed_predictions'],0)

    def test_unsigned_assistant_review_requires_exact_identity_and_failed_scope(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td);run_fixed(rt,b,s,schema_bad,limit=1)
            report=evaluate(rt,load_runs(rt),fixture_references(rt['candidate']),b.summary());member=report['members'][0]
            row=dict(run_id=member['run_id'],input_hash=member['input_hash'],raw_sha256=sha256(member['attempts'][0]['raw_output'].encode()).hexdigest(),
                     status='failed',review_scope='failed_raw_diagnostic_only',dimensions=copy.deepcopy(member['review']['dimensions']))
            row['dimensions']['material_promises']['verdict_candidate']='defect_candidate'
            packet=dict(records=[row]);attached=attach_semantic_reviews(copy.deepcopy(report),packet)
            self.assertEqual(attached['assistant_review_summary']['total_dimension_candidates'],18)
            self.assertIsNone(attached['assistant_review_summary']['semantic_accuracy'])
            self.assertEqual(len(attached['assistant_review_summary']['critical_safety_promise_candidates']),1)
            self.assertIsNone(attached['assistant_review_summary']['critical_safety_promise_candidates'][0]['human_confirmed'])
            for change in ('input_hash','review_scope','human_score'):
                bad=copy.deepcopy(packet)
                if change=='human_score':next(iter(bad['records'][0]['dimensions'].values()))['human_score']=1
                elif change=='review_scope':bad['records'][0][change]='accepted_output'
                else:bad['records'][0][change]='wrong'
                with self.assertRaises(ValueError):attach_semantic_reviews(copy.deepcopy(report),bad)


if __name__=='__main__':unittest.main()
