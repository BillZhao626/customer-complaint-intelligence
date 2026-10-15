"""P2.5 acceptance gates, entirely synthetic and offline."""
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy

from src.domain.contracts import EmailInput, RunConfig


def sample(sid='one', body='[store:A] [negative]'):
    from src.evaluation.e2e_schema import Sample
    from tests.fixtures import VALID
    from src.evaluation.core import FIELDS
    email = EmailInput(email_id=sid, subject='Synthetic fixture', body=body)
    return Sample.model_validate(dict(dataset_id='fixture-v1', sample_id=sid, split='development',
        provenance=dict(kind='developer_synthetic', source='explicit unit fixture', independent=False),
        template_group=sid, semantic_group=sid, subject=email.subject, email_body=email.body,
        input_hash=email.input_hash, input_schema_version='email-input-v1', taxonomy_version='research-products-v2',
        annotation_version='pending-v1', expected={f:VALID[f] for f in FIELDS}, reference_status='developer_reference',
        summary_reference={}, reply_reference={}, attribution_reference={},
        applicable_checks=['seven_fields','summary','reply','aggregate','traceability']))


class BoundaryTests(unittest.TestCase):
    def test_candidate_uses_real_service_path_with_new_bound_ledger(self):
        from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
        from src.infrastructure.pilot_budget import PilotBudget
        from src.infrastructure.repository import Repository
        from src.application.analysis_service import AnalysisService
        from src.application.service_boundary_prompt import PROMPT_HASH
        from tests.fixtures import VALID
        email=EmailInput(email_id='candidate-fitting',subject='Fitting',body='Can I arrange a fitting service?')
        captured=[]
        async def provider(payload,timeout):
            captured.append(payload)
            return json.dumps(dict(VALID,product_category='Service/Other')),{}
        analyzer=DeepSeekAnalyzer(LiveSettings('fixture',True,max_attempts=1),provider,prompt_profile='service-boundary-v1')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            budget=PilotBudget.create(root/'candidate-budget.sqlite3',[email.input_hash],{'config':analyzer.config.model_dump()})
            run=AnalysisService(Repository(root/'candidate.sqlite3'),analyzer,budget=budget).analyze(email)
            self.assertEqual(run.status,'succeeded')
            self.assertEqual(run.attempts[0].metadata['actual_system_prompt_sha256'],PROMPT_HASH)
            self.assertEqual(json.loads(captured[0][1][1]),dict(subject=email.subject,body=email.body))
            self.assertIn('service-boundary-v1',captured[0][0][1])
            old=DeepSeekAnalyzer(LiveSettings('fixture',True,max_attempts=1),provider)
            with self.assertRaises(Exception):budget.verify_config(old.config)

    def test_service_decision_table(self):
        from src.evaluation.category_boundary import decide_category
        for service in ('fitting service','repair service','installation service','opening hours','after-sales service','staff attitude'):
            with self.subTest(service=service):
                self.assertEqual(decide_category(None, service, 'service'), 'Service/Other')
        self.assertEqual(decide_category('Electronics', None, 'product'), 'Electronics')
        self.assertEqual(decide_category(None, None, 'unknown'), 'unknown')
        self.assertEqual(decide_category('Electronics','repair service','product'), 'Electronics')
        self.assertEqual(decide_category('Electronics','repair service','service'), 'Service/Other')
        self.assertEqual(decide_category('Electronics','repair service','ambiguous'), 'unknown')

    def test_frozen_prompt_and_separate_candidate(self):
        from src.application.live_prompt import PROMPT_HASH, PROMPT_VERSION
        from src.application.service_boundary_prompt import PROMPT_HASH as new_hash, PROMPT_VERSION as new_version
        self.assertEqual(PROMPT_HASH, 'c0b72907c1fce9fc191352882502910e6c154c109577559d8e4aad1fbfbe8b23')
        self.assertNotEqual(PROMPT_HASH, new_hash)
        self.assertNotEqual(PROMPT_VERSION, new_version)


