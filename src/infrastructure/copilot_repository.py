"""Append-only internal assistant sidecar. Does not mutate product/research data."""
from contextlib import contextmanager, closing
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from src.application.product_workflow import Conflict, timestamp
from src.domain.contracts import digest


class CopilotRepository:
    def __init__(self, product_path):
        p = Path(product_path)
        self.path = p.with_name(p.stem+'-copilot.sqlite3')
        with self.connect() as c:
            version = c.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if version not in (0, 1) or tables not in (set(), {'qa_runs', 'qa_budgets'}):
                raise Conflict('不是兼容的Copilot独立库')
            c.execute('''CREATE TABLE IF NOT EXISTS qa_runs (
                run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                request_hash TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
                context_json TEXT NOT NULL, question TEXT NOT NULL, result_json TEXT,
                created_at TEXT NOT NULL, budget_id TEXT, UNIQUE(case_id,operation_id))''')
            c.execute('CREATE TABLE IF NOT EXISTS qa_budgets (budget_id TEXT PRIMARY KEY, config_hash TEXT NOT NULL, max_requests INTEGER NOT NULL, used INTEGER NOT NULL)')
            c.execute("CREATE TRIGGER IF NOT EXISTS immutable_qa_delete BEFORE DELETE ON qa_runs BEGIN SELECT RAISE(ABORT,'qa immutable'); END")
            c.execute("CREATE TRIGGER IF NOT EXISTS immutable_qa_update BEFORE UPDATE ON qa_runs WHEN OLD.status != 'running' OR NEW.status NOT IN ('succeeded','failed') OR OLD.run_id != NEW.run_id OR OLD.case_id != NEW.case_id OR OLD.operation_id != NEW.operation_id OR OLD.request_hash != NEW.request_hash OR OLD.context_json != NEW.context_json OR OLD.question != NEW.question OR OLD.mode != NEW.mode OR OLD.created_at != NEW.created_at OR OLD.budget_id IS NOT NEW.budget_id BEGIN SELECT RAISE(ABORT,'qa immutable'); END")
            c.execute('PRAGMA user_version=1')

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as c:
            c.row_factory = sqlite3.Row
            with c: yield c

    @staticmethod
    def decode(row):
        if row is None: return None
        row = dict(row)
        row['context'] = json.loads(row.pop('context_json'))
        if digest({k:v for k,v in row['context'].items() if k != 'context_hash'}) != row['context']['context_hash']:
            raise Conflict('问答上下文校验失败')
        row['result'] = json.loads(row.pop('result_json') or 'null')
        return row

    def history(self, case_id):
        with self.connect() as c:
            return [self.decode(r) for r in c.execute('SELECT * FROM qa_runs WHERE case_id=? ORDER BY created_at,run_id', (case_id,))]

    def claim(self, context, question, operation_id, mode, config_hash, budget=None):
        request_hash = digest(dict(context=context, question=question, mode=mode, config_hash=config_hash))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT * FROM qa_runs WHERE case_id=? AND operation_id=?', (context['case_id'], operation_id)).fetchone()
            if old:
                if old['request_hash'] != request_hash: raise Conflict('同一操作的问题或上下文已变化，请重新提交')
                return self.decode(old), False
            # Same question and exact saved context reuse a persisted answer.
            old = c.execute('SELECT * FROM qa_runs WHERE case_id=? AND request_hash=?', (context['case_id'], request_hash)).fetchone()
            if old: return self.decode(old), False
            if budget:
                budget_id, limit = budget
                if not budget_id.startswith('copilot-mock-') or not 1 <= limit <= 20: raise ValueError('需要独立的受控问答预算')
                c.execute('INSERT OR IGNORE INTO qa_budgets VALUES(?,?,?,0)', (budget_id, config_hash, limit))
                b = c.execute('SELECT * FROM qa_budgets WHERE budget_id=?', (budget_id,)).fetchone()
                if b['config_hash'] != config_hash or b['max_requests'] != limit or b['used'] >= limit: raise Conflict('问答预算不匹配或已耗尽')
                c.execute('UPDATE qa_budgets SET used=used+1 WHERE budget_id=?', (budget_id,))
            run_id = str(uuid4())
            c.execute('INSERT INTO qa_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (run_id, context['case_id'], operation_id, request_hash, mode, 'running', json.dumps(context, ensure_ascii=False), question, None, timestamp(), budget[0] if budget else None))
            return self.decode(c.execute('SELECT * FROM qa_runs WHERE run_id=?', (run_id,)).fetchone()), True

    def finish(self, run_id, result, status='succeeded'):
        with self.connect() as c:
            c.execute('UPDATE qa_runs SET status=?,result_json=? WHERE run_id=? AND status=?', (status, json.dumps(result, ensure_ascii=False), run_id, 'running'))
            return self.decode(c.execute('SELECT * FROM qa_runs WHERE run_id=?', (run_id,)).fetchone())
