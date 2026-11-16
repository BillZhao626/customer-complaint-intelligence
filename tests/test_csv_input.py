"""CSV faults must stay local to their tab, preserving the durable P4 workflow."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class CSVInputTests(unittest.TestCase):
    def test_invalid_bytes_and_unreadable_files_are_safe_but_valid_values_survive(self):
        from src.app.csv_input import CSVInputError, read_csv_input
        for raw in (b'', b'email_id,email_text\n', b'email_id,email_text\n1,"private unterminated', b'email_id,email_text\n1,\xff'):
            with self.subTest(raw=raw), self.assertRaises(CSVInputError) as caught:
                read_csv_input(io.BytesIO(raw))
            self.assertNotIn('private', str(caught.exception))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CSVInputError):
                read_csv_input(Path(directory) / 'absent.csv')
        frame = read_csv_input(io.BytesIO('email_id,email_text\nqa,"中文, quoted"\n'.encode()))
        self.assertEqual(frame.to_dict('records'), [{'email_id': 'qa', 'email_text': '中文, quoted'}])


class CSVBoundaryUI(unittest.TestCase):
    def test_bad_uploads_leave_other_tabs_and_saved_case_available_then_recover(self):
        from src.application.analysis_service import AnalysisService
        from src.application.product_demo import ProductFake, SCENARIOS, example
        from src.application.product_workflow import ProductStore
        from src.infrastructure.repository import Repository
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            store = ProductStore(base / 'product.sqlite3')
            email, _ = example(SCENARIOS[0])
            run = AnalysisService(Repository(base / 'analysis.sqlite3'), ProductFake(email, SCENARIOS[0])).analyze(email)
            original = store.create(run)
            env = dict(COMPLAINT_PRODUCT_DB=str(store.path), COMPLAINT_DB_PATH=str(base / 'legacy.sqlite3'))
            for label in ('Upload customer email CSV', 'Prediction CSV', 'Golden label CSV'):
                # Read failures must not leak source contents into an exception panel.
                payload = {'value': b''}
                def upload(name, *args, **kwargs):
                    return io.BytesIO(payload['value']) if name == label else None
                with self.subTest(label=label), patch.dict(os.environ, env), patch('streamlit.file_uploader', side_effect=upload):
                    app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=45)
                    app.query_params['case_id'] = original['case_id']
                    app.run()
                    self.assertFalse(app.exception, [e.message for e in app.exception])
                    self.assertTrue(any('CSV' in e.value for e in app.error))
                    self.assertTrue(any(b.label == 'Generate sample dataset' for b in app.button))
                    self.assertTrue(any(r.label == 'Dashboard view' for r in app.radio))
                    self.assertTrue(any(email.body in t.value for t in app.text))
                    self.assertEqual(store.get(original['case_id']), original)
                    payload['value'] = b'email_id,email_text\nqa-csv,Camera question\n'
                    app.run()
                    self.assertFalse(app.exception, [e.message for e in app.exception])
                    self.assertFalse(any('CSV' in e.value for e in app.error))
                    self.assertEqual(store.get(original['case_id']), original)
