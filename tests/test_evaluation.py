import csv
import json
import unittest
from pathlib import Path
from collections import Counter
from src.evaluation.core import evaluate,FIELDS,validate_summary
from src.evaluation.run_i4e2_reviewed_80_eval_v1 import compute_weighted_metrics
from src.evaluation.run_i4g_full_pool_deepseek_batch_v1 import summarize

ROOT=Path(__file__).resolve().parents[1]
def rows(path):
    with (ROOT/path).open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


class EvaluationTests(unittest.TestCase):
    def test_empty_null_and_duplicate_ids(self):
        for bad in (None,'','  ',float('nan')):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                evaluate([{'email_id':bad,'sentiment':'positive'}],[{'email_id':'x','sentiment':'positive'}],['sentiment'])
        with self.assertRaises(ValueError):
            evaluate([{'sentiment':'positive'}],[],['sentiment'])

    def test_empty_reference_unavailable(self):
        r=evaluate([],[],FIELDS)
        self.assertEqual(r['status'],'invalid')
        self.assertIsNone(r['correct_fields'])

    def test_extra_prediction_not_ignored(self):
        gold=[{'email_id':'x','sentiment':'positive'}]
        r=evaluate(gold+[{'email_id':'y','sentiment':'positive'}],gold,['sentiment'])
        self.assertEqual(r['status'],'invalid')
        self.assertEqual(r['extra_prediction_ids'],['y'])
        self.assertEqual(r['field_metrics'],{})

    def test_missing_cell_never_filled_unknown(self):
        import pandas as pd
        for bad in (None,'',float('nan'),pd.NA,pd.NaT,[],{}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                evaluate([{'email_id':'x','sentiment':bad}],[{'email_id':'x','sentiment':bad}],['sentiment'])

    def test_corrupt_summary_unavailable(self):
        original=json.loads((ROOT/'outputs/i4e2_reviewed_80_summary_v1.json').read_text())
        self.assertTrue(validate_summary(original)['available'])
        for patch in ({'total_cases':0},{'total_field_count':1},{'overall_field_accuracy':float('nan')},
                      {'overall_field_accuracy':1.0},{'total_mismatch_count':-1},{'field_metrics':{}},
                      {'api_error_count':999},{'fields_compared':FIELDS[:6]}):
            with self.subTest(patch=patch):
                self.assertFalse(validate_summary({**original,**patch})['available'])

    def test_f06_each_bad_row_refuses_acceptance(self):
        original=rows('outputs/i4g_full_pool_deepseek_predictions_v1.csv')
        for patch in ({'backend_used':'mock_fallback'},{'parse_success':False},{'schema_validation_success':False},
                      {'api_attempted':False},{'api_error':'garbage'},{'error_message':'failed'},
                      {'api_error_message':'failed'},{'status':'failed'},{'email_id':''},{'email_id':original[0]['email_id']}):
            test=[dict(r) for r in original];test[-1].update(patch)
            with self.subTest(patch=patch):
                self.assertFalse(summarize(test,0)['accepted_for_dashboard_prediction_mode'])


class HistoricalTests(unittest.TestCase):
    def test_historical_80_raw_all_metrics(self):
        predictions=rows('outputs/i4e2_reviewed_80_predictions_v1.csv')
        gold=rows('data/golden/golden_labels_review_sample_v1_reviewed.csv')
        r=evaluate(predictions,gold)
        self.assertEqual((r['correct_fields'],r['total_fields'],len(r['mismatches']),r['whole_email_correct']),(494,560,66,32))
        saved=json.loads((ROOT/'outputs/i4e2_reviewed_80_summary_v1.json').read_text())
        metrics,mismatches=compute_weighted_metrics(predictions,gold)
        self.assertEqual(len(mismatches),66)
        for field,metric in metrics.items():
            for key,value in metric.items():
                self.assertAlmostEqual(value,saved['field_metrics'][field][key],places=10)

    def test_historical_400_flags_and_exact_input_ids(self):
        predictions=rows('outputs/i4g_full_pool_deepseek_predictions_v1.csv')
        inputs=rows('data/synthetic/customer_emails_full_v1.csv')
        self.assertEqual(len(predictions),400)
        self.assertEqual({r['email_id'] for r in predictions},{r['email_id'] for r in inputs})
        self.assertTrue(summarize(predictions,0)['accepted_for_dashboard_prediction_mode'])
        self.assertEqual(len(rows('outputs/i4g_full_pool_deepseek_failed_cases_v1.csv')),0)

    def test_historical_14_dashboard_tables(self):
        from src.dataset import build_i4f_full_pool_dashboard_stats_v1 as synthetic
        from src.dataset import build_i5c_deepseek_prediction_dashboard_stats_v1 as prediction
        joined=synthetic.join_rows(rows('data/synthetic/customer_emails_full_v1.csv'),rows('data/golden/golden_labels_full_auto_v1.csv'))
        checks=0
        for module,source,folder,prefix,labelprefix in [(synthetic,joined,'dashboard_i4f','','label_'),(prediction,rows('outputs/i4g_full_pool_deepseek_predictions_v1.csv'),'dashboard_i5c_deepseek','deepseek_','')]:
            for filename,actual in [('store_complaint_ranking_v1.csv',module.store_ranking(source)),('product_negative_sentiment_ranking_v1.csv',module.product_ranking(source)),('store_by_product_matrix_v1.csv',module.store_product_matrix(source))]:
                saved=rows('outputs/'+folder+'/'+prefix+filename)
                self.assertEqual(len(saved),len(actual))
                for a,b in zip(saved,actual):
                    for key,value in b.items():
                        if isinstance(value,(int,float)):
                            self.assertAlmostEqual(float(a[key]),value,places=10)
                        else:
                            self.assertEqual(a[key],str(value))
                checks+=1
            for field in ['sentiment','urgency','complaint_reason','source_attribution']:
                saved=rows('outputs/'+folder+'/'+prefix+field+'_distribution_v1.csv')
                self.assertEqual(Counter(r[labelprefix+field] for r in source),Counter({r[field]:int(r['count']) for r in saved}))
                for r in saved:
                    self.assertAlmostEqual(float(r['percentage']),int(r['count'])*100/len(source),places=8)
                checks+=1
        self.assertEqual(checks,14)

    def test_legacy_smoke_31_mismatches_unchanged(self):
        import pandas as pd
        from src.evaluation.run_smoke_test_v1 import run_predictions,find_mismatches
        predictions=run_predictions(pd.read_csv(ROOT/'data/raw/smoke_test_emails_v1.csv'))
        gold=pd.read_csv(ROOT/'data/golden/golden_labels_smoke_v1.csv')
        self.assertEqual(len(predictions),18)
        self.assertEqual(len(find_mismatches(predictions,gold)),31)

    def test_legacy_smoke_report_explicit_six_field_compatibility(self):
        import pandas as pd
        from src.evaluation import run_smoke_test_v1 as smoke
        from src.evaluation.evaluate_results import evaluate_predictions
        predictions=smoke.run_predictions(pd.read_csv(ROOT/'data/raw/smoke_test_emails_v1.csv'))
        gold=pd.read_csv(ROOT/'data/golden/golden_labels_smoke_v1.csv')
        report=evaluate_predictions(predictions,gold,smoke.DEFAULT_LABEL_COLUMNS)
        self.assertEqual(report['total_fields'],108)
        self.assertEqual(report['correct_fields'],77)
        self.assertIn('31 of 108',smoke.build_markdown_report(report,smoke.find_mismatches(predictions,gold)))
