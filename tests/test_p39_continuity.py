"""Offline fixed-plan failure isolation, restart and hard safety boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_p39_context_live import setup_fixture,fake
from src.application.p39_context_live import run_smoke
from src.application.p39_continuity import build_runtime,run_fixed,reconcile,engineering_check,diagnose
from src.infrastructure.p39_continuity_budget import ContinuityBudget
from src.infrastructure.deepseek import LiveError
from src.domain.contracts import EmailInput,RunConfigV31,digest


def setup(td, initial=None):
    parent,b,s = setup_fixture(td)
    if initial:
        run_smoke(parent,b,s,initial)
    rt = build_runtime(parent,'EXPLICIT OFFLINE CONTINUITY FIXTURE',Path(td)/'continued')
    budget = ContinuityBudget(b.path,b.counter); budget.install(rt)
    return rt,budget,s


async def schema_bad(msgs,remaining):
    raw,meta = await fake(msgs,remaining)
    value = json.loads(raw); value['schema_version'] = 'bad-fixture'
    return json.dumps(value),meta


class ContinuityTests(unittest.TestCase):
    def test_resume_failed_original_then_complete_64_and_restart_no_resend(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s = setup(td,schema_bad); calls=[]
            async def provider(msgs,remaining):
                calls.append(msgs)
                return await (schema_bad if len(calls)%3 == 0 else fake)(msgs,remaining)
            result = run_fixed(rt,b,s,provider)
            self.assertEqual(len(calls),63); self.assertEqual(result['attempted'],64)
            self.assertEqual(result['failed'],22); self.assertEqual(result['budget']['shared_requests'],65)
            self.assertIsNone(result['budget']['halted'])
            self.assertEqual(json.loads(calls[0][1][1])['email_id'],rt['candidate']['inputs'][rt['candidate']['schedule'][1]['input_index']]['email']['email_id'])
            self.assertIn('Additional researcher-approved general content rules',calls[0][0][1])
            with b.connection() as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM wire_stops').fetchone()[0],1)
                self.assertEqual(c.execute("SELECT COUNT(*) FROM approvals WHERE kind='smoke'").fetchone()[0],0)
                checkpoint=json.loads(c.execute('SELECT receipt FROM r3_checkpoints').fetchone()[0])
            self.assertEqual(checkpoint['attempts'],8); self.assertGreater(checkpoint['failed'],0)
            self.assertIsNone(checkpoint['human_content_approval'])
            run_fixed(rt,ContinuityBudget(b.path,b.counter),s,provider)
            self.assertEqual(len(calls),63)
            self.assertTrue(all(r.result is None for r in reconcile(rt,b) if r.status=='failed'))

    def test_parse_empty_schema_and_reply_gate_failures_continue_paired_B(self):
        for kind in ('parse','empty','schema','reply'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
                rt,b,s = setup(td); calls=[]
                async def provider(msgs,remaining):
                    calls.append(msgs);raw,meta=await fake(msgs,remaining)
                    if len(calls)==1:
                        if kind=='parse':raw='{"unfinished":'
                        elif kind=='empty':raw=''
                        else:
                            value=json.loads(raw)
                            if kind=='schema':value['schema_version']='wrong'
                            else:value['suggested_reply']='We have already refunded your payment.'
                            raw=json.dumps(value)
                    return raw,meta
                result=run_fixed(rt,b,s,provider,limit=2)
                self.assertEqual(len(calls),2);self.assertEqual(result['failed'],1)
                self.assertEqual(result['accepted'],1);self.assertIsNone(b.summary()['halted'])
                failed=reconcile(rt,b)[0];self.assertIsNone(failed.result)
                self.assertIn(diagnose(failed)['stage'],('parsing','schema','safety_gate'))

    def test_truncated_output_is_quality_failure_with_valid_usage(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            async def truncated(msgs,remaining):
                raw,meta=await fake(msgs,remaining);meta['finish_reason']='length';return raw[:20],meta
            result=run_fixed(rt,b,s,truncated,limit=2)
            self.assertEqual(result['failed'],2);self.assertIsNone(b.summary()['halted'])

    def test_unknown_send_retains_locks_no_automatic_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td);calls=[]
            async def timeout(msgs,remaining):calls.append(1);raise LiveError('timeout')
            with self.assertRaises(ValueError):run_fixed(rt,b,s,timeout)
            state=b.summary();self.assertTrue(state['active_lease']);self.assertTrue(state['active_wire_claim'])
            with self.assertRaises(PermissionError):run_fixed(rt,b,s,timeout)
            self.assertEqual(len(calls),1);self.assertEqual(b.summary()['shared_requests'],2)

    def test_usage_model_payload_cost_anomalies_stop_even_if_output_failed(self):
        for change in ({'total_tokens':301},{'resolved_model':'unapproved'},{'cache_miss_tokens':-1},
                       {'actual_payload_sha256':None},{'actual_payload_bytes':50001},{'input_tokens':None}):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
                rt,b,s=setup(td);calls=[]
                async def bad(msgs,remaining):
                    calls.append(1);raw,meta=await schema_bad(msgs,remaining);meta.update(change);return raw,meta
                with self.assertRaises(ValueError):run_fixed(rt,b,s,bad)
                self.assertEqual(len(calls),1);self.assertEqual(b.summary()['halted'],'r3_engineering_safety_stop')

    def test_persistence_exception_and_pending_claim_block_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td);calls=[]
            async def provider(msgs,remaining):calls.append(1);return await fake(msgs,remaining)
            with patch('src.infrastructure.p39_live_context.ContextLiveRepository.finish_live',side_effect=OSError('offline disk fault')):
                with self.assertRaises(OSError):run_fixed(rt,b,s,provider)
            self.assertEqual(len(calls),1);self.assertTrue(b.summary()['active_lease'])
            with self.assertRaises(PermissionError):run_fixed(rt,b,s,provider)
            self.assertEqual(len(calls),1)

    def test_source_drift_never_dispatches_and_runtime_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            with patch('src.application.p39_continuity.source_hash',return_value='changed'):
                with self.assertRaises(ValueError):run_fixed(rt,b,s,fake)
            replacement=copy.deepcopy(rt);replacement['authorization_evidence']='different'
            from hashlib import sha256
            replacement['authorization_sha256']=sha256(b'different').hexdigest()
            replacement.pop('runtime_hash');replacement['runtime_hash']=digest(replacement)
            with self.assertRaises(PermissionError):b.install(replacement)
            self.assertEqual(b.summary()['shared_requests'],1)

    def test_eight_attempt_checkpoint_required_before_ninth_request(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            run_fixed(rt,b,s,schema_bad,limit=8)
            with b.connection() as c:
                receipt=json.loads(c.execute('SELECT receipt FROM r3_checkpoints').fetchone()[0])
            self.assertEqual(receipt['failed'],8);self.assertTrue(receipt['engineering_safe'])
            result=run_fixed(rt,b,s,fake,limit=10)
            self.assertEqual(result['attempted'],10);self.assertEqual(result['failed'],8)

    def test_atomic_claim_race_and_wrong_arm_cannot_reserve(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td);other=ContinuityBudget(b.path,b.counter)
            config=RunConfigV31.model_validate(rt['candidate']['configs']['A'])
            email=EmailInput.model_validate(rt['candidate']['inputs'][rt['candidate']['schedule'][0]['input_index']]['email'])
            b.verify_config(config);other.verify_config(config)
            b.acquire('first',email.input_hash)
            with self.assertRaises(PermissionError):other.acquire('second',email.input_hash)
            self.assertEqual(b.summary()['shared_requests'],1)

    def test_engineering_historical_stop_is_never_acknowledged(self):
        with tempfile.TemporaryDirectory() as td:
            parent,b,s=setup_fixture(td);b.halt('usage_or_payload_anomaly')
            rt=build_runtime(parent,'OFFLINE FIXTURE',Path(td)/'continued')
            with self.assertRaises(PermissionError):ContinuityBudget(b.path,b.counter).install(rt)

    def test_reserved_without_durable_run_is_not_retried(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            with b.connection() as c:
                c.execute("INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES('v2_reserved','missing',0.1,'fixture')")
            with self.assertRaises(ValueError):run_fixed(rt,b,s,fake)
            self.assertEqual(b.summary()['new_reserved_requests'],1)

    def test_currency_cap_and_fixed_cap_are_not_refunded_after_failure(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            with b.connection() as c:
                c.execute("UPDATE events SET upper_cny=9.99 WHERE kind='inherited_v1'")
            with self.assertRaises(PermissionError):run_fixed(rt,b,s,fake)
            self.assertEqual(b.summary()['shared_requests'],1)


if __name__=='__main__':unittest.main()
