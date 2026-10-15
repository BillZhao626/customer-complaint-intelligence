import json
from pathlib import Path
import tempfile
import unittest
from src.application.analysis_service import AnalysisService
from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.repository import Repository
from src.evaluation.p2_report import generate,FIELDS,percentile
from tests.fixtures import EMAILS,VALID

class PilotReportTests(unittest.TestCase):
    def test_failed_sent_sample_stays_in_all_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);space=root/'.local';space.mkdir()
            repo=Repository(space/'runs.sqlite3')
            budget=PilotBudget.create(space/'budget.sqlite3',[e.input_hash for e in EMAILS[:2]],{})
            async def provider(payload,timeout):
                body=json.loads(payload[1][1])['body']
                return (json.dumps(VALID) if body==EMAILS[0].body else '{}'),{}
            service=AnalysisService(repo,DeepSeekAnalyzer(LiveSettings('fixture',True,max_attempts=1),provider),budget=budget)
            for email in EMAILS[:2]:service.analyze(email)
            fixture=root/'fixtures.json'
            fixture.write_text(json.dumps({'cases':[dict(email=e.model_dump(),expected={f:VALID[f] for f in FIELDS}) for e in EMAILS[:2]]}),encoding='utf-8')
            dest=Path(generate(root,space,fixture));metrics=json.loads((dest/'metrics.json').read_text(encoding='utf-8'))
            self.assertEqual(metrics['overall_fields']['numerator'],7)
            self.assertEqual(metrics['overall_fields']['denominator'],14)
            self.assertEqual(metrics['all_seven']['denominator'],2)
            self.assertEqual(metrics['structure']['accepted']['numerator'],1)
            self.assertEqual(metrics['structure']['raw_schema']['denominator'],2)
            self.assertIsNone(metrics['cost']['all_attempts_estimate_cny'])
            self.assertIsNone(metrics['usage']['total_tokens'])
            self.assertTrue((dest/'attempts.csv').exists())
            self.assertNotIn('|\n\n|',(dest/'REPORT.md').read_text(encoding='utf-8'))

    def test_empty_and_small_sample_percentiles(self):
        self.assertIsNone(percentile([],.95))
        self.assertEqual(percentile([10],.95),10)
        self.assertEqual(percentile([0,100],.95),95)
