"""One visible correction, no repeated repair, no reference answers."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_p310_execution import inputs,authorization,fake_provider
from src.application.p310_experiment import make_plan,run_plan,ReadOnlyResearchRepository
from src.application.p310_correction import context_for,messages,identity
from src.infrastructure.p310_budget import ResearchBudget
from src.infrastructure.v3_live_settings import V3PilotSettings


class CorrectionTests(unittest.TestCase):
    def test_visible_parent_lineage_and_single_extra_call(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            root=Path(tmp);b=ResearchBudget.create(root/'budget.sqlite3',authorization(),True)
            settings=V3PilotSettings(api_key='offline',enabled=True,max_tokens=4000,max_attempts=1)
            first=make_plan(inputs(1));calls,p=fake_provider(['broken JSON'])
            run_plan(first,b,settings,root/'first',p)
            parent=ReadOnlyResearchRepository(root/'first'/'runs.sqlite3').list_runs()[0]
            c=context_for(parent);self.assertFalse(c['reference_answers_supplied']);self.assertFalse(c['human_scores_supplied'])
            corrected=make_plan([dict(email=parent.email.model_dump(),source='explicit first-pass parent',repair_context=c)],'correction')
            second_calls,p2=fake_provider();run_plan(corrected,b,settings,root/'second',p2)
            result=ReadOnlyResearchRepository(root/'second'/'runs.sqlite3').list_runs()[0]
            self.assertIsNone(parent.result);self.assertIsNotNone(result.result)
            self.assertEqual(result.metadata['correction_parent_run_id'],parent.run_id)
            self.assertEqual(result.metadata['correction_parent_raw_sha256'],c['prior_raw_sha256'])
            self.assertEqual(len(calls),1);self.assertEqual(len(second_calls),1);self.assertEqual(b.summary()['reserved_attempts'],2)
            from src.evaluation.p310_workflow_report import combine
            workflow=combine(first,[parent],corrected,[result])
            self.assertEqual(workflow['arms']['challenger']['first_pass_accepted'],0)
            self.assertEqual(workflow['arms']['challenger']['final_accepted'],1)
            self.assertEqual(workflow['arms']['challenger']['additional_calls'],1)
            self.assertEqual(workflow['members'][0]['original_status_unchanged'],'failed')
            corrected['inputs'][0]['repair_context']['parent_run_hash']='changed'
            with self.assertRaises(ValueError):combine(first,[parent],corrected,[result])
            with self.assertRaises(ValueError):context_for(result)
            changed=make_plan([dict(email=parent.email.model_dump(),source='different source marker',repair_context=c)],'correction')
            with self.assertRaises(PermissionError):b.register_plan(changed)
            c['prior_raw']='changed'
            with self.assertRaises(ValueError):messages(parent.email,c)

    def test_corrector_identity_is_a_workflow_not_single_call_improvement(self):
        i=identity();self.assertEqual(i['max_corrections'],1);self.assertTrue(i['extra_calls_reported'])
        self.assertFalse(i['model_improvement_proven']);self.assertFalse(i['default_enabled'])
