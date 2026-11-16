"""Append-only local knowledge requests; notes never become approved facts."""
import json
import sqlite3
from contextlib import closing
from src.domain.contracts import digest
from src.application.product_workflow import Conflict, timestamp


class KnowledgeTasks:
    def __init__(self, store):
        self.store = store
        self.path = store.path.with_name(store.path.stem+'-knowledge-tasks.sqlite3')
        with closing(sqlite3.connect(self.path)) as c, c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables not in (set(), {'knowledge_notes'}): raise Conflict('非知识待办工作库')
            c.execute('''CREATE TABLE IF NOT EXISTS knowledge_notes (
                operation_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, case_id TEXT NOT NULL,
                input_hash TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)''')
            for action in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS no_{action.lower()} BEFORE {action} ON knowledge_notes BEGIN SELECT RAISE(ABORT,'knowledge notes immutable'); END")

    def list(self, case_id):
        with closing(sqlite3.connect(self.path)) as c:
            c.row_factory = sqlite3.Row
            return [dict(r,owner_status='OWNER_PENDING',use_in_model=False) for r in c.execute('SELECT * FROM knowledge_notes WHERE case_id=? ORDER BY created_at,operation_id',(case_id,))]

    def append(self, case_id, *, revision, operation_id, kind, body):
        case = self.store.get(case_id)
        if not case: raise KeyError(case_id)
        if kind not in ('request','note') or not body.strip() or len(body)>10000: raise ValueError('Invalid knowledge note')
        request = dict(case_id=case_id,revision=revision,kind=kind,body=body,input_hash=case['run'].input_hash)
        identity = digest(request)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT request_hash FROM knowledge_notes WHERE operation_id=?',(operation_id,)).fetchone()
            if row:
                if row[0]!=identity: raise Conflict('知识待办标识与原请求不一致')
            else:
                if revision!=case['revision']: raise Conflict('Stale revision')
                c.execute('INSERT INTO knowledge_notes VALUES(?,?,?,?,?,?,?)',(operation_id,identity,case_id,case['run'].input_hash,kind,body,timestamp()))
        return self.list(case_id)
