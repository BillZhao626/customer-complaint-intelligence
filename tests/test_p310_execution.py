"""Fake-only budget, fixed-plan persistence and restart verification."""
from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from tests.test_urgency_context import fixture
from src.application.p310_experiment import make_plan,run_plan,ResearchRepository,ReadOnlyResearchRepository,ByteCounter,messages_for
from src.infrastructure.p310_budget import ResearchBudget,CANONICAL
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.application.p39_experiment import wire_bytes
from src.domain.contracts import EmailInput,RunConfigV31,digest


def authorization():
    evidence='offline fixture explicit test authorization, no real provider'
    return dict(status='researcher_explicitly_authorized',requests=180,cny=30,model='deepseek-flash',offline_fixture=True,
                user_approval_evidence=evidence,user_approval_sha256=sha256(evidence.encode()).hexdigest(),
                price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',prices={'input_cny_per_million':2,'output_cny_per_million':8},
                model_availability_verified=True,prior_p39_ledger_sha256='fixture',prices_verified_at=datetime.now(timezone.utc).isoformat())


def inputs(count=2):
    return [dict(email=EmailInput(email_id='fixture-'+str(n),subject='Offline inquiry '+str(n),body='Can this model '+str(n)+' use a cable?').model_dump(),source='explicit offline test fixture') for n in range(count)]


def fake_provider(outputs=None,anomaly=None):
    calls=[]
    async def provider(msgs,remaining):
        data=json.loads(msgs[1][1]);e,d=fixture(data['body'],'low','other')
        raw=json.dumps(d);index=len(calls)
        if outputs is not None and index<len(outputs) and outputs[index] is not None:raw=outputs[index]
        calls.append(data['email_id']);payload=wire_bytes(msgs)
        m=dict(resolved_model='deepseek-flash',input_tokens=100,output_tokens=100,total_tokens=200,
               cache_hit_tokens=0,cache_miss_tokens=100,actual_payload_sha256=sha256(payload).hexdigest(),actual_payload_bytes=len(payload),finish_reason='stop')
        if anomaly:m.update(anomaly)
        return raw,m
    return calls,provider


