"""R9's one authorized ledger, immutable first attempts and shared production replay."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOCAL = ROOT / '.local/r9-quality-20261109-v1'
DOCS = ROOT / 'docs/r9-quality-20261109-v1'
R7 = ROOT / '.local/r7-20261106-v1'
R8 = ROOT / '.local/r8-quality-20261109-v1'
R8_DOCS = ROOT / 'docs/r8-quality-20261109-v1'
OWNER = ROOT / 'docs/r8-owner-cal-20261109-v1/owner-overlay.json'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, value):
    from src.application.p5b8r1_experiment import write_first
    if path.exists():
        if read(path) != value:
            raise ValueError(f'Immutable result drift: {path}')
    else:
        write_first(path, value)
    return value


def prepare():
    from src.domain.contracts import digest
    from src.evaluation.experiment_integrity import file_hash
    from src.application.p5b8r1_experiment import MODEL
    from src.application.service_response import identity as composer_identity
    from src.evaluation.owner_calibrated_judge import identity as judge_identity

    LOCAL.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    target = LOCAL / 'R9_Codex_Master_Prompt.md'
    if not target.exists():
        shutil.copy2(Path.home() / 'Downloads/R9_Codex_Master_Prompt.md', target)
    owner = read(OWNER)
    r8closed = read(R8 / 'CLOSED.json')
    assert owner['counts'] == dict(PASS=3, PARTIAL=5, FAIL=1)
    assert r8closed['paid_requests'] == 432 and r8closed['halted']
    saved = read(R8_DOCS / 'dev-results.json')
    assert saved['n'] == 54 and saved['counts']['new_verdict'] == dict(PASS=51, UNKNOWN=3)
    r7_cases = read(R7 / 'holdout.json')
    assert len(r7_cases) == len({c['email']['email_id'] for c in r7_cases}) == 54
    owner_ids = {c['case_id'] for c in owner['cases']}
    cases = {}
    for v in owner['cases']:
        path = ROOT / v['trace_path']
        assert file_hash(path) == v['trace_sha256']
        r = read(path)
        cases[v['case_id']] = dict(email=r['email'], r8_trace=v['trace_path'],
                                   owner=v['owner_verdict'], family=v['semantic_family'],
                                   email_quality=v['email_quality']['flag'])
    for case in r7_cases:
        cid = case['email']['email_id']
        cases.setdefault(cid, dict(email=case['email'], family=case['family'],
                                   r8_trace=(R8 / 'traces' / f'DEV-v2-{cid}' / 'GUIDED-reply.json').relative_to(ROOT).as_posix(),
                                   owner=None, email_quality='R7_SYNTHETIC'))
    for cid, case in cases.items():
        old = read(ROOT / case['r8_trace'])
        case.update(case_id=cid, input_hash=old['slot']['input_hash'], r8_run=old['slot']['run_id'],
                    r8_reply_hash=digest(old['slot']['reply']), r8_composer=old['composer'],
                    r8_trace_sha256=file_hash(ROOT / case['r8_trace']))
    save(LOCAL / 'dev-cases.json', dict(cases=list(cases.values()), owner_ids=list(c['case_id'] for c in owner['cases']),
                                        full_dev_ids=[c['email']['email_id'] for c in r7_cases]))
    assert len(owner_ids) == 9 and len(cases) == 59
    plan = dict(
        authorization_scope='R9-20261109-ONE-LEDGER', planned_requests=600, proposed_cny_cap=30,
        allowed_call_ids=[f'R9-{i:03}' for i in range(1, 601)],
        pricing=dict(input_cny_per_million=2, output_cny_per_million=8, checked='2026-11-09',
                     source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                     basis='peak cache miss bound; actual account charge unavailable'),
    )
    save(LOCAL / 'plan.json', plan)
    save(LOCAL / 'authorization.json', dict(
        scope=plan['authorization_scope'], cny=30, provider_requests=600, plan_hash=digest(plan),
        user_approval_verbatim='本轮按附件新建独立R9模型调用账本，以人民币30元、最多600次底层Provider请求作为总上限，额度内自行安排DEV、Judge和独立泛化，不复用关闭的历史账本，不逐批请求重复批准。',
        historical_authorization_reused=False, date='2026-11-09 Asia/Shanghai',
    ))
    save(LOCAL / 'design.json', dict(
        roles=['owner nine first', 'complete 54 fixed DEV', 'blinded Judge controls', 'post-freeze synthetic transfer'],
        first_attempt='Keep every first response. Compare a fixed complete revision, never best per item.',
        model=MODEL, composer=composer_identity(), judge=judge_identity(),
        authority='Owner qualitative anchors; development AI evidence review; no independent human numeric Gold',
        pass_standard='Useful complete response to current primary goals, scoped practical help, verified facts and truthful pending actions, no material hard error',
        initial_call_allocation={'dev_analysis_reply':118,'dev_pair_judge':59,'judge_control_min':48,
                                 'holdout_min_24_analysis_reply_judge':72,'iteration_and_reserve':303},
        historic_ledger_hashes={name:file_hash(path) for name,path in
                                [('R8-active-closed', R8/'live/budget.sqlite3'),
                                 ('R8-close-marker',R8/'CLOSED.json'),
                                 ('R8-delivered-copy',R8_DOCS/'R8_TRACE_AND_LEDGER/budget-CLOSED.sqlite3')]},
    ))
    print('Prepared 9 anchors, 54 fixed DEV and 59 unique inputs', flush=True)


def freeze(revision, inputs=(), independent=None):
    from src.evaluation.experiment_integrity import freeze as freeze_sources, verify
    paths = [LOCAL / name for name in ('R9_Codex_Master_Prompt.md', 'plan.json', 'authorization.json',
                                        'dev-cases.json', 'design.json')]
    manifest = freeze_sources(ROOT, inputs=[*paths, OWNER, *inputs])
    if independent:
        manifest['independent_dataset'] = {k:str(v.resolve()) for k,v in independent.items()}
        verify(manifest)
    return save(LOCAL / 'freezes' / f'{revision}.json', manifest)


class Run:
    def __init__(self, revision, workers=1):
        from src.infrastructure.p5b8r3_execution import Dispatcher
        from src.infrastructure.structured_reply_provider import StructuredReplyProvider
        if (LOCAL / 'CLOSED.json').exists():
            raise PermissionError('R9 closed')
        self.revision = revision
        self.workers = workers
        plan = read(LOCAL / 'plan.json')
        self.dispatcher = Dispatcher(LOCAL / 'live', plan, authorization=read(LOCAL / 'authorization.json'),
                                     provider=StructuredReplyProvider(), mode='LIVE',max_inflight=workers)
        self.dispatcher.plan = dict(plan, execution_integrity=read(LOCAL / 'freezes' / f'{revision}.json'))
        self.calls = LOCAL / 'call-map.sqlite3'
        with sqlite3.connect(self.calls) as db:
            db.execute('CREATE TABLE IF NOT EXISTS logical (key TEXT UNIQUE NOT NULL, slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 600))')

    def invoke(self, key, messages, payload):
        logical = f'{self.revision}-{key}'
        with sqlite3.connect(self.calls) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT slot FROM logical WHERE key=?', (logical,)).fetchone()
            if row:
                slot = row[0]
            else:
                slot = db.execute('SELECT COALESCE(MAX(slot),0)+1 FROM logical').fetchone()[0]
                db.execute('INSERT INTO logical VALUES (?,?)', (logical,slot))
        return self.dispatcher.call(f'R9-{slot:03}', messages, dict(payload, logical_identity=logical))

    def each(self, fn, cases):
        if self.workers==1:
            for case in cases:
                fn(case)
            return
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for _ in pool.map(fn,cases):
                pass

    def generate(self, case, role):
        from src.application.r6u0_workflow import generate
        cid = case['email']['email_id']
        folder = LOCAL / 'traces' / self.revision / cid
        path = folder / 'GUIDED-reply.json'
        if path.exists():
            record = read(path)
            if record['slot']['input_hash'] != case['input_hash']:
                raise ValueError('Saved trace input drift')
            return record
        result = generate(case['email'], lambda stage,m,p:self.invoke(f'{cid}-{stage}',m,p), folder,
                          role=role, arms=('GUIDED',), revision=self.revision,
                          authorized_facts=case.get('authorized_facts'))['GUIDED']
        print(f'{self.revision} {cid} first: analysis={result["analysis_parse"]["status"]}, reply={result["parse"]["status"]}', flush=True)
        return result

    def judge(self, name, email, slots, *, reverse=False, role='JUDGE'):
        from src.domain.contracts import EmailInput
        from src.evaluation import owner_calibrated_judge as j
        path = LOCAL / 'judgments' / self.revision / f'{name}.json'
        if path.exists():
            return read(path)
        email = EmailInput.model_validate(email)
        if not all(s['parse_ok'] and s['reply'].strip() for s in slots):
            return save(path, dict(status='UNASSESSABLE_FIRST_STRUCTURE', parsed=None, error='First reply not structurally eligible'))
        if len(slots) == 2:
            payload, key = j.blind_pair(email, slots, reverse=reverse)
            system = j.SYSTEM
        else:
            slot = dict(slots[0], slot='X')
            slot['deterministic_fact_audit'] = j.audit_slot(slot, email)
            slot['quote_inventory'] = j.prior.quote_inventory(email, slot)
            payload = dict(customer=email.model_dump(),answers=[slot],judge_version=j.VERSION)
            key = {'X': {'run_id':slot['run_id']}}
            system = j.SYSTEM+'\nAssess the ONE answer X. Return one answer and preference UNKNOWN.'
        call = self.invoke(name, [('system',system),('human',json.dumps(payload,ensure_ascii=False))],
                           dict(stage='judge',dataset_role=role,case_id=email.email_id,
                                input_hash=email.input_hash,judge=j.identity()))
        try:
            parsed = j.parse(call['raw'], payload)
            error = None
        except (ValueError, KeyError, TypeError, AttributeError, AssertionError) as exc:
            parsed = None
            error = str(exc)
        return save(path, dict(parsed=parsed,error=error,call=call,payload=payload,key=key,
                               status='PARSED' if parsed else 'UNKNOWN_PROTOCOL'))


def dev(revision, selection,workers=1):
    manifest = read(LOCAL / 'dev-cases.json')
    run = Run(revision,workers)
    cases=[c for c in manifest['cases'] if selection!='owner' or c['case_id'] in manifest['owner_ids']]
    run.each(lambda case:run.generate(case,'EXPOSED_DEV'),cases)


def dev_judge(revision, selection,workers=1):
    manifest = read(LOCAL / 'dev-cases.json')
    run = Run(revision,workers)
    def assess_case(item):
        i,case=item
        cid=case['case_id']
        if selection=='owner' and cid not in manifest['owner_ids']:
            return
        old = read(ROOT / case['r8_trace'])
        new = read(LOCAL / 'traces' / revision / cid / 'GUIDED-reply.json')
        slots=[old['slot'],new['slot']]
        run.judge(f'DEVPAIR-{cid}',case['email'],slots,reverse=bool(i%2))
        if cid in manifest['owner_ids']:
            run.judge(f'DEVPAIR-{cid}-SWAP',case['email'],slots,reverse=not bool(i%2))
    run.each(assess_case,enumerate(manifest['cases']))


def close(revision):
    run=Run(revision)
    run.dispatcher.halt('R9_COMPLETED_NO_REUSE')
    summary=run.dispatcher.summary()
    save(LOCAL/'CLOSED.json',summary)
    save(DOCS/'ledger-summary.json',summary)
    with run.dispatcher.connect() as db, (DOCS/'request-ledger.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['request','logical','run_id','state','input_tokens','output_tokens','total_tokens','upper_cny'])
        logicals=dict(sqlite3.connect(run.calls).execute('SELECT slot,key FROM logical'))
        for ident,rid,state,upper,meta in db.execute('SELECT identity,run_id,state,COALESCE(settled_micro,reserved_micro),metadata FROM calls ORDER BY identity'):
            p=json.loads(meta)['provider'] if meta else {}
            w.writerow([ident,logicals[int(ident.split('-')[1])],rid,state,p.get('input_tokens'),p.get('output_tokens'),p.get('total_tokens'),upper/1e6])
    print(summary,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','freeze','dev','dev-judge','close'))
    parser.add_argument('--revision',default='dev-v1')
    parser.add_argument('--selection',choices=('owner','all'),default='all')
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args()
    if args.command=='prepare':
        prepare()
    elif args.command=='freeze':
        freeze(args.revision)
    elif args.command=='dev':
        dev(args.revision,args.selection,args.workers)
    elif args.command=='dev-judge':
        dev_judge(args.revision,args.selection,args.workers)
    else:
        close(args.revision)
