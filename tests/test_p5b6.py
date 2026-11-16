from tests.archive_support import requires_archive
import unittest
import tempfile
from pathlib import Path
from src.application.research_insights import ResearchInsights,member_metric
from src.evaluation.classification_research import classification,build_report
from src.dataset.research_generation import plan,accept_response,audit

ROOT=Path(__file__).resolve().parents[1]


class ClassificationTests(unittest.TestCase):
    def test_missing_prediction_retains_denominator_and_macro(self):
        m=classification([('negative','negative'),('neutral',None),('positive','neutral')])
        self.assertEqual((m['correct'],m['n']),(1,3));self.assertAlmostEqual(m['accuracy'],1/3)
        self.assertAlmostEqual(m['macro_f1'],1/3);self.assertEqual(m['classes']['neutral']['recall'],0)

    def test_no_gold_is_unknown(self):
        self.assertIsNone(classification([(None,'negative')])['accuracy'])

    def test_membership_rejects_outside_denominator(self):
        with self.assertRaises(ValueError):member_metric([{'id':'a'}],[{'id':'b'}],'bad')

    def test_generator_preserves_candidate_identity(self):
        p=plan();self.assertEqual(p['status'],'LIVE_GENERATION_PENDING');self.assertIsNone(p['authorization'])
        r=accept_response(p['jobs'][0],'{"subject":"Thanks","body":"The radio sounds good."}',model='offline-fixture',parameters={},request_id=None,usage=None)
        self.assertIsNone(r['independent_labels']);self.assertIn('NOT_GOLD',r['source'])
        with self.assertRaises(ValueError):accept_response(p['jobs'][0],'{"subject":"x","body":"y","label":"positive"}',model='x',parameters={},request_id=None,usage=None)
        self.assertEqual(audit(['same','same'])['exact_duplicates'],1)

    def test_generation_collection_cannot_impersonate_live_or_overwrite(self):
        from src.dataset.research_generation import collect_responses
        p=plan();j=p['jobs'][0]
        response=dict(job_id=j['id'],messages_hash=j['messages_hash'],model='offline-fixture',raw='{"subject":"Thanks","body":"The radio sounds good."}')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'new-collection'
            m=collect_responses(p,[response],out,identity='OFFLINE_TRANSPORT_FIXTURE',baseline_texts=['The radio sounds good.'])
            self.assertEqual(m['live_generated_count'],0)
            saved=__import__('json').loads((out/(j['id']+'.json')).read_text(encoding='utf-8'))
            self.assertTrue(saved['exact_duplicate_of_baseline']);self.assertIsNone(saved['independent_labels'])
            with self.assertRaises(FileExistsError):collect_responses(p,[response],out,identity='OFFLINE_TRANSPORT_FIXTURE')
            with self.assertRaises(ValueError):collect_responses(p,[response],Path(tmp)/'not-authorized',identity='AUTHORIZED_SAVED_RESPONSE_IMPORT')


@requires_archive('outputs/dashboard_i4f/dashboard_stats_v1.json', '.local/p5b5r2/R3')
class HistoricalResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=ResearchInsights(ROOT)

    def test_template_statistics_match_frozen_tables(self):
        s=self.catalog.snapshot('template400');self.assertEqual(s['selected'],400)
        import csv
        with (ROOT/'outputs/dashboard_i4f/store_complaint_ranking_v1.csv').open(encoding='utf-8-sig') as f:old=list(csv.DictReader(f))
        self.assertEqual([(x['store_location'],x['complaint_count']) for x in s['store_ranking']],[(x['store_location'],int(x['complaint_count'])) for x in old])
        self.assertEqual(sum(g['count']['numerator'] for g in s['groups']['sentiment']),400)

    def test_filter_and_drilldown_exact_membership(self):
        s=self.catalog.snapshot('template400',sentiment='negative')
        for g in s['groups']['product_category']:
            for mid in g['count']['member_ids']:
                r=self.catalog.member('template400',mid)
                self.assertEqual(r['prediction']['sentiment'],'negative')
                self.assertEqual(r['prediction']['product_category'],g['values']['product_category'])
        with self.assertRaises(ValueError):self.catalog.snapshot('template400',start='2026-01-01T00:00:00+00:00')

    def test_runtime_context_does_not_fragment_frozen_arm(self):
        self.assertEqual(len(self.catalog.records['r2-R3']),18)
        self.assertIn('freeze_hash',self.catalog.sources['r2-R3']['version']['parameters'])
        self.assertIn('prompt_hash',self.catalog.records['r2-R3'][0]['config'])

    def test_historical_scores_overlap_and_missing_coverage(self):
        report=build_report(ROOT,self.catalog);raw=report['reports'][0]
        self.assertEqual((raw['fields']['sentiment']['correct'],raw['fields']['sentiment']['n']),(78,80))
        self.assertEqual(sum(m['correct'] for m in raw['fields'].values()),494)
        self.assertEqual(report['overlap']['n'],0);self.assertIsNone(report['overlap']['pooled_score'])
        self.assertEqual(report['overlap']['unique_case_ids'],104)
        self.assertFalse(report['leakage']['independent_holdout'])
        draft=next(r for r in report['reports'] if r['id']=='p36-draft-v3')
        self.assertEqual(draft['scope_metrics']['clean_reference']['n'],23)
        self.assertEqual(draft['scope_metrics']['clean_reference']['excluded_ids'],['F176'])
        self.assertEqual(sum(m['correct'] for m in draft['scope_metrics']['clean_reference']['fields'].values()),143)

    def test_api_gets_readonly_and_invalid_sources(self):
        from fastapi.testclient import TestClient
        from src.app.p5b6_api import create
        with tempfile.TemporaryDirectory() as d:
            client=TestClient(create(Path(d)/'product.sqlite3'))
            self.assertEqual(client.get('/api/research/insights?source=template400').json()['selected'],400)
            self.assertEqual(client.get('/api/research/insights?source=absent').status_code,422)
            self.assertEqual(client.get('/api/research/member?source=template400&member_id=absent').status_code,404)
            self.assertEqual(client.post('/api/research/insights').status_code,403)
            self.assertEqual(client.get('/api/p5b5r2/live/status').json()['halted'],'P5B6_NO_PAID_AUTHORIZATION')
            token=client.get('/api/session').json()['token']
            response=client.post('/api/p5b5r2/live',headers={'x-p5-token':token,'origin':'http://127.0.0.1:8771'},json=dict(subject='Offline permission test',body='Synthetic test only',synthetic_confirmed=True,operation_id='offline-no-paid-call'))
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json()['code'],'live_closed')
            pack=client.get('/api/p5b5r2/review').json()
            self.assertEqual(len(pack['items']),23);self.assertFalse(pack['human_signed'])


if __name__=='__main__':unittest.main()
