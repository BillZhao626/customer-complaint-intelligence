"""R10 authorized first-attempt experiment, with a separate ledger and traces."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.r9 import read, save
from src.domain.contracts import digest
from src.evaluation.experiment_integrity import file_hash

LOCAL = ROOT / '.local/r10-quality-20261109-v1'
DOCS = ROOT / 'docs/r10-quality-20261109-v1'
R9 = ROOT / '.local/r9-quality-20261109-v1'
OWNER = ROOT / 'docs/r8-owner-cal-20261109-v1/owner-overlay.json'
TARGET = (
    'R7H-030', 'R7H-034', 'R7H-035', 'R7H-049', 'R8H-016', 'R8H-022',
    'R91H-023', 'R94H-005', 'R94H-007', 'R94H-012', 'R7H-004'
)


def prepare():
    from src.application.p5b8r1_experiment import MODEL
    from src.domain.contracts import EmailInput
    for version in ('r8', 'r9'):
        marker = ROOT / '.local' / f'{version}-quality-20261109-v1' / 'CLOSED.json'
        assert read(marker)['halted']
    assert read(R9 / 'CLOSED.json')['paid_requests'] == 589
    manifest = read(R9 / 'dev-cases.json')
    assert len(manifest['full_dev_ids']) == 54 and len(manifest['owner_ids']) == 9
    assert len(manifest['cases']) == 59 and read(OWNER)['counts'] == dict(PASS=3, PARTIAL=5, FAIL=1)
    for case in manifest['cases']:
        assert file_hash(ROOT / case['r8_trace']) == case['r8_trace_sha256']
    manifest['diagnostics'] = [
        case for name in ('holdout-v1', 'holdout-v4') for case in read(R9 / f'{name}-cases.json')
        if case['case_id'] in TARGET
    ]
    for case in manifest['cases'] + manifest['diagnostics']:
        cid = case['case_id']
        assert EmailInput.model_validate(case['email']).input_hash == case['input_hash']
        historical_revision = 'holdout-v1' if cid.startswith('R91') else 'holdout-v4' if cid.startswith('R94') else 'dev-v2'
        old = R9 / 'traces' / historical_revision / cid / 'GUIDED-reply.json'
        assert read(old)['slot']['input_hash'] == case['input_hash']
        case.update(r9_trace=old.relative_to(ROOT).as_posix(), r9_trace_sha256=file_hash(old))
    save(LOCAL / 'dev-cases.json', manifest)
    plan = dict(authorization_scope='R10-20261109-ONE-LEDGER', planned_requests=600, proposed_cny_cap=20,
                allowed_call_ids=[f'R10-{i:03}' for i in range(1, 601)],
                pricing=dict(input_cny_per_million=2, output_cny_per_million=8, checked='2026-11-09',
                             source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
                             basis='peak cache-miss token estimate; actual account charge unknown'))
    save(LOCAL / 'plan.json', plan)
    save(LOCAL / 'authorization.json', dict(scope=plan['authorization_scope'], cny=20, provider_requests=600,
        plan_hash=digest(plan), historical_authorization_reused=False, date='2026-11-09 Asia/Shanghai',
        user_approval_verbatim='本轮建议使用独立新账本，预算上限人民币20元、最多600次底层Provider请求，以先到者为限；只有我正式发送本消息才授权该额度，不得复用关闭的R9账本。'))
    save(LOCAL / 'design.json', dict(model=MODEL, attempts=1, retries=0,
        pass_rule='The R9 four-status evidence rule is retained. Service and evidence audits are reported separately, including conflicts.',
        roles=['targeted exposed diagnostic', '59 unique fixed DEV/Owner', 'designed Judge controls', 'post-freeze synthetic transfer'],
        primary='All 54 new fixed first answers and 9 Owner anchors, no confirmed serious factual error or new regression',
        human_gold='Prior nine qualitative anchors are immutable and exposed. New numerical ratings require independent human input.'))


def freeze(revision, inputs=(), independent=None):
    from src.evaluation.experiment_integrity import freeze as freeze_sources, verify
    names = ('plan.json', 'authorization.json', 'dev-cases.json', 'design.json')
    manifest = freeze_sources(ROOT, inputs=[*(LOCAL / n for n in names), OWNER, *inputs])
    if independent:
        manifest['independent_dataset'] = {k: str(v.resolve()) for k, v in independent.items()}
    verify(manifest)
    return save(LOCAL / 'freezes' / f'{revision}.json', manifest)


class Run:
    def __init__(self, revision, workers=1):
        from src.infrastructure.p5b8r3_execution import Dispatcher
        from src.infrastructure.structured_reply_provider import StructuredReplyProvider
        if (LOCAL / 'CLOSED.json').exists():
            raise PermissionError('R10 closed')
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
        return self.dispatcher.call(f'R10-{slot:03}', messages, dict(payload, logical_identity=logical))

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


def close(revision):
    run=Run(revision)
    run.dispatcher.halt('R10_COMPLETED_NO_REUSE')
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



def evaluate(revision, selection, workers):
    manifest = read(LOCAL / 'dev-cases.json')
    cases = manifest['cases']
    if selection == 'target':
        cases = [row for row in cases + manifest['diagnostics'] if row['case_id'] in TARGET or row['case_id'] in manifest['owner_ids']]
    run = Run(revision, workers)
    def assess(item):
        i, case = item
        cid = case['case_id']
        old = ROOT / case['r9_trace']
        if file_hash(old) != case['r9_trace_sha256']:
            raise ValueError('Historical response drift')
        new = run.generate(case, 'EXPOSED_DEV')
        historical = read(old)
        result = run.judge(f'DEVPAIR-{cid}', case['email'], [historical['slot'], new['slot']], reverse=bool(i % 2))
        print(cid, result['status'], flush=True)
    run.each(assess, enumerate(cases))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'freeze', 'evaluate', 'close'))
    parser.add_argument('--revision', default='dev-v1')
    parser.add_argument('--selection', choices=('target', 'all'), default='target')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'freeze':
        freeze(args.revision)
    elif args.command == 'evaluate':
        evaluate(args.revision, args.selection, args.workers)
    else:
        close(args.revision)
