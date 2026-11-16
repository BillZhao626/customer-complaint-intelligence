"""Final R2 read-only aggregation. No provider import, replay, repair or old writes.

Default writes four NEW final artifacts exclusively. --check builds in memory and
prints compact counts only. --out may point at a fresh isolated review directory.
"""
from collections import Counter, defaultdict
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import argparse
import csv
import json
import os
import re
import socket
import sqlite3
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false', LANGSMITH_TRACING='false',
                  LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')
from src.domain.contracts import EmailInput, AnalysisRun
from src.application.product_workflow import analysis_data
from src.application.product_quality import inspect as original_guard
from src.application.p5b5r2_guard import inspect as r2_guard, VERSION as GUARD_VERSION
from src.evaluation.p5b5 import read, hashfile
from src.evaluation.p5b5r2_judge import diagnose, RULE_VERSION

LOCAL = ROOT/'.local/p5b5r2'
HISTORY = ROOT/'.local/p5b5-live-20261030-v1'
VERSION = 'p5b5r2-final-results-1'
OUTPUTS = ('RESULTS.json', 'RESULTS.md', 'FIRST_REPLIES.json', 'PROVIDER_LEDGER.csv')


def hashed(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def relative(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def file_ref(path):
    path = Path(path)
    return dict(path=relative(path), sha256=hashfile(path)) if path.is_file() else None


def quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1)*probability
    left = int(index)
    right = min(left+1, len(ordered)-1)
    return ordered[left] + (ordered[right]-ordered[left])*(index-left)


def read_budget():
    db = LOCAL/'budget.sqlite3'
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        reservations = [dict(row) for row in conn.execute('''SELECT r.*,s.cost AS settled_upper_cny,
            p.stage,p.n_before,p.settled_and_pending_before,p.new_bound
            FROM reservations r LEFT JOIN settlements s USING(run_id)
            LEFT JOIN precalls p USING(run_id) ORDER BY r.id''')]
        policy = dict(conn.execute('SELECT * FROM policy').fetchone())
        active = [dict(row) for row in conn.execute('SELECT * FROM lease')]
    settled = sum(row['settled_upper_cny'] for row in reservations if row['settled_upper_cny'] is not None)
    pending = sum(row['reserved_cny'] for row in reservations if row['settled_upper_cny'] is None)
    authorization = read(LOCAL/'authorization.json')
    assert authorization['limits']['cny'] == 10 and authorization['limits']['requests'] == 300
    assert len(reservations) <= 300 and settled+pending <= 10+1e-9
    budget = dict(calls=len(reservations), cost_upper_cny=settled+pending, settled_upper_cny=settled,
        unresolved_reserved_upper_cny=pending, unresolved_billing=sum(r['settled_upper_cny'] is None for r in reservations),
        actual_bill='UNKNOWN', actual_bill_cny=None, limit_cny=10, limit_requests=300,
        remaining_requests=300-len(reservations), remaining_upper_cny=10-settled-pending,
        halted=policy['halted'], active_lease=bool(active),
        pending_dispatches=sum(not r['completed'] for r in reservations),
        authorization=file_ref(LOCAL/'authorization.json'), ledger=file_ref(db),
        method='settled peak cache-miss upper estimates plus full unresolved reservations; actual account bill unavailable',
        unknown_policy='No automatic redispatch; known received parser failures retained separately.')
    return budget, reservations


def judge_links():
    index = defaultdict(list)
    for directory in (HISTORY, LOCAL):
        for key_path in sorted((directory/'judge-keys').glob('*.json')):
            key = read(key_path)
            path = directory/'judge'/key_path.stem/'judgment.json'
            if not path.is_file():
                continue
            record = read(path)
            parsed = record.get('parsed')
            for slot, arm in zip(('A', 'B'), key.get('order', [])):
                answer = next((a for a in parsed.get('answers', []) if a.get('slot') == slot), None) if isinstance(parsed, dict) else None
                index[(key['case_id'], key.get('turn', 1), arm)].append(dict(
                    identity='HISTORICAL_JUDGE_NOT_R2' if directory == HISTORY else 'R2_LLM_JUDGE_PROVISIONAL_NOT_HUMAN',
                    key=file_ref(key_path), judgment=file_ref(path), frozen_input=file_ref(path.parent/'frozen-input.json'),
                    valid_stored_parse=answer is not None, answer=answer,
                    parse_error=record.get('parse_error'), repeat_or_reverse=bool(re.search(r'-(?:repeat|reverse)$', key_path.stem))))
    return index


def discover_records():
    groups = {}
    for arm in ('B2', 'E1', 'E2', 'E3', 'E4'):
        path = HISTORY/arm/'results.json'
        groups[arm] = dict(directory=HISTORY/arm, historical=True, rows=[(r, path) for r in read(path)], planned=18)
    for directory in sorted(LOCAL.iterdir()):
        if not directory.is_dir() or directory.name in {'judge', 'judge-keys', 'recovery', 'web-dist'}:
            continue
        path = directory/'results.json'
        records = [(r, path) for r in read(path)] if path.is_file() else [
            (read(p), p) for p in sorted(directory.glob('*/evaluation.json'))]
        if not records:
            continue
        groups[directory.name] = dict(directory=directory, historical=False, rows=records,
            planned=18 if directory.name in {'R1', 'R2', 'R3'} else 10 if directory.name in {'B2-SCENARIO', 'FINAL'} else len(records))
    return groups


def load_run(row, row_path, group, links, settlements):
    path = Path(row['run_path'])
    run = read(path)
    assert run['run_id'] == row['run_id'] and run['input_hash'] == row['input_hash']
    attempts = run.get('attempts', [])
    assert len(attempts) <= 1, 'Unexpected retry: retain and investigate rather than pick an attempt'
    attempt = attempts[0] if attempts else {}
    email = EmailInput.model_validate(run['email'])
    assert email.input_hash == run['input_hash']
    raw = attempt.get('raw_output')
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}
    accepted = run['status'] == 'succeeded'
    assert row['first_contract'] == accepted
    reply = row.get('reply', '')
    if data:
        assert reply == data.get('suggested_reply', ''), 'First reply differs from raw output'
    runtime = row.get('runtime') or dict(context={}, events=[])
    events = runtime.get('events', [])
    context = runtime.get('context', {})
    current = context.get('latest_request') or email.body.rsplit('[customer · current message]\n', 1)[-1]
    rule = diagnose(reply, events=events, expected_input_hash=email.input_hash,
                    customer_context=[dict(role='customer', text=current)])
    # ProductStore guards receive the stored canonical analysis, including its
    # schema identity; passing raw JSON omits schema_version and changes gates.
    guard_data = analysis_data(AnalysisRun.model_validate(run))
    old = original_guard(email, guard_data, reply, accepted=accepted)
    new = r2_guard(email, guard_data, reply, accepted=accepted, events=events)
    turn = row.get('turn')
    if turn is None:
        match = re.search(r'-T(\d+)$', email.email_id)
        turn = int(match.group(1)) if match else 1
    metadata = attempt.get('metadata', {})
    cost = metadata.get('cost_cny') if group['historical'] else settlements.get(run['run_id'])
    frozen = path.parent/'frozen-input.json'
    original_frozen = read(frozen) if frozen.is_file() else None
    return dict(case_id=row['case_id'], turn=turn, arm=row['arm'], run_id=run['run_id'], input_hash=email.input_hash,
        input=run['email'], current_customer=current, reply=reply, raw=raw, parsed_output=data, canonical_analysis=guard_data,
        status=run['status'], first_contract=accepted,
        provider_received=bool(row.get('provider_received')), error=row.get('error'),
        first_attempt=attempt, elapsed_ms=attempt.get('elapsed_ms'), config=run['config'],
        config_sha256=hashed(run['config']), runtime=runtime, runtime_sha256=hashed(runtime),
        diagnostic=rule, historical_diagnostic=row.get('diagnostic'), original_guard=old, r2_guard=new,
        historical_guard=dict(product_gate_pass=old['status'] != 'blocked', contract_pass=accepted,
                              findings=old['findings'], receipts=events),
        original_guard_unblocked=old['status'] != 'blocked', r2_guard_unblocked=new['status'] != 'blocked',
        semantic_pass=None, human_approved=False, human_numeric_labels=0,
        cost_upper_cny=cost, metadata=metadata,
        path=relative(path), run_ref=file_ref(path), evaluation=file_ref(row_path),
        raw_sha256=sha256(raw.encode('utf-8')).hexdigest() if isinstance(raw, str) else None,
        frozen_input=original_frozen, frozen_input_ref=file_ref(frozen),
        wire_request=file_ref(path.parent/'wire-request.json'),
        provider_response=file_ref(path.parent/'provider-response.txt'), provider_http=file_ref(path.parent/'provider-http.json'),
        judge_links=links.get((row['case_id'], turn, row['arm']), []),
        identity='HISTORICAL_P5B5_FIRST_OUTPUT_REASSESSED_OFFLINE_NOT_NEW_REQUEST' if group['historical'] else 'R2_NEW_REAL_FIRST_OUTPUT_SYNTHETIC',
        issue_count=len(data.get('issues', [])) if isinstance(data.get('issues'), list) else None)


