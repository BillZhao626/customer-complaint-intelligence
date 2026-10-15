import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from src.application.analysis_service import AnalysisService
from src.application.analyzers import OfflineFake,LegacyMock
from src.domain.contracts import EmailInput,RunConfig
from src.infrastructure.repository import Repository
from tests.fixtures import EMAILS,EXPECTED,VALID


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='complaint_test_')
        self.path=Path(self.temp.name)/'runs.sqlite3'
        self.repo=Repository(self.path)
        self.fake=OfflineFake()
        self.service=AnalysisService(self.repo,self.fake)

    def tearDown(self):
        self.temp.cleanup()

    def seed(self):
        return [self.service.analyze(e) for e in EMAILS]

    def test_fake_service_save_new_connection(self):
        runs=self.seed()
        fresh=Repository(self.path)
        for run,email,expected in zip(runs,EMAILS,EXPECTED):
            saved=fresh.get(run.run_id)
            self.assertEqual(saved.email,email)
            self.assertEqual(saved.input_hash,email.input_hash)
            self.assertEqual(saved.config.backend,'offline_fake')
            self.assertEqual(saved.status,'succeeded')
            self.assertEqual((saved.result.store_location,saved.result.sentiment,saved.result.is_complaint),expected)
            self.assertEqual(json.loads(saved.attempts[0].raw_output),saved.result.model_dump())
            self.assertEqual(saved.attempts[0].contract_status,'passed')

    def test_idempotency_skips_analyzer(self):
        first=self.service.analyze(EMAILS[0])
        with patch.object(self.fake,'analyze',side_effect=AssertionError('must reuse')):
            second=self.service.analyze(EMAILS[0])
        self.assertEqual(first.run_id,second.run_id)
        self.assertEqual(len(self.repo.list_runs()),1)

    def test_concurrent_unique_success(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(lambda _: self.service.analyze(EMAILS[0]).run_id,range(4)))
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(len(self.repo.list_runs()),1)

    def test_content_and_prompt_produce_separate_runs(self):
        a=self.service.analyze(EMAILS[0])
        b=self.service.analyze(EMAILS[0].model_copy(update={'body':EMAILS[0].body+' changed'}))
        service=AnalysisService(self.repo,self.fake,RunConfig(prompt_version='offline-demo-v2'))
        c=service.analyze(EMAILS[0])
        self.assertEqual(len({a.run_id,b.run_id,c.run_id}),3)
        self.assertNotEqual(a.input_hash,b.input_hash)
        self.assertNotEqual(a.cohort_id,c.cohort_id)
        self.assertEqual(service.aggregate(c.cohort_id)[0]['denominator'],1)

    def test_failed_attempts_are_retained_and_excluded(self):
        self.seed()
        bad=EmailInput(email_id='failed',subject='Synthetic failure',body='[fail]')
        failed=[self.service.analyze(bad) for _ in range(2)]
        self.assertNotEqual(failed[0].run_id,failed[1].run_id)
        self.assertTrue(all(r.status=='failed' and r.result is None for r in failed))
        self.assertEqual(failed[0].attempts[0].error.error_type,'analyzer_error')
        self.assertEqual(len(self.repo.list_runs(status='failed')),2)
        self.assertEqual(sum(g['denominator'] for g in self.service.aggregate(self.service.config.cohort_id)),4)

    def test_parse_and_contract_stages(self):
        for i,raw in enumerate(['not json','[]','{}',json.dumps(dict(VALID,is_complaint='false'))]):
            with self.subTest(raw=raw),patch.object(self.fake,'analyze',return_value=raw):
                run=self.service.analyze(EMAILS[0].model_copy(update={'email_id':str(i)}))
                self.assertEqual(run.status,'failed')
                attempt=run.attempts[0]
                self.assertEqual(attempt.raw_output,raw)
                self.assertEqual(attempt.parse_status,'failed' if i==0 else 'passed')
                self.assertEqual(attempt.contract_status,'not_run' if i==0 else 'failed')

    def test_business_warning_saved(self):
        with patch.object(self.fake,'analyze',return_value=json.dumps(dict(VALID,is_complaint=False))):
            run=self.service.analyze(EMAILS[0])
        self.assertEqual(run.status,'succeeded')
        self.assertEqual(run.attempts[0].business_status,'warning')

    def test_transaction_rolls_back_email_run_result_and_attempt(self):
        with self.repo.connect() as conn:
            conn.execute("CREATE TRIGGER fail_attempt BEFORE INSERT ON attempts BEGIN SELECT RAISE(ABORT,'injected'); END;")
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.analyze(EMAILS[0])
        with self.repo.connect() as conn:
            for table in ('emails','runs','results','attempts'):
                self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)

    def test_foreign_key_and_attempt_uniqueness(self):
        with self.repo.connect() as conn,self.assertRaises(sqlite3.IntegrityError):
            conn.execute('INSERT INTO results VALUES(?,?)',('absent','{}'))
        run=self.service.analyze(EMAILS[0])
        with self.repo.connect() as conn,self.assertRaises(sqlite3.IntegrityError):
            conn.execute('INSERT INTO attempts VALUES(?,?,?)',(run.run_id,1,'{}'))

    def test_numerator_denominator_and_member_trace(self):
        runs=self.seed()
        groups={g['group']:g for g in self.service.aggregate(self.service.config.cohort_id)}
        self.assertEqual(set(groups),{'A','B','unknown'})
        a=groups['A']
        self.assertEqual((a['numerator'],a['denominator'],a['negative_rate']),(1,2,0.5))
        self.assertEqual(set(a['member_run_ids']),{runs[0].run_id,runs[1].run_id})
        self.assertEqual(a['negative_member_run_ids'],[runs[0].run_id])
        self.assertEqual(self.repo.get(a['negative_member_run_ids'][0]).email,EMAILS[0])

    def test_filters_unknown_and_empty(self):
        self.seed()
        self.assertEqual(len(self.repo.list_runs(store='A',product='Electronics',status='succeeded')),2)
        self.assertEqual(len(self.repo.list_runs(store='unknown')),1)
        groups=self.service.aggregate(self.service.config.cohort_id,'product_category',store='A')
        self.assertEqual((groups[0]['group'],groups[0]['numerator'],groups[0]['denominator']),('Electronics',1,2))
        self.assertEqual(self.service.aggregate(self.service.config.cohort_id,store='absent'),[])
        with self.assertRaises(ValueError):
            self.service.aggregate(None)

    def test_backend_identity_and_cohort_separation(self):
        self.seed()
        legacy=AnalysisService(self.repo,LegacyMock())
        run=legacy.analyze(EmailInput(email_id='legacy',subject='Synthetic',body='A broken blender from Shanghai Pudong Store.'))
        self.assertEqual(run.status,'succeeded')
        self.assertEqual(run.config.backend,'legacy_mock')
        self.assertEqual(run.result.source_attribution,'unknown')
        self.assertNotIn('source_attribution',json.loads(run.attempts[0].raw_output))
        self.assertEqual(sum(g['denominator'] for g in self.service.aggregate(self.service.config.cohort_id)),4)
        with self.assertRaises(ValueError):
            AnalysisService(self.repo,self.fake,RunConfig(backend='legacy_mock'))

    def test_protected_database_location_refused(self):
        root=Path(__file__).resolve().parents[1]
        for folder in ('data/raw','outputs','docs/dissertation'):
            with self.subTest(folder=folder),self.assertRaises(ValueError):
                Repository(root/folder/'forbidden.sqlite3')

    def test_unsupported_database_version_is_not_migrated(self):
        with self.repo.connect() as conn:
            conn.execute('PRAGMA user_version=99')
        with self.assertRaises(ValueError):
            Repository(self.path)

    def test_repository_rejects_unbound_run_metadata(self):
        run=self.service.analyze(EMAILS[0])
        for patch_data in ({'input_hash':'tampered'},{'cohort_id':'tampered'},{'idempotency_key':'tampered'},
                           {'attempts':[]},{'status':'failed'}):
            with self.subTest(patch_data=patch_data),self.assertRaises(ValueError):
                self.repo.save(run.model_copy(update=patch_data))
