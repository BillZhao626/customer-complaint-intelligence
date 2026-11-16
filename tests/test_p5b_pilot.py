from tests.archive_support import requires_archive
"""Economic and input provenance tests: all temporary, SDK MockTransport only."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import httpx
from src.evaluation.p5b_pilot import (Budget,Analyzer,build_manifest,verify_manifest,messages,
    second_email,read,ROOT,write_new)
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.domain.contracts import EmailInput


@requires_archive('docs/p5q/HUMAN_CALIBRATION_PACK_v1.json')
class P5BPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p5b_test_');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.email=EmailInput(email_id='fixture',subject='offline',body='测试合成来信')
        self.settings=V3PilotSettings(api_key='offline-test-not-key',enabled=True,max_tokens=4000,max_attempts=1)

    def test_manifest_exact_fixed_16_18(self):
        m=build_manifest();verify_manifest(m)
        self.assertEqual(len(m['schedule']),18)
        self.assertEqual(len(m['cases']),16)
        self.assertFalse(any('customer_reply' in c for c in m['cases']))

    def test_manifest_tamper_rejected(self):
        m=build_manifest();m['cases'][0]['turns'][0]['body']='替换样本'
        with self.assertRaisesRegex(ValueError,'drift'):verify_manifest(m)

    def test_real_history_substitution(self):
        c=build_manifest()['cases'][-1]
        e,history=second_email(c,'本轮实际模型首回复')
        self.assertIn('本轮实际模型首回复',e.body)
        self.assertNotIn('未核实前不能当作已确认预约',e.body)
        self.assertEqual(history[1]['source'],'REAL_MODEL_UNSENT_DEV')

    def test_missing_history_not_offline_fallback(self):
        with self.assertRaises(ValueError):second_email(build_manifest()['cases'][-1],None)

    def budget(self):
        b=Budget.create(self.path/'budget.sqlite3',[],dict(pricing={}))
        a=Analyzer(self.settings,self.path/'evidence')
        b.bind(self.email,a.config)
        return b,a

    def test_exclusive_ledger_creation(self):
        self.budget()
        with self.assertRaises(FileExistsError):Budget.create(self.path/'budget.sqlite3',[],{})

    def test_reserve_counts_and_no_retry(self):
        b,a=self.budget();b.acquire('run',self.email.input_hash)
        cost=b.reserve('run',1,self.email.input_hash,messages(self.email),4000)
        self.assertGreater(cost,0)
        with self.assertRaises(LiveError):b.reserve('run',2,self.email.input_hash,messages(self.email),4000)

    def test_unknown_usage_halts_next_request(self):
        b,a=self.budget()
        self.assertIsNone(b.estimate_cost(dict(input_tokens=100,output_tokens=None,total_tokens=None)))
        with self.assertRaises(LiveError):b.bind(self.email,a.config)

    def test_budget_five_cny_guard(self):
        b,a=self.budget();b.acquire('run',self.email.input_hash)
        with b.connection() as c:
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',('earlier',1,'x',4.999,'fixture'))
        with self.assertRaises(LiveError):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)

    def test_turn_18_guard(self):
        b,a=self.budget();b.acquire('run',self.email.input_hash)
        with b.connection() as c:
            for n in range(18):c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(str(n),1,'x',0.001,'fixture'))
        with self.assertRaises(LiveError):b.reserve('run',1,self.email.input_hash,messages(self.email),4000)

    def test_sdk_full_raw_and_wire_capture(self):
        seen=[]
        def handle(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json=dict(id='provider-fixture',object='chat.completion',created=1,model='deepseek-flash',
                choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content='{"suggested_reply":"fixture"}'))],
                usage=dict(prompt_tokens=100,completion_tokens=10,total_tokens=110)))
        a=Analyzer(self.settings,self.path/'evidence',mock_http_transport=httpx.MockTransport(handle))
        raw,meta=asyncio.run(a.request(self.email,False,90))
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0]['max_tokens'],4000)
        self.assertEqual(meta['input_tokens'],100)
        self.assertEqual(read(self.path/'evidence/wire-request.json')['messages'][0]['content'],messages(self.email)[0][1])
        self.assertTrue((self.path/'evidence/provider-response.txt').is_file())

    def test_accepted_originals_not_rewritten(self):
        old=read(ROOT/'docs/p5q/owner_accepted_references_v1.json')
        new=read(ROOT/'docs/p5q/owner_directed_references_v2_PROPOSED.json')
        self.assertEqual(old['anchors'],new['preserved_anchors'])
        self.assertTrue(all(a['identity']=='OWNER_DIRECTED_DEV_ANCHOR_CANDIDATE' for a in new['new_candidates']))

    def test_service_sdk_repository_idempotency_and_handoff(self):
        from src.application.p5_quality import example
        from src.evaluation.p5b_pilot import Service
        from src.infrastructure.repository import Repository
        from src.application.product_workflow import ProductStore
        email,data=example('P5A-F10-M01-2')
        calls=[]
        def handle(request):
            calls.append(1)
            return httpx.Response(200,json=dict(id='fixture',object='chat.completion',created=1,model='deepseek-flash',
                choices=[dict(index=0,finish_reason='stop',message=dict(role='assistant',content=json.dumps(data,ensure_ascii=False)))],
                usage=dict(prompt_tokens=100,completion_tokens=100,total_tokens=200)))
        a=Analyzer(self.settings,self.path/'evidence',mock_http_transport=httpx.MockTransport(handle))
        b=Budget.create(self.path/'budget.sqlite3',[],dict(pricing={'price_source':'offline-fixture','prices_verified_at':'fixture','prices':{}}))
        b.bind(email,a.config)
        service=Service(Repository(self.path/'runs.sqlite3'),a,b)
        run=service.analyze(email)
        self.assertEqual(run.status,'succeeded',run.model_dump())
        self.assertEqual(service.analyze(email).run_id,run.run_id)
        self.assertEqual(len(calls),1)
        store=ProductStore(self.path/'product.sqlite3')
        case=store.create(run,origin='new_analysis')
        case=store.act(case['case_id'],'request_handoff',expected_revision=case['revision'],actor='fixture',
            actor_type='demo_test',reason='明确人工请求',operation_id='fixture-handoff')
        self.assertEqual(sum(e['action']=='request_handoff' for e in case['events']),1)
        self.assertFalse(any(e['action']=='take_over' for e in case['events']))


if __name__=='__main__':unittest.main()
