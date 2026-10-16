"""Fixed-schedule P3.9 budget. No reset, automatic retests or historical write path."""
from datetime import datetime, timezone
import json
from pathlib import Path
from src.domain.contracts import EmailInput, digest
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.application.p39_experiment import preflight, messages, validate_smoke_review


class P39Budget(PilotBudget):
    def __init__(self, path, counter):
        path = Path(path).resolve(); root = Path(__file__).resolve().parents[2]
        if path.is_relative_to(root) and not path.is_relative_to(root / '.local/p39'):
            raise ValueError('P3.9 ledger must be isolated from historical assets')
        super().__init__(path); self.counter = counter; self._config = None

    @classmethod
    def create(cls, path, m, auth, counter):
        preflight(m, auth)
        if auth is None: raise PermissionError('Missing P3.9 authorization')
        path = Path(path).resolve(); root = Path(__file__).resolve().parents[2]
        if path.is_relative_to(root) and not path.is_relative_to(root / '.local/p39'):
            raise ValueError('Historical path forbidden')
        # Explicit creation and schema are local to this new ledger only.
        path.parent.mkdir(parents=True, exist_ok=False)
        with path.open('xb'): pass
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.executescript('''CREATE TABLE policy(id INTEGER PRIMARY KEY,manifest TEXT,allowed TEXT,halted TEXT);
                CREATE TABLE lease(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT NOT NULL);
                CREATE TABLE reservations(id INTEGER PRIMARY KEY,run_id TEXT,attempt_no INTEGER,input_hash TEXT,
                  reserved_cny REAL,created_at TEXT,completed INTEGER DEFAULT 0,UNIQUE(run_id,attempt_no));
                CREATE TABLE claims(run_id TEXT PRIMARY KEY,arm TEXT,input_hash TEXT,config_hash TEXT);
                CREATE TABLE payloads(run_id TEXT PRIMARY KEY,bounds TEXT);
                CREATE TABLE content_gate(id INTEGER PRIMARY KEY,receipt_hash TEXT,review TEXT);''')
            conn.execute('INSERT INTO policy VALUES(1,?,?,NULL)', (json.dumps(dict(experiment=m,authorization=auth)), json.dumps([r['input_hash'] for r in m['inputs']])))
        return cls(path, counter)

    def saved_policy(self):
        with self.connection() as c: return json.loads(c.execute('SELECT manifest FROM policy').fetchone()[0])

    def pricing(self): return self.saved_policy()['authorization']

    def estimate_cost(self, metadata):
        i, o = metadata.get('input_tokens'), metadata.get('output_tokens'); p = self.pricing()['prices']
        return (i*p['input_cny_per_million']+o*p['output_cny_per_million'])/1e6 if type(i) is int and type(o) is int else None

    def verify_config(self, config):
        saved = self.saved_policy(); preflight(saved['experiment'], saved['authorization'])
        if config.model_dump() not in saved['experiment']['configs'].values(): raise LiveError('configuration_error')
        self._config = config

    def acquire(self, run_id, input_hash):
        if self._config is None: raise LiveError('configuration_error')
        super().acquire(run_id,input_hash)
        with self.connection() as c:
            c.execute('INSERT INTO claims VALUES(?,?,?,?)',(run_id,self._config.parameters['arm'],input_hash,digest(self._config.model_dump())))

    def reserve(self, run_id, attempt_no, input_hash, msgs, max_tokens):
        if attempt_no != 1 or max_tokens != 4000: raise LiveError('configuration_error')
        bound = self.counter.measure(msgs)
        if bound['payload_bytes'] > 50000: raise LiveError('configuration_error')
        exhausted = False
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            raw, halted = c.execute('SELECT manifest,halted FROM policy').fetchone(); policy=json.loads(raw)
            m, auth = policy['experiment'], policy['authorization']; preflight(m,auth)
            n,total = c.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            if halted or c.execute('SELECT run_id FROM lease').fetchone() != (run_id,): raise LiveError('configuration_error')
            if n >= 64 or n >= auth['requests']: exhausted=True
            else:
                step=m['schedule'][n];row=m['inputs'][step['input_index']]
                if n >= 8 and not c.execute('SELECT 1 FROM content_gate').fetchone(): raise LiveError('configuration_error')
                expected=(step['arm'],row['input_hash'],digest(m['configs'][step['arm']]))
                if c.execute('SELECT arm,input_hash,config_hash FROM claims WHERE run_id=?',(run_id,)).fetchone()!=expected or input_hash!=row['input_hash']:
                    raise LiveError('configuration_error')
                if msgs != messages(EmailInput.model_validate(row['email']),step['arm']): raise LiveError('configuration_error')
                prices=auth['prices'];cost=(bound['input_token_reserve']*prices['input_cny_per_million']+4000*prices['output_cny_per_million'])/1e6
                if total+cost > auth['cny']: exhausted=True
            if exhausted: c.execute("UPDATE policy SET halted='authorization_limit'")
            else:
                c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',
                          (run_id,attempt_no,input_hash,cost,datetime.now(timezone.utc).isoformat()))
                c.execute('INSERT INTO payloads VALUES(?,?)',(run_id,json.dumps(bound)))
        if exhausted: raise LiveError('configuration_error')
        return cost

    def approve_remaining(self, review, receipt):
        validate_smoke_review(review,receipt)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]!=8: raise ValueError('Smoke request count mismatch')
            if c.execute('SELECT 1 FROM content_gate').fetchone(): raise ValueError('Approval already recorded')
            c.execute('INSERT INTO content_gate VALUES(1,?,?)',(digest(receipt),json.dumps(review)))
