"""Business assertions against explicit synthetic cases and real application UI."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.application.attribution_service import AttributionService
from src.infrastructure.dashboard_sources import ReadOnlyRepository, sqlite_source
from src.infrastructure.repository import Repository
from src.evaluation.p3_fixture import seed
from src.domain.contracts import RunConfig, idempotency_key


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'runs.sqlite3'
        self.repo=Repository(self.path)
        self.samples,self.runs=seed(self.repo)
        self.service=AttributionService(self.runs,'fixture',self.samples)
        self.cohort=self.runs[0].cohort_id

    def tearDown(self):self.temp.cleanup()

    def test_denominators_and_states(self):
        s=self.service.snapshot(self.cohort)
        self.assertEqual([s['metrics'][k]['numerator'] for k in ('emails','successful','complaints_all','negative_all','valid_attribution')],[10,7,5,4,3])
        self.assertEqual(s['metrics']['complaints_all']['rate'],.5)
        self.assertEqual(s['metrics']['complaints_success']['denominator'],7)
        self.assertEqual(s['metrics']['valid_attribution']['denominator'],5)
        self.assertEqual({k:v['numerator'] for k,v in s['states'].items()},dict(succeeded=7,failed=1,fallback=1,running=0,interrupted_or_unknown=1))
        self.assertEqual(s['unknown']['source_attribution']['numerator'],1)
        self.assertEqual({g['values']['source_attribution']:g['count']['numerator'] for g in s['groups']['attribution_states']},
            {'product issue':2,'store service issue':1,'none':2,'unclear':1,'unknown':1})

    def test_every_numerator_and_denominator_recover_original(self):
        s=self.service.snapshot(self.cohort)
        all_metrics=list(s['metrics'].values())+list(s['states'].values())+list(s['unknown'].values())+[s['attribution_unavailable']]
        for groups in s['groups'].values():
            for group in groups:all_metrics.extend(group[k] for k in ('count','negative','complaints'))
        for m in all_metrics:
            self.assertEqual(m['numerator'],len(m['member_run_ids']))
            self.assertEqual(m['denominator'],len(m['denominator_run_ids']))
            self.assertLessEqual(set(m['member_run_ids']),set(m['denominator_run_ids']))
            for rid in m['denominator_run_ids']:
                self.assertEqual(self.repo.get(rid).email.input_hash,s['members'][rid]['input_hash'])

    def test_filters_and_cross_tab(self):
        s=self.service.snapshot(self.cohort,store='A')
        self.assertEqual(s['metrics']['emails']['numerator'],4) # includes excluded fallback
        self.assertEqual(s['metrics']['successful']['numerator'],3)
        self.assertEqual(s['metrics']['negative_success']['rate'],2/3)
        self.assertEqual(s['prefilter_states']['failed'],1)
        self.assertEqual(s['filtered_out'],6)
        s=self.service.snapshot(self.cohort,product='Service/Other',sentiment='negative')
        self.assertEqual(s['metrics']['emails']['numerator'],1)
        self.assertEqual(s['groups']['store_product'][0]['values'],dict(store_location='B',product_category='Service/Other'))

    def test_empty_denominators_never_zero_percent(self):
        for kwargs in ({'store':'absent'},{'status':'failed'},{'status':'fallback'}):
            s=self.service.snapshot(self.cohort,**kwargs)
            self.assertIsNone(s['metrics']['complaints_success']['rate'])
            self.assertEqual(s['groups']['source_attribution'],[])

    def test_versions_separated_and_explicit(self):
        old=self.runs[0];config=RunConfig(model_id='p3-explicit-fixture-v1',prompt_version='other-version')
        extra=old.model_copy(update=dict(run_id='new-version',config=config,cohort_id=config.cohort_id,idempotency_key=idempotency_key(old.email,config)))
        service=AttributionService(self.runs+[extra],'fixture',self.samples)
        self.assertEqual(service.snapshot(self.cohort)['metrics']['emails']['numerator'],10)
        self.assertEqual(service.snapshot(config.cohort_id)['metrics']['emails']['numerator'],1)
        self.assertEqual(len(service.snapshot(config.cohort_id)['missing_sample_ids']),9)
        with self.assertRaises(ValueError):service.snapshot(None)

    def test_latest_retry_not_double_counted(self):
        failed=self.runs[7];retry=failed.model_copy(update=dict(run_id='retry',created_at='2099-01-01T00:00:00+00:00'))
        s=AttributionService(self.runs+[retry],'fixture',self.samples).snapshot(self.cohort)
        self.assertEqual(s['metrics']['emails']['numerator'],10)
        self.assertEqual(s['superseded_run_ids'],[failed.run_id])
        self.assertIn('retry',s['states']['failed']['member_run_ids'])

    def test_time_filter_and_timezone_validation(self):
        t=self.runs[0].created_at
        self.assertEqual(self.service.snapshot(self.cohort,start=t,end=t)['metrics']['emails']['numerator'],1)
        with self.assertRaises(ValueError):self.service.snapshot(self.cohort,start='2026-10-15')
        with self.assertRaises(ValueError):self.service.snapshot(self.cohort,start='2099-01-01T00:00:00Z',end=t)

    def test_dataset_hash_and_run_binding(self):
        broken=self.runs[0].model_copy(update={'input_hash':'0'*64})
        with self.assertRaises(ValueError):AttributionService([broken],'fixture',self.samples)
        with self.assertRaises(ValueError):AttributionService(self.runs,'fixture',self.samples[1:])
        with self.assertRaises(ValueError):AttributionService([self.runs[0]]*2,'fixture')
        mixed=[s.model_dump() for s in self.samples];mixed[0]['provenance']['source']='other'
        with self.assertRaises(ValueError):AttributionService(self.runs,'fixture',mixed)

    def test_readonly_adapter_does_not_write_or_migrate(self):
        before=self.path.read_bytes();ro=ReadOnlyRepository(self.path)
        self.assertEqual(ro.get(self.runs[0].run_id),self.runs[0])
        with self.assertRaises(sqlite3.OperationalError):
            with ro.connect() as conn:conn.execute('DELETE FROM runs')
        self.assertEqual(before,self.path.read_bytes())
        with self.assertRaises(FileNotFoundError):ReadOnlyRepository(self.path.with_name('missing.sqlite3'))

    def test_reference_difference_is_not_hidden(self):
        from src.evaluation.e2e import evaluate
        report=evaluate(self.samples,self.runs)
        self.assertTrue(any(m['sample_id']=='p3-wrong-attribution' and m['field']=='source_attribution' for m in report['mismatches']))
        self.assertIsNone(report['independent_accuracy'])
        self.assertEqual(report['summary']['status'],'PENDING')

    def test_legacy_source_unavailable_not_unknown(self):
        from src.application.analysis_service import AnalysisService
        from src.application.analyzers import LegacyMock
        run=AnalysisService(self.repo,LegacyMock()).analyze(self.samples[0].email())
        s=AttributionService([run],'legacy').snapshot(run.cohort_id)
        self.assertEqual(s['attribution_unavailable']['numerator'],1)
        self.assertEqual(s['unknown']['source_attribution']['numerator'],0)
        self.assertEqual(s['groups']['attribution_states'][0]['values'],{'source_attribution':'unavailable'})

    def test_actual_app_filters_trace_and_empty_selection(self):
        from streamlit.testing.v1 import AppTest
        manifest=Path(self.temp.name)/'dataset.json';manifest.write_text(json.dumps([s.model_dump() for s in self.samples]),encoding='utf-8')
        with patch.dict(os.environ,{'COMPLAINT_DB_PATH':str(self.path),'COMPLAINT_DATASET_MANIFEST':str(manifest)}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            app.radio(key='dashboard_view').set_value('P3 versioned attribution').run()
            self.assertFalse(app.exception)
            self.assertFalse(any(x.value=='Current Session Analysis Results' for x in app.subheader))
            app.selectbox(key='p3_store').set_value('B').run()
            app.selectbox(key='p3_product').set_value('Service/Other').run()
            app.selectbox(key='p3_sentiment').set_value('negative').run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.selectbox(key='p3_member').options),1)
            app.button(key='p3_open').click().run()
            self.assertTrue(any(self.samples[2].email_body in x.value for x in app.text))
            app.selectbox(key='p3_status').set_value('failed').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('No eligible members' in x.value for x in app.info))
