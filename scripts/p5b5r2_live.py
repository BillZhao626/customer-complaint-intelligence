"""Explicit R2 authorization: independent CNY10 / 300 provider requests, serial.

Every SDK invocation is pre-reserved. UNKNOWN locks the ledger; no retry endpoint.
"""
import argparse
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from threading import Lock
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b5 import read,write_new,hashfile
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.application.p5b3_runtime import Analyzer
from src.application.p39_experiment import wire_bytes,dependencies
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.domain.contracts import EmailInput,AnalysisRun,digest
from src.application.p5b5r2_pipeline import ConversationState,ConversationStore,ActionStore,LocalFacts,messages
from datetime import datetime,timezone

def now():return datetime.now(timezone.utc).isoformat()

def fixture_facts(email):
    if not any(x in email.body for x in ('USB','接口','C200')):return []
    return [dict(input_hash=email.input_hash,kind='knowledge_lookup',authority='PUBLIC_GENERAL_KNOWLEDGE',
        source_url='https://www.usb.org/usb-charger-pd',version='accessed-20261030',observed_at='2026-10-30',
        quote='USB has evolved from a data interface capable of supplying limited power',
        conclusion='USB can carry data and power depending on device design. This does not verify C200 webcam support.')]

LOCAL=ROOT/'.local/p5b5r2';LOCK=Lock()
LIMITS=dict(cny=10,requests=300,concurrency=1,retries=0)
CORE=['scripts/p5b5r2_live.py','src/application/p5b5r2_pipeline.py','src/application/p5b5_state_v3.py',
 'src/application/p5b5_state_v2.py','src/application/p5b5_pipeline.py','src/application/p5b2_prompt.py',
 'src/domain/analysis_v32.py','src/application/p5b3_runtime.py','src/application/live_execution.py',
 'src/application/analysis_service.py','src/infrastructure/deepseek.py','scripts/p5b5_e3.py','scripts/p5b5_e4.py']

class Budget(PilotBudget):
    def pricing(self):return read(LOCAL/'authorization.json')['pricing']
    def bind(self,email,config,msgs,stage):
        self.expected=email;self.config=config;self.msgs=msgs;self.stage=stage
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            manifest,allowed,halted=c.execute('SELECT manifest,allowed,halted FROM policy').fetchone()
            if read(LOCAL/'authorization.json')!=json.loads(manifest) or halted or c.execute('SELECT 1 FROM lease').fetchone():raise LiveError('interrupted_or_unknown')
            values=set(json.loads(allowed));values.add(email.input_hash)
            c.execute('UPDATE policy SET allowed=?',(json.dumps(sorted(values)),))
    def verify_config(self,config):
        if config!=self.config or read(LOCAL/'authorization.json')['limits']!=LIMITS:raise LiveError('configuration_error')
        if config.model_id!='deepseek-flash':raise LiveError('configuration_error')
    def reserve(self,run_id,attempt_no,input_hash,messages,max_tokens):
        if attempt_no!=1 or max_tokens!=4000 or input_hash!=self.expected.input_hash or messages!=self.msgs:raise LiveError('configuration_error')
        size=len(wire_bytes(messages))+1024
        if size>100000:raise LiveError('configuration_error')
        bound=(size*2+max_tokens*8)/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            n=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
            total=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
            halted=c.execute('SELECT halted FROM policy').fetchone()[0]
            allowed=json.loads(c.execute('SELECT allowed FROM policy').fetchone()[0])
            if halted or c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or n>=300 or total+bound>10 or input_hash not in allowed:raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,bound,now()))
            c.execute('INSERT INTO precalls VALUES(?,?,?,?,?,?)',(run_id,self.stage,n,total,bound,now()))
        return bound
    def estimate_cost(self,meta):
        i,o,t=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v)is not int or v<0 for v in (i,o,t)) or i+o!=t or o>4000 or i>len(wire_bytes(self.msgs))+1024:
            self.halt('UNKNOWN_BILLING');return None
        upper=(i*2+o*8)/1e6
        with self.connection() as c:
            run_id=c.execute('SELECT run_id FROM lease').fetchone()[0]
            c.execute('INSERT INTO settlements VALUES(?,?)',(run_id,upper))
        return upper

