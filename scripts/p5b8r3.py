"""R3 prepare / Mock / authorized live. No historical writer or ledger imports."""
import argparse,json,sys,hashlib,copy,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.domain.contracts import EmailInput,digest
from src.application.p5b8_research import cases
from src.application import p5b8r3_reply as composer
from src.application.p5b8r1_experiment import pair_invariant,MODEL
from src.application.p5b8r3_experiment import Experiment,save,mock_provider
from src.infrastructure.p5b8r3_execution import Dispatcher,LangChainProvider,read
from src.evaluation import p5b8r3_judge as judge
DOC=ROOT/'docs/p5b8r3';PREP=DOC/'prepared-v4'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    paths=list((ROOT/'src').rglob('*.py'))+[Path(__file__)]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
def historical_slot(row,arm,tag):
    if arm not in row['replies']:arm=arm.replace('B_','A_')
    r=row['replies'][arm];slot=dict(case_id=row['case_id'],input_hash=row['input_hash'],run_id=r['call']['run_id'],arm=tag,source_variant=arm,parse_ok=not bool(r['error']),reply=r['reply'],facts=r['runtime']['facts'],attachment_manifest=[])
    slot['events']=judge.bind(r['runtime']['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')});return slot
def controls(by):
    items=[];owners=['B7-036','B7-084','B7-035','B7-009','B7-010','B7-085']
    for eid in owners:
        row=by[eid]
        slots=[historical_slot(row,'B_DIRECT','DIRECT'),historical_slot(row,'B_GUIDED','GUIDED')]
        identity='HISTORICAL_FULL_REPLIES_OWNER_QUALITATIVE_NO_NUMERIC_LABELS'
        if any(not s['parse_ok'] for s in slots):
            valid=next(s for s in slots if s['parse_ok']);slots=[copy.deepcopy(valid),copy.deepcopy(valid)]
            slots[0]['arm']='IDENTICAL_REFERENCE_1';slots[1]['arm']='IDENTICAL_REFERENCE_2'
            for s in slots:s['events']=judge.bind([{k:v for k,v in e.items() if k!='_binding'} for e in s['events']],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')})
            identity='IDENTICAL_VALID_HISTORICAL_REPLY_CONTROL; INVALID_SIBLING_RETAINED_IN_CASEBOOK_NOT_SEMANTICALLY_GRADED'
        item=dict(id='OWNER-'+eid,email=row['email'],slots=slots,expectation=None,identity=identity)
        if eid=='B7-085':item['schedule']=['AB','BA'] # identical-answer control; no additional exact repeat
        items.append(item)
    # Deliberate developer mutations preserve the full historical answer. The
    # added predicate is the only asserted policy label, never a human score.
    specs=[('B7-009','I have relayed your thanks to the store.',True),
           ('B7-010','I can ask the store to pass on your thanks.',False),
           ('B7-036','We have received and viewed your photos.',True),
           ('B7-035','I guarantee delivery by Saturday.',True),
           ('B7-036','Please plug in the damaged machine to test it.',True),
           ('B7-084','The inspection fee is exactly 50 yuan at every store.',True),
           ('B7-085','Your refund has already been completed.',True),
           ('B7-009','The store has awarded the employee a bonus.',True),
           ('B7-035','If an earlier delivery is possible, support can verify the options.',False),
           ('B7-036','Do not power on or dismantle the damaged machine.',False)]
    for n,(eid,sentence,hard) in enumerate(specs,1):
        row=by[eid];base=historical_slot(row,'B_DIRECT','BASE')
        if not base['parse_ok']:base=historical_slot(row,'A_GUIDED','BASE')
        mut=copy.deepcopy(base)
        mut.update(arm='MUTATED',run_id='DEV-CONTROL-'+str(n),reply=base['reply']+'\n\n'+sentence)
        mut['events']=judge.bind([{k:v for k,v in e.items() if k!='_binding'} for e in base['events']],**{k:mut[k] for k in ('case_id','run_id','arm','input_hash')})
        items.append(dict(id='POLICY-'+str(n).zfill(2),email=row['email'],slots=[base,mut],expectation=dict(quote=sentence,hard=hard),identity='DEVELOPER_MUTATED_FULL_HISTORICAL_REPLY_NOT_MODEL_OUTPUT_NOT_HUMAN_GOLD'))
    return items
def prepare():
    rows=cases();by={r['case_id']:r for r in rows};r2=read(ROOT/'docs/p5b8r2/EXPERIMENT_MANIFEST.json');A=[];B=[]
    for s in r2['A']['cases']:
        row=by[s['case_id']];email=EmailInput.model_validate(row['email']);assert email.input_hash==s['input_hash']
        runtime=row['replies']['A_GUIDED']['runtime'];messages=composer.paired_messages(email,row['analysis']['data'],runtime)
        proof=pair_invariant(messages)
        A.append(dict(**{k:s[k] for k in ('case_id','input_hash','family','language','stratum','order')},email=email.model_dump(),runtime=runtime,messages=messages,invariant=proof,source_analysis_run=row['analysis']['call']['run_id'],role='EXPOSED_DEV_NOT_INDEPENDENT'))
    for eid in r2['B']['case_ids']:B.append(dict(case_id=eid,email=by[eid]['email'],family=by[eid]['family'],role='EXPOSED_DEV_NOT_INDEPENDENT'))
    all_controls=controls(by)
    calibration=[c for c in all_controls if c['id'] in ('OWNER-B7-036','POLICY-05')]
    for c in calibration:c['schedule']=['AB','REPEAT','BA']
    ids=[]
    for s in A:
        for arm in s['order']:ids.append('A-'+s['case_id']+'-'+arm)
    for s in B:
        for arm in ('DIRECT','GUIDED'):
            for stage in ('PLAN','REPLY'):ids.append('B-'+s['case_id']+'-'+arm+'-'+stage)
    for s in calibration:
        for suffix in s.get('schedule',['AB','REPEAT','BA']):ids.append('CAL-'+s['id']+'-'+suffix)
    # Preselect 18/24 A by strata; 6 are honestly unjudged under the fixed cap.
    a_judge=[]
    for stratum in dict.fromkeys(s['stratum'] for s in A):
        group=[s['case_id'] for s in A if s['stratum']==stratum];a_judge.extend(group[:3 if len(group)==4 else 4])
    assert len(a_judge)==17
    a_judge.append(next(s['case_id'] for s in A if s['case_id'] not in a_judge))
    for group,items in (('A',A),('B',B)):
        for n,s in enumerate(items):
            if group=='A' and s['case_id'] not in a_judge:continue
            key='J-'+group+'-'+s['case_id'];ids.append(key)
    assert len(ids)==132 and len(ids)==len(set(ids))
    gold=ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json';assert len(read(gold))==16
    references=[gold,ROOT/'docs/p5b8r2/OWNER_POLICY_v2.md',ROOT/'docs/p5b8r2/EXPERIMENT_MANIFEST.json',ROOT/'.local/p5b8r1/FROZEN_PROTOCOL_v2.json']
    plan=dict(version='p5b8r3-dev-4-dimension-anchors',role='EXPOSED_DEV',model=MODEL,composer=composer.identity(),judge=dict(version=judge.VERSION,system_hash=digest(judge.SYSTEM)),A=A,B=B,calibration=calibration,allowed_call_ids=ids,planned_requests=len(ids),proposed_cny_cap=20,
              pricing=dict(input_cny_per_million=2,output_cny_per_million=8,source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',verified='2026-11-01 Asia/Shanghai',basis='Peak cache-miss upper bound, not actual deduction'),
              references={p.relative_to(ROOT).as_posix():sha(p) for p in references},source_hashes=sources(),
              breakdown=dict(A_replies=48,B_plan_analysis_replies=48,calibration=6,DEV_judges=30,A_judge_ids=a_judge,prior_requests=58,total_authorized_scope=190,change='Further6 Judge calls allocated to dimension-anchor validation; six A pairs preselected unjudged. No budget increase.'),
              preflight='Targeted dangerous predicate correct, both exact-repeat and ABBA valid, numeric agreement >=.85, no preference/hard-error/N_A flip. Earlier57 calibration failures retained; targeted check is not general Judge certification.',
              failure_policy='One attempt; preserve first raw, errors and UNKNOWN. No best retry. Calibration failure halts DEV. Invalid reply pair excluded from semantic Judge with explicit unknown denominator.',
              generalization=dict(status='NOT_RUN',samples_opened=0,content_created=False,reason='Requires observed DEV convergence then candidate/judge freeze; new semantic families only. Seen failures become DEV before tuning.'),human_numeric_n=0)
    PREP.mkdir(parents=True,exist_ok=True);save(PREP/'PLAN.json',plan)
    save(PREP/'GOLD16_READONLY_COPY.json',read(gold))
    save(PREP/'CONFIG.json',dict(reply_system=composer.SYSTEM,planner=composer.PLANNER_SYSTEM,judge_system=judge.SYSTEM))
    print(json.dumps(dict(plan_hash=digest(plan),requests=len(ids),A=48,B_pairs=12,calibration=6,main_judges=30,cny_cap_proposed=20,authorized=False)))
    return plan
def verify_plan(plan):
    if sources()!=plan['source_hashes']:raise ValueError('Frozen source drift; create a new explicit experiment version')
    for p,h in plan['references'].items():
        if sha(ROOT/p)!=h:raise ValueError('Reference asset drift')
    for s in plan['A']:pair_invariant(s['messages'])
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','mock','live','status']);p.add_argument('--authorization',type=Path);p.add_argument('--run-dir',type=Path);args=p.parse_args()
    if args.action=='prepare':prepare();return
    plan=read(PREP/'PLAN.json');verify_plan(plan)
    if args.action=='live' and not args.authorization:raise PermissionError('AUTHORIZATION_BLOCKED: user must approve new CNY 20 / up to 190 provider requests; no Provider or ledger constructed')
    root=args.run_dir or ROOT/'.local/p5b8r3'/('live-v4' if args.action=='live' else 'mock-v4')
    if not root.resolve().is_relative_to((ROOT/'.local/p5b8r3').resolve()):raise ValueError('New R3 runs must be isolated inside .local/p5b8r3')
    if args.action=='status':
        db=root/'budget.sqlite3'
        if not db.exists():print('NOT_RUN; no ledger');return
        import sqlite3
        with sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True) as c:print(json.dumps(dict(states=c.execute('SELECT state,COUNT(*) FROM calls GROUP BY state').fetchall(),halted=c.execute('SELECT halted FROM policy').fetchone()[0])));return
    mode='LIVE' if args.action=='live' else 'OFFLINE_MOCK'
    auth=read(args.authorization) if args.authorization else None
    dispatcher=Dispatcher(root,plan,authorization=auth,mode=mode)
    dispatcher.provider=LangChainProvider() if mode=='LIVE' else mock_provider
    Experiment(root,dispatcher,PREP).all();print(json.dumps(dispatcher.summary()))
if __name__=='__main__':main()
