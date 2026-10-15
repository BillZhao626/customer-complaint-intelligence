"""Safe self-contained smoke fixtures; no historical research assets required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os

from src.application.analysis_service import AnalysisService
from src.application.analyzers import OfflineFake
from src.domain.contracts import EmailInput
from src.infrastructure.repository import Repository


class PortableSmoke(unittest.TestCase):
    def test_service_roundtrip_aggregate_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'runs.sqlite3'
            service = AnalysisService(Repository(path), OfflineFake())
            emails = [EmailInput(email_id=str(i), subject='Synthetic smoke', body=body)
                      for i, body in enumerate(('[store:A] [negative]', '[store:A] [positive]', '[fail]'))]
            runs = [service.analyze(email) for email in emails]
            self.assertEqual(service.analyze(emails[0]).run_id, runs[0].run_id)
            self.assertEqual(Repository(path).get(runs[0].run_id).email, emails[0])
            self.assertEqual(runs[2].status, 'failed')
            group = service.aggregate(runs[0].cohort_id)[0]
            self.assertEqual((group['numerator'], group['denominator'], group['negative_rate']), (1, 2, .5))
            self.assertEqual(set(group['member_run_ids']), {r.run_id for r in runs[:2]})

    def test_actual_app_without_historical_assets(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'COMPLAINT_DB_PATH': str(Path(directory) / 'ui.sqlite3')}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30).run()
            self.assertFalse(app.exception)
            app.button(key='offline_analyze').click().run()
            self.assertFalse(app.exception)
            run_id = app.session_state['offline_run_id']
            app.run()
            self.assertEqual(app.session_state['offline_run_id'], run_id)
            self.assertTrue(any('saved successfully' in s.value for s in app.success))
