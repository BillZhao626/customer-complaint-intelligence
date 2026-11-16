"""Owner authorized P5-B8 first-attempt experiments. Never touches old ledgers."""
import argparse,asyncio,json,os,sys,time
from pathlib import Path
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.domain.contracts import EmailInput,digest
from src.evaluation.p5b_pilot import read,write_new
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.infrastructure.v3_live_settings import V3PilotSettings
from src.application.p5b3_runtime import Analyzer
from src.application.p39_experiment import wire_bytes,dependencies
from src.application.p5b5_pipeline import now
from src.application import p5b8_pipeline as pipe
from src.application.live_execution import strict_json
LOCAL=ROOT/'.local/p5b8'; LIMITS=dict(cny=12,requests=400,concurrency=1,retries=0)
CORE=['scripts/p5b8_live.py','src/application/p5b8_pipeline.py','src/application/p5b3_runtime.py','src/infrastructure/deepseek.py','src/application/p39_experiment.py','src/evaluation/p5b5r2_judge.py']

class Budget(PilotBudget):
    def bind(self,email,config,msgs,stage):
        self.expected=email;self.config=config;self.msgs=msgs;self.stage=stage
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE');manifest,allowed,halted=c.execute('SELECT manifest,allowed,halted FROM policy').fetchone()
            if json.loads(manifest)!=read(LOCAL/'authorization.json') or halted or c.execute('SELECT 1 FROM lease').fetchone():raise LiveError('interrupted_or_unknown')
            values=set(json.loads(allowed));values.add(email.input_hash);c.execute('UPDATE policy SET allowed=?',(json.dumps(sorted(values)),))
    def reserve(self,run_id,attempt_no,input_hash,msgs,max_tokens):
        if attempt_no!=1 or max_tokens!=4000 or input_hash!=self.expected.input_hash or msgs!=self.msgs:raise LiveError('configuration_error')
        size=len(wire_bytes(msgs))+1024;bound=(size*2+4000*8)/1e6
        if size>100000:raise LiveError('configuration_error')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE');n=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
            total=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
            halted=c.execute('SELECT halted FROM policy').fetchone()[0]
            if halted or c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or n>=400 or total+bound>12:raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,bound,now()))
            c.execute('INSERT INTO precalls VALUES(?,?,?,?,?,?,?)',(run_id,self.stage,n,total,bound,'LLM_SYNTHETIC_OR_AUTHORIZED_DEV_NO_CUSTOMER_PII',now()))
        return bound
    def estimate_cost(self,meta):
        i,o,t=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v)is not int or v<0 for v in (i,o,t)) or i+o!=t or o>4000 or i>len(wire_bytes(self.msgs))+1024:raise RuntimeError('UNKNOWN_BILLING')
        cost=(i*2+o*8)/1e6
        with self.connection() as c:
            rid=c.execute('SELECT run_id FROM lease').fetchone()[0];c.execute('INSERT INTO settlements VALUES(?,?)',(rid,cost))
        return cost

