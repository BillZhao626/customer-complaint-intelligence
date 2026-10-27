import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from src.infrastructure.repository import Repository
from tests.fixtures import EMAILS

ROOT=Path(__file__).resolve().parents[1]


class StreamlitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='complaint_ui_')
        self.db=Path(self.temp.name)/'ui.sqlite3'
        self.env=patch.dict(os.environ,{'COMPLAINT_DB_PATH':str(self.db),
            'COMPLAINT_PRODUCT_DB':str(Path(self.temp.name)/'product.sqlite3')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def app(self):
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        self.assertFalse(app.exception,[e.message for e in app.exception])
        return app

    def submit(self,app,email):
        app.text_input(key='offline_email_id').set_value(email.email_id)
        app.text_input(key='offline_subject').set_value(email.subject)
        app.text_area(key='offline_body').set_value(email.body)
        app.button(key='offline_analyze').click().run()
        self.assertFalse(app.exception,[e.message for e in app.exception])
        return app.session_state['offline_run_id']

    def test_single_save_rerun_reopen_and_idempotency(self):
        app=self.app()
        self.assertEqual([t.label for t in app.tabs],['智能接待','业务分析','研究与开发者工具','单条处理 / Single Analysis','批量分析 / Batch Analysis','统计看板 / Dashboard','评测 / Evaluation'])
        run_id=self.submit(app,EMAILS[0])
        app.run()
        self.assertTrue(any('saved successfully' in x.value for x in app.success))
        self.assertEqual(self.submit(app,EMAILS[0]),run_id)
        fresh=self.app()
        fresh.text_input(key='offline_lookup').set_value(run_id)
        fresh.button(key='offline_load').click().run()
        self.assertFalse(fresh.exception)
        self.assertTrue(any(EMAILS[0].body in t.value for t in fresh.text))
        self.assertEqual(len(Repository(self.db).list_runs()),1)
        # A completely new session also loads a bookmarked run_id query parameter.
        bookmarked=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30)
        bookmarked.query_params['run_id']=run_id
        bookmarked.run()
        self.assertTrue(any(EMAILS[0].body in t.value for t in bookmarked.text))

    def test_fixture_aggregation_filters_and_member_original(self):
        app=self.app()
        ids=[self.submit(app,email) for email in EMAILS]
        app.selectbox(key='offline_store').set_value('A').run()
        tables=[df.value for df in app.dataframe if 'numerator' in df.value.columns]
        self.assertEqual((tables[0].iloc[0]['numerator'],tables[0].iloc[0]['denominator'],tables[0].iloc[0]['negative_rate']),(1,2,0.5))
        app.radio(key='offline_membership').set_value('negative numerator members').run()
        self.assertEqual(app.selectbox(key='offline_member').value,ids[0])
        app.button(key='offline_open_member').click().run()
        self.assertEqual(app.session_state['offline_run_id'],ids[0])
        self.assertTrue(any(EMAILS[0].body in t.value for t in app.text))
        app.selectbox(key='offline_product').set_value('Electronics').run()
        app.selectbox(key='offline_dimension').set_value('product_category').run()
        self.assertFalse(app.exception,[e.message for e in app.exception])
        app.selectbox(key='offline_store').set_value('unknown').run()
        self.assertFalse(app.exception)

    def test_blank_input_and_fake_failure(self):
        app=self.app()
        app.text_area(key='offline_body').set_value(' ')
        app.button(key='offline_analyze').click().run()
        self.assertTrue(any('Invalid input' in x.value for x in app.error))
        self.assertFalse(app.success)
        app.text_area(key='offline_body').set_value('[fail]')
        app.button(key='offline_analyze').click().run()
        self.assertTrue(any('Run failed' in x.value for x in app.error))
        self.assertFalse(app.success)
        app.selectbox(key='offline_status').set_value('failed').run()
        self.assertFalse(app.exception)
        self.assertFalse(any('numerator' in df.value.columns for df in app.dataframe))

    def test_save_failure_never_success(self):
        repo=Repository(self.db)
        with repo.connect() as conn:
            conn.execute("CREATE TRIGGER fail_result BEFORE INSERT ON results BEGIN SELECT RAISE(ABORT,'test'); END;")
        app=self.app()
        app.button(key='offline_analyze').click().run()
        self.assertTrue(any('Save failed' in x.value for x in app.error))
        self.assertFalse(app.success)
        self.assertEqual(repo.list_runs(),[])

    def test_three_historical_dashboard_modes(self):
        app=self.app()
        for mode in ['DeepSeek Prediction Statistics','Formal Reviewed Golden Evaluation','Synthetic Reference Statistics']:
            next(r for r in app.radio if r.label=='Dashboard Data Mode').set_value(mode).run()
            self.assertFalse(app.exception,[e.message for e in app.exception])
        self.assertTrue(any(m.value=='88.21%' for m in app.metric))

    def test_missing_unreadable_and_invalid_reports_no_fabricated_metrics(self):
        # Intercept only read of the summary; never rename frozen files.
        original=Path.read_text
        for failure in ('missing','invalid-json','invalid-schema','unreadable'):
            def reader(path,*args,**kwargs):
                if path.name=='i4e2_reviewed_80_summary_v1.json':
                    if failure=='missing': raise FileNotFoundError('injected missing')
                    if failure=='unreadable': raise PermissionError('injected unreadable')
                    return '{invalid' if failure=='invalid-json' else '{}'
                return original(path,*args,**kwargs)
            with self.subTest(failure=failure),patch.object(Path,'read_text',reader):
                app=self.app()
                self.assertTrue(any(m.value=='unavailable' for m in app.metric))
                next(r for r in app.radio if r.label=='Dashboard Data Mode').set_value('Formal Reviewed Golden Evaluation').run()
                self.assertFalse(app.exception,[e.message for e in app.exception])
                self.assertFalse(any(m.value in ('88.21%','494','560','80') for m in app.metric))
                self.assertTrue(any('unavailable' in w.value for w in app.warning))
