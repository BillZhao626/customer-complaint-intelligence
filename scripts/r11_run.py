"""Explicit new-ledger R11 first-attempt runner. No automatic retry."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/r11-quality-20261109-v1'
DOCS=ROOT/'docs/r11-quality-20261109-v1'
args=argparse.ArgumentParser()
args.add_argument('command',choices=['freeze','controls','generate','score','summary','close'])
args.add_argument('--revision',default='judge-pilot-v1')
args.add_argument('--judge',choices=['old','candidate'],default='candidate')
args.add_argument('--dataset',default='dev-cases.json')
args.add_argument('--selection',default='all')
args.add_argument('--workers',type=int,default=6)
opt=args.parse_args()
CODE=LOCAL/'historical-source/fixed-v3' if opt.judge=='old' else ROOT
if opt.judge=='old':
    # Historical code has an isolated project root. Supply the already-authorized
    # account setting in memory; never copy .env into an evidence/source archive.
    import os
    for line in (ROOT/'.env').read_text('utf8').splitlines():
        if '=' in line:
            key,value=line.split('=',1)
            if key.strip()=='LLM_API_KEY':os.environ.setdefault('LLM_API_KEY',value.strip().strip('"').strip("'"))
sys.path.insert(0,str(CODE))
from src.domain.contracts import EmailInput,digest
from src.evaluation.experiment_integrity import freeze,verify,file_hash
if opt.judge=='old':
    # Only evaluator code is historical. Shared R11 accounting has its own hash.
    import importlib.util
    spec=importlib.util.spec_from_file_location('r11_accounting',ROOT/'src/infrastructure/p5b8r3_execution.py')
    accounting=importlib.util.module_from_spec(spec);spec.loader.exec_module(accounting)
    Dispatcher=accounting.Dispatcher
else:
    from src.infrastructure.p5b8r3_execution import Dispatcher
from src.infrastructure.structured_reply_provider import StructuredReplyProvider
if opt.judge=='old':
    from src.evaluation import owner_calibrated_judge as judge
else:
    from src.evaluation import service_judge as judge

def read(p):return json.loads(Path(p).read_text('utf8'))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert read(p)==v,str(p)
    else:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
    return v

class Run:
    def __init__(self):
        if (LOCAL/'CLOSED.json').exists():raise PermissionError('R11 ledger closed')
        # Warm optional SDK imports once, before worker threads construct clients.
        import langchain_openai
        import src.application.p5b3_runtime
        plan=read(LOCAL/'plan.json')
        self.dispatcher=Dispatcher(LOCAL/'live',plan,authorization=read(LOCAL/'authorization.json'),
            provider=StructuredReplyProvider(),mode='LIVE',max_inflight=opt.workers)
        self.dispatcher.plan=dict(plan,execution_integrity=read(LOCAL/'freezes'/f'{opt.revision}-{opt.judge}.json'))
        self.db=LOCAL/'call-map.sqlite3'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE IF NOT EXISTS logical (key TEXT UNIQUE NOT NULL, slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 1200))')
    def invoke(self,key,messages,payload):
        logical=f'{opt.revision}-{opt.judge}-{key}'
        with sqlite3.connect(self.db) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT slot FROM logical WHERE key=?',(logical,)).fetchone()
            slot=row[0] if row else db.execute('SELECT COALESCE(MAX(slot),0)+1 FROM logical').fetchone()[0]
            if not row:db.execute('INSERT INTO logical VALUES (?,?)',(logical,slot))
        return self.dispatcher.call(f'R11-{slot:04}',messages,dict(payload,logical_identity=logical,
            parent_experiment=opt.revision,model_role=payload.get('stage'),evaluator=judge.identity()))
    def each(self,fn,items):
        with ThreadPoolExecutor(max_workers=opt.workers) as pool:
            return list(pool.map(fn,items))
    def score(self,name,email,slots,reverse=False,rubric=None):
        path=LOCAL/'judgments'/opt.revision/opt.judge/f'{name}.json'
        if path.exists():return read(path)
        e=EmailInput.model_validate(email)
        if not all(s['parse_ok'] and s['reply'].strip() for s in slots):
            return save(path,dict(status='UNASSESSABLE_FIRST_STRUCTURE',parsed=None))
        if len(slots)==2:
            payload,key=judge.blind_pair(e,slots,reverse=reverse);system=judge.SYSTEM
        else:
            s=dict(slots[0],slot='X')
            s['deterministic_fact_audit']=judge.audit_slot(s,e)
            from src.evaluation.p5b8r4_judge import quote_inventory
            s['quote_inventory']=quote_inventory(e,s)
            payload=dict(customer=e.model_dump(),answers=[s],judge_version=judge.VERSION)
            key={'X':dict(run_id=s['run_id'])};system=judge.SYSTEM+'\nAssess the ONE answer X. Return one answer, preference UNKNOWN.'
        if rubric:
            payload['registered_service_requirements']=rubric
            system+='\nApply the supplied registered requirements to service coverage. They are researcher-authored criteria, not a reference answer or human verdict. They authorize no fact or operation. A useful official conditional path remains sufficient when final policy facts are unavailable.'
        call=self.invoke(name,[('system',system),('human',json.dumps(payload,ensure_ascii=False))],
            dict(stage='judge',case_id=e.email_id,input_hash=e.input_hash,dataset_role='JUDGE'))
        try:parsed=judge.parse(call['raw'],payload);error=None
        except (ValueError,KeyError,TypeError,AttributeError,AssertionError) as ex:parsed=None;error=str(ex)
        r=save(path,dict(status='PARSED' if parsed else 'UNKNOWN_PROTOCOL',parsed=parsed,error=error,
            call=call,payload=payload,key=key,evaluator=judge.identity()))
        print(name,r['status'],error or '',flush=True)
        return r
    def generate(self,c):
        from src.application.r6u0_workflow import generate
        path=LOCAL/'traces'/opt.revision/c['case_id']/'GUIDED-reply.json'
        if path.exists():return read(path)
        r=generate(c['email'],lambda s,m,p:self.invoke(c['case_id']+'-'+s,m,p),path.parent,
            role=c.get('dataset_role','EXPOSED_DEV'),arms=('GUIDED',),revision=opt.revision,
            authorized_facts=c.get('authorized_facts'))['GUIDED']
        print(c['case_id'],'FIRST',r['parse']['status'],flush=True)
        return r

def dataset():
    rows=read(LOCAL/opt.dataset)
    if isinstance(rows,dict):rows=rows['cases']
    if opt.selection!='all':
        ids=set(opt.selection.split(','));rows=[r for r in rows if r.get('case_id',r.get('family')) in ids]
    return rows

if opt.command=='freeze':
    inputs=[LOCAL/'plan.json',LOCAL/'authorization.json',LOCAL/opt.dataset,DOCS/'PROTOCOL.md',Path(__file__),ROOT/'src/infrastructure/p5b8r3_execution.py']
    manifest=freeze(CODE,inputs=inputs)
    data=read(LOCAL/opt.dataset)
    if isinstance(data,list) and data and all(c.get('dataset_role')=='INDEPENDENT_TEST' for c in data):
        from src.evaluation.experiment_integrity import family_preflight
        paths=dict(candidates=LOCAL/opt.dataset,history=LOCAL/'exposure-registry.json',aliases=LOCAL/'holdout-family-aliases.json')
        family_preflight(data,read(paths['history']),read(paths['aliases']))
        manifest=freeze(CODE,inputs=inputs+[paths['history'],paths['aliases'],DOCS/'holdout-preregistration.json'])
        manifest['independent_dataset']={k:str(p.resolve()) for k,p in paths.items()}
        verify(manifest)
    save(LOCAL/'freezes'/f'{opt.revision}-{opt.judge}.json',manifest)
elif opt.command=='summary':
    with sqlite3.connect(LOCAL/'live/budget.sqlite3') as db:
        print(db.execute('SELECT state,COUNT(*),SUM(COALESCE(settled_micro,reserved_micro))/1000000.0 FROM calls GROUP BY state').fetchall())
elif opt.command=='close':
    run=Run();run.dispatcher.halt('R11_COMPLETED_NO_REUSE');save(LOCAL/'CLOSED.json',run.dispatcher.summary())
else:
    run=Run();rows=dataset()
    if opt.command=='generate':run.each(run.generate,rows)
    elif opt.command=='controls':
        def control(c):
            for n,rev in [('AB1',False),('BA',True),('AB2',False),('AB3',False)]:
                run.score(c['family']+'-'+n,c['email'],c['slots'],rev)
        run.each(control,rows)
    else:
        def assess(c):
            slots=[read(ROOT/p)['slot'] for p in c['score_paths']]
            return run.score(c['score_name'],c['email'],slots,c.get('reverse',False),c.get('rubric'))
        run.each(assess,rows)
