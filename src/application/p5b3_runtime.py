"""Explicit P5-B3 experiment authorization; shared serial budget for UI and CLI."""
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock

from src.evaluation.p5b2 import Analyzer as B2Analyzer, Budget as B2Budget
from src.evaluation.p5b_pilot import now, read, write_new
from src.application.p39_experiment import wire_bytes, wire_payload
from src.application.analysis_service import AnalysisService
from src.domain.contracts import EmailInput, digest
from src.infrastructure.repository import Repository
from src.infrastructure.deepseek import LiveError

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT/'.local/p5b3-20261029-v1'
LOCK = Lock()


class Budget(B2Budget):
    def bind(self, email, config, stage, msgs=None):
        super().bind(email, config, stage)
        self.msgs = msgs

    def reserve(self, run_id, attempt_no, input_hash, msgs, max_tokens):
        if attempt_no != 1 or max_tokens != 4000 or input_hash != self.expected.input_hash or msgs != self.msgs:
            raise LiveError('configuration_error')
        size = len(wire_bytes(msgs))+1024
        if size > 100000: raise LiveError('configuration_error')
        cost = (size*2+max_tokens*8)/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            n = c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
            # Settled upper costs plus all unresolved reservations, not assumed free failures.
            spent = c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
            halted = c.execute('SELECT halted FROM policy').fetchone()[0]
            if halted or c.execute('SELECT run_id FROM lease').fetchone() != (run_id,) or n >= 120 or spent+cost > 5:
                raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)', (run_id,1,input_hash,cost,now()))
            c.execute('INSERT INTO stage_reservations VALUES(?,?)',(run_id,self.stage))
        return cost

    def estimate_cost(self, meta):
        i,o,t = [meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v) is not int or v < 0 for v in (i,o,t)) or i+o != t or o > 4000 or i > len(wire_bytes(self.msgs))+1024:
            self.halt('UNKNOWN_BILLING'); return None
        cost = (i*2+o*8)/1e6
        with self.connection() as c:
            run_id = c.execute('SELECT run_id FROM lease').fetchone()[0]
            c.execute('INSERT INTO settlements VALUES(?,?)',(run_id,cost))
        return cost


class Analyzer(B2Analyzer):
    def __init__(self, settings, evidence, *, candidate=False, **kwargs):
        super().__init__(settings,evidence,**kwargs)
        if candidate:
            from src.application.p5b3_prompt import messages, system, VERSION
            self.messages = lambda email, repair=False: messages(email)
            self.config = self.config.model_copy(update=dict(prompt_version=VERSION,prompt_hash=sha256(system().encode()).hexdigest(),parameters=dict(self.config.parameters,experiment='p5b3')))

    async def request(self, email, repair, remaining):
        from langsmith import tracing_context
        self.settings.validate()
        client, transport = self.make_client(min(self.settings.http_timeout,remaining))
        msgs = self.messages(email); observed = {}
        async def audit(request):
            body = await request.aread()
            if str(request.url) != 'https://api.deepseek.com/chat/completions' or json.loads(body) != wire_payload(msgs):
                raise LiveError('configuration_error')
            write_new(self.evidence/'wire-request.json',json.loads(body))
            observed.update(payload_sha256=sha256(body).hexdigest(),dispatch_at=now())
        async def capture(response):
            body = await response.aread()
            write_new(self.evidence/'provider-response.txt',body.decode())
            write_new(self.evidence/'provider-http.json',dict(status=response.status_code,received_at=now(),body_sha256=sha256(body).hexdigest(),headers={k:v for k,v in response.headers.items() if k in ('date','x-request-id','x-ds-request-id')}))
        transport.event_hooks.update(request=[audit],response=[capture])
        try:
            with tracing_context(enabled=False):
                response = await asyncio.wait_for(client.ainvoke(msgs,config={'callbacks':[]}),timeout=remaining)
            meta,usage = response.response_metadata or {}, response.usage_metadata or {}
            write_new(self.evidence/'langchain-response.json',response.model_dump(mode='json'))
            return response.content,dict(resolved_model=meta.get('model_name'),model_snapshot='unavailable',provider_response_id=meta.get('id'),response_id=response.id,finish_reason=meta.get('finish_reason'),input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),total_tokens=usage.get('total_tokens'),usage=usage,token_usage=meta.get('token_usage'),**observed)
        finally: await transport.aclose()


def settings():
    from src.infrastructure.v3_live_settings import V3PilotSettings
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    return replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000)


def generate(email, *, stage, candidate=False, store=None, extra_runtime=None, context_hash=None):
    """No retry on unknown dispatch. Same content/config reopens the persisted run."""
    if not LOCK.acquire(blocking=False): raise ValueError('已有模型请求进行中')
    try:
        email = EmailInput.model_validate(email)
        auth = read(LOCAL/'authorization.json')
        if auth['limits'] != dict(provider_calls=120,cny=5,concurrency=1,retries=0): raise ValueError('Authorization drift')
        ev = LOCAL/stage/email.input_hash
        a = Analyzer(settings(),ev,candidate=candidate)
        runtime={}
        if candidate:
            if store is None: raise ValueError('Action store required')
            from src.application.p5b3_actions import journal
            known=(extra_runtime or {}).get('scoped_facts',[])
            ctx,tasks=journal(store).prepare(email,has_known_answer=bool(known))
            runtime=dict(customer_context=ctx.model_dump(),action_results=tasks,**(extra_runtime or {}))
            from src.application.p5b3_prompt import messages
            a.messages=lambda e,repair=False:messages(e,runtime)
        a.config = a.config.model_copy(update=dict(parameters=dict(a.config.parameters,experiment='p5b3',stage=stage)))
        if candidate:
            a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,runtime_context_hash=digest(runtime))))
        if context_hash:
            a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,context_hash=context_hash)))
        repo = Repository(LOCAL/stage/'runs.sqlite3')
        budget = Budget(LOCAL/'budget.sqlite3')
        # A persisted unknown/prepared request may never be blindly redispatched.
        if (ev/'frozen-input.json').exists():
            if not (ev/'run.json').exists(): raise ValueError('请求结果未知，请检查运行轨迹，禁止重复派发')
            from src.domain.contracts import AnalysisRun
            run = AnalysisRun.model_validate(read(ev/'run.json'))
        else:
            write_new(ev/'frozen-input.json',dict(email=email.model_dump(),config=a.config.model_dump(),messages=a.messages(email),trusted_runtime=runtime,at=now()))
            budget.bind(email,a.config,stage,a.messages(email))
            run = AnalysisService(repo,a,budget=budget).analyze(email)
            write_new(ev/'run.json',run.model_dump(mode='json'))
        if store is not None:
            case = store.create(run,'P5-B3 / '+stage,origin='new_analysis')
            if candidate:
                from src.application.p5b3_actions import execute
                execute(store,case['case_id'])
            return store.get(case['case_id'])
        return run
    finally: LOCK.release()
