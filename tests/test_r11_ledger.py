"""Explicit rejection recovery keeps budget counts and forbids silent redispatch."""
import json
from pathlib import Path
import tempfile
import unittest
from src.infrastructure.p5b8r3_execution import Dispatcher

class RejectionTests(unittest.TestCase):
    def test_recovery_preserves_reservation_and_original_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(planned_requests=2,proposed_cny_cap=1,allowed_call_ids=['a','b'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
            def reject(messages,folder,payload):
                (folder/'provider-http.json').write_text(json.dumps(dict(status=402)))
                (folder/'provider-response.txt').write_text(json.dumps(dict(error=dict(message='Insufficient Balance'))))
                raise RuntimeError('explicit fake HTTP rejection')
            d=Dispatcher(tmp,plan,provider=reject)
            with self.assertRaises(RuntimeError):d.call('a',[('human','fixture')])
            before=d.summary()['reserved_or_settled_upper_cny']
            d.reconcile_rejection('a',402)
            self.assertEqual(d.summary()['reserved_or_settled_upper_cny'],before)
            self.assertEqual(d.summary()['states'],{'REJECTED_402':1})
            with self.assertRaisesRegex(RuntimeError,'UNKNOWN_DO_NOT_RETRY'):d.call('a',[('human','fixture')])
            d.provider=lambda m,f,p:('{}',dict(input_tokens=1,output_tokens=1,total_tokens=2))
            self.assertEqual(d.call('b',[('human','other')])['raw'],'{}')
            self.assertEqual(sum(d.summary()['states'].values()),2)
    def test_successful_wire_cannot_be_reconciled_as_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(planned_requests=1,proposed_cny_cap=1,allowed_call_ids=['a'],pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
            def success(m,f,p):
                (f/'provider-http.json').write_text('{"status":200}')
                (f/'provider-response.txt').write_text('{"choices":[{}]}')
                raise RuntimeError('interrupted fixture')
            d=Dispatcher(tmp,plan,provider=success)
            with self.assertRaises(RuntimeError):d.call('a',[('human','fixture')])
            with self.assertRaises(ValueError):d.reconcile_rejection('a',402)
            with self.assertRaises(ValueError):d.reconcile_rejection('a','NOT_DISPATCHED')

if __name__=='__main__':unittest.main()
