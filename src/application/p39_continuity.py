"""Failure-inclusive fixed experiment. Frozen prediction chain is imported unchanged."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from src.application.p39_context_live import (
    ContextLiveAnalyzer, ContextLiveService, verify_runtime as verify_parent, write_new,
)
from src.application.p39_v2 import messages
from src.domain.contracts import EmailInput, digest
from src.domain.analysis_v31_context import ContextAnalysisV31, stored_context_analysis
from src.infrastructure.context_repository import ReadOnlyContextRepository
from src.infrastructure.p39_live_context import ContextLiveRepository

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'evaluation-continuity-v1'


def source_hash():
    paths = ('src/application/p39_continuity.py', 'src/infrastructure/p39_continuity_budget.py',
             'scripts/p39_continuity.py')
    return digest({p: sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})


def build_runtime(parent, evidence, out):
    verify_parent(parent)
    if not evidence.strip():
        raise PermissionError('Explicit continuity authorization required')
    body = dict(version=VERSION, candidate=parent['candidate'], parent_runtime=parent,
                execution_chain_hash=source_hash(), runtime_directory=str(Path(out).resolve()),
                offline_test_fixture=parent['offline_test_fixture'], price_receipt=parent['price_receipt'],
                authorization_evidence=evidence, authorization_sha256=sha256(evidence.encode()).hexdigest(),
                fixed_requests=64, combined_fixed_ceiling=65, challenger_max=6, combined_auto_ceiling=71,
                reply_status='unreviewed_unsent', human_content_approval=None)
    body['runtime_hash'] = digest(body)
    verify_runtime(body)
    return body


def verify_runtime(rt):
    body = dict(rt); claim = body.pop('runtime_hash')
    if digest(body) != claim or rt['version'] != VERSION or rt['execution_chain_hash'] != source_hash():
        raise ValueError('Continuity execution identity drift')
    verify_parent(rt['parent_runtime'])
    if (rt['candidate'] != rt['parent_runtime']['candidate']
        or rt['price_receipt'] != rt['parent_runtime']['price_receipt']
        or rt['offline_test_fixture'] != rt['parent_runtime']['offline_test_fixture']
        or sha256(rt['authorization_evidence'].encode()).hexdigest() != rt['authorization_sha256']
        or (rt['fixed_requests'], rt['combined_fixed_ceiling'], rt['challenger_max'], rt['combined_auto_ceiling']) != (64,65,6,71)
        or rt['reply_status'] != 'unreviewed_unsent' or rt['human_content_approval'] is not None):
        raise ValueError('Continuity scope drift')
    if not rt['offline_test_fixture'] and Path(rt['runtime_directory']) != (ROOT/'.local/p39/v2/r3-runtime').resolve():
        raise PermissionError('One continuation runtime only')
    if Path(rt['runtime_directory']) == Path(rt['parent_runtime']['runtime_directory']):
        raise PermissionError('Historical runtime is read-only')


def diagnose(run):
    """Earliest verifiable rejection; diagnosis never becomes a model prediction."""
    from src.application.live_execution import strict_json
    from src.application.reply_review import check
    if not run.attempts:
        return dict(stage='dispatch', error='missing_attempt', prediction=False)
    raw = run.attempts[-1].raw_output
    stage = 'parsing'
    try:
        data = strict_json(raw)
        stage = 'schema'
        value = ContextAnalysisV31.model_validate(data)
        stage = 'semantic_validation'
        value.validate_input(run.email)
        stage = 'safety_gate'
        check(value)
    except (ValueError, TypeError) as exc:
        return dict(stage=stage, error=str(exc), exception_type=type(exc).__name__, prediction=False,
                    raw_sha256=sha256(raw.encode()).hexdigest() if raw is not None else None)
    return dict(stage='accepted' if run.result else 'service', error=None, prediction=False)


def engineering_check(run, rt, counter):
    """Check economics and infrastructure before considering model quality."""
    arm = run.config.parameters.get('arm'); m = rt['candidate']
    if arm not in ('A','B') or run.config.model_dump() != m['configs'][arm] or run.input_hash != run.email.input_hash:
        raise ValueError('Run identity drift')
    if run.status not in ('succeeded','failed') or len(run.attempts) != 1:
        raise ValueError('Unknown send or attempt count')
    a = run.attempts[0]; meta = a.metadata
    if meta.get('dispatch') != 'response_received':
        raise ValueError('Response receipt missing')
    if meta.get('resolved_model') != m['configs'][arm]['model_id']:
        raise ValueError('Resolved model drift')
    if meta.get('actual_system_prompt_sha256') != m['configs'][arm]['prompt_hash']:
        raise ValueError('Actual Prompt identity drift')
    values = [meta.get(k) for k in ('input_tokens','output_tokens','total_tokens','cache_hit_tokens','cache_miss_tokens')]
    bound = counter.measure(messages(run.email,arm))
    cost = run.metadata.get('cost_cny'); reserve = meta.get('reserved_upper_cny')
    payload = meta.get('actual_payload_sha256'); size = meta.get('actual_payload_bytes')
    if (any(type(v) is not int or v < 0 for v in values) or values[2] != values[0]+values[1]
        or values[3]+values[4] != values[0] or values[0] > bound['input_token_reserve'] or values[1] > 4000
        or type(cost) not in (int,float) or not math.isfinite(cost) or cost < 0
        or type(reserve) not in (int,float) or not math.isfinite(reserve) or cost > reserve
        or meta.get('cost_cny') != cost
        or not isinstance(payload,str) or len(payload) != 64 or any(c not in '0123456789abcdef' for c in payload)
        or type(size) is not int or not 0 < size <= 50000
        or meta.get('finish_reason') not in ('stop','length','content_filter')):
        raise ValueError('Usage, cost or payload anomaly')
    p = rt['price_receipt']['prices']
    expected = (values[0]*p['input_cny_per_million']+values[1]*p['output_cny_per_million'])/1e6
    if abs(cost-expected) > 1e-10:
        raise ValueError('Price calculation drift')
    if any(run.metadata.get(k) != 0 for k in ('sdk_retries','application_retries','json_repair_retries')) or run.metadata.get('fallback') is not False:
        raise ValueError('Retry or fallback drift')
    if (run.status == 'succeeded') != (run.result is not None):
        raise ValueError('Failed output promoted to success')
    if run.result:
        if a.error is not None or a.contract_status != 'passed':
            raise ValueError('Accepted attempt inconsistency')
        stored_context_analysis(run)
        return 'accepted'
    if not a.error or a.error.error_type not in ('empty_response','invalid_json','raw_schema_invalid'):
        raise ValueError('Non-quality execution failure')
    d = diagnose(run)
    if a.error.error_type == 'raw_schema_invalid' and d['stage'] not in ('schema','semantic_validation','safety_gate'):
        raise ValueError('Unexplained service rejection')
    return 'model_quality_failure'


def load_runs(rt):
    runs = []
    for directory in (rt['parent_runtime']['runtime_directory'], rt['runtime_directory']):
        db = Path(directory)/'runs.sqlite3'
        if db.exists():
            runs.extend(ReadOnlyContextRepository(db).list_runs())
    return runs


def reconcile(rt, budget):
    """All reservations are matched to immutable saved runs; no inferred dispatch."""
    verify_runtime(rt)
    state = budget.summary()
    if state['halted'] or state['active_lease'] or state['active_wire_claim']:
        raise PermissionError('Stopped or unsettled dispatch')
    return ordered_runs(rt,budget)


def ordered_runs(rt,budget):
    """Read-only schedule audit, also used before acknowledging an old stop."""
    runs = load_runs(rt); by = {r.run_id:r for r in runs}
    if len(by) != len(runs):
        raise ValueError('Duplicate durable run')
    with budget.connection() as c:
        events = c.execute("SELECT run_id,upper_cny FROM events WHERE kind='v2_reserved' ORDER BY id").fetchall()
        settled = {r[0] for r in c.execute("SELECT run_id FROM events WHERE kind='settled'")}
        completed = {r[0]:r[1] for r in c.execute('SELECT run_id,completed FROM wire_payloads')}
    if len(events) != len(runs) or len(events) > 64:
        raise ValueError('Reservation/run count mismatch')
    ordered = []
    for index,(rid,reserve) in enumerate(events):
        run = by.get(rid); step = rt['candidate']['schedule'][index]
        row = rt['candidate']['inputs'][step['input_index']]
        if (not run or run.input_hash != row['input_hash'] or run.email.model_dump() != row['email']
            or run.config.model_dump() != rt['candidate']['configs'][step['arm']]
            or 'settled:'+rid not in settled or completed.get(rid) != 1
            or run.attempts[-1].metadata.get('reserved_upper_cny') != reserve):
            raise ValueError('Schedule/settlement drift')
        engineering_check(run,rt,budget.counter)
        ordered.append(run)
    return ordered


def binding(run, rt, counter):
    return dict(run_id=run.run_id, input_hash=run.input_hash, config_hash=digest(run.config.model_dump()),
                run_hash=digest(run.model_dump()), status=run.status, classification=engineering_check(run,rt,counter),
                attempt_hash=digest(run.attempts[0].model_dump()), diagnosis=diagnose(run),
                reply_status='unreviewed_unsent', human_review='pending')


def run_fixed(rt, budget, settings, provider=None, limit=64):
    from dataclasses import replace
    verify_runtime(rt)
    if type(limit) is not int or not 0 <= limit <= 64:
        raise ValueError('Invalid fixed-plan limit')
    settings = replace(settings,max_tokens=4000,max_attempts=1); settings.validate()
    out = Path(rt['runtime_directory']); out.mkdir(parents=True,exist_ok=True)
    repo = ContextLiveRepository(out/'runs.sqlite3')
    analyzers = {a:ContextLiveAnalyzer(settings,rt['candidate'],a,budget.counter,provider) for a in ('A','B')}
    try:
        while True:
            saved = reconcile(rt,budget)
            for r in saved:
                budget.record(binding(r,rt,budget.counter))
            if len(saved) >= 8:
                budget.checkpoint(saved[:8])
            if len(saved) >= limit:
                break
            step = rt['candidate']['schedule'][len(saved)]
            email = EmailInput.model_validate(rt['candidate']['inputs'][step['input_index']]['email'])
            run = ContextLiveService(repo,analyzers[step['arm']],budget=budget).analyze(email)
            reread = ReadOnlyContextRepository(out/'runs.sqlite3').get(run.run_id)
            if reread is None or reread.model_dump() != run.model_dump():
                raise ValueError('SQLite reload drift')
            path = out/('run-'+run.run_id+'.json')
            if path.exists():
                if json.loads(path.read_text(encoding='utf8')) != run.model_dump():
                    raise ValueError('Export drift')
            else:
                write_new(path,run.model_dump())
            category = engineering_check(run,rt,budget.counter)
            budget.record(binding(run,rt,budget.counter))
            print(json.dumps(dict(step=len(saved)+1,pair=step['pair'],arm=step['arm'],run_id=run.run_id,
                                  status=run.status,classification=category,tokens=run.attempts[0].metadata['total_tokens']),ensure_ascii=False),flush=True)
    except BaseException:
        budget.halt('r3_engineering_safety_stop')
        raise
    return dict(version=VERSION,attempted=len(saved),planned=64,accepted=sum(r.result is not None for r in saved),
                failed=sum(r.result is None for r in saved),not_attempted=64-len(saved),budget=budget.summary(),reply_status='unreviewed_unsent')
