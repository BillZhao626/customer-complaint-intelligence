"""P1 defect regressions; initial red run recorded before implementation."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class EvaluationRegression(unittest.TestCase):
    def evaluate(self, pred, gold):
        from src.evaluation.evaluate_results import evaluate_predictions
        return evaluate_predictions(pd.DataFrame(pred), pd.DataFrame(gold), ['sentiment'])

    def test_f01_missing_prediction(self):
        with self.assertRaises(ValueError):
            self.evaluate([{'email_id':'x'}], [{'email_id':'x','sentiment':'negative'}])

    def test_f01_missing_gold(self):
        with self.assertRaises(ValueError):
            self.evaluate([{'email_id':'x','sentiment':'negative'}], [{'email_id':'x'}])

    def test_f02_many_to_many(self):
        rows = [{'email_id':'x','sentiment':'negative'}] * 2
        with self.assertRaises(ValueError):
            self.evaluate(rows, rows)

    def test_f02_80_vs_79(self):
        rows = [{'email_id':str(i),'sentiment':'negative'} for i in range(80)]
        report = self.evaluate(rows[:-1], rows)
        self.assertEqual((report['status'], report['expected'], report['matched'], report['coverage']), ('invalid',80,79,79/80))
        self.assertEqual(report['metrics'], [])

    def test_f02_formal_duplicate(self):
        from src.evaluation.run_i4e2_reviewed_80_eval_v1 import compute_weighted_metrics
        rows = pd.read_csv(ROOT/'outputs/i4e2_reviewed_80_predictions_v1.csv',keep_default_na=False).to_dict('records')
        with self.assertRaises(ValueError):
            compute_weighted_metrics(rows+rows[:1], rows)


class ContractRegression(unittest.TestCase):
    def test_f03_empty_provider_payload(self):
        from src.chains.langchain_complaint_chain import _prepare_llm_payload
        with self.assertRaises(ValueError):
            _prepare_llm_payload({}, 'x', 'offline', 'deepseek_api')

    def test_f03_illegal_bool(self):
        from src.chains.langchain_complaint_chain import _to_bool
        with self.assertRaises(ValueError):
            _to_bool('unrecognized')

    def test_f04_canonical_represents_research_labels(self):
        from src.domain.contracts import PRODUCT_CATEGORIES
        actual=set(pd.read_csv(ROOT/'data/synthetic/customer_emails_full_v1.csv')['product_category'])
        self.assertEqual(set(PRODUCT_CATEGORIES),actual|{'unknown'})


class PresentationRegression(unittest.TestCase):
    def test_f05_missing_summary(self):
        import app
        with patch.object(app.st,'metric') as metric, patch.object(app.st,'warning') as warning, patch.object(app.st,'columns') as columns:
            app.render_formal_evaluation_summary({}, {})
            columns.assert_not_called()
            metric.assert_not_called()
            self.assertTrue(warning.called)

    def test_f06_mixed_backend(self):
        from src.evaluation.run_i4g_full_pool_deepseek_batch_v1 import summarize
        row={'backend_used':'deepseek_api','parse_success':True,'schema_validation_success':True,'api_attempted':True,'api_error':False}
        rows=[dict(row,email_id=str(i)) for i in range(400)]
        rows[-1]['backend_used']='mock_fallback'
        report=summarize(rows,0)
        self.assertFalse(report['accepted_for_dashboard_prediction_mode'])
        self.assertEqual(report['failed_count'],1)