def init():
    a=dict(identity='P5-B5-R2-OWNER-CURRENT-CHAT-20261030',authorized_at=now(),limits=LIMITS,
      authorization_text='用户授权独立人民币10元、底层总300次（生成/对照/Judge），逐次预检；合成或授权实验输入；禁止UNKNOWN重发和外部业务动作。',
      pricing=dict(price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',prices_verified_at='2026-10-30',prices=dict(input_peak_miss_cny_per_million=2,output_peak_cny_per_million=8,input_peak_hit_cny_per_million=.04),actual_bill='UNKNOWN'),
      provider='deepseek-flash',documented_version='DeepSeek-V4.1-Flash-1017',weights_snapshot='unavailable',dependencies=dependencies(),
      privacy='Only synthetic development and newly authored synthetic evaluation scenarios; no external business actions; no traces',
      preregistration=dict(champion='B2',promotion='Requires calibrated semantics + human subjective approval + independent evidence; engineering alone insufficient',
      first_contract_minimum='16/18 on same DEV turns',unknown='retain denominator and halt all dispatch',independent='new synthetic scenario goal checks are provisional, not independent human Gold',
      plans=['calibrate Judge controls before paired scoring','R1 all18 first turns; failure evidence leads to R2 only if needed','blinded full18 pairs with repeated/reversed subset','frozen new synthetic scenarios run once after candidate freeze','one live UI synthetic smoke'] ))
    write_new(LOCAL/'authorization.json',a)
    b=Budget.create(LOCAL/'budget.sqlite3',[],a)
    with b.connection() as c:
        c.execute('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL NOT NULL)')
        c.execute('CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,settled_and_pending_before REAL,new_bound REAL,created_at TEXT)')
    print('R2 independent budget initialized; no requests yet',flush=True)

def configured(email,ev,arm,msgs,freeze):
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    a=Analyzer(replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000),ev,candidate=False)
    a.messages=lambda e,repair=False:msgs
    a.config=a.config.model_copy(update=dict(prompt_version='p5b5r2-'+arm,prompt_hash=digest([t for role,t in msgs if role=='system']),
       parameters=dict(a.config.parameters,experiment='p5b5r2',arm=arm,freeze_hash=digest(freeze),messages_hash=digest(msgs))))
    return a