class ResearchExecutionTests(unittest.TestCase):
    def test_missing_authorization_has_no_filesystem_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'new'/'budget.sqlite3'
            with self.assertRaises(PermissionError):ResearchBudget.create(target,None,fixture=True)
            self.assertFalse(target.parent.exists())

    def test_no_production_allowance_cloning_or_fixture_confusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):ResearchBudget.create(Path(tmp)/'clone.sqlite3',authorization(),fixture=False)
            with self.assertRaises(PermissionError):ResearchBudget.create(CANONICAL,authorization(),fixture=True)

    def test_exclusive_create_and_root_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'budget.sqlite3';b=ResearchBudget.create(path,authorization(),True)
            with self.assertRaises(FileExistsError):ResearchBudget.create(path,authorization(),True)
            with b.connection() as c:
                m=json.loads(c.execute('SELECT manifest FROM policy').fetchone()[0]);m['authorization']['requests']=181
                c.execute('UPDATE policy SET manifest=?',(json.dumps(m),))
            with self.assertRaises(PermissionError):ResearchBudget(path,True)

    def test_quality_failure_continues_and_restart_never_resends(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            path=Path(tmp);b=ResearchBudget.create(path/'budget.sqlite3',authorization(),True);plan=make_plan(inputs())
            calls,provider=fake_provider(['invalid JSON',None]);settings=V3PilotSettings(api_key='offline-only',enabled=True,max_tokens=4000,max_attempts=1)
            result=run_plan(plan,b,settings,path/'run',provider)
            self.assertEqual(len(calls),2);self.assertEqual(result['budget']['reserved_attempts'],2)
            self.assertFalse(result['budget']['active_lease']);self.assertFalse(result['budget']['pending_dispatches'])
            saved=ReadOnlyResearchRepository(path/'run'/'runs.sqlite3').list_runs()
            self.assertEqual(sorted(r.status for r in saved),['failed','succeeded'])
            self.assertTrue(all(len(r.attempts)==1 for r in saved))
            run_plan(plan,ResearchBudget(path/'budget.sqlite3',True),settings,path/'run',provider)
            self.assertEqual(len(calls),2)
            self.assertTrue(all(r.metadata.get('application_actions_executed',[])==[] for r in saved))

    def test_usage_and_model_anomaly_stop_before_second_request(self):
        for anomaly in ({'total_tokens':999},{'resolved_model':'changed-model'},{'cache_miss_tokens':None},{'actual_payload_sha256':'bad'}):
            with self.subTest(anomaly=anomaly),tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
                path=Path(tmp);b=ResearchBudget.create(path/'budget.sqlite3',authorization(),True);plan=make_plan(inputs())
                calls,provider=fake_provider(anomaly=anomaly)
                settings=V3PilotSettings(api_key='offline-only',enabled=True,max_tokens=4000,max_attempts=1)
                with self.assertRaises(ValueError):run_plan(plan,b,settings,path/'run',provider)
                self.assertEqual(len(calls),1);self.assertTrue(b.summary()['halted']);self.assertTrue(b.summary()['active_lease'])
                with self.assertRaises(PermissionError):run_plan(plan,b,settings,path/'run',provider)
                self.assertEqual(len(calls),1)

    def test_fixed_payload_schedule_and_attempt_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=ResearchBudget.create(Path(tmp)/'budget.sqlite3',authorization(),True);plan=make_plan(inputs());b.register_plan(plan)
            cfg=RunConfigV31.model_validate(plan['configs']['challenger']);b.verify_config(cfg)
            email=EmailInput.model_validate(plan['inputs'][0]['email']);other=EmailInput.model_validate(plan['inputs'][1]['email'])
            with self.assertRaises(PermissionError):b.acquire('bad',other.input_hash)
            b.acquire('run',email.input_hash)
            with self.assertRaises(PermissionError):b.reserve('run',2,email.input_hash,messages_for(email,'challenger'),4000)
            with self.assertRaises(PermissionError):b.reserve('run',1,email.input_hash,messages_for(other,'challenger'),4000)
            self.assertEqual(b.summary()['reserved_attempts'],0)
            b.reserve('run',1,email.input_hash,messages_for(email,'challenger'),4000)
            b.completed('run',1);b.release('run')
            self.assertTrue(b.summary()['active_lease'])
            with self.assertRaises(PermissionError):b.acquire('new',other.input_hash)

    def test_shared_request_and_currency_hard_caps(self):
        for count,cost in ((180,0),(1,30)):
            with self.subTest(count=count,cost=cost),tempfile.TemporaryDirectory() as tmp:
                b=ResearchBudget.create(Path(tmp)/'budget.sqlite3',authorization(),True);plan=make_plan(inputs());b.register_plan(plan)
                b.verify_config(RunConfigV31.model_validate(plan['configs']['challenger']))
                e=EmailInput.model_validate(plan['inputs'][0]['email']);b.acquire('run',e.input_hash)
                with b.connection() as c:
                    for n in range(count):c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(str(n),1,e.input_hash,cost/count,'fixture'))
                with self.assertRaises(PermissionError):b.reserve('run',1,e.input_hash,messages_for(e,'challenger'),4000)
                self.assertEqual(b.summary()['reserved_attempts'],count)

    def test_fixture_never_initializes_real_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);b=ResearchBudget.create(path/'budget.sqlite3',authorization(),True)
            with self.assertRaises(PermissionError):run_plan(make_plan(inputs()),b,V3PilotSettings(api_key='offline',enabled=True,max_tokens=4000,max_attempts=1),path/'run')
            self.assertFalse((path/'run').exists())

    def test_new40_rejects_wrong_count_and_iteration_after_exposure(self):
        with self.assertRaises(ValueError):make_plan(inputs(39),'new40')
        with tempfile.TemporaryDirectory() as tmp:
            b=ResearchBudget.create(Path(tmp)/'budget.sqlite3',authorization(),True)
            b.register_plan(make_plan(inputs()))
            evaluation=make_plan(inputs(40),'new40');b.register_plan(evaluation)
            self.assertEqual(len(evaluation['schedule']),80)
            changed=make_plan(inputs(3))
            with self.assertRaises(PermissionError):b.register_plan(changed)