def init():
    paths=sorted((ROOT/'.local/p5b7/dataset').glob('B7-*.json'));assert len(paths)==90
    ds=[read(p) for p in paths];by={d['email_id']:d for d in ds}
    b_ids=list(dict.fromkeys([next(d['email_id'] for d in ds if d['family']==fam) for fam in dict.fromkeys(d['family'] for d in ds)]+['B7-035','B7-036','B7-074']))
    judge_ids=list(dict.fromkeys([d['email_id'] for fam in dict.fromkeys(d['family'] for d in ds) for d in [x for x in ds if x['family']==fam][:3]]+['B7-035','B7-036','B7-074']))
    plan=dict(version='p5b8-preregistered-1',at=now(),A_ids=list(by),B_ids=b_ids,judge_A_ids=judge_ids,swap_ids=judge_ids[:6],ablation_ids=list(by)[:8],
        inputs={k:dict(path=str(p.relative_to(ROOT)),sha256=sha256(p.read_bytes()).hexdigest(),input_hash=by[k]['input_hash'],role='DEV_REGRESSION_EXPOSED_B7') for k,p in zip(by,paths,strict=True)},
        independent_scenarios=[dict(id='B8N-001',language='en',family='subscription-double-charge',situation='A politely written disputed duplicate subscription charge, useful transaction reference, no anger adjectives.'),dict(id='B8N-002',language='zh',family='store-accessibility',situation='A store accessibility barrier with praise for one employee and a request for a concrete remedy, no personal medical details.'),dict(id='B8N-003',language='en',family='loyalty-points',situation='Missing loyalty points after a valid purchase, indirect frustrated service comment and request for verification.'),dict(id='B8N-004',language='zh',family='multi-turn-preference',situation='Two short customer turns in the same email, original repair request corrected to undecided return versus replacement; original fictional order number corrected; agent history has no merchant promises.')],
        controls=['conditional_logistics','negated_safety','internal_without_receipt','wrong_input_receipt','wrong_action_receipt','attachment_invented','connected_invented','normal_fault'],
        endpoints='Primary provisional paired: no hard error AND B1=2 AND B2=2; UNKNOWN unscored remains in dispatched denominator. A and B separate.',
        max_planned_calls=390,source_identity='LLM_SYNTHETIC_NOT_HUMAN_GOLD')
    write_new(LOCAL/'authorization.json',dict(identity='P5B8-OWNER-20261031-CURRENT-CHAT',at=now(),limits=LIMITS,pricing=dict(url='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',verified_date='2026-10-31',input_peak_miss=2,output_peak=8,actual_bill='UNKNOWN'),model='deepseek-flash',documented_version='DeepSeek-V4.1-Flash-1017',weights_snapshot='unavailable',dependencies=dependencies(),privacy='Fictional retail research only. No actual customers, no secrets. No external business actions. LangSmith tracing disabled.'))
    b=Budget.create(LOCAL/'budget.sqlite3',[],read(LOCAL/'authorization.json'))
    with b.connection() as c:c.executescript('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL NOT NULL);CREATE TABLE precalls(run_id TEXT PRIMARY KEY,stage TEXT,n_before INTEGER,total_before REAL,bound REAL,privacy_check TEXT,created_at TEXT);')
    write_new(LOCAL/'plan.json',plan)
    write_new(LOCAL/'freeze.json',dict(at=now(),sources={r:sha256((ROOT/r).read_bytes()).hexdigest() for r in CORE},protocol_hash=sha256((ROOT/'docs/p5b8/PROTOCOL.md').read_bytes()).hexdigest(),plan_hash=digest(plan)))
    import shutil
    for r in CORE:
        dest=LOCAL/'frozen-source'/r;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/r,dest)
    print('P5-B8 initialized, no calls',flush=True)

def raw_call(identity,msgs,stage,payload=None):
    ev=LOCAL/'calls'/stage/identity
    if (ev/'frozen-input.json').exists():
        if not (ev/'response.json').exists():raise RuntimeError('UNKNOWN_IDENTITY_NEVER_REDISPATCH '+identity)
        frozen=read(ev/'frozen-input.json')
        if digest(frozen['messages'])!=digest(msgs):raise RuntimeError('IMMUTABLE_IDENTITY_INPUT_DRIFT')
        return read(ev/'response.json')
    f=read(LOCAL/'freeze.json');plan=read(LOCAL/'plan.json')
    if any(sha256((ROOT/r).read_bytes()).hexdigest()!=h for r,h in f['sources'].items()) or digest(plan)!=f['plan_hash']:raise RuntimeError('Frozen source/plan drift')
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    email=EmailInput(email_id=identity,subject=stage,body=json.dumps(msgs,ensure_ascii=False))
    a=Analyzer(replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000),ev,candidate=False);a.messages=lambda e,repair=False:msgs
    a.config=a.config.model_copy(update=dict(prompt_version='p5b8-'+stage,prompt_hash=digest([t for r,t in msgs if r=='system']),parameters=dict(a.config.parameters,experiment='p5b8',stage=stage)))
    # Environment check without ever printing keys.
    a.settings.validate();b=Budget(LOCAL/'budget.sqlite3');b.bind(email,a.config,msgs,stage)
    rid=str(uuid4());b.acquire(rid,email.input_hash)
    try:bound=b.reserve(rid,1,email.input_hash,msgs,4000)
    except BaseException:b.release(rid);raise
    write_new(ev/'frozen-input.json',dict(run_id=rid,messages=msgs,payload=payload,config=a.config.model_dump(),at=now(),privacy_check='SYNTHETIC_AUTHORIZED',freeze_hash=digest(f)))
    start=time.perf_counter()
    try:
        raw,meta=asyncio.run(a.request(email,False,90));cost=b.estimate_cost(meta)
        row=dict(run_id=rid,raw=raw,metadata=meta,cost_upper=cost,reserved=bound,elapsed_ms=(time.perf_counter()-start)*1000)
        write_new(ev/'response.json',row);b.completed(rid,1);b.release(rid)
        print(stage+' '+identity+' saved',flush=True);return row
    except BaseException as exc:
        write_new(ev/'error.json',dict(type=type(exc).__name__,at=now(),status='UNKNOWN_DO_NOT_RETRY'))
        b.halt('UNKNOWN_TRANSPORT_BILLING_OR_STORAGE');raise

