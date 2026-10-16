"""Explicit fake provider only. These tests never prove real semantic accuracy."""
import copy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_p38 import ab_manifest,authorization
from src.application.p39_experiment import build_manifest,preflight,messages,wire_bytes,run_live,validate_smoke_review
from src.infrastructure.p39_budget import P39Budget
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.domain.contracts import EmailInput,RunConfigV31,digest
from src.application.v31_demo import pipeline_probe


class CounterFixture:
    def measure(self,msgs):
        raw=wire_bytes(msgs)
        return dict(payload_bytes=len(raw),payload_sha256=sha256(raw).hexdigest(),input_token_reserve=12000,
                    exact_api_token_proof=False,token_count_source='EXPLICIT OFFLINE FIXTURE')


def manifest(): return build_manifest(ab_manifest(),'fixture-archive','fixture-tokenizer')


def auth(m,**kwargs):
    a=authorization(m,**kwargs)
    a['authorization_evidence_sha256']=sha256(a['authorization_evidence'].encode('utf8')).hexdigest()
    return a


async def fake(msgs,timeout):
    p=json.loads(msgs[1][1]);e=EmailInput(email_id=p['email_id'],subject=p['subject'],body=p['body'])
    return pipeline_probe(e).model_dump_json(),dict(resolved_model='deepseek-flash',input_tokens=100,output_tokens=200,total_tokens=300)


