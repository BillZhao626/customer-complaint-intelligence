"""Bounded P5-B2 replay and sequential first-generation experiment."""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from src.evaluation.p5b_pilot import ROOT, read, write_new, now, second_email
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import DeepSeekAnalyzer, LiveError
from src.domain.contracts import EmailInput, RunConfigV32, digest
from src.domain.analysis_v32 import PROFILE, validate, wire_schema
from src.application.p5b2_prompt import system, messages, VERSION
from src.application.p39_experiment import wire_bytes, wire_payload, dependencies
from src.application.live_execution import strict_json
from src.application.analysis_service import AnalysisService

LOCAL=ROOT/'.local/p5b2-20261029-v1'
DOC=ROOT/'docs/p5b2'
BASE=ROOT/'docs/p5b_dev_pilot'
EXPLORATORY={'CAL-03','CAL-05','CAL-08','CAL-10','CAL-11','CAL-12'}
SOURCE_PATHS=['src/domain/analysis_v32.py','src/domain/contracts.py','src/domain/versioned_analysis.py',
    'src/application/urgency_context_v2.py','src/application/p5b2_prompt.py','src/application/analysis_service.py',
    'src/infrastructure/repository.py','src/application/product_workflow.py','src/evaluation/p5b2.py',
    'src/application/live_execution.py','src/application/reply_review.py','src/application/product_quality.py',
    'src/infrastructure/deepseek.py','src/application/v31_prompt.py','src/application/p39_v2.py',
    'scripts/p5b2.py']

def hashes(): return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCE_PATHS}

def replay():
    from src.domain.analysis_v31_context import ContextAnalysisV31
    from src.application.reply_review import check
    rows=[]
    for s in read(BASE/'pilot_manifest_16.json')['schedule']:
        r=read(BASE/'evidence/turns'/s['turn_id']/'run.json')
        email=EmailInput.model_validate(r['email']); raw=r['attempts'][0]['raw_output']
        provider=read(BASE/'evidence/turns'/s['turn_id']/'provider-response.txt')
        if provider['choices'][0]['message']['content']!=raw: raise ValueError('Baseline raw mismatch')
        data=strict_json(raw); out=dict(**s,raw_sha256=sha256(raw.encode()).hexdigest(),input_hash=email.input_hash)
        for arm in ('old','candidate'):
            try:
                if arm=='old':
                    value=ContextAnalysisV31.model_validate(data).validate_input(email);check(value)
                    changes=[]
                else: value,_,changes,_=validate(data,email,legacy=True)
                out[arm+'_accepted']=True;out[arm+'_reason']=None;out[arm+'_changes']=changes
            except ValueError as exc:
                out[arm+'_accepted']=False;out[arm+'_reason']=str(exc)
        if out['old_accepted']!=(r['status']=='succeeded'): raise ValueError('Baseline outcome drift')
        rows.append(out)
    write_new(DOC/'OFFLINE_REPLAY.json',dict(identity='OFFLINE_NO_PROVIDER_CALL',rows=rows))
    return dict(old=sum(r['old_accepted'] for r in rows),candidate=sum(r['candidate_accepted'] for r in rows),n=len(rows))