class EvaluationFoundationTests(unittest.TestCase):
    def evaluate(self, samples=None):
        from src.evaluation.e2e import execute_offline, evaluate
        from src.infrastructure.repository import Repository
        with tempfile.TemporaryDirectory() as directory:
            samples = samples or [sample()]
            repo = Repository(Path(directory)/'r.sqlite3')
            runs = execute_offline(samples, repo)
            return samples, runs, evaluate(samples, runs)

    def test_missing_reviews_never_pass(self):
        _, _, report = self.evaluate()
        self.assertEqual(report['summary']['status'], 'PENDING')
        self.assertEqual(report['reply']['status'], 'PENDING')
        self.assertFalse(report['reply']['ready_to_send'])
        self.assertIsNone(report['independent_accuracy'])
        self.assertFalse(report['browser_e2e_verified'])

    def test_failed_and_missing_predictions_remain_in_denominator(self):
        from src.evaluation.e2e import evaluate
        samples, runs, _ = self.evaluate([sample(), sample('fail','[fail]'), sample('missing')])
        report = evaluate(samples, runs[:2])
        self.assertEqual(report['counts'], dict(eligible=3,attempted=2,succeeded=1,failed=1,uncertain=0,fallback=0,missing=1,evaluated=3,pending=0))
        self.assertEqual(report['fields']['sentiment']['denominator'], 3)
        self.assertEqual(report['fields']['sentiment']['correct'], 1)

    def test_input_hash_mismatch_rejected(self):
        from src.evaluation.e2e import evaluate
        samples, runs, _ = self.evaluate()
        changed = sample(body='different input')
        with self.assertRaises(ValueError): evaluate([changed], runs)

    def test_versions_not_combined(self):
        from src.evaluation.e2e import evaluate
        samples, runs, _ = self.evaluate([sample(),sample('two')])
        changed = runs[1].model_copy(update={'config': RunConfig(prompt_version='other')})
        with self.assertRaises(ValueError): evaluate(samples, [runs[0],changed])

    def test_pending_labels_not_independent(self):
        from src.evaluation.e2e import evaluate
        samples, runs, _ = self.evaluate()
        data=samples[0].model_dump();data['reference_status']='human_pending';data['expected']={f:None for f in data['expected']}
        from src.evaluation.e2e_schema import Sample
        report=evaluate([Sample.model_validate(data)],runs)
        self.assertEqual(report['counts']['pending'],1)
        self.assertIsNone(report['fields']['sentiment']['accuracy'])
        self.assertIsNone(report['independent_accuracy'])

    def test_cannot_self_declare_gold(self):
        from src.evaluation.e2e_schema import Sample
        data=sample().model_dump();data['reference_status']='human_gold'
        with self.assertRaises(ValueError):Sample.model_validate(data)

    def test_duplicate_sample_and_group_leakage_rejected(self):
        from src.evaluation.e2e_schema import validate_dataset
        s=sample()
        with self.assertRaises(ValueError):validate_dataset([s,s])
        other=s.model_copy(update={'sample_id':'two','split':'holdout_candidate'})
        with self.assertRaises(ValueError):validate_dataset([s,other])

    def test_aggregate_member_original_and_version(self):
        _,_,report=self.evaluate([sample(),sample('two','[store:A] [positive]'),sample('three','[fail]')])
        group=report['aggregates']['store_location'][0]
        self.assertEqual((group['numerator'],group['denominator'],group['negative_rate']),(1,2,.5))
        self.assertEqual(len(report['traceability']),3)
        self.assertTrue(report['aggregate_verification']['passed'])

    def test_review_binding_is_required(self):
        from src.evaluation.e2e import evaluate
        samples,runs,_=self.evaluate()
        with self.assertRaises(ValueError):evaluate(samples,runs,reviews=[{'sample_id':'one','run_id':'wrong'}])

    def test_reference_schema_rejects_invalid_labels(self):
        from src.evaluation.e2e_schema import Sample
        data=sample().model_dump();data['expected']['sentiment']='perfect'
        with self.assertRaises(ValueError):Sample.model_validate(data)

    def test_source_cohorts_cannot_mix(self):
        from src.evaluation.e2e_schema import validate_dataset
        s=sample();other=sample('two').model_copy(update={'dataset_id':'historical-80'})
        with self.assertRaises(ValueError):validate_dataset([s,other])

    def test_confusion_macro_f1_keeps_failure_false_negative(self):
        from src.evaluation.e2e import score_pairs
        report=score_pairs([('negative','negative'),('negative','<failed>'),('positive','positive')])
        self.assertEqual(report['confusion_matrix']['negative']['<failed>'],1)
        self.assertAlmostEqual(report['macro_f1'],5/6)
        self.assertEqual(report['denominator'],3)

    def test_fallback_never_counts_as_correct(self):
        from src.evaluation.e2e import evaluate
        samples,runs,_=self.evaluate()
        run=runs[0].model_copy(update={'metadata':{'fallback':True}})
        report=evaluate(samples,[run])
        self.assertEqual(report['counts']['fallback'],1)
        self.assertEqual(report['fields']['sentiment']['correct'],0)
        self.assertEqual(report['aggregate_verification']['fallback_excluded'],1)
        self.assertFalse(report['aggregate_verification']['passed'])

    def test_approved_review_critical_error_and_output_hash(self):
        from src.evaluation.e2e import evaluate,output_hash,SUMMARY_RUBRIC
        from src.evaluation.e2e_schema import Sample
        samples,runs,_=self.evaluate()
        data=samples[0].model_dump();data['summary_reference']=dict(status='approved',facts=['Synthetic demonstration'],constraints=['No invented facts'],reviewer='unit-fixture-reviewer')
        s=Sample.model_validate(data);r=runs[0]
        review=dict(kind='summary',sample_id=s.sample_id,run_id=r.run_id,input_hash=s.input_hash,cohort_id=r.cohort_id,
            output_hash=output_hash(r),rubric_version='content-rubric-v1',reviewer='unit-fixture-reviewer',status='approved',
            scores={k:2 for k in SUMMARY_RUBRIC},critical_errors=[],evidence=['Explicit synthetic test assertion'])
        self.assertEqual(evaluate([s],runs,[review])['summary']['status'],'PASSED')
        review['critical_errors']=['Unsupported fact']
        self.assertEqual(evaluate([s],runs,[review])['summary']['status'],'FAILED')
        review['output_hash']='0'*64
        with self.assertRaises(ValueError):evaluate([s],runs,[review])

    def test_unknown_is_distinct_from_failure(self):
        from src.evaluation.e2e import score_pairs
        r=score_pairs([('unknown','unknown'),('unknown','<failed>')])
        self.assertEqual((r['correct'],r['denominator']),(1,2))

    def test_blank_reference_rejected(self):
        from src.evaluation.e2e_schema import Sample
        data=sample().model_dump();data['expected']['store_location']='  '
        with self.assertRaises(ValueError):Sample.model_validate(data)