def load_email(eid):
    p=LOCAL/'new-dataset'/(eid+'.json') if eid.startswith('B8N-') else ROOT/'.local/p5b7/dataset'/(eid+'.json')
    d=read(p)
    if not eid.startswith('B8N-'):
        identity=read(LOCAL/'plan.json')['inputs'][eid]
        assert sha256(p.read_bytes()).hexdigest()==identity['sha256'] and d['source']=='LLM_SYNTHETIC'
    return EmailInput(email_id=eid,subject=d['subject'],body=d['body'])
def analysis(email):
    dest=LOCAL/'analysis'/(email.email_id+'.json')
    if dest.exists():return read(dest)
    r=raw_call(email.email_id,pipe.analysis_messages(email),'ANALYSIS',email.model_dump())
    try:d=pipe.validate_analysis(r['raw'],email);error=None
    except (ValueError,TypeError,KeyError,AssertionError) as e:d=None;error=str(e)
    out=dict(case_id=email.email_id,input_hash=email.input_hash,data=d,error=error,call=r,annotation_status='MODEL_PROVISIONAL_NOT_GOLD')
    write_new(dest,out);return out
def reply(email,runtime,variant,anal=None):
    dest=LOCAL/'replies'/variant/(email.email_id+'.json')
    if dest.exists():return read(dest)
    r=raw_call(email.email_id,pipe.reply_messages(email,runtime,anal),variant,dict(email=email.model_dump(),runtime=runtime,analysis=anal))
    try:
        d=strict_json(r['raw']);assert set(d)=={'reply'} and isinstance(d['reply'],str) and d['reply'].strip();text=d['reply'];error=None
    except (ValueError,TypeError,KeyError,AssertionError) as e:text='';error=str(e)
    out=dict(case_id=email.email_id,input_hash=email.input_hash,variant=variant,reply=text,error=error,runtime=runtime,analysis_supplied=anal is not None,call=r,checks=pipe.check_reply(email,text,runtime))
    write_new(dest,out);return out
def run_A(ids):
    for n,eid in enumerate(ids):
        e=load_email(eid);a=analysis(e);rp=LOCAL/'runtime/A'/(eid+'.json')
        if not rp.exists():write_new(rp,pipe.execute(e,pipe.guided_actions(a['data']),LOCAL/'state/A'/eid/'actions.sqlite3'))
        runtime=read(rp)
        for v in (['A_DIRECT','A_GUIDED'] if n%2==0 else ['A_GUIDED','A_DIRECT']):reply(e,runtime,v,a['data'] or {'status':'ANALYSIS_UNAVAILABLE'} if v=='A_GUIDED' else None)
def run_B():
    for eid in read(LOCAL/'plan.json')['B_ids']:
        e=load_email(eid);a=analysis(e);dp=LOCAL/'plans'/(eid+'.json')
        if not dp.exists():
            r=raw_call(eid,[('system',pipe.PLAN_SYSTEM),('human',json.dumps(e.model_dump(),ensure_ascii=False))],'B_PLAN',e.model_dump())
            try:actions=pipe.validate_plan(r['raw'],e);error=None
            except (ValueError,AssertionError,TypeError,KeyError) as ex:actions=[];error=str(ex)
            write_new(dp,dict(actions=actions,error=error,call=r))
        for v,actions in [('B_DIRECT',read(dp)['actions']),('B_GUIDED',pipe.guided_actions(a['data']))]:
            rp=LOCAL/'runtime'/v/(eid+'.json')
            if not rp.exists():write_new(rp,pipe.execute(e,actions,LOCAL/'state'/v/eid/'actions.sqlite3'))
            reply(e,read(rp),v,a['data'] or {'status':'ANALYSIS_UNAVAILABLE'} if v=='B_GUIDED' else None)
def run_new():
    for s in read(LOCAL/'plan.json')['independent_scenarios']:
        dest=LOCAL/'new-dataset'/(s['id']+'.json')
        if not dest.exists():
            r=raw_call(s['id'],[('system','Generate a natural fictional retail customer email, no actual personal data. JSON only {"subject":"...","body":"..."}. Do not output labels or case IDs. Follow specified language. For two turns include both customer turns with clear delimiters and a short generic assistant question, no fabricated merchant promises.'),('human',json.dumps(s,ensure_ascii=False))],'NEW_GENERATION',s)
            d=strict_json(r['raw']);assert set(d)=={'subject','body'}
            write_new(dest,dict(**d,case_id=s['id'],source='LLM_SYNTHETIC',dataset_role='INDEPENDENT_SYNTHETIC_FAMILY_TRANSFER_NOT_HUMAN_GOLD',family=s['family'],generation_call=r))
    run_A([s['id'] for s in read(LOCAL/'plan.json')['independent_scenarios']])