def business_counts(runs):
    events = {e['event_id']:e for run in runs for e in run['runtime'].get('events', []) if e.get('event_id')}
    queries = [e for e in events.values() if e['status'] == 'executed' and 'result' in e.get('payload', {})]
    query_results = Counter(e['payload']['result'].get('status', 'UNKNOWN') for e in queries)
    return dict(email_turns=len(runs), conversations=len({(r['arm'],r['case_id']) for r in runs}),
        source_conversations=len({r['case_id'] for r in runs}),
        analysis_issues=sum(r['issue_count'] or 0 for r in runs), issue_count_unknown=sum(r['issue_count'] is None for r in runs),
        accepted_analysis_issues=sum((r['issue_count'] or 0) for r in runs if r['first_contract']),
        unique_events=len(events), event_status_counts=dict(Counter(e['status'] for e in events.values())),
        query_executions=len(queries), query_result_counts=dict(query_results),
        local_tasks_created=sum(e['status']=='created' for e in events.values()),
        handoff_pending=sum(e['status']=='handoff_pending' for e in events.values()),
        external_business_completed=0, human_connected=0, customer_goal_completed=None,
        definitions='Conversation counts are distinct arm+source case; source_conversations deduplicates case IDs across arms. analysis_issues counts raw parseable list entries, including failed-contract rows; accepted_analysis_issues separately limits to accepted contracts. Email-turn, issue and unique event counts use different denominators; a local task is not external completion or customer resolution.')


