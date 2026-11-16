"""No API: reject source drift and family leakage before a provider is invoked."""
import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from src.evaluation.experiment_integrity import freeze,verify,verify_loaded_code,file_hash,family_preflight,IntegrityError
from src.infrastructure.p5b8r3_execution import Dispatcher

ROOT=Path(__file__).resolve().parents[1]
def record(case,family,input_hash):
    return dict(case_id=case,family=family,input_hash=input_hash,family_review=dict(reviewed_against_full_registry=True))

class ExecutionIntegrityTests(unittest.TestCase):
    def test_drift_during_response_invalidates_run_preserving_raw_and_usage(self):
        from src.domain.contracts import digest
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);dataset=root/'dataset.json';dataset.write_text('[]','utf8')
            integrity=freeze(ROOT,inputs=[dataset]);calls=[]
            def provider(*args):
                calls.append('dispatched');dataset.write_text('["changed while request ran"]','utf8')
                return '{"reply":"fixture"}',dict(input_tokens=10,output_tokens=10,total_tokens=20)
            plan=dict(planned_requests=2,proposed_cny_cap=1,allowed_call_ids=['ONE','TWO'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8),execution_integrity=integrity)
            d=Dispatcher(root/'mock',plan,provider=provider)
            with self.assertRaisesRegex(IntegrityError,'Frozen input drift'):d.call('ONE',[('human','JSON fixture')])
            self.assertTrue((root/'mock/calls'/digest('ONE')/'response.json').exists())
            with d.connect() as conn:
                state,cost=conn.execute('select state,settled_micro from calls').fetchone()
                self.assertEqual(state,'INTEGRITY_FAILED');self.assertIsNotNone(cost)
            with self.assertRaises(IntegrityError):d.call('TWO',[('human','JSON fixture')])
            self.assertEqual(calls,['dispatched'])

    def test_independent_dispatch_requires_pinned_dataset_registry(self):
        with tempfile.TemporaryDirectory() as t:
            calls=[];plan=dict(planned_requests=1,proposed_cny_cap=1,allowed_call_ids=['ONE'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8),execution_integrity=freeze(ROOT))
            d=Dispatcher(Path(t),plan,provider=lambda *args:calls.append(args))
            with self.assertRaisesRegex(ValueError,'Independent dispatch requires'):
                d.call('ONE',[('human','JSON fixture')],dict(dataset_role='INDEPENDENT_TEST'))
            self.assertFalse(calls)
    def test_stale_import_and_changed_constant_fail_even_with_current_file_hash(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'probe.py';name='src._integrity_probe'
            original='VERSION="v1"\ndef policy():\n    return "old"\n'
            p.write_text(original,'utf8');module=types.ModuleType(name);module.__file__=str(p);exec(compile(original,str(p),'exec'),module.__dict__)
            hashes={'probe.py':file_hash(p)};verify_loaded_code(root,hashes,modules={name:module})
            p.write_text(original.replace('"old"','"new"'),'utf8')
            with self.assertRaisesRegex(IntegrityError,'Loaded implementation'):
                verify_loaded_code(root,{'probe.py':file_hash(p)},modules={name:module})
            p.write_text(original.replace('"v1"','"v2"'),'utf8')
            with self.assertRaisesRegex(IntegrityError,'Loaded constant'):
                verify_loaded_code(root,{'probe.py':file_hash(p)},modules={name:module})

    def test_input_drift_blocks_dispatch_before_reservation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);input_path=root/'dataset.json';input_path.write_text('[]','utf8')
            integrity=freeze(ROOT,inputs=[input_path]);verify(integrity)
            plan=dict(planned_requests=1,proposed_cny_cap=1,allowed_call_ids=['ONE'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8),execution_integrity=integrity)
            calls=[];d=Dispatcher(root/'mock',plan,provider=lambda *args:calls.append(args))
            input_path.write_text('["changed"]','utf8')
            with self.assertRaisesRegex(IntegrityError,'Frozen input drift'):d.call('ONE',[('human','JSON fixture')])
            self.assertEqual(calls,[])
            with d.connect() as conn:self.assertEqual(conn.execute('select count(*) from calls').fetchone()[0],0)

    def test_historical_family_cannot_be_renamed_or_hash_reused(self):
        history=[record('R3N-007','accessible-digital-instructions','a'*64)]
        aliases={'accessible_manual_after_positive_visit':'accessible-digital-instructions'}
        with self.assertRaisesRegex(IntegrityError,'EXPOSED_CANONICAL_FAMILY'):
            family_preflight([record('new-name','accessible_manual_after_positive_visit','b'*64)],history,aliases)
        with self.assertRaisesRegex(IntegrityError,'EXPOSED_INPUT_HASH'):
            family_preflight([record('new-name','different-family','a'*64)],history)
        self.assertEqual(family_preflight([record('novel','different-family','b'*64)],history)['candidates'],1)

    def test_unreviewed_or_duplicate_new_input_is_not_independent(self):
        row=record('new','new-family','c'*64);row['family_review']={}
        with self.assertRaisesRegex(IntegrityError,'FAMILY_REVIEW_MISSING'):family_preflight([row],[])
        row['family_review']['reviewed_against_full_registry']=True
        with self.assertRaisesRegex(IntegrityError,'DUPLICATE_CANDIDATE_INPUT'):family_preflight([row,dict(row,case_id='copy')],[])

    def test_closed_r6_entry_does_not_construct_dispatcher(self):
        from scripts import p5b8r6
        with patch('src.infrastructure.p5b8r3_execution.Dispatcher') as constructor:
            with self.assertRaisesRegex(PermissionError,'R6_CLOSED_PERMANENTLY'):p5b8r6.dispatcher()
            constructor.assert_not_called()
