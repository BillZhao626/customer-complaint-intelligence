"""P5-B7: new owner-authorized ledger; reuse LangChain analyzer and workflow.

All requests are serial, first attempts only. Existing identities are read, never
redispatched. Any unknown transport/billing/storage stops the entire ledger.
"""
import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b_pilot import read, write_new
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.application.p5b3_runtime import Analyzer
from src.application.p39_experiment import wire_bytes, dependencies
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.domain.contracts import EmailInput, AnalysisRun, digest
from src.dataset.research_generation import SYSTEM, SCENARIOS, accept_response
from src.application.p5b5r2_pipeline import ConversationState, ActionStore, messages

LOCAL=ROOT/'.local/p5b7';LIMITS=dict(cny=20,requests=600,concurrency=1,retries=0)
CORE=['scripts/p5b7_live.py','src/application/p5b3_runtime.py','src/infrastructure/deepseek.py',
      'src/application/p5b2_prompt.py','src/application/p5b5r2_pipeline.py','src/domain/analysis_v32.py',
      'src/application/analysis_service.py','src/application/live_execution.py','src/application/p5b5_state_v3.py',
      'src/application/p5b5_state_v2.py','src/application/p5b5_pipeline.py','src/application/p39_v2.py',
      'src/application/v31_prompt.py','scripts/p5b5_e4.py','scripts/p5b5_e3.py']
def now():return datetime.now(timezone.utc).isoformat()

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
        if config!=self.config or read(LOCAL/'authorization.json')['limits']!=LIMITS or config.model_id!='deepseek-flash':raise LiveError('configuration_error')
    def reserve(self,run_id,attempt_no,input_hash,msgs,max_tokens):
        if attempt_no!=1 or max_tokens!=4000 or input_hash!=self.expected.input_hash or msgs!=self.msgs:raise LiveError('configuration_error')
        size=len(wire_bytes(msgs))+1024
        if size>100000:raise LiveError('configuration_error')
        bound=(size*2+max_tokens*8)/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            n=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
            total=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
            halted=c.execute('SELECT halted FROM policy').fetchone()[0]
            if halted or c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or n>=600 or total+bound>20:raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,bound,now()))
            c.execute('INSERT INTO precalls VALUES(?,?,?,?,?,?)',(run_id,self.stage,n,total,bound,now()))
        return bound
    def estimate_cost(self,meta):
        i,o,t=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v)is not int or v<0 for v in (i,o,t)) or i+o!=t or o>4000 or i>len(wire_bytes(self.msgs))+1024:
            self.halt('UNKNOWN_BILLING');return None
        cost=(i*2+o*8)/1e6
        with self.connection() as c:
            run_id=c.execute('SELECT run_id FROM lease').fetchone()[0]
            c.execute('INSERT INTO settlements VALUES(?,?)',(run_id,cost))
        return cost