class P39Tests(unittest.TestCase):
    def test_sdk_http_body_audit_and_cache_usage_with_mock_transport(self):
        import asyncio
        import httpx
        from src.application.p39_experiment import P39Analyzer,wire_payload
        m=manifest();e=EmailInput.model_validate(m['inputs'][0]['email']);seen=[]
        async def check():
            a=P39Analyzer(V3PilotSettings('OFFLINE_FIXTURE',True,max_tokens=4000,max_attempts=1),m,'B',CounterFixture())
            client,transport=a.make_client(10)
            async def handler(request):
                seen.append(json.loads(request.content))
                return httpx.Response(200,json=dict(id='offline-response',object='chat.completion',created=0,model='deepseek-flash',
                    choices=[dict(index=0,message=dict(role='assistant',content=pipeline_probe(e).model_dump_json()),finish_reason='stop')],
                    usage=dict(prompt_tokens=100,completion_tokens=200,total_tokens=300,prompt_cache_hit_tokens=60,prompt_cache_miss_tokens=40)))
            original=transport._transport
            transport._transport=httpx.MockTransport(handler)
            a.make_client=lambda timeout:(client,transport)
            try:
                raw,meta=await a.request(e,False,30)
                self.assertEqual(json.loads(raw)['schema_version'],'analysis-v3.1')
                self.assertEqual(meta['cache_hit_tokens'],60);self.assertEqual(meta['cache_miss_tokens'],40)
                self.assertGreater(meta['actual_payload_bytes'],0)
                self.assertEqual(seen,[wire_payload(messages(e,'B'))])
            finally:await original.aclose()
        asyncio.run(check())

    def test_source_parent_whitelist_schema_schedule_and_no_answers(self):
        m=manifest();self.assertEqual(preflight(m)['scheduled_requests'],64)
        self.assertEqual(m['inputs'],m['parent_p38_manifest']['inputs'])
        self.assertEqual(m['schedule'],m['parent_p38_manifest']['schedule'])
        from src.application.v31_prompt import system
        from src.application.p39_experiment import system as new_system
        self.assertEqual(new_system('A'),system('A'))
        self.assertTrue(new_system('B').startswith(system('B')))
        e=EmailInput.model_validate(m['inputs'][0]['email']);p=json.loads(messages(e,'B')[1][1])
        self.assertEqual(set(p),{'email_id','subject','body','input_hash','evidence_catalog'})

    def test_report_retains_missing_failed_denominators_and_null_human_scores(self):
        from tests.test_p38 import fixture_references
        from src.evaluation.p39_report import evaluate
        m=manifest();report=evaluate(m,[],fixture_references(m['parent_p38_manifest']))
        self.assertEqual(len(report['pairs']),32);self.assertEqual(report['not_attempted'],64)
        for a in ('A','B'):
            self.assertEqual(report['arms'][a]['old_seven_consistency']['fixed_denominator'],168)
            self.assertIsNone(report['arms'][a]['issue_semantic_accuracy'])
            self.assertIsNone(report['arms'][a]['actual_invoice_cost_cny'])
        self.assertTrue(all(p['semantic_winner'] is None for p in report['pairs']))

    def test_specific_information_inquiry_low_cannot_declare_general_help_basis(self):
        from tests.test_p38 import one
        from src.domain.analysis_v31 import AnalysisV31
        e,d=one('Does this device have a wired mode? Nothing is broken.','low','none','general_help','none')
        with self.assertRaisesRegex(ValueError,'Urgency contradicts declared policy basis'):
            AnalysisV31.model_validate(d)
        # Diagnostic fixture only, never a runtime repair of provider output.
        diagnostic=copy.deepcopy(d);diagnostic['issues'][0]['urgency_basis']='other'
        AnalysisV31.model_validate(diagnostic).validate_input(e)

    def test_authorization_hard_caps_expiration_evidence_and_source_drift(self):
        m=manifest();a=auth(m);self.assertTrue(preflight(m,a)['paid_dispatch_allowed'])
        for key,value in [('requests',73),('cny',11),('requests',True),('authorization_evidence','forged'),('prices_verified_at',(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())]:
            bad=dict(a);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):preflight(m,bad)
        bad=copy.deepcopy(m);bad['schedule'].reverse();bad.pop('manifest_hash');bad['manifest_hash']=digest(bad)
        with self.assertRaises(ValueError):preflight(bad,a)

    def test_missing_auth_or_smoke_approval_precedes_client_and_database(self):
        m=manifest()
        with tempfile.TemporaryDirectory() as td,patch('src.infrastructure.v3_live_settings.V3PilotSettings.from_env',side_effect=AssertionError('must not initialize')):
            out=Path(td)/'runtime'
            with self.assertRaises(PermissionError):run_live(m,None,out,CounterFixture())
            self.assertFalse(out.exists())
            out.mkdir();(out/'smoke-receipt.json').write_text('{}',encoding='utf8')
            with self.assertRaises(PermissionError):run_live(m,auth(m),out,CounterFixture(),'remaining')
            self.assertFalse((out/'budget.sqlite3').exists())

    def test_p39_historical_path_and_exclusive_creation(self):
        m=manifest()
        with self.assertRaises(ValueError):P39Budget.create(Path(__file__).resolve().parents[1]/'.local/p36/forbidden/budget.sqlite3',m,auth(m),CounterFixture())
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'runtime/budget.sqlite3';P39Budget.create(p,m,auth(m),CounterFixture())
            with self.assertRaises(FileExistsError):P39Budget.create(p,m,auth(m),CounterFixture())

    def test_hard_request_currency_caps_restart_and_concurrent_lease(self):
        m=manifest();step=m['schedule'][0];e=EmailInput.model_validate(m['inputs'][step['input_index']]['email'])
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'runtime/budget.sqlite3';b=P39Budget.create(p,m,auth(m,requests=1),CounterFixture())
            b.verify_config(RunConfigV31.model_validate(m['configs'][step['arm']]))
            b.acquire('one',e.input_hash);b.reserve('one',1,e.input_hash,messages(e,step['arm']),4000)
            restarted=P39Budget(p,CounterFixture())
            self.assertEqual(restarted.summary()['reserved_attempts'],1)
            with self.assertRaises(LiveError):restarted.acquire('two',e.input_hash)
            b.completed('one',1);b.release('one');b.acquire('two',e.input_hash)
            with self.assertRaises(LiveError):b.reserve('two',1,e.input_hash,messages(e,step['arm']),4000)
            self.assertEqual(b.summary()['halted'],'authorization_limit')
        with tempfile.TemporaryDirectory() as td:
            b=P39Budget.create(Path(td)/'runtime/budget.sqlite3',m,auth(m,cny=.001),CounterFixture())
            b.verify_config(RunConfigV31.model_validate(m['configs'][step['arm']]));b.acquire('one',e.input_hash)
            with self.assertRaises(LiveError):b.reserve('one',1,e.input_hash,messages(e,step['arm']),4000)
            self.assertEqual(b.summary()['reserved_attempts'],0)

    def test_payload_and_fixed_order_cannot_bypass_budget(self):
        m=manifest();s=m['schedule'][0];e=EmailInput.model_validate(m['inputs'][s['input_index']]['email'])
        with tempfile.TemporaryDirectory() as td:
            b=P39Budget.create(Path(td)/'runtime/budget.sqlite3',m,auth(m),CounterFixture())
            b.verify_config(RunConfigV31.model_validate(m['configs'][s['arm']]));b.acquire('one',e.input_hash)
            with self.assertRaises(LiveError):b.reserve('one',1,e.input_hash,messages(e,'B' if s['arm']=='A' else 'A'),4000)
            with self.assertRaises(LiveError):b.reserve('one',2,e.input_hash,messages(e,s['arm']),4000)
            self.assertEqual(b.summary()['reserved_attempts'],0)

    def test_fake_smoke_reload_and_durable_gate_blocks_ninth_call(self):
        m=manifest();a=auth(m);settings=V3PilotSettings('OFFLINE_FIXTURE',True,max_tokens=4000,max_attempts=1)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'runtime';r=run_live(m,a,out,CounterFixture(),settings=settings,provider=fake)
            self.assertEqual(r['returned_runs'],8);self.assertEqual(r['budget']['reserved_attempts'],8)
            receipt=json.loads((out/'smoke-receipt.json').read_text(encoding='utf8'))
            self.assertEqual(receipt['passed_pairs'],4);self.assertIsNone(receipt['human_content_approval'])
            with self.assertRaises(PermissionError):run_live(m,a,out,CounterFixture(),'remaining',settings=settings,provider=fake)
            b=P39Budget(out/'budget.sqlite3',CounterFixture());s=m['schedule'][8];e=EmailInput.model_validate(m['inputs'][s['input_index']]['email'])
            b.verify_config(RunConfigV31.model_validate(m['configs'][s['arm']]));b.acquire('bypass',e.input_hash)
            with self.assertRaises(LiveError):b.reserve('bypass',1,e.input_hash,messages(e,s['arm']),4000)
            self.assertEqual(b.summary()['reserved_attempts'],8)

    def test_fake_approval_bound_to_outputs_then_only_56_remaining_no_retests(self):
        m=manifest();a=auth(m);settings=V3PilotSettings('OFFLINE_FIXTURE',True,max_tokens=4000,max_attempts=1)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'runtime';run_live(m,a,out,CounterFixture(),settings=settings,provider=fake)
            receipt=json.loads((out/'smoke-receipt.json').read_text(encoding='utf8'))
            review=dict(status='researcher_approved',reviewer='EXPLICIT OFFLINE TEST FIXTURE',user_approval_evidence='SIMULATED TEST ONLY',smoke_receipt_hash=digest(receipt))
            bad=dict(review,smoke_receipt_hash='bad')
            with self.assertRaises(PermissionError):validate_smoke_review(bad,receipt)
            r=run_live(m,a,out,CounterFixture(),'remaining',review,settings=settings,provider=fake)
            self.assertEqual(r['returned_runs'],56);self.assertEqual(r['budget']['reserved_attempts'],64)
            self.assertEqual(r['budget']['pending_dispatches'],0)

    def test_failure_model_drift_and_unknown_usage_stop_without_retest(self):
        m=manifest();a=auth(m);settings=V3PilotSettings('OFFLINE_FIXTURE',True,max_tokens=4000,max_attempts=1)
        async def invalid(*args):return '{}',dict(resolved_model='deepseek-flash',input_tokens=100,output_tokens=100,total_tokens=200)
        async def drift(*args):
            raw,meta=await fake(*args);meta['resolved_model']='changed-model';return raw,meta
        async def unknown(*args):
            raw,meta=await fake(*args);meta['input_tokens']=None;return raw,meta
        for provider,reason in [(invalid,'failure_requires_review'),(drift,'resolved_model_identity_drift'),(unknown,'usage_or_cost_anomaly')]:
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as td:
                out=Path(td)/'runtime';r=run_live(m,a,out,CounterFixture(),settings=settings,provider=provider)
                self.assertEqual(r['budget']['halted'],reason);self.assertEqual(r['budget']['reserved_attempts'],1)
                self.assertFalse((out/'smoke-receipt.json').exists())

    def test_unknown_send_keeps_global_lease(self):
        async def timeout(*args):raise TimeoutError()
        m=manifest()
        with tempfile.TemporaryDirectory() as td:
            r=run_live(m,auth(m),Path(td)/'runtime',CounterFixture(),settings=V3PilotSettings('OFFLINE_FIXTURE',True,max_tokens=4000,max_attempts=1),provider=timeout)
            self.assertEqual(r['budget']['reserved_attempts'],1);self.assertTrue(r['budget']['active_lease'])
            self.assertEqual(r['budget']['halted'],'usage_or_cost_anomaly')