JUDGE_EXTRA='''P5-B8 amendment: Do not favor long replies. No fixed reference wording is required. Conditional safe suggestions and negated dangerous verbs are not unsafe actions.
Do not treat customer-reported attachments as received. Evaluate empathy relative to actual expressed tone (neutral objective faults need no exaggerated apology).
For each answer additionally give "emotion_fit":0/1/2 and "emotion_reason":"...". These are provisional judgments, not human Gold.
Primary scores and H01..H07 retain original semantics. Tone/politeness does not prove issue resolution. Distinguish local request progress from resolution.'''
def judge_pair(eid,experiment='A',swap=False):
    from src.evaluation.p5b5r2_judge import JUDGE_SYSTEM_V31,parse_judgment
    e=load_email(eid);variants=[experiment+'_DIRECT',experiment+'_GUIDED'];idx=(read(LOCAL/'plan.json')['A_ids'].index(eid) if eid.startswith('B7') else int(eid[-3:]))
    order=variants if (idx%2==0)!=swap else list(reversed(variants));answers=[]
    for slot,v in zip(('A','B'),order,strict=True):
        r=read(LOCAL/'replies'/v/(eid+'.json'));answers.append(dict(slot=slot,reply=r['reply'],events=r['runtime']['events'],expected_input_hash=e.input_hash,attachment_manifest=[]))
    p=dict(customer_context=[dict(role='customer',text=e.subject+'\n'+e.body)],current_turn=1,reference_requirements=None,reference_identity='NO_HUMAN_GOLD',answers=answers)
    identity=experiment+'-'+eid+('-swap' if swap else '');dest=LOCAL/'judgments'/(identity+'.json')
    if dest.exists():return
    r=raw_call(identity,[('system',JUDGE_SYSTEM_V31+JUDGE_EXTRA),('human',json.dumps(p,ensure_ascii=False))],'JUDGE_PAIR',dict(blind_payload=p,slot_order=order))
    try:d=parse_judgment(r['raw'],p);error=None
    except (ValueError,TypeError,KeyError,AttributeError) as ex:d=None;error=str(ex)
    write_new(dest,dict(case_id=eid,experiment=experiment,swap=swap,order=order,parsed=d,error=error,call=r,payload=p,identity='SAME_PROVIDER_AUTOMATIC_JUDGE_NOT_HUMAN'))
def run_judge():
    from src.evaluation.p5b5r2_judge import controls,control_payload,JUDGE_SYSTEM_V31,parse_judgment
    plan=read(LOCAL/'plan.json')
    for ctrl in controls():
        if ctrl['id'] not in plan['controls']:continue
        dest=LOCAL/'controls'/(ctrl['id']+'.json')
        if dest.exists():continue
        p=control_payload(ctrl);r=raw_call(ctrl['id'],[('system',JUDGE_SYSTEM_V31+JUDGE_EXTRA),('human',json.dumps(p,ensure_ascii=False))],'JUDGE_CONTROL',p)
        try:d=parse_judgment(r['raw'],p);error=None
        except (ValueError,KeyError,TypeError,AttributeError) as ex:d=None;error=str(ex)
        write_new(dest,dict(control=ctrl,parsed=d,error=error,call=r))
    for eid in plan['judge_A_ids']:judge_pair(eid)
    for eid in plan['swap_ids']:judge_pair(eid,swap=True)
    for eid in plan['B_ids']:judge_pair(eid,'B')
    for s in plan['independent_scenarios']:judge_pair(s['id'])
def status():
    b=Budget(LOCAL/'budget.sqlite3')
    with b.connection() as c:
        total=c.execute('SELECT COALESCE(SUM(COALESCE(s.cost,r.reserved_cny)),0) FROM reservations r LEFT JOIN settlements s USING(run_id)').fetchone()[0]
        stages=c.execute('SELECT stage,COUNT(*),SUM(s.cost) FROM precalls p LEFT JOIN settlements s USING(run_id) GROUP BY stage').fetchall()
    return dict(b.summary(),settled_and_pending_upper_cny=total,limits=LIMITS,stages=stages,actual_bill='UNKNOWN')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','A','B','new','ablation','judge','all','status','halt']);a=p.parse_args().action
    if a=='init':init()
    elif a=='status':print(json.dumps(status(),ensure_ascii=False))
    elif a=='halt':Budget(LOCAL/'budget.sqlite3').halt('P5B8_EXPERIMENT_COMPLETED')
    else:
        plan=read(LOCAL/'plan.json')
        if a in ('A','all'):run_A(plan['A_ids'])
        if a in ('B','all'):run_B()
        if a in ('new','all'):run_new()
        if a in ('ablation','all'):
            for eid in plan['ablation_ids']:reply(load_email(eid),read(LOCAL/'runtime/A'/(eid+'.json')),'NO_SENTIMENT',pipe.strip_sentiment(read(LOCAL/'analysis'/(eid+'.json'))['data'] or {'status':'ANALYSIS_UNAVAILABLE'}))
        if a in ('judge','all'):run_judge()
