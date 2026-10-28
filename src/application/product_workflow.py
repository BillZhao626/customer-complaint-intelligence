"""Local review application. No provider client and no real send implementation."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from src.application.product_quality import inspect, VERSION
from src.application.live_execution import strict_json
from src.domain.contracts import AnalysisRun, digest, idempotency_key


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def raw_hash(run):
    raw = run.attempts[-1].raw_output if run.attempts else None
    return sha256(raw.encode()).hexdigest() if isinstance(raw, str) else None


def analysis_data(run):
    """Validate original identity without upgrading failed raw to business data."""
    if run.input_hash != run.email.input_hash or run.cohort_id != run.config.cohort_id or run.idempotency_key != idempotency_key(run.email, run.config):
        raise ValueError('Source run identity mismatch')
    if run.status != 'succeeded':
        try:
            return strict_json(run.attempts[-1].raw_output)
        except (ValueError, TypeError, IndexError):
            return None
    if not run.result or not run.attempts or run.attempts[-1].contract_status != 'passed' or run.attempts[-1].error:
        raise ValueError('Source outcome mismatch')
    if run.config.schema_version in ('analysis-v3', 'analysis-v3.1'):
        if (run.config.parameters or {}).get('urgency_validation_profile'):
            from src.domain.analysis_v31_context import stored_context_analysis
            return stored_context_analysis(run).model_dump()
        from src.domain.versioned_analysis import stored_analysis
        return stored_analysis(run).model_dump()
    if run.config.schema_version != 'analysis-v2':
        raise ValueError('Unsupported source schema')
    if run.config.backend != 'legacy_mock' and strict_json(run.attempts[-1].raw_output) != run.result.model_dump():
        raise ValueError('Source raw/result mismatch')
    return run.result.model_dump()


class Conflict(ValueError):
    """Stale page or illegal state change. Reload before further action."""


class ProductStore:
    """Additive, separate SQLite database; never initializes an experiment DB."""
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        root = Path(__file__).resolve().parents[2]
        if self.path.is_relative_to(root) and not self.path.is_relative_to(root / '.local/p4'):
            raise ValueError('Product writes must use .local/p4, never an experiment path')
        if self.path.suffix not in ('.sqlite3', '.sqlite', '.db'):
            raise ValueError('Dedicated SQLite file required')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            version = c.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version not in (0, 1) or (version == 0 and tables) or (version == 1 and 'product_cases' not in tables):
                raise ValueError('Not a product database; no implicit migration')
            # Individual DDL statements keep initialization in one transaction.
            ddl = [
                '''CREATE TABLE IF NOT EXISTS product_cases (
                case_id TEXT PRIMARY KEY, source_key TEXT UNIQUE NOT NULL,
                source_kind TEXT NOT NULL CHECK(source_kind IN ('real_replay','offline_fake','legacy_mock')),
                source_ref TEXT NOT NULL, snapshot_json TEXT NOT NULL, snapshot_hash TEXT NOT NULL,
                accepted INTEGER NOT NULL, created_at TEXT NOT NULL)''',
                '''CREATE TABLE IF NOT EXISTS product_workflow (
                case_id TEXT PRIMARY KEY REFERENCES product_cases(case_id),
                state TEXT NOT NULL CHECK(state IN ('pending_review','changes_requested','approved','rejected','simulated_sent','analysis_failed')),
                revision INTEGER NOT NULL, current_version INTEGER NOT NULL)''',
                '''CREATE TABLE IF NOT EXISTS product_drafts (
                case_id TEXT NOT NULL REFERENCES product_cases(case_id), version INTEGER NOT NULL,
                body TEXT NOT NULL, body_hash TEXT NOT NULL, quality_json TEXT NOT NULL,
                editor TEXT NOT NULL, actor_type TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(case_id,version))''',
                '''CREATE TABLE IF NOT EXISTS product_events (
                event_id TEXT PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL,
                case_id TEXT NOT NULL REFERENCES product_cases(case_id), revision INTEGER NOT NULL,
                version INTEGER NOT NULL, action TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
                actor TEXT NOT NULL, actor_type TEXT NOT NULL, reason TEXT NOT NULL,
                details_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(case_id,revision))''',
                '''CREATE TABLE IF NOT EXISTS product_simulations (
                receipt_id TEXT PRIMARY KEY, case_id TEXT UNIQUE NOT NULL REFERENCES product_cases(case_id),
                version INTEGER NOT NULL, body_hash TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode='simulation_only'))''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_drafts_update BEFORE UPDATE ON product_drafts BEGIN SELECT RAISE(ABORT,'draft versions immutable'); END''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_drafts_delete BEFORE DELETE ON product_drafts BEGIN SELECT RAISE(ABORT,'draft versions immutable'); END''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_events_update BEFORE UPDATE ON product_events BEGIN SELECT RAISE(ABORT,'audit events immutable'); END''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_events_delete BEFORE DELETE ON product_events BEGIN SELECT RAISE(ABORT,'audit events immutable'); END''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_cases_update BEFORE UPDATE ON product_cases BEGIN SELECT RAISE(ABORT,'source snapshots immutable'); END''',
                '''CREATE TRIGGER IF NOT EXISTS immutable_receipts_update BEFORE UPDATE ON product_simulations BEGIN SELECT RAISE(ABORT,'receipts immutable'); END''',
            ]
            for statement in ddl:
                c.execute(statement)
            c.execute('PRAGMA user_version=1')

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=5)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA synchronous=FULL')
        try:
            with c:
                yield c
        finally:
            c.close()

    def _event(self, c, case_id, revision, version, action, old, new, actor, actor_type, reason, details, operation_id, request_hash):
        c.execute('INSERT INTO product_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (str(uuid4()), operation_id, request_hash, case_id, revision, version, action, old, new, actor, actor_type, reason, json.dumps(details, ensure_ascii=False), timestamp()))

    def create(self, run, source_ref='local analysis', *, origin='historical_replay'):
        run = AnalysisRun.model_validate(run)
        data = analysis_data(run)
        kind = 'real_replay' if run.config.backend == 'deepseek_live' else run.config.backend
        if origin not in ('historical_replay', 'new_analysis'):
            raise ValueError('Unknown product origin')
        if (run.config.parameters or {}).get('product_transport') == 'offline_mock_http':
            kind = 'offline_fake'
        if origin == 'new_analysis':
            source_ref = 'new_analysis:' + source_ref
        snapshot = run.model_dump()
        key = digest(dict(run_id=run.run_id, input_hash=run.input_hash, raw_hash=raw_hash(run), snapshot_hash=digest(snapshot)))
        accepted = run.status == 'succeeded'
        body = run.result.suggested_reply if accepted else None
        quality = inspect(run.email, data, body, accepted)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT case_id FROM product_cases WHERE source_key=?', (key,)).fetchone()
            if row:
                case_id = row[0]
            else:
                case_id = str(uuid4())
                state = 'pending_review' if accepted else 'analysis_failed'
                c.execute('INSERT INTO product_cases VALUES(?,?,?,?,?,?,?,?)',
                          (case_id, key, kind, source_ref, run.model_dump_json(), digest(snapshot), int(accepted), timestamp()))
                c.execute('INSERT INTO product_workflow VALUES(?,?,0,?)', (case_id, state, 1 if accepted else 0))
                if accepted:
                    c.execute('INSERT INTO product_drafts VALUES(?,?,?,?,?,?,?,?)',
                              (case_id, 1, body, digest(body), json.dumps(quality, ensure_ascii=False), 'system_import', 'system', timestamp()))
                self._event(c, case_id, 0, 1 if accepted else 0, 'created', None, state, 'system_import', 'system',
                            'Unreviewed draft; no inherited human approval', dict(raw_hash=raw_hash(run), quality=quality), 'create:' + key, key)
                # A customer asking for a person is a routing signal, never an
                # instruction to execute a model/tool or an inherited approval.
                # Bind the request in the same transaction as the new case.
                from src.application.service_triage import current_customer_text, explicit_human_request, is_p47_case, VERSION as ROUTING_VERSION
                if is_p47_case(dict(run=run)) and explicit_human_request(current_customer_text(dict(run=run))):
                    version = 1 if accepted else 0
                    c.execute('UPDATE product_workflow SET revision=1 WHERE case_id=?', (case_id,))
                    self._event(c, case_id, 1, version, 'request_handoff', state, state, 'customer_request_rule', 'system',
                        '客户明确要求人工客服；仅记录本地转交请求，尚无人接管。',
                        dict(quality=quality, guard_version=VERSION, checks={}, handoff=dict(mode='local_demo_only',
                            routing_version=ROUTING_VERSION, reason_codes=['customer_requested'], run_id=run.run_id,
                            input_hash=run.input_hash, draft_version=version, body_hash=digest(body) if body is not None else None)),
                        'customer-handoff:' + key, digest(dict(source_key=key, action='request_handoff', routing=ROUTING_VERSION)))
        return self.get(case_id)

    def get(self, case_id):
        with self.connect() as c:
            # Keep workflow, versions and audit rows in one read snapshot.
            c.execute('BEGIN')
            row = c.execute('SELECT * FROM product_cases JOIN product_workflow USING(case_id) WHERE case_id=?', (case_id,)).fetchone()
            if row is None:
                return None
            record = dict(row)
            drafts = [dict(r) for r in c.execute('SELECT * FROM product_drafts WHERE case_id=? ORDER BY version', (case_id,))]
            events = [dict(r) for r in c.execute('SELECT * FROM product_events WHERE case_id=? ORDER BY revision', (case_id,))]
            receipt = c.execute('SELECT * FROM product_simulations WHERE case_id=?', (case_id,)).fetchone()
        run = AnalysisRun.model_validate_json(record.pop('snapshot_json'))
        # Preserve SQLite v1 and historical snapshots. Derive display provenance
        # from immutable config/source_ref without rewriting old stored enums.
        if (run.config.parameters or {}).get('product_transport') == 'offline_mock_http':
            record['source_kind'] = 'offline_mock_http'
        elif run.config.backend == 'deepseek_live' and record['source_ref'].startswith('new_analysis:'):
            record['source_kind'] = 'real_new_analysis'
        if digest(run.model_dump()) != record['snapshot_hash']:
            raise ValueError('Source snapshot integrity failure')
        data = analysis_data(run)
        for d in drafts:
            if digest(d['body']) != d['body_hash']:
                raise ValueError('Draft integrity failure')
            d['quality'] = json.loads(d.pop('quality_json'))
        for e in events:
            e['details'] = json.loads(e.pop('details_json'))
        current = next((d for d in drafts if d['version'] == record['current_version']), None)
        return dict(record, run=run, analysis=data, drafts=drafts, events=events, draft=current,
                    quality=inspect(run.email, data, current['body'] if current else None, bool(record['accepted'])),
                    receipt=dict(receipt) if receipt else None)

    def list_cases(self):
        with self.connect() as c:
            ids = [r[0] for r in c.execute('SELECT case_id FROM product_cases ORDER BY created_at DESC,case_id')]
        return [self.get(i) for i in ids]

    def act(self, case_id, action, *, expected_revision, actor, actor_type, reason='', body=None, checks=None, operation_id=None):
        if action not in ('save_edit', 'insert_suggestion', 'approve', 'reject', 'request_changes', 'simulate_send', 'request_handoff', 'take_over'):
            raise Conflict('Unknown or unauthorized action')
        if not actor.strip() or actor_type not in ('local_human', 'demo_test'):
            raise Conflict('Explicit local reviewer identity or labeled demo/test actor required')
        if len(actor) > 200 or len(reason) > 10000:
            raise ValueError('Actor or reason too long')
        operation_id = operation_id or str(uuid4())
        checks = checks or {}
        request = dict(case_id=case_id, action=action, expected_revision=expected_revision, actor=actor, actor_type=actor_type, reason=reason, body=body, checks=checks)
        request_hash = digest(request)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            previous = c.execute('SELECT request_hash FROM product_events WHERE operation_id=?', (operation_id,)).fetchone()
            if previous:
                if previous[0] != request_hash:
                    raise Conflict('Idempotency key reused for a different operation')
            else:
                row = c.execute('SELECT * FROM product_workflow WHERE case_id=?', (case_id,)).fetchone()
                if row is None:
                    raise Conflict('Case not found')
                state, revision, version = row['state'], row['revision'], row['current_version']
                if revision != expected_revision:
                    raise Conflict('Stale page: reload current case before changing it')
                if state == 'analysis_failed' and action not in ('request_handoff', 'take_over'):
                    raise Conflict('Failed analysis has no reviewable draft')
                if state == 'simulated_sent':
                    if action == 'simulate_send':
                        return self.get(case_id)
                    raise Conflict('Simulation snapshot is terminal; retain the approved content')
                record = self.get(case_id)
                current_body = record['draft']['body'] if record['draft'] else None
                quality = inspect(record['run'].email, record['analysis'], current_body, bool(record['accepted']))
                new_state = state
                details = dict(quality=quality, checks=checks, guard_version=VERSION)
                if action in ('request_handoff', 'take_over'):
                    if not reason.strip():
                        raise Conflict('Local handoff or takeover requires an explicit reason')
                    from src.application.service_triage import triage
                    route = triage(record)
                    details['handoff'] = dict(mode='local_demo_only', routing_version=route['version'],
                        routing_hash=route['routing_hash'], reason_codes=route['reason_codes'],
                        run_id=record['run'].run_id, input_hash=record['run'].input_hash,
                        source_kind=record['source_kind'], draft_version=version,
                        body_hash=record['draft']['body_hash'] if record['draft'] else None)
                elif action in ('save_edit', 'insert_suggestion'):
                    if not isinstance(body, str) or not body.strip() or len(body) > 30000:
                        raise ValueError('Nonblank reply up to 30000 characters required')
                    if action == 'insert_suggestion' and state == 'rejected' and body == current_body:
                        raise Conflict('Rejected draft must be edited before a new review')
                    if action == 'insert_suggestion':
                        suggestion = record['run'].result.suggested_reply
                        mode = checks.get('insertion_mode')
                        if mode not in ('replace', 'append') or (mode == 'replace' and body != suggestion) or (mode == 'append' and not body.endswith(suggestion)):
                            raise Conflict('Inserted text must bind to the current original suggestion')
                        details['draft_source'] = dict(kind='copilot_suggestion', run_id=record['run'].run_id,
                            input_hash=record['run'].input_hash, suggestion_hash=digest(suggestion), mode=mode)
                    if body == current_body and action == 'save_edit':
                        return record
                    version += 1
                    quality = inspect(record['run'].email, record['analysis'], body, True)
                    c.execute('INSERT INTO product_drafts VALUES(?,?,?,?,?,?,?,?)',
                              (case_id, version, body, digest(body), json.dumps(quality, ensure_ascii=False), actor, actor_type, timestamp()))
                    new_state = 'pending_review'
                    details.update(quality=quality, previous_version=version - 1)
                elif action == 'approve':
                    from src.application.service_triage import is_p47_case, triage
                    if is_p47_case(record):
                        if state == 'changes_requested':
                            raise Conflict('已退回的草稿须实际修改并保存新版本后，再重新审核。')
                        route = triage(record)
                        if route['requires_takeover'] and not route['takeover_complete']:
                            raise Conflict('此会话须先由本地操作者接管，再审核当前回复。')
                    if state not in ('pending_review', 'changes_requested', 'approved'):
                        raise Conflict('Rejected draft must be edited before a new review')
                    if state == 'approved':
                        return record
                    if quality['status'] == 'blocked':
                        raise Conflict('Blocking quality findings must be corrected; analysis defects cannot be waived by reply editing')
                    required = ['facts_evidence', 'authority_privacy', 'all_issues']
                    if quality['safety_review_required']:
                        required.append('safety')
                    if any(checks.get(k) is not True for k in required) or not reason.strip():
                        raise Conflict('Review checklist and a reason are required; no automatic approval')
                    new_state = 'approved'
                    details['body_hash'] = record['draft']['body_hash']
                elif action in ('reject', 'request_changes'):
                    if state == 'rejected' and action == 'request_changes':
                        raise Conflict('Rejected draft requires a new edited version before review can reopen')
                    if not reason.strip():
                        raise Conflict('Rejection or return requires a reason')
                    new_state = 'rejected' if action == 'reject' else 'changes_requested'
                elif action == 'simulate_send':
                    from src.application.service_triage import is_p47_case, triage
                    if is_p47_case(record):
                        route = triage(record)
                        if route['requires_takeover'] and not route['takeover_complete']:
                            raise Conflict('此会话须先由本地操作者接管，再审核当前回复。')
                    if state != 'approved' or quality['status'] == 'blocked':
                        raise Conflict('Only current approved and unblocked draft can be simulated')
                    approval = next((e for e in reversed(record['events']) if e['action'] == 'approve' and e['version'] == version), None)
                    if not approval or approval['details'].get('body_hash') != record['draft']['body_hash'] or digest(approval['details']['quality']) != digest(quality):
                        raise Conflict('Approval identity or quality policy changed; return for review')
                    receipt_id = str(uuid4())
                    c.execute("INSERT INTO product_simulations VALUES(?,?,?,?,?,?,'simulation_only')",
                              (receipt_id, case_id, version, record['draft']['body_hash'], current_body, timestamp()))
                    details['receipt_id'] = receipt_id
                    new_state = 'simulated_sent'
                revision += 1
                c.execute('UPDATE product_workflow SET state=?,revision=?,current_version=? WHERE case_id=?',
                          (new_state, revision, version, case_id))
                self._event(c, case_id, revision, version, action, state, new_state, actor, actor_type, reason, details, operation_id, request_hash)
        return self.get(case_id)

    def dashboard(self):
        cases = self.list_cases()
        from collections import Counter, defaultdict
        groups = defaultdict(list)
        for c in cases:
            groups[(c['source_kind'], c['run'].cohort_id)].append(c)
        def eligible(r):
            return r['accepted'] and not any(f['scope'] == 'analysis' and f['severity'] == 'block' for f in r['quality']['findings'])
        return dict(total=len(cases), states=dict(Counter(c['state'] for c in cases)),
                    groups=[dict(source_kind=k[0], cohort_id=k[1], total=len(rows),
                                 model=rows[0]['run'].config.model_id, prompt=rows[0]['run'].config.prompt_version,
                                 accepted=sum(bool(r['accepted']) for r in rows), failed=sum(not r['accepted'] for r in rows),
                                 blocked=sum(r['quality']['status'] == 'blocked' for r in rows),
                                 business_denominator=sum(bool(eligible(r)) for r in rows),
                                 negative=sum(r['run'].result.sentiment == 'negative' for r in rows if eligible(r)),
                                 unknown_sentiment=sum(r['run'].result.sentiment == 'unknown' for r in rows if eligible(r)),
                                 analysis_blocked=sum(bool(r['accepted']) and not eligible(r) for r in rows),
                                 reply_blocked=sum(any(f['scope'] == 'reply' and f['severity'] == 'block' for f in r['quality']['findings']) for r in rows),
                                 fallback=sum(bool(r['run'].metadata.get('fallback', False)) for r in rows),
                                 member_case_ids=[r['case_id'] for r in rows],
                                 business_member_case_ids=[r['case_id'] for r in rows if eligible(r)],
                                 denominator='Contract-accepted with no blocking analysis diagnostic for sentiment; failed raw and analysis conflicts excluded. No independent semantic certification. One case per immutable source run, versions not mixed.') for k, rows in groups.items()],
                    caveat='Contract acceptance is not semantic correctness. Workflow counts are local operations; replay and fake are separated.')
