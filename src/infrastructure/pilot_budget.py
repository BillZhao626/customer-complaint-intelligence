"""Durable, fail-closed authorization ledger shared by CLI and UI. No reset API."""
from contextlib import contextmanager,closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from src.domain.contracts import digest
from src.infrastructure.deepseek import LiveError

PRICE_SOURCE='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
PRICE_DATE='2026-10-15'
INPUT_CNY_PER_MILLION=2.0
OUTPUT_CNY_PER_MILLION=8.0

def estimate_cost(metadata):
    i,o=metadata.get('input_tokens'),metadata.get('output_tokens')
    return (i*INPUT_CNY_PER_MILLION+o*OUTPUT_CNY_PER_MILLION)/1e6 if i is not None and o is not None else None

class PilotBudget:
    def __init__(self,path):
        self.path=Path(path).resolve()
        if not self.path.is_file():
            raise LiveError('configuration_error')

    @classmethod
    def create(cls,path,allowed_inputs,manifest):
        path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive file creation: never reset an existing budget.
        with path.open('xb'): pass
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.executescript('''CREATE TABLE policy(id INTEGER PRIMARY KEY, manifest TEXT, allowed TEXT, halted TEXT);
                CREATE TABLE lease(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT NOT NULL);
                CREATE TABLE reservations(id INTEGER PRIMARY KEY,run_id TEXT,attempt_no INTEGER,input_hash TEXT,
                    reserved_cny REAL,created_at TEXT,completed INTEGER DEFAULT 0, UNIQUE(run_id,attempt_no));''')
            conn.execute('INSERT INTO policy VALUES(1,?,?,NULL)',(json.dumps(manifest,sort_keys=True),json.dumps(sorted(allowed_inputs))))
        return cls(path)

    @contextmanager
    def connection(self):
        conn=sqlite3.connect(self.path,timeout=10)
        try:
            with conn: yield conn
        finally: conn.close()

    def acquire(self,run_id,input_hash):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            policy=conn.execute('SELECT allowed,halted FROM policy WHERE id=1').fetchone()
            if not policy or policy[1] or input_hash not in json.loads(policy[0]):
                raise LiveError('configuration_error')
            if conn.execute('SELECT 1 FROM lease').fetchone():
                raise LiveError('interrupted_or_unknown')
            conn.execute('INSERT INTO lease VALUES(1,?)',(run_id,))

    def verify_config(self,config):
        with self.connection() as conn:
            manifest=json.loads(conn.execute('SELECT manifest FROM policy WHERE id=1').fetchone()[0])
        if 'config' in manifest and config.model_dump()!=manifest['config']:
            raise LiveError('configuration_error')

    def reserve(self,run_id,attempt_no,input_hash,messages,max_tokens):
        # UTF-8 byte count + 1024 framing margin bounds text tokens conservatively.
        size=len(json.dumps(messages,ensure_ascii=False).encode('utf-8'))+1024
        if size>20000 or max_tokens>2000: raise LiveError('configuration_error')
        cost=(size*INPUT_CNY_PER_MILLION+max_tokens*OUTPUT_CNY_PER_MILLION)/1e6
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            lease=conn.execute('SELECT run_id FROM lease WHERE id=1').fetchone()
            policy=conn.execute('SELECT allowed,halted FROM policy WHERE id=1').fetchone()
            if lease!=(run_id,) or policy[1] or input_hash not in json.loads(policy[0]): raise LiveError('configuration_error')
            n,total=conn.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            hashes={r[0] for r in conn.execute('SELECT DISTINCT input_hash FROM reservations')}
            if n>=20 or total+cost>20 or len(hashes|{input_hash})>12: raise LiveError('configuration_error')
            conn.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',
                         (run_id,attempt_no,input_hash,cost,datetime.now(timezone.utc).isoformat()))
        return cost

    def completed(self,run_id,attempt_no):
        with self.connection() as conn:
            conn.execute('UPDATE reservations SET completed=1 WHERE run_id=? AND attempt_no=?',(run_id,attempt_no))

    def release(self,run_id):
        with self.connection() as conn: conn.execute('DELETE FROM lease WHERE run_id=?',(run_id,))

    def halt(self,reason):
        with self.connection() as conn: conn.execute('UPDATE policy SET halted=? WHERE id=1',(reason,))

    def summary(self):
        with self.connection() as conn:
            n,cost,inputs=conn.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0),COUNT(DISTINCT input_hash) FROM reservations').fetchone()
            return dict(reserved_attempts=n,reserved_upper_cny=cost,distinct_inputs=inputs,
                pending_dispatches=conn.execute('SELECT COUNT(*) FROM reservations WHERE completed=0').fetchone()[0],
                active_lease=bool(conn.execute('SELECT 1 FROM lease').fetchone()),halted=conn.execute('SELECT halted FROM policy').fetchone()[0])