def make_plan():
    counts=[8,6,20,15,12,11,6,5,7]
    stores=['Hangzhou West Lake Store','Shanghai Pudong Store','Beijing Chaoyang Store','Ningbo Tianyi Store','Shenzhen Nanshan Store','Nanjing Xinjiekou Store','Suzhou Industrial Park Store','Wenzhou Lucheng Store']
    products=[('Electronics','wireless headphones'),('Home Appliances','coffee machine'),('Clothing','linen shirt'),('Furniture','office chair'),('Beauty/Personal Care','face cream'),('Sports/Outdoor','running shoes'),('Food/Beverage','tea gift box'),('Service/Other','membership plan')]
    backgrounds=['ordinary brief message written on a phone','careful account of what happened with a useful detail','polite but indirect customer wording','direct concise request without an introduction','some personal context relevant to the purchase','slightly disorganized but understandable account','customer who has already tried one reasonable step']
    jobs=[]
    for family,n in zip(SCENARIOS,counts,strict=True):
        scenario,mood,_,_,_=family
        for j in range(n):
            k=len(jobs);category,product=products[(k*3+j//3)%len(products)]
            config=dict(scenario=scenario,intended_tone=mood,product_category_intent=category,
                product=None if scenario=='missing-product' else product,store=None if scenario in ('missing-store','inquiry') and j%3!=1 else stores[(k+j//2)%len(stores)],
                language='en' if k%10 in (1,4,8) else 'zh',expression=backgrounds[(k+j)%len(backgrounds)],
                omission_policy='Do not name null entities. Other information may naturally be absent; do not fill a checklist.',
                situation_variant=(['damaged packaging and a faulty item','intermittent failure during ordinary use','wrong item or size','noticeable quality issue','uncertain warranty path'][j%5] if scenario=='fault' else
                    ['refund pending with no clear update','asking what return steps apply','unexpected fee while seeking a refund'][j%3] if scenario=='refund' else
                    ['unclear charge without identifying the item','unanswered customer service request','staff service experience without a product name'][j%3] if scenario=='missing-product' else
                    ['praise plus one unresolved concern','service charge question after a good purchase','two related requests in one email'][j%3] if scenario=='mixed-experience' else 'one plausible '+scenario+' experience'),
                conversation_style='a follow-up email may briefly quote a previous customer message, without fabricating a prior agent promise' if k%13==0 else 'one email',
                privacy='Fictional retail research only; no actual customer identities, phone numbers, addresses or credentials. No synthetic case ID in the prose.')
            msgs=[('system',SYSTEM+' Use the requested language naturally. Product/category intentions are generation context, not labels to return. Vary structure and length; avoid boilerplate synthetic disclaimers.'),('human',json.dumps(config,ensure_ascii=False))]
            jobs.append(dict(id=f'B7-{k+1:03}',family=scenario,config=config,messages=msgs,messages_hash=digest(msgs),purpose='NEW_SYNTHETIC_EVALUATION_NOT_HUMAN_GOLD'))
    paired=[x['id'] for family in SCENARIOS for x in [j for j in jobs if j['family']==family[0]][:2]]
    return dict(version='p5b7-generation-1',n=100,jobs=jobs,paired_ids=paired,parameters=dict(temperature=0,max_tokens=4000,thinking='disabled'),
        rationale='Purposive uneven scenario coverage, not a market sample. 30% English. First two per family fixed before inference for paired diagnosis. Complete email/conversation is the split unit.',
        exposure='No generated item is independent human Gold. All new outcomes are provisional; any case used for fixes becomes DEV.',source_plan='src/dataset/research_generation.py nine scenario families')

def init():
    write_new(LOCAL/'authorization.json',dict(identity='P5-B7-OWNER-20261030-CURRENT-CHAT',authorized_at=now(),limits=LIMITS,
        authorization_text='独立人民币20元/Provider600次，生成、LangChain分析、回复、配对与Judge；逐次预检，合成或明确授权输入；UNKNOWN不重发；不恢复旧账本；禁止外部业务操作。',
        provider='deepseek-flash',documented_version='DeepSeek-V4.1-Flash-1017',weights_snapshot='unavailable',dependencies=dependencies(),
        pricing=dict(price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',prices_verified_at='2026-10-30',prices=dict(input_peak_miss_cny_per_million=2,output_peak_cny_per_million=8,input_peak_hit_cny_per_million=.04),actual_bill='UNKNOWN'),
        privacy='Only fictional retail emails + already authorized synthetic DEV controls. Tracing disabled. No external business writes.',
        champion='B2',R3='NOT_PROMOTED',first_attempts_only=True))
    b=Budget.create(LOCAL/'budget.sqlite3',[],read(LOCAL/'authorization.json'))
    with b.connection() as c:c.executescript('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL NOT NULL); CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,settled_and_pending_before REAL,new_bound REAL,created_at TEXT);')
    write_new(LOCAL/'generation-plan.json',make_plan())
    f=dict(at=now(),sources={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in CORE},plan_hash=digest(read(LOCAL/'generation-plan.json')))
    write_new(LOCAL/'freeze.json',f)
    import shutil
    for rel in CORE:
        dest=LOCAL/'frozen-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
    print('New P5-B7 ledger initialized; no dispatch',flush=True)

def configured(email,ev,stage,msgs):
    f=read(LOCAL/'freeze.json')
    if any(sha256((ROOT/p).read_bytes()).hexdigest()!=h for p,h in f['sources'].items()):raise ValueError('Frozen chain source drift')
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    a=Analyzer(replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000),ev,candidate=False)
    a.messages=lambda e,repair=False:msgs
    a.config=a.config.model_copy(update=dict(prompt_version='p5b7-'+stage,prompt_hash=digest([t for r,t in msgs if r=='system']),parameters=dict(a.config.parameters,experiment='p5b7',arm=stage,freeze_hash=digest(f),messages_hash=digest(msgs))))
    return a

def raw_call(identity,msgs,stage,*,payload=None):
    ev=LOCAL/stage/identity
    if (ev/'frozen-input.json').exists():
        if not (ev/'response.json').exists():raise ValueError('UNKNOWN identity: never redispatch '+identity)
        return read(ev/'response.json')
    email=EmailInput(email_id=identity,subject=stage,body=json.dumps(msgs,ensure_ascii=False))
    a=configured(email,ev,stage,msgs);b=Budget(LOCAL/'budget.sqlite3');b.bind(email,a.config,msgs,stage);b.verify_config(a.config)
    run_id=str(uuid4());write_new(ev/'frozen-input.json',dict(email=email.model_dump(),payload=payload,messages=msgs,config=a.config.model_dump(),run_id=run_id,at=now()))
    b.acquire(run_id,email.input_hash);bound=b.reserve(run_id,1,email.input_hash,msgs,4000)
    import time
    start=time.perf_counter()
    try:
        raw,meta=asyncio.run(a.request(email,False,90));cost=b.estimate_cost(meta)
        row=dict(run_id=run_id,raw=raw,metadata=meta,cost_upper=cost,reserved=bound,elapsed_ms=(time.perf_counter()-start)*1000)
        write_new(ev/'response.json',row);b.completed(run_id,1)
        if cost is None:raise RuntimeError('UNKNOWN_BILLING')
        b.release(run_id);print(stage+' '+identity+' saved',flush=True);return row
    except BaseException:
        b.halt('UNKNOWN_TRANSPORT_BILLING_OR_STORAGE');raise

def generate():
    for job in read(LOCAL/'generation-plan.json')['jobs']:
        row=raw_call(job['id'],job['messages'],'GENERATION')
        dest=LOCAL/'dataset'/(job['id']+'.json')
        if dest.exists():continue
        try:
            accepted=accept_response(dict(id=job['id'],messages=job['messages'],messages_hash=job['messages_hash'],config=job['config']),row['raw'],model='deepseek-flash',parameters=read(LOCAL/'generation-plan.json')['parameters'],request_id=row['metadata'].get('provider_response_id'),usage=row['metadata'])
            email=EmailInput(email_id=job['id'],subject=accepted['subject'],body=accepted['body'])
            accepted.update(input_hash=email.input_hash,source='LLM_SYNTHETIC',family=job['family'],generation_run_id=row['run_id'],gold_status='NONE_INTENT_IS_NOT_GOLD',purpose=job['purpose'])
            write_new(dest,accepted)
        except (ValueError,TypeError,KeyError) as exc:write_new(LOCAL/'generation-rejections'/(job['id']+'.json'),dict(error=str(exc),generation_run_id=row['run_id']))

def analyze_one(email,arm='B2',*,runtime=None):
    ev=LOCAL/arm/email.email_id
    if (ev/'frozen-input.json').exists():
        if not (ev/'run.json').exists():raise ValueError('UNKNOWN: do not redispatch')
        return AnalysisRun.model_validate(read(ev/'run.json'))
    from src.application.p5b2_prompt import messages as b2
    if runtime is None:
        state=ConversationState(email.email_id);state.update('customer',email.body)
        runtime=ActionStore(LOCAL/arm/'actions.sqlite3').execute(state,email.input_hash) if arm=='R3' else dict(context=state.extract(),events=[])
    msgs=b2(email) if arm=='B2' else messages(email,runtime,'R3')
    a=configured(email,ev,arm,msgs);b=Budget(LOCAL/'budget.sqlite3');b.bind(email,a.config,msgs,arm)
    write_new(ev/'frozen-input.json',dict(email=email.model_dump(),runtime=runtime,messages=msgs,config=a.config.model_dump(),at=now(),reference_in_prompt=False))
    run=AnalysisService(Repository(LOCAL/arm/'runs.sqlite3'),a,budget=b).analyze(email)
    write_new(ev/'run.json',run.model_dump(mode='json'))
    attempt=run.attempts[0] if run.attempts else None
    from src.evaluation.p5b5r2_judge import diagnose
    parsed=(attempt.parsed_output or {}) if attempt else {}
    row=dict(case_id=email.email_id,arm=arm,run_id=run.run_id,input_hash=email.input_hash,reply=parsed.get('suggested_reply',''),runtime=runtime,first_contract=run.status=='succeeded',error=attempt.error.error_type if attempt and attempt.error else run.metadata.get('error_type'),diagnostic=diagnose(parsed.get('suggested_reply',''),events=runtime['events'],expected_input_hash=email.input_hash))
    write_new(ev/'evaluation.json',row)
    print(arm+' '+email.email_id+' '+run.status,flush=True)
    if run.status=='interrupted_or_unknown' or not attempt or attempt.metadata.get('dispatch')!='response_received' or attempt.metadata.get('cost_cny') is None:
        b.halt('UNKNOWN_OR_INFRASTRUCTURE');raise RuntimeError('Dispatch halted; no unknown retry')
    return run

def batch(arm):
    paired=set(read(LOCAL/'generation-plan.json')['paired_ids'])
    seen=set()
    for path in sorted((LOCAL/'dataset').glob('B7-*.json')):
        d=read(path);body=' '.join(d['body'].lower().split())
        if body in seen:continue
        seen.add(body)
        if arm=='R3' and d['email_id'] not in paired:continue
        analyze_one(EmailInput(email_id=d['email_id'],subject=d['subject'],body=d['body']),arm)

def judge():
    from src.evaluation.p5b5r2_judge import controls,control_payload,JUDGE_SYSTEM_V31
    # Full inherited policy controls, no new human numerical labels.
    for c in controls():
        raw_call('control-'+c['id'],[('system',JUDGE_SYSTEM_V31),('human',json.dumps(control_payload(c),ensure_ascii=False))],'JUDGE',payload=control_payload(c))
    for i,eid in enumerate(read(LOCAL/'generation-plan.json')['paired_ids']):
        a=read(LOCAL/'B2'/eid/'evaluation.json');b=read(LOCAL/'R3'/eid/'evaluation.json');d=read(LOCAL/'dataset'/(eid+'.json'))
        order=['B2','R3'] if i%2==0 else ['R3','B2'];rows={'B2':a,'R3':b}
        payload=dict(customer_context=[dict(role='customer',text=d['subject']+'\n'+d['body'])],current_turn=1,
            reference_requirements=None,reference_identity='NO_HUMAN_GOLD_GENERATOR_INTENT_WITHHELD',
            answers=[dict(slot=slot,reply=rows[arm]['reply'],events=rows[arm]['runtime']['events'],expected_input_hash=rows[arm]['input_hash'],attachment_manifest=[]) for slot,arm in zip(('A','B'),order,strict=True)])
        raw_call('pair-'+eid,[('system',JUDGE_SYSTEM_V31),('human',json.dumps(payload,ensure_ascii=False))],'JUDGE',payload=dict(blind_payload=payload,slot_order=order))

def status():
    b=Budget(LOCAL/'budget.sqlite3');s=b.summary()
    with b.connection() as c:
        spent=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
        stages=c.execute('SELECT stage,COUNT(*),SUM(s.cost) FROM precalls p LEFT JOIN settlements s USING(run_id) GROUP BY stage').fetchall()
    return dict(s,settled_and_pending_upper_cny=spent,limits=LIMITS,stages=stages,actual_bill='UNKNOWN')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','generate','analyze','paired','judge','all','status','halt']);a=p.parse_args()
    if a.action=='init':init()
    elif a.action=='status':print(json.dumps(status(),ensure_ascii=False))
    elif a.action=='halt':Budget(LOCAL/'budget.sqlite3').halt('P5B7_EXPERIMENT_COMPLETED')
    else:
        if a.action in ('generate','all'):generate()
        if a.action in ('analyze','all'):batch('B2')
        if a.action in ('paired','all'):batch('R3')
        if a.action in ('judge','all'):judge()
