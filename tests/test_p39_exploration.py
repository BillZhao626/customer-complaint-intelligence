"""Shared-envelope exploratory allowance, explicit offline provider only."""
import json
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from tests.test_p39_continuity import setup,schema_bad
from tests.test_p39_context_live import fake
from src.application.p39_continuity import run_fixed,reconcile
from src.application.p39_exploration import (build_plan,ExplorationBudget,run_exploration,exploration_runs,verify_plan)
from src.domain.contracts import EmailInput,RunConfigV31
from src.domain.contracts import digest
from src.infrastructure.deepseek import LiveError


class ExplorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.rt,cls.original,cls.settings=setup(cls.root)
        run_fixed(cls.rt,cls.original,cls.settings,fake)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def clone(self,count=6):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);root=Path(td.name)
        with closing(sqlite3.connect(self.original.path)) as source,closing(sqlite3.connect(root/'budget.sqlite3')) as target:source.backup(target)
        b=ExplorationBudget(root/'budget.sqlite3',self.original.counter)
        samples=[r['email']['email_id'] for r in self.rt['candidate']['inputs'][:count]]
        plan=build_plan(self.rt,b,samples,root/'explore')
        b.install_plan(plan)
        return plan,b

    def test_six_calls_include_quality_failures_cumulative71_and_restart_zero(self):
        plan,b=self.clone();calls=[]
        async def provider(msgs,remaining):
            calls.append(msgs);return await (schema_bad if len(calls)%2 else fake)(msgs,remaining)
        result=run_exploration(plan,b,self.settings,provider)
        self.assertEqual(len(calls),6);self.assertEqual(result['accepted'],3);self.assertEqual(result['failed'],3)
        self.assertEqual(b.summary()['shared_requests'],71)
        self.assertEqual(len(reconcile(self.rt,b)),64)
        self.assertEqual(len(exploration_runs(plan,b)),6)
        run_exploration(plan,b,self.settings,provider);self.assertEqual(len(calls),6)
        b.verify_config(RunConfigV31.model_validate(plan['config']))
        with self.assertRaises(PermissionError):b.acquire('seventh',plan['inputs'][0]['input_hash'])
        self.assertEqual(b.summary()['shared_requests'],71)
        for msgs in calls:
            self.assertEqual(set(json.loads(msgs[1][1])),{'email_id','subject','body','input_hash','evidence_catalog'})

    def test_unknown_send_halts_without_consuming_additional_calls(self):
        plan,b=self.clone(2);calls=[]
        async def unknown(msgs,remaining):calls.append(1);raise LiveError('timeout')
        with self.assertRaises(ValueError):run_exploration(plan,b,self.settings,unknown)
        self.assertTrue(b.summary()['active_lease']);self.assertTrue(b.summary()['active_wire_claim'])
        with self.assertRaises(PermissionError):run_exploration(plan,b,self.settings,unknown)
        self.assertEqual(len(calls),1);self.assertEqual(b.summary()['shared_requests'],66)

    def test_model_drift_stops_even_with_schema_bad(self):
        plan,b=self.clone(2);calls=[]
        async def bad(msgs,remaining):
            calls.append(1);raw,meta=await schema_bad(msgs,remaining);meta['resolved_model']='different';return raw,meta
        with self.assertRaises(ValueError):run_exploration(plan,b,self.settings,bad)
        self.assertEqual(len(calls),1);self.assertEqual(b.summary()['halted'],'r3_challenger_engineering_stop')

    def test_allowance_not_available_before_fixed_completion_or_for_seven_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            rt,b,s=setup(td)
            with self.assertRaises(PermissionError):build_plan(rt,b,[],Path(td)/'explore')
        samples=[r['email']['email_id'] for r in self.rt['candidate']['inputs'][:7]]
        with self.assertRaises(ValueError):build_plan(self.rt,self.original,samples,self.root/'bad')

    def test_offline_sdk_request_has_challenger_messages_and_frozen_options(self):
        import asyncio,httpx
        from src.application import p39r3_challenger as prompt
        from src.application.p39_context_live import ContextLiveAnalyzer
        from src.application.p39_experiment import wire_payload
        from src.application.v31_demo import pipeline_probe
        plan,b=self.clone(1);e=EmailInput.model_validate(plan['inputs'][0]['email']);seen=[]
        async def check():
            analyzer=ContextLiveAnalyzer(self.settings,self.rt['candidate'],'B',b.counter)
            analyzer.config=RunConfigV31.model_validate(plan['config']);analyzer.messages=lambda email,repair=False:prompt.messages(email)
            client,transport=analyzer.make_client(10);original=transport._transport
            async def handler(req):
                seen.append(json.loads(req.content))
                return httpx.Response(200,json=dict(id='offline',object='chat.completion',created=0,model='deepseek-flash',
                    choices=[dict(index=0,message=dict(role='assistant',content=pipeline_probe(e).model_dump_json()),finish_reason='stop')],
                    usage=dict(prompt_tokens=100,completion_tokens=200,total_tokens=300,prompt_cache_hit_tokens=60,prompt_cache_miss_tokens=40)))
            transport._transport=httpx.MockTransport(handler);analyzer.make_client=lambda timeout:(client,transport)
            try:await analyzer.request(e,False,30)
            finally:await original.aclose()
        asyncio.run(check());self.assertEqual(seen,[wire_payload(prompt.messages(e))])

    def test_rehashed_plan_or_wrong_champion_binding_sends_zero(self):
        plan,b=self.clone(1);calls=[]
        async def provider(msgs,remaining):calls.append(1);return await fake(msgs,remaining)
        changed=copy.deepcopy(plan);changed['champion_runs']=['different-champion-run']
        changed.pop('plan_hash');changed['plan_hash']=digest(changed)
        with self.assertRaises(PermissionError):run_exploration(changed,b,self.settings,provider)
        with self.assertRaises(PermissionError):b.install_plan(changed)
        self.assertEqual(calls,[]);self.assertEqual(b.summary()['shared_requests'],65)


if __name__=='__main__':unittest.main()
