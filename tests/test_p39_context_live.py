"""Formal live orchestrator with explicit offline provider/HTTP fixtures only."""
import asyncio
import copy
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.application.p39_context_live import (build_runtime,run_smoke,ContextLiveAnalyzer,ContextLiveService,verify_runtime)
from src.application.p39_v2 import manifest as context_manifest,messages
from src.application.p39_experiment import wire_payload
from src.application.v31_demo import pipeline_probe
from src.domain.contracts import EmailInput,RunConfigV31,digest
from src.infrastructure.p39_envelope import P39Envelope
from src.infrastructure.p39_live_context import ContextLiveBudget,ContextLiveRepository
from src.infrastructure.context_repository import ReadOnlyContextRepository
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from tests.test_p39 import manifest,CounterFixture
from tests.test_urgency_context import prior_fixture


def setup_fixture(td):
    root=Path(td);old=root/'old.sqlite3';prior_fixture(old)
    parent=manifest();parent['manifest_hash']='fixture-parent'
    m=context_manifest(parent,'fixture-evidence')
    req=dict(user_evidence='OFFLINE FIXTURE ONLY',user_evidence_sha256=sha256(b'OFFLINE FIXTURE ONLY').hexdigest(),combined_planned_requests=65,explicit_extra_allowance=1,offline_test_fixture=True)
    envelope=P39Envelope.create(root/'envelope.sqlite3',old,m,req)
    approval=dict(status='researcher_approved_comparison_change',reviewer='OFFLINE TEST FIXTURE',manifest_hash=m['manifest_hash'],user_approval_evidence='OFFLINE FIXTURE ONLY',user_approval_evidence_sha256=req['user_evidence_sha256'])
    price=dict(checked_at=datetime.now(timezone.utc).isoformat(),price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',model='deepseek-flash',model_availability_verified=True,prices=dict(input_cny_per_million=2,output_cny_per_million=8))
    counter=CounterFixture();runtime=build_runtime(m,approval,price,root/'runtime',counter,fixture=True)
    envelope.approve(approval)
    budget=ContextLiveBudget(envelope.path,counter);budget.install(runtime)
    settings=V3PilotSettings('OFFLINE_FIXTURE_ONLY',True,max_tokens=4000,max_attempts=1)
    return runtime,budget,settings


async def fake(msgs,remaining):
    p=json.loads(msgs[1][1]);email=EmailInput(email_id=p['email_id'],subject=p['subject'],body=p['body'])
    return pipeline_probe(email).model_dump_json(),dict(resolved_model='deepseek-flash',input_tokens=100,output_tokens=200,total_tokens=300,
        cache_hit_tokens=60,cache_miss_tokens=40,finish_reason='stop',actual_payload_sha256=sha256(json.dumps(wire_payload(msgs)).encode()).hexdigest(),actual_payload_bytes=20000)


class ContextLiveTests(unittest.TestCase):
    def test_formal_eight_sqlite_reload_idempotency_receipt_and_gate(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td);calls=[]
            async def counted(msgs,remaining):calls.append(msgs);return await fake(msgs,remaining)
            result=run_smoke(rt,b,s,counted)
            self.assertEqual(result['returned_runs'],8);self.assertEqual(len(calls),8)
            self.assertEqual(b.summary()['shared_requests'],9)
            self.assertAlmostEqual(b.summary()['shared_reserved_upper_cny'],.04+8*.056)
            receipt=json.loads((Path(rt['runtime_directory'])/'smoke-receipt.json').read_text(encoding='utf8'))
            self.assertEqual(len(receipt['run_bindings']),8);self.assertIsNone(receipt['human_content_approval'])
            repo=ReadOnlyContextRepository(Path(rt['runtime_directory'])/'runs.sqlite3')
            for binding in receipt['run_bindings']:
                r=repo.get(binding['run_id']);self.assertEqual(r.metadata['runtime_hash'],rt['runtime_hash'])
                self.assertEqual(sha256(r.attempts[-1].raw_output.encode()).hexdigest(),binding['raw_sha256'])
            # Restart reuses all 8 durable runs and sends nothing.
            run_smoke(rt,ContextLiveBudget(b.path,b.counter),s,counted);self.assertEqual(len(calls),8)
            b.verify_config(RunConfigV31.model_validate(rt['candidate']['configs']['A']))
            with self.assertRaises(PermissionError):b.acquire('ninth','unapproved')
            self.assertEqual(b.summary()['shared_requests'],9)

    def test_real_sdk_payload_audit_both_approved_prompts_no_reference(self):
        import httpx
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td);m=rt['candidate'];email=EmailInput.model_validate(m['inputs'][0]['email'])
            async def check():
                for arm in ('A','B'):
                    analyzer=ContextLiveAnalyzer(s,m,arm,b.counter);client,transport=analyzer.make_client(10);original=transport._transport;seen=[]
                    async def handler(req):
                        seen.append(json.loads(req.content))
                        return httpx.Response(200,json=dict(id='offline-fixture',object='chat.completion',created=0,model='deepseek-flash',
                            choices=[dict(index=0,message=dict(role='assistant',content=pipeline_probe(email).model_dump_json()),finish_reason='stop')],
                            usage=dict(prompt_tokens=100,completion_tokens=200,total_tokens=300,prompt_cache_hit_tokens=60,prompt_cache_miss_tokens=40)))
                    transport._transport=httpx.MockTransport(handler);analyzer.make_client=lambda timeout:(client,transport)
                    try:
                        raw,meta=await analyzer.request(email,False,30)
                        self.assertEqual(seen,[wire_payload(messages(email,arm))]);self.assertTrue(meta['actual_payload_sha256'])
                        self.assertEqual(set(json.loads(messages(email,arm)[1][1])),{'email_id','subject','body','input_hash','evidence_catalog'})
                    finally:await original.aclose()
            asyncio.run(check())

    def test_contract_failure_stops_one_no_receipt_no_retry(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td);calls=[]
            async def bad(msgs,remaining):
                calls.append(1);raw,meta=await fake(msgs,remaining);d=json.loads(raw);d['schema_version']='invalid';return json.dumps(d),meta
            r=run_smoke(rt,b,s,bad)
            self.assertEqual(len(calls),1);self.assertEqual(r['budget']['halted'],'failure_requires_review')
            self.assertEqual(r['budget']['shared_requests'],2)
            self.assertFalse((Path(rt['runtime_directory'])/'smoke-receipt.json').exists())
            run_smoke(rt,b,s,bad);self.assertEqual(len(calls),1)

    def test_unknown_send_keeps_both_leases_across_restart(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td)
            async def timeout(msgs,remaining):raise LiveError('timeout')
            result=run_smoke(rt,b,s,timeout)
            state=ContextLiveBudget(b.path,b.counter).summary()
            self.assertTrue(state['active_lease']);self.assertTrue(state['active_wire_claim'])
            self.assertEqual(state['shared_requests'],2);self.assertIsNone(result['smoke_receipt_hash'])
            run_smoke(rt,b,s,timeout);self.assertEqual(b.summary()['shared_requests'],2)

    def test_model_usage_cache_and_payload_anomalies_each_stop_first(self):
        for change,reason in [({'resolved_model':'different'},'resolved_model_identity_drift'),({'total_tokens':301},'usage_or_payload_anomaly'),
                              ({'cache_hit_tokens':101},'usage_or_payload_anomaly'),({'actual_payload_sha256':None},'usage_or_payload_anomaly')]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as td:
                rt,b,s=setup_fixture(td)
                async def bad(msgs,remaining):raw,meta=await fake(msgs,remaining);meta.update(change);return raw,meta
                result=run_smoke(rt,b,s,bad)
                self.assertEqual(result['budget']['halted'],reason);self.assertEqual(result['budget']['new_reserved_requests'],1)

    def test_wrong_arm_prompt_and_runtime_replacement_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td);m=rt['candidate'];row=m['inputs'][m['schedule'][0]['input_index']];email=EmailInput.model_validate(row['email'])
            b.verify_config(RunConfigV31.model_validate(m['configs']['B']))
            with self.assertRaises(PermissionError):b.acquire('bad-arm',email.input_hash)
            b.verify_config(RunConfigV31.model_validate(m['configs']['A']));b.acquire('valid',email.input_hash)
            with self.assertRaises(PermissionError):b.reserve('valid',1,email.input_hash,messages(email,'B'),4000)
            self.assertEqual(b.summary()['new_reserved_requests'],0)
            replacement=copy.deepcopy(rt);replacement['runtime_directory']+='-clone';replacement.pop('runtime_hash');replacement['runtime_hash']=digest(replacement)
            with self.assertRaises(PermissionError):b.install(replacement)

    def test_source_drift_and_missing_approval_never_initialize_client(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup_fixture(td)
            with patch('src.application.p39_context_live.execution_hash',return_value='changed'):
                with self.assertRaises(ValueError):verify_runtime(rt)
            rt=copy.deepcopy(rt);rt['comparison_approval']['manifest_hash']='wrong';rt.pop('runtime_hash');rt['runtime_hash']=digest(rt)
            with self.assertRaises(PermissionError):verify_runtime(rt)