def freeze(arm,reason):
    manifest=dict(arm=arm,reason=reason,at=now(),sources={p:hashfile(ROOT/p) for p in CORE},
      data_hash=hashfile(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json'),first_outputs_only=True)
    write_new(LOCAL/arm/'freeze.json',manifest)
    import shutil
    for rel in CORE:
        p=LOCAL/arm/'source'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,p)
    return manifest

def check_freeze(f):
    if any(hashfile(ROOT/p)!=h for p,h in f['sources'].items()):raise ValueError('Frozen source drift')

def generate_one(email,state,arm,out,freeze_manifest,*,context_hash=None):
    check_freeze(freeze_manifest)
    ev=out/email.email_id
    if (ev/'frozen-input.json').exists():
        if not (ev/'run.json').exists():raise ValueError('UNKNOWN: never redispatch incomplete identity')
        return AnalysisRun.model_validate(read(ev/'run.json')),read(ev/'evaluation.json')
    runtime=dict(context=state.extract(),events=[]) if arm.startswith('B2') else ActionStore(out/'actions.sqlite3').execute(state,email.input_hash,facts=LocalFacts(fixture_facts(email)))
    from src.application.p5b2_prompt import messages as b2
    msgs=b2(email) if arm.startswith('B2') else messages(email,runtime,arm)
    a=configured(email,ev,arm,msgs,freeze_manifest)
    if context_hash:a.config=a.config.model_copy(update=dict(parameters=dict(a.config.parameters,context_hash=context_hash)))
    budget=Budget(LOCAL/'budget.sqlite3');budget.bind(email,a.config,msgs,arm)
    write_new(ev/'frozen-input.json',dict(email=email.model_dump(),runtime=runtime,messages=msgs,config=a.config.model_dump(),at=now(),reference_in_prompt=False))
    run=AnalysisService(Repository(out/'runs.sqlite3'),a,budget=budget).analyze(email)
    write_new(ev/'run.json',run.model_dump(mode='json'))
    attempt=run.attempts[0] if run.attempts else None
    try:parsed=json.loads(attempt.raw_output)
    except (ValueError,TypeError,AttributeError):parsed={}
    from src.evaluation.p5b5r2_judge import diagnose
    reply=parsed.get('suggested_reply','')
    record=dict(case_id=state.conversation_id,arm=arm,run_id=run.run_id,input_hash=email.input_hash,run_path=str(ev/'run.json'),reply=reply,
      first_contract=run.status=='succeeded',provider_received=bool(attempt and attempt.metadata.get('dispatch')=='response_received'),
      error=attempt.error.error_type if attempt and attempt.error else run.metadata.get('error_type'),runtime=runtime,
      diagnostic=diagnose(reply,events=runtime['events'],expected_input_hash=email.input_hash))
    write_new(ev/'evaluation.json',record)
    print(json.dumps(dict(arm=arm,case=state.conversation_id,status=run.status,requests=budget.summary()['reserved_attempts']),ensure_ascii=False),flush=True)
    if run.status=='interrupted_or_unknown' or not record['provider_received'] or attempt.metadata.get('cost_cny') is None:
        budget.halt('UNKNOWN_OR_INFRASTRUCTURE');raise RuntimeError('Unknown/infrastructure; no further dispatch')
    return run,record

def generate(arm):
    out=LOCAL/arm
    f=freeze(arm,'E4+v3 source state; general cancellation, issue receipt and safety corrections' if arm=='R1' else 'Evidence-based amendment recorded in source diff')
    rows=[];store=ConversationStore(out/'conversation.sqlite3')
    gold=read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')
    for g in gold:
        history=[];turn=0
        for m in g['input_messages']:
            if m['role']!='customer':continue
            turn+=1;state=store.update(g['case_id'],'customer',m['text'],g['case_id']+f'-T{turn}-customer')
            body=m['text'] if not history else '\n\n'.join(history)+'\n\n[customer · current message]\n'+g['title']+'\n'+m['text']
            email=EmailInput(email_id=g['case_id']+f'-T{turn}',subject=g['title'],body=body)
            run,row=generate_one(email,state,arm,out,f);row['turn']=turn;rows.append(row)
            store.update(g['case_id'],'assistant',row['reply'],g['case_id']+f'-T{turn}-assistant')
            history.extend([f'[customer · turn-{turn} · SYNTHETIC_DEV]\n{g["title"]}\n{m["text"]}',f'[assistant · turn-{turn} · REAL_FIRST_UNSENT]\n{row["reply"]}'])
    write_new(out/'results.json',rows)

def raw_judge(payload,identity,system):
    ev=LOCAL/'judge'/identity
    if ev.exists():raise ValueError('Judge identity exists; never replace first score')
    email=EmailInput(email_id='judge-'+identity,subject='Blinded R2 development evaluation',body=json.dumps(payload,ensure_ascii=False))
    msgs=[('system',system),('human',email.body)]
    f=dict(judge_system_hash=digest(system),source_hash=hashfile(ROOT/'src/evaluation/p5b5r2_judge.py'))
    a=configured(email,ev,'JUDGE',msgs,f);b=Budget(LOCAL/'budget.sqlite3');b.bind(email,a.config,msgs,'JUDGE');b.verify_config(a.config)
    run_id=str(uuid4());write_new(ev/'frozen-input.json',dict(payload=payload,messages=msgs,config=a.config.model_dump(),at=now(),run_id=run_id))
    b.acquire(run_id,email.input_hash);bound=b.reserve(run_id,1,email.input_hash,msgs,4000)
    import time
    start=time.perf_counter()
    try:
        raw,meta=asyncio.run(a.request(email,False,90));cost=b.estimate_cost(meta)
        from src.evaluation.p5b5r2_judge import parse_judgment
        try:parsed=parse_judgment(raw,payload);parse_error=None
        except (ValueError,TypeError,KeyError,AttributeError) as exc:parsed=None;parse_error=str(exc)
        write_new(ev/'judgment.json',dict(run_id=run_id,raw=raw,parsed=parsed,parse_error=parse_error,metadata=meta,cost_upper=cost,reserved=bound,elapsed_ms=(time.perf_counter()-start)*1000,identity='LLM_JUDGE_PROVISIONAL_NOT_HUMAN'))
        b.completed(run_id,1)
        if cost is None:raise RuntimeError('UNKNOWN_BILLING')
        b.release(run_id);print('Judge '+identity+' recorded',flush=True)
    except BaseException:
        b.halt('UNKNOWN_JUDGE_OR_STORAGE');raise

def status_ui():
    if not (LOCAL/'budget.sqlite3').exists():return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='NOT_INITIALIZED')
    b=Budget(LOCAL/'budget.sqlite3');s=b.summary()
    with b.connection() as c:spent=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
    return dict(s,enabled=not s['halted'] and not s['active_lease'] and s['reserved_attempts']<300 and spent<10,remaining_requests=300-s['reserved_attempts'],remaining_cny=10-spent,actual_bill='UNKNOWN')