def arm_summary(arm, group, runs):
    times = [r['elapsed_ms'] for r in runs if isinstance(r['elapsed_ms'], (int, float))]
    token_values = [r['metadata'].get('total_tokens') for r in runs]
    cost_values = [r['cost_upper_cny'] for r in runs]
    freeze_path = group['directory']/'freeze.json'
    freeze = read(freeze_path) if freeze_path.exists() else None
    scenario = arm in {'B2-SCENARIO', 'FINAL'}
    identity = ('HISTORICAL_P5B5_NOT_R2_RETEST' if group['historical'] else
                'ONE_SHOT_NEW_SYNTHETIC_SCENARIO_NOT_HUMAN_GOLD' if scenario else
                'UI_SYNTHETIC_FIRST_OUTPUT_SEPARATE_COHORT' if arm.startswith('UI') else 'EXPOSED_SYNTHETIC_DEV')
    return dict(arm=arm, n=len(runs), n_planned=group['planned'], not_run=max(0, group['planned']-len(runs)),
        contract=sum(r['first_contract'] for r in runs), contract_failed=sum(not r['first_contract'] for r in runs),
        guard=sum(r['original_guard_unblocked'] for r in runs), r2_guard=sum(r['r2_guard_unblocked'] for r in runs),
        guard_label='original product guard unblocked; still requires human review',
        r2_guard_label='same current R2 guard for every arm; unblocked is not semantic pass',
        hard_errors=sum(bool(r['diagnostic']['hard_findings']) for r in runs),
        hard_error_findings=sum(len(r['diagnostic']['hard_findings']) for r in runs),
        error_families=dict(Counter(r['error'] for r in runs if r['error'])),
        rule_error_families=dict(Counter(f['code'] for r in runs for f in r['diagnostic']['hard_findings'])),
        provider_received=sum(r['provider_received'] for r in runs),
        unknown_runs=sum(r['status']=='interrupted_or_unknown' for r in runs),
        latency=dict(p50=statistics.median(times) if times else None, p95=quantile(times, .95), n_measured=len(times), unit='ms',method='first provider-attempt elapsed; inclusive linear quantile'),
        tokens=sum(v for v in token_values if type(v) is int) if any(type(v) is int for v in token_values) else None,
        tokens_unknown=sum(type(v) is not int for v in token_values),
        token_breakdown={k:sum(r['metadata'].get(k) or 0 for r in runs) for k in ('input_tokens','output_tokens','total_tokens')},
        cost=sum(v for v in cost_values if isinstance(v, (int, float))) if all(isinstance(v, (int, float)) for v in cost_values) else None,
        cost_known_upper=sum(v for v in cost_values if isinstance(v, (int, float))),
        cost_unknown=sum(v is None for v in cost_values), actual_bill='UNKNOWN',
        semantic_pass=None, semantic_human_unknown=len(runs), identity=identity,
        dataset_role=['INDEPENDENT_TEST'] if scenario else ['DEV_REGRESSION'] if arm.startswith('UI') else ['DEV_REGRESSION','CALIBRATION'],
        independent_human_gold=False, business=business_counts(runs),
        change=freeze.get('reason') if freeze else 'Historical frozen generation; offline reassessment only',
        freeze=freeze, freeze_ref=file_ref(freeze_path),
        prompt_hashes=sorted({r['config'].get('prompt_hash') for r in runs if r['config'].get('prompt_hash')}))