class Budget(PilotBudget):
    def pricing(self):
        with self.connection() as c:return json.loads(c.execute('SELECT manifest FROM policy').fetchone()[0])['pricing']
    def bind(self,email,config,stage):
        self.expected=email;self.config=config;self.stage=stage
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            allowed,halted=c.execute('SELECT allowed,halted FROM policy').fetchone()
            if halted or c.execute('SELECT 1 FROM lease').fetchone(): raise LiveError('interrupted_or_unknown')
            a=set(json.loads(allowed));a.add(email.input_hash)
            c.execute('UPDATE policy SET allowed=?',(json.dumps(sorted(a)),))
    def verify_config(self,config):
        if config!=self.config:raise LiveError('configuration_error')
    def reserve(self,run_id,attempt_no,input_hash,msgs,max_tokens):
        if attempt_no!=1 or max_tokens!=4000 or input_hash!=self.expected.input_hash or msgs!=messages(self.expected):raise LiveError('configuration_error')
        size=len(wire_bytes(msgs))+1024
        if size>100000:raise LiveError('configuration_error')
        cost=(size*2+max_tokens*8)/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            n,total=c.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            # Stage is durably recorded by run id; no implicit retries or extra generations.
            count=c.execute('SELECT COUNT(*) FROM stage_reservations WHERE stage=?',(self.stage,)).fetchone()[0]
            halted=c.execute('SELECT halted FROM policy').fetchone()[0]
            if halted or c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or n>=40 or total+cost>5 or count>=({'explore':6,'formal':18}[self.stage]):raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,cost,now()))
            c.execute('INSERT INTO stage_reservations VALUES(?,?)',(run_id,self.stage))
        return cost
    def estimate_cost(self,meta):
        i,o,t=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v)is not int or v<0 for v in (i,o,t)) or i+o!=t or o>4000 or i>len(wire_bytes(messages(self.expected)))+1024:
            self.halt('UNKNOWN_BILLING');return None
        return (i*2+o*8)/1e6

class Analyzer(DeepSeekAnalyzer):
    def __init__(self,settings,evidence,*,mock_http_transport=None):
        super().__init__(settings,prompt_profile='multi-issue-v31-B',mock_http_transport=mock_http_transport)
        self.evidence=Path(evidence);self.messages=lambda email,repair=False:messages(email)
        params=dict(self.config.parameters,validation_profile=PROFILE,knowledge='K0',experiment='p5b2')
        self.config=RunConfigV32(**dict(self.config.model_dump(),schema_version='analysis-v3.2',
            prompt_version=VERSION,prompt_hash=sha256(system().encode()).hexdigest(),parameters=params))
    async def request(self,email,repair,remaining):
        from langsmith import tracing_context
        self.settings.validate(); client,transport=self.make_client(min(self.settings.http_timeout,remaining));observed={}
        async def audit(request):
            body=await request.aread()
            if str(request.url)!='https://api.deepseek.com/chat/completions' or request.method!='POST' or json.loads(body)!=wire_payload(messages(email)):raise LiveError('configuration_error')
            write_new(self.evidence/'wire-request.json',json.loads(body))
            observed.update(payload_sha256=sha256(body).hexdigest(),payload_bytes=len(body),dispatch_at=now())
        async def capture(response):
            body=await response.aread()
            write_new(self.evidence/'provider-response.txt',body.decode())
            write_new(self.evidence/'provider-http.json',dict(status=response.status_code,received_at=now(),body_sha256=sha256(body).hexdigest(),headers={k:v for k,v in response.headers.items() if k in ('date','x-request-id','x-ds-request-id')}))
        transport.event_hooks.update(request=[audit],response=[capture])
        try:
            with tracing_context(enabled=False):response=await asyncio.wait_for(client.ainvoke(messages(email),config={'callbacks':[]}),timeout=remaining)
            meta=response.response_metadata or {};usage=response.usage_metadata or {}
            write_new(self.evidence/'langchain-response.json',response.model_dump(mode='json'))
            return response.content,dict(resolved_model=meta.get('model_name'),model_snapshot='unavailable',
                provider_response_id=meta.get('id'),response_id=response.id,finish_reason=meta.get('finish_reason'),
                input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),total_tokens=usage.get('total_tokens'),
                usage=usage,token_usage=meta.get('token_usage'),**observed)
        finally:await transport.aclose()

