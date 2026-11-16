"""Authorized R11 continuation, isolated 2,000-request ledger and first attempts."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.r11_owner5 import ROOT, LOCAL as L, DOCS as D, PRIOR, read, save, sha

sys.path.insert(0, str(ROOT))
from src.domain.contracts import EmailInput, digest
from src.evaluation import service_judge as judge
from src.evaluation.experiment_integrity import freeze
from src.evaluation.p5b8r4_judge import quote_inventory
from src.infrastructure.p5b8r3_execution import Dispatcher
from src.infrastructure.structured_reply_provider import StructuredReplyProvider
import scripts.r11_followthrough_run as previous

previous.LOCAL = L
previous.DOCS = D


def initialize():
    approval = '我正式授权本轮新增最多2,000次底层Provider请求，不设置人民币金额硬上限，另建独立账本，原4,000次关闭账本不得复用。额度内自主推进，不需要逐批申请批准。'
    plan = dict(
        authorization_scope='R11-OWNER5-P0-P05-P1-2000-20261110',
        planned_requests=2000, proposed_cny_cap=None, budget_mode='REQUEST_ONLY',
        allowed_call_ids=[f'R11O-{n:04}' for n in range(1, 2001)],
        pricing=dict(input_cny_per_million=2, output_cny_per_million=8,
                     basis='Retained conservative cache-miss estimate; actual debit unknown',
                     historical_price_date='2026-11-09'),
    )
    save(L / 'plan.json', plan)
    save(L / 'authorization.json', dict(
        scope=plan['authorization_scope'], provider_requests=2000, cny=None, budget_mode='REQUEST_ONLY',
        monetary_cap_explicitly_waived=True, plan_hash=digest(plan), authorization='this_user_message',
        user_approval_verbatim=approval, date='2026-11-10 Asia/Shanghai',
        supplement_sha256=sha(L / 'R11_P0_Judge_P05_E2E_P1_Academic_2000Call_Supplement.md'),
        original_closed_ledger_sha256=sha(PRIOR / 'live/budget.sqlite3'),
    ))
    print('Prepared independent 2000 request authorization. No requests sent.')


def freeze_revision(revision, dataset):
    inputs = [L / 'plan.json', L / 'authorization.json', dataset,
              D / 'JUDGE_BOUNDARY_CONTRACT.md', D / 'owner-all-version-map.json']
    manifest = freeze(ROOT, inputs=inputs)
    save(L / 'freezes' / f'{revision}.json', manifest)
    for relative, expected in manifest['source_hashes'].items():
        source, target = ROOT / relative, L / 'source-snapshots' / revision / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(source.read_bytes())
        assert sha(target) == expected
    print('FROZEN', revision, len(manifest['source_hashes']))


class Run(previous.Run):
    def __init__(self, revision, workers=2):
        if (L / 'CLOSED.json').exists():
            raise PermissionError('This ledger is closed')
        import src.application.p5b3_runtime
        self.revision, self.workers = revision, workers
        plan = read(L / 'plan.json')
        self.dispatcher = Dispatcher(L / 'live', plan, authorization=read(L / 'authorization.json'),
                                     provider=StructuredReplyProvider(), mode='LIVE', max_inflight=workers)
        self.dispatcher.plan = dict(plan, execution_integrity=read(L / 'freezes' / f'{revision}.json'))
        self.db = L / 'call-map.sqlite3'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE IF NOT EXISTS logical (key TEXT UNIQUE NOT NULL, slot INTEGER PRIMARY KEY CHECK(slot BETWEEN 1 AND 2000))')

    def invoke(self, key, messages, payload):
        identity = self.revision + '-' + key
        with sqlite3.connect(self.db, timeout=20) as db:
            db.execute('BEGIN IMMEDIATE')
            found = db.execute('SELECT slot FROM logical WHERE key=?', (identity,)).fetchone()
            number = found[0] if found else db.execute('SELECT COALESCE(MAX(slot),0)+1 FROM logical').fetchone()[0]
            if not found:
                db.execute('INSERT INTO logical VALUES (?,?)', (identity, number))
        return self.dispatcher.call(f'R11O-{number:04}', messages,
                                    dict(payload, logical_identity=identity, parent_experiment=self.revision))

    def generate(self, case):
        uncertain = L / 'traces' / self.revision / case['case_id'] / 'GENERATION_UNCERTAIN.json'
        if uncertain.exists():
            return read(uncertain)
        return super().generate(case)

    def score(self, item):
        name = item['score_name']
        path = L / 'judgments' / self.revision / f'{name}.json'
        if path.exists():
            return read(path)
        source = EmailInput.model_validate(item['email'])
        slots = item['slots']
        if item.get('trace_path'):
            trace = ROOT / item['trace_path']
            if not trace.is_file():
                return save(path, dict(parsed=None, error='MISSING_FIRST_GENERATION_RECORD', not_dispatched=True,
                                       call=dict(identity=None, metadata={}), payload=dict(customer=item['email'], answers=[]), key={}))
            slots = [read(trace)['slot']]
        if not all(s['parse_ok'] and s['reply'].strip() for s in slots):
            return save(path, dict(parsed=None, error='UNASSESSABLE_FIRST_STRUCTURE', not_dispatched=True,
                                   call=dict(identity=None, metadata={}), payload=dict(customer=item['email'], answers=slots), key={}))
        if len(slots) == 2:
            payload, key = judge.blind_pair(source, slots, reverse=item.get('reverse', False))
        else:
            slot = dict(slots[0], slot='X')
            slot['deterministic_fact_audit'] = judge.audit_slot(slot, source)
            slot['quote_inventory'] = quote_inventory(source, slot)
            payload = dict(customer=source.model_dump(), answers=[slot], judge_version=judge.VERSION)
            key = dict(X=dict(run_id=slot['run_id']))
        judge.prepare_payload(payload)
        if item.get('wire') == 'MATRIX_V1':
            payload['judge_wire'] = 'MATRIX_V1'
        schema = judge.output_schema(payload)
        from src.application.reply_guidance import service_checks
        standard = service_checks(source, dict(facts=slots[0].get('facts', {}), context={}))
        payload['first_reply_standard'] = dict(
            unit='First reply obligations using supplied evidence',
            source_triggered_checks=standard['topics'],
            order_reference_rule=standard['intake_rule'],
            required_paths=standard['path_requirements'],
        )
        payload['output_schema'] = schema
        system = judge.SYSTEM
        if item.get('wire') == 'MATRIX_V1':
            from src.evaluation.service_judge_matrix import INSTRUCTION
            system += INSTRUCTION
        contract = {}
        presentation = 'STRICT_JSON_OBJECT'
        if item.get('wire') == 'STRICT_TOOL':
            from src.evaluation.service_judge_protocol import strict_transport_schema
            contract['strict_output_contract'] = dict(name='assess_service', schema=strict_transport_schema(schema))
            presentation = 'STRICT_TOOL_ARGUMENTS'
            system += '\nReturn the assess_service tool arguments only. This function returns evaluation data and executes no business operation.\n'
        call = self.invoke('JUDGE-' + name, [('system', system), ('human', json.dumps(payload, ensure_ascii=False))],
                           dict(stage='judge', dataset_role=item.get('role', 'JUDGE_DEV'),
                                case_id=source.email_id, input_hash=source.input_hash,
                                evaluator=judge.identity(), presentation=presentation, **contract))
        try:
            parsed, error = judge.parse(call['raw'], payload), None
        except (ValueError, TypeError, KeyError, AttributeError, AssertionError) as exc:
            parsed, error = None, str(exc)
        result = dict(parsed=parsed, error=error, call=call, payload=payload, key=key,
                      evaluator=judge.identity(), reference_provenance=item.get('reference_provenance'))
        save(path, result)
        print(name, 'PARSED' if parsed else error, flush=True)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('initialize', 'freeze', 'score', 'generate', 'summary', 'close'))
    parser.add_argument('--revision', default='judge-pilot-v17')
    parser.add_argument('--dataset')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.command == 'initialize':
        initialize()
        return
    dataset = L / args.dataset if args.dataset else None
    if args.command == 'freeze':
        freeze_revision(args.revision, dataset)
        return
    run = Run(args.revision, args.workers)
    if args.command == 'summary':
        print(json.dumps(run.dispatcher.summary(), ensure_ascii=False))
        return
    if args.command == 'close':
        run.dispatcher.halt('R11_2000_CLOSEOUT_COMPLETE_NO_REUSE')
        save(L / 'CLOSED.json', run.dispatcher.summary())
        return
    items = read(dataset)
    if isinstance(items, dict):
        items = items['cases']
    run.each(run.score if args.command == 'score' else run.generate, items)


if __name__ == '__main__':
    main()