def provider_ledger(reservations):
    observed = {}
    for path in sorted(LOCAL.glob('**/frozen-input.json')):
        frozen = read(path)
        run_path = path.parent/'run.json'
        judge_path = path.parent/'judgment.json'
        run = read(run_path) if run_path.is_file() else None
        judgment = read(judge_path) if judge_path.is_file() else None
        run_id = run['run_id'] if run else frozen.get('run_id')
        if not run_id:
            continue
        attempt = (run.get('attempts') or [{}])[0] if run else {}
        metadata = attempt.get('metadata', {}) if run else (judgment or {}).get('metadata', {})
        langchain = path.parent/'langchain-response.json'
        if not metadata and langchain.is_file():
            value = read(langchain)
            metadata = dict(value.get('usage_metadata', {}), **value.get('response_metadata', {}))
        http = path.parent/'provider-http.json'
        observed[run_id] = dict(email_id=frozen.get('email',{}).get('email_id'),
            arm=frozen.get('config',{}).get('parameters',{}).get('arm'),
            evidence_directory=relative(path.parent), run_status=run.get('status') if run else None,
            judge_parse_status='VALID' if judgment and judgment.get('parsed') is not None else 'INVALID' if judgment else None,
            provider_http_status=read(http).get('status') if http.exists() else None,
            input_tokens=metadata.get('input_tokens'),output_tokens=metadata.get('output_tokens'),total_tokens=metadata.get('total_tokens'),
            provider_response_id=metadata.get('provider_response_id'),dispatch_at=metadata.get('dispatch_at'),
            frozen_input_sha256=hashfile(path),
            request_sha256=hashfile(path.parent/'wire-request.json') if (path.parent/'wire-request.json').exists() else None,
            response_sha256=hashfile(path.parent/'provider-response.txt') if (path.parent/'provider-response.txt').exists() else None,
            run_sha256=hashfile(run_path) if run else None,judgment_sha256=hashfile(judge_path) if judgment else None)
    result = []
    for ordinal, reservation in enumerate(reservations, 1):
        row = dict(ordinal=ordinal, **reservation, **observed.get(reservation['run_id'], {}))
        row['effective_upper_cny'] = row['settled_upper_cny'] if row['settled_upper_cny'] is not None else row['reserved_cny']
        row['provider_response_observed'] = bool(row.get('response_sha256'))
        row['dispatch_state'] = ('RESPONSE_RECEIVED' if row['provider_response_observed'] else
                                 'STARTED_RESPONSE_UNKNOWN' if row.get('request_sha256') else 'RESERVED_NO_WIRE_EVIDENCE')
        row['true_response_unknown'] = row['dispatch_state'] == 'STARTED_RESPONSE_UNKNOWN'
        row['automatic_retry'] = False
        result.append(row)
    return result