def freeze(stage):
    m=read(BASE/'pilot_manifest_16.json')
    # Verify the inherited inputs without forcing the historical source code to match new code.
    for c in m['cases']:
        if [sha256(t['body'].encode()).hexdigest() for t in c['turns']]!=c['input_text_sha256']:raise ValueError('Input drift')
    snap=dict(stage=stage,created_at=now(),source_hashes=hashes(),dependencies=dependencies(),
        baseline_manifest_sha256=sha256((BASE/'pilot_manifest_16.json').read_bytes()).hexdigest(),
        prompt_sha256=sha256(system().encode()).hexdigest(),schema_hash=digest(wire_schema()),
        parameters=m['parameters'],limits=dict(provider_calls=40,cny=5,explore=6,formal=18,concurrency=1),
        offline_verified=True,human_gold=None,knowledge='K0')
    write_new(DOC/(stage+'-freeze.json'),snap)
    write_new(DOC/(stage+'-system-prompt.txt'),system())
    write_new(DOC/(stage+'-wire-schema.json'),wire_schema())
    return snap

def run(stage,settings):
    frozen=read(DOC/(stage+'-freeze.json'))
    if frozen['source_hashes']!=hashes() or frozen['dependencies']!=dependencies():raise ValueError('Frozen code/dependencies drift')
    auth=read(LOCAL/'authorization.json')
    if (datetime.now(timezone.utc)-datetime.fromisoformat(auth['pricing']['prices_verified_at'])).total_seconds()>=86400:raise ValueError('Price receipt expired')
    if not (settings.model=='deepseek-flash' and settings.max_attempts==1 and settings.max_tokens==4000):raise ValueError('Settings drift')
    write_new(LOCAL/stage/'run-start.json',dict(at=now(),freeze_hash=digest(frozen)))
    budget=Budget(LOCAL/'budget.sqlite3')
    from src.infrastructure.repository import Repository
    repo=Repository(LOCAL/stage/'runs.sqlite3')
    rows=[]
    for case in read(BASE/'pilot_manifest_16.json')['cases']:
        if stage=='explore' and case['calibration_id'] not in EXPLORATORY:continue
        prior=None
        for n,t in enumerate(case['turns'],1):
            tid=case['source_id'] if len(case['turns'])==1 else case['source_id']+'-T'+str(n)
            if n==2 and not prior:
                rows.append(dict(turn_id=tid,status='DEPENDENCY_FAILED'));continue
            email,history=second_email(case,prior) if n==2 else (EmailInput(email_id=tid,**t),[])
            ev=LOCAL/stage/'turns'/tid;a=Analyzer(settings,ev)
            a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,stage=stage,freeze_hash=digest(frozen))))
            write_new(ev/'frozen-input.json',dict(email=email.model_dump(),input_hash=email.input_hash,current_customer=t,history=history,config=a.config.model_dump(),messages=messages(email)))
            budget.bind(email,a.config,stage)
            r=AnalysisService(repo,a,budget=budget).analyze(email)
            write_new(ev/'run.json',r.model_dump(mode='json'))
            attempt=r.attempts[-1] if r.attempts else None
            try:prior=strict_json(attempt.raw_output).get('suggested_reply')
            except (ValueError,AttributeError,TypeError):prior=None
            meta=attempt.metadata if attempt else {}
            row=dict(turn_id=tid,calibration_id=case['calibration_id'],run_id=r.run_id,status=r.status,reply=prior,
                parse_status=attempt.parse_status if attempt else 'not_run',contract_status=attempt.contract_status if attempt else 'not_run',
                provider=meta,input_hash=email.input_hash,history=history,human_scores=None)
            rows.append(row);write_new(ev/'receipt.json',row)
            print(json.dumps(dict(stage=stage,case=case['calibration_id'],turn=tid,status=r.status,tokens=meta.get('total_tokens')),ensure_ascii=False),flush=True)
            if meta.get('dispatch')!='response_received' or meta.get('cost_cny') is None or meta.get('resolved_model')!='deepseek-flash':
                budget.halt('UNKNOWN_BILLING_OR_EXECUTION');write_new(LOCAL/stage/'results.json',rows);return budget.summary()
    if stage=='formal':budget.halt('planned_generation_complete')
    write_new(LOCAL/stage/'results.json',rows)
    return budget.summary()