def generate_ui(subject,body,operation_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',operation_id):raise ValueError('Invalid operation identity')
    if not LOCK.acquire(blocking=False):raise ValueError('Another request is active')
    try:
        email=EmailInput(email_id=operation_id,subject=subject,body=body)
        for identity in ('UI','UI-R3'):
            ev=LOCAL/identity/operation_id
            if (ev/'frozen-input.json').exists():
                if read(ev/'frozen-input.json')['email']!=email.model_dump():raise ValueError('Operation content conflict')
                if not (ev/'run.json').exists():raise ValueError('UNKNOWN: no redispatch')
                return AnalysisRun.model_validate(read(ev/'run.json'))
        out=LOCAL/'UI-R3'
        f=read(out/'freeze.json') if (out/'freeze.json').exists() else freeze('UI-R3','Final R3 controlled synthetic UI path; same global ledger')
        state=ConversationState(operation_id);state.update('customer',body)
        run,_=generate_one(email,state,'UI-R3',out,f);return run
    finally:LOCK.release()

def generate_followup_ui(parent_run,body,operation_id,*,context_messages,subject):
    """Analyze actual saved conversation + local simulated reply, no fake substitution."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',operation_id):raise ValueError('Invalid operation identity')
    if not LOCK.acquire(blocking=False):raise ValueError('Another request is active')
    try:
        from src.application.mail_threads import assemble_context
        if not context_messages or context_messages[-1].get('role')!='assistant_simulation':raise ValueError('Reviewed local simulation receipt required')
        out=LOCAL/'UI-FOLLOWUP';ev=out/operation_id
        email=EmailInput(email_id=operation_id,subject=subject,body=assemble_context(context_messages,subject,body))
        if (ev/'frozen-input.json').exists():
            if read(ev/'frozen-input.json')['email']!=email.model_dump():raise ValueError('Operation content conflict')
            if not (ev/'run.json').exists():raise ValueError('UNKNOWN: no redispatch')
            return AnalysisRun.model_validate(read(ev/'run.json'))
        state=ConversationState('thread-'+parent_run.run_id)
        for m in context_messages:state.update('customer' if m['role']=='customer' else 'assistant',m['body'])
        state.update('customer',body)
        f=read(out/'freeze.json') if (out/'freeze.json').exists() else freeze('UI-FOLLOWUP','Final R3 live followup, actual prior local simulation receipt')
        run,_=generate_one(email,state,'UI-FOLLOWUP',out,f,context_hash=digest(context_messages));return run
    finally:LOCK.release()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','generate','status','halt']);p.add_argument('--arm',default='R1');a=p.parse_args()
    if a.action=='init':init()
    elif a.action=='generate':generate(a.arm)
    elif a.action=='status':print(json.dumps(status_ui(),ensure_ascii=False))
    else:Budget(LOCAL/'budget.sqlite3').halt('R2_EXPERIMENT_COMPLETED')