def build():
    budget, reservations = read_budget()
    settlements = {r['run_id']:r['settled_upper_cny'] for r in reservations}
    links = judge_links()
    groups = discover_records()
    gold = {g['case_id']:g for g in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    scenario_path = LOCAL/'scenario-holdout.json'
    scenario = {g['case_id']:g for g in read(scenario_path)['cases']}
    assert hashfile(scenario_path) == read(LOCAL/'scenario-holdout-manifest.json')['sha256']
    arms = []
    pair_map = {}
    all_runs = []
    for arm, group in groups.items():
        runs = [load_run(row,path,group,links,settlements) for row,path in group['rows']]
        assert len({r['run_id'] for r in runs}) == len(runs), 'Duplicate first run identity'
        arms.append(arm_summary(arm, group, runs))
        all_runs.extend(runs)
        for run in runs:
            key = (run['case_id'], run['turn'])
            g = gold.get(run['case_id'])
            s = scenario.get(run['case_id'])
            pair = pair_map.setdefault(key, dict(case_id=key[0],turn=key[1],input=dict(subject=run['input']['subject'],body=run['current_customer']),
                gold=g, synthetic_expectations=s if not g else None,
                reference_status=g['gold_status'] if g else 'SYNTHETIC_EXPECTATIONS_NOT_HUMAN_GOLD' if s else 'UI_SYNTHETIC_NO_GOLD',
                dataset_role=['DEV_REGRESSION','CALIBRATION'] if g else ['INDEPENDENT_TEST'] if s else ['DEV_REGRESSION'],
                runs={}, judge=[]))
            assert arm not in pair['runs'], 'Duplicate arm/case/turn: never choose a preferred retry'
            pair['runs'][arm] = run
            pair['judge'].extend(run['judge_links'])
    judge_path = ROOT/'docs/p5b5r2/JUDGE_REAL.json'
    judge = read(judge_path) if judge_path.is_file() else dict(status='NOT_RUN',human_numeric_labels=0)
    changes = {}
    for path in sorted(LOCAL.glob('*-amendment.json')):
        changes[path.stem] = dict(content=read(path),source=file_ref(path))
    ledger = provider_ledger(reservations)
    budget.update(provider_wire_records=sum(bool(r.get('request_sha256')) for r in ledger),
                  provider_response_records=sum(r['provider_response_observed'] for r in ledger),
                  true_response_unknown=sum(r['true_response_unknown'] for r in ledger),
                  reserved_without_wire_evidence=sum(r['dispatch_state']=='RESERVED_NO_WIRE_EVIDENCE' for r in ledger),
                  provider_tokens=sum(r.get('total_tokens') or 0 for r in ledger),
                  tokens_unknown=sum(r.get('total_tokens') is None for r in ledger),
                  stages=dict(Counter(r.get('stage') or 'UNKNOWN' for r in ledger)),
                  first_ui_requests=[dict(ordinal=r['ordinal'],stage=r.get('stage'),run_id=r['run_id'],status=r.get('run_status')) for r in ledger if str(r.get('stage','')).startswith('UI')])
    report = dict(version=VERSION, grader_version=RULE_VERSION, guard_version=GUARD_VERSION,
        grader_source=file_ref(ROOT/'src/evaluation/p5b5r2_judge.py'),guard_source=file_ref(ROOT/'src/application/p5b5r2_guard.py'),
        report_source=file_ref(Path(__file__)), arms=arms, pairs=list(pair_map.values()),
        budget=budget, judge=judge, judge_source=file_ref(judge_path),changes=changes,
        champion='B2',candidate='R3',promotion='NOT_PROMOTED',human_numeric_labels=0,
        independent_human_gold=0, dataset_hash=hashfile(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json'),
        scenario_manifest=read(LOCAL/'scenario-holdout-manifest.json'),
        history_identity='B2/E1–E4 are prior B5 generations reassessed read-only; never included in R2 provider calls.',
        comparability='Original guard and SAME current R2 guard reported separately. Same 18 exposed DEV turns; multi-turn downstream inputs include each arm own first reply. Scenario and UI cohorts have separate denominators. Rule silence is not semantic pass.',
        semantic_pass=None, business=business_counts([r for r in all_runs if not r['identity'].startswith('HISTORICAL')]),
        limitations=['All inputs are synthetic/authorized experimental data, not a customer-population sample.',
                    'No independent human numerical labels: human agreement and formal semantic promotion uncomputed.',
                    'Same-provider Judge is provisional and not independent expert certification.',
                    'One-shot new synthetic scenarios were not used for tuning; small n cannot establish population generalization.',
                    'Internal requests, UNKNOWN lookups and handoff_pending do not mean external business completion.',
                    'Known HTTP response with invalid Judge parse is retained, distinct from true response UNKNOWN.'])
    replies = dict(version=VERSION,champion='B2',candidate='R3',promotion='NOT_PROMOTED',
                   identity='ALL_FIRST_REPLIES_WITH_FAILURES_RETAINED',arms=[dict(arm=a['arm'],n=a['n'],identity=a['identity']) for a in arms],
                   replies=[dict(case_id=r['case_id'],turn=r['turn'],arm=r['arm'],input=r['input'],reply=r['reply'],
                                 first_contract=r['first_contract'],error=r['error'],run_id=r['run_id'],
                                 input_hash=r['input_hash'],raw_sha256=r['raw_sha256'],run=r['run_ref'],
                                 identity=r['identity']) for r in all_runs])
    return report, replies, ledger


def markdown(report):
    lines = ['# P5-B5-R2 真实结果与停止结论', '',
        '2026-10-30，Asia/Shanghai。**保留 B2 为 Champion，R3 为本轮最终候选，不正式晋升。**', '',
        '以下是实际首次输出的只读汇总。契约通过、产品门禁未阻断与语义正确分开；规则未报错不代表语义通过。失败留在原分母，未运行/未评分另列。', '',
        '|版本|来源 / 实际首次输入|契约通过|原门禁未阻断|同 R2 门禁未阻断|规则硬错回合|p50 / p95 ms|Tokens|费用上界 ¥|',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    number = lambda x: 'UNKNOWN' if x is None else f'{x:.6f}' if isinstance(x,float) else str(x)
    for a in report['arms']:
        lines.append(f"|{a['arm']}|{a['identity']} · {a['n']}|{a['contract']}/{a['n']}|{a['guard']}/{a['n']}|{a['r2_guard']}/{a['n']}|{a['hard_errors']}/{a['n']}|{number(a['latency']['p50'])} / {number(a['latency']['p95'])}|{number(a['tokens'])}|{number(a['cost'])}|")
    b = report['budget']
    lines += ['', 'B2/E1–E4 是历史 B5 首次生成，本轮仅离线重评。开发回合、一次新合成场景和各 UI 实验不混合分母。多轮第 2 轮包含各版本自己的首次回复，因此不声称其完整上下文逐字相同。', '',
        f"新账本实际预留 {b['calls']}/300 次，保守费用上界 ¥{b['cost_upper_cny']:.6f}/¥10；其中未决费用预留 ¥{b['unresolved_reserved_upper_cny']:.6f}。实际独占账单 UNKNOWN。Provider 请求/响应留证 {b['provider_wire_records']}/{b['provider_response_records']}，真正响应未知 {b['true_response_unknown']}，账本 halted={b['halted']}。全部生成、对照和 Judge 共用该账本；零自动重试。", '',
        f"新调用 tokens={b['provider_tokens']}，未知 token 记录 {b['tokens_unknown']}。逐次金额与请求额度预检、请求/响应 SHA、stage 和结算在 [PROVIDER_LEDGER.csv](PROVIDER_LEDGER.csv)；完整各案 raw、config、冻结输入、回执与 Judge 链接在 [RESULTS.json](RESULTS.json)。", '',
        '真实循环保留 R1/R2/R3 的全部首次输出。R2/R3 改动依据、源码冻结及实际 Prompt hash 在 JSON 的 changes/arms 中；不覆写旧成绩，也不以最好重试替换失败。', '',
        '## Judge、语义与晋升', '',
        '实际 Judge 原始记录、混淆矩阵、无效评分、逐维数值分母及重复/反序稳定性见 [JUDGE_REAL.json](JUDGE_REAL.json)。同源模型 Judge 和开发控制不冒充真人真值。有效真人数值标签为 0，人机逐维一致率不可计算，正式 semantic_pass 保持 null。', '',
        '候选契约改善和具体待办推进可以复核；尚不能据此认证整体客服质量超过 B2。一次新合成场景有开发隔离与输入 hash，但没有独立真人 Gold，且样本量很小。保留 B2，不作总体泛化提升结论。', '',
        '## 本地业务与产品范围', '',
        f"本轮新模型路径共 {report['business']['email_turns']} 个邮件回合、{report['business']['conversations']} 个会话身份、{report['business']['analysis_issues']} 个解析 Issue（无法计数 {report['business']['issue_count_unknown']} 回合）。去重事件 {report['business']['unique_events']}，查询执行 {report['business']['query_executions']}，结果分布 {json.dumps(report['business']['query_result_counts'],ensure_ascii=False)}；内部任务 created={report['business']['local_tasks_created']}，人工申请 pending={report['business']['handoff_pending']}。", '',
        '以上邮件、Issue、查询和事件有不同分母。已创建本地待办、查询 UNKNOWN、申请人工都不等于客户目标已完成；真实外部发信、退款、改约、联系物流、真人接入均为 0。逐案业务事件保留在 runtime。', '',
        'UI、UI-R3、UI-FOLLOWUP 若已执行，在表和账本中各自单列。模型更新、浏览器可交互及独立主观验收分开；最终截图和真实操作记录见 UI_ACCEPTANCE。', '',
        '完整首次回复：[FIRST_REPLIES.json](FIRST_REPLIES.json)。九项逐项结论见 [ACCEPTANCE.md](ACCEPTANCE.md)；统一人工包只汇总真正需要主观/政策判断的事项。原三条逐字参考和历史裁决不要求重签。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT/'docs/p5b5r2'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    def blocked(*args, **kwargs):
        raise RuntimeError('Final reporting forbids network access')
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    report, replies, ledger = build()
    if not args.check:
        if report['budget']['active_lease'] or not report['budget']['halted']:
            raise RuntimeError('Finalize only after the independent budget is halted and no request lease is active; --check is read-only while running.')
        out = Path(args.out)
        if any((out/name).exists() for name in OUTPUTS):
            raise FileExistsError('Final artifact exists: never overwrite. Use --check or a fresh --out directory.')
        out.mkdir(parents=True, exist_ok=True)
        for name, value in [('RESULTS.json',report),('FIRST_REPLIES.json',replies)]:
            with (out/name).open('x',encoding='utf-8') as f:
                json.dump(value,f,ensure_ascii=False,indent=2)
        with (out/'RESULTS.md').open('x',encoding='utf-8') as f:
            f.write(markdown(report))
        keys = list(dict.fromkeys(key for row in ledger for key in row))
        with (out/'PROVIDER_LEDGER.csv').open('x',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(ledger)
    print(json.dumps(dict(arms=[{k:a[k] for k in ('arm','n','contract','guard','r2_guard')} for a in report['arms']],
                          budget=report['budget'],pairs=len(report['pairs']),check_only=args.check),ensure_ascii=False))


if __name__ == '__main__':
    main()