class AuditAndGoldTests(unittest.TestCase):
    def packets(self):
        from src.evaluation.gold import blank_queue
        s=sample();packets=[]
        for name in ('unit-test-A','unit-test-B','unit-test-adjudicator'):
            p=blank_queue([s],name);p.update(reviewer=name,human_declaration=True,independent_of_predictions=True)
            row=p['annotations'][0];row['status']='reviewed'
            for f,annotation in row['fields'].items():annotation.update(value=getattr(s.expected,f),evidence=[s.email_body],certainty='high',rationale='Unit-test fixture only')
            for kind in ('summary','reply','attribution'):row[kind+'_reference']=dict(status='approved',facts=['Test fact'],constraints=['Test constraint'],forbidden=[],alternatives=[],reviewer=name)
            packets.append(p)
        from src.domain.contracts import digest
        from src.evaluation.e2e_schema import dataset_hash
        a,b,final=packets
        adj=dict(reviewer=final['reviewer'],human_declaration=True,status='approved',dataset_hash=dataset_hash([s]),packet_hashes=[digest(a),digest(b)],decisions=[],final_packet=final)
        return s,a,b,adj

    def test_freeze_roundtrip_and_tamper(self):
        from src.evaluation.gold import freeze,verify_freeze
        s,a,b,adj=self.packets()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'manifest.json'
            manifest=freeze([s],a,b,adj,path)
            self.assertFalse(manifest['independent_holdout'])
            self.assertEqual(verify_freeze(manifest)[0].reference_status,'human_gold')
            with self.assertRaises(FileExistsError):freeze([s],a,b,adj,path)
            manifest['samples'][0]['expected']['sentiment']='positive'
            with self.assertRaises(ValueError):verify_freeze(manifest)

    def test_disagreement_requires_adjudication(self):
        from src.evaluation.gold import compare,freeze
        from src.domain.contracts import digest
        s,a,b,adj=self.packets();b['annotations'][0]['fields']['sentiment']['value']='neutral'
        self.assertEqual(len(compare([s],a,b)['disagreements']),1)
        adj['packet_hashes']=[digest(a),digest(b)]
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValueError):freeze([s],a,b,adj,Path(directory)/'f.json')

    def test_gold_evidence_must_exist_and_reviewers_distinct(self):
        from src.evaluation.gold import compare
        s,a,b,_=self.packets()
        with self.assertRaises(ValueError):compare([s],a,a)
        b['annotations'][0]['fields']['sentiment']['evidence']=['Invented evidence']
        with self.assertRaises(ValueError):compare([s],a,b)

    def test_template_family_cannot_leak_across_variants(self):
        from src.evaluation.dataset_audit import group_rows
        rows=[dict(email_id='a',email_body='x',generation_template_id='f_01',scenario_type='family'),
              dict(email_id='b',email_body='very different',generation_template_id='f_02',scenario_type='family')]
        r=group_rows(rows);self.assertEqual(r['groups']['a'],r['groups']['b'])

    def test_template_and_near_duplicate_grouping(self):
        from src.evaluation.dataset_audit import group_rows
        rows=[dict(email_id='a',email_body='My red coat from A is broken.',product_name='red coat',store_location='A',generation_template_id='t'),
              dict(email_id='b',email_body='My blue coat from B is broken.',product_name='blue coat',store_location='B',generation_template_id='u')]
        result=group_rows(rows)
        self.assertEqual(result['groups']['a'],result['groups']['b'])

    def test_freeze_requires_actual_reviewers(self):
        from src.evaluation.gold import freeze
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            freeze([sample()],[],[],{},Path(directory)/'freeze.json')

    def test_git_payload_denies_private_assets(self):
        from scripts.audit_git_payload import DENIED_PREFIXES
        for name in ('.local/budget.sqlite3','data/synthetic/a.csv','outputs/pred.csv','docs/dissertation/thesis.md'):
            self.assertTrue(name.startswith(DENIED_PREFIXES))
