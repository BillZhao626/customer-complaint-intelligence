"""Approved P3.9-v2 live storage and shared-envelope adapter.

Economic events remain in the sole pre-existing envelope. Additional tables
bind dispatch to the approved schedule and retain unknown sends across restart.
No creation/reset of authorization, automatic retest or smoke approval API.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from src.domain.contracts import EmailInput, digest
from src.domain.analysis_v31_context import stored_context_analysis
from src.infrastructure.context_repository import ContextRepository
from src.infrastructure.repository import Repository
from src.infrastructure.p39_envelope import P39Envelope
from src.infrastructure.deepseek import LiveError
from src.application.p39_v2 import messages, require_comparison_approval


class ContextLiveRepository(ContextRepository):
    def claim_live(self, email, config):
        return Repository.claim_live(self, email, config)

    def finish_live(self, run_id, status, result, metadata):
        if status not in ('succeeded', 'failed', 'interrupted_or_unknown') or (status == 'succeeded') != (result is not None):
            raise ValueError('Invalid terminal state')
        current = self.get(run_id)
        if result:
            stored_context_analysis(current.model_copy(update={'status': status, 'result': result, 'metadata': metadata}))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if result:
                c.execute('INSERT INTO results VALUES(?,?)', (run_id, result.model_dump_json()))
            c.execute('UPDATE runs SET status=?,execution_state=?,metadata_json=? WHERE run_id=?',
                      ('succeeded' if result else 'failed', status, json.dumps(metadata), run_id))
        return self.get(run_id)


class ContextLiveBudget(P39Envelope):
    """Adds typed dispatch bindings; never creates a new economic envelope."""
    def __init__(self, path, counter):
        super().__init__(path)
        self.counter = counter
        self._config = None

    def install(self, runtime):
        from src.application.p39_context_live import verify_runtime
        verify_runtime(runtime)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            m = self.current_manifest(c)
            if m != runtime['candidate']:
                raise ValueError('Approved candidate drift')
            request=json.loads(c.execute('SELECT request FROM root').fetchone()[0])
            if bool(request.get('offline_test_fixture')) != runtime['offline_test_fixture']:
                raise PermissionError('Cannot attach offline fixture identity to production authorization')
            approval = c.execute("SELECT evidence FROM approvals WHERE kind='comparison'").fetchone()
            require_comparison_approval(m, json.loads(approval[0]) if approval else None)
            c.executescript('''CREATE TABLE IF NOT EXISTS live_wiring(id INTEGER PRIMARY KEY CHECK(id=1),runtime TEXT);
                CREATE TABLE IF NOT EXISTS wire_claim(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT,input_hash TEXT,arm TEXT,config_hash TEXT);
                CREATE TABLE IF NOT EXISTS wire_payloads(run_id TEXT PRIMARY KEY,bounds TEXT,completed INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS wire_stops(id INTEGER PRIMARY KEY,reason TEXT,created_at TEXT);''')
            row = c.execute('SELECT runtime FROM live_wiring').fetchone()
            if row:
                if json.loads(row[0]) != runtime:
                    raise PermissionError('Existing runtime identity cannot be replaced')
            else:
                if c.execute("SELECT 1 FROM events WHERE kind='v2_reserved'").fetchone() or c.execute('SELECT 1 FROM lease').fetchone():
                    raise PermissionError('Cannot initialize wiring after dispatch')
                c.execute('INSERT INTO live_wiring VALUES(1,?)', (json.dumps(runtime),))

    def runtime(self):
        with self.connection() as c:
            return json.loads(c.execute('SELECT runtime FROM live_wiring').fetchone()[0])

    def pricing(self):
        p = self.runtime()['price_receipt']
        return dict(price_source=p['price_source'], prices_verified_at=p['checked_at'], prices=p['prices'])

    def estimate_cost(self, metadata):
        i, o = metadata.get('input_tokens'), metadata.get('output_tokens')
        p = self.pricing()['prices']
        return (i*p['input_cny_per_million']+o*p['output_cny_per_million'])/1e6 if type(i) is int and type(o) is int and min(i,o)>=0 else None

    def verify_config(self, config):
        from src.application.p39_context_live import verify_runtime
        runtime = self.runtime(); verify_runtime(runtime)
        if config.model_dump() not in runtime['candidate']['configs'].values():
            raise LiveError('configuration_error')
        self._config = config

    def acquire(self, run_id, input_hash):
        if self._config is None:
            raise LiveError('configuration_error')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            prior = json.loads(c.execute('SELECT prior FROM root').fetchone()[0])
            if sha256(Path(prior['source_path']).read_bytes()).hexdigest() != prior['source_sha256']:
                raise PermissionError('Inherited ledger changed')
            if c.execute('SELECT 1 FROM wire_stops').fetchone() or c.execute('SELECT 1 FROM wire_claim').fetchone() or c.execute('SELECT 1 FROM lease').fetchone():
                raise PermissionError('Stopped or unsettled global dispatch')
            n = c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0]
            # This executable supports smoke only. No path can approve/dispatch remaining.
            if n >= 8:
                raise PermissionError('Researcher receipt-bound content approval required')
            m = self.current_manifest(c); step = m['schedule'][n]; row = m['inputs'][step['input_index']]
            if input_hash != row['input_hash'] or self._config.model_dump() != m['configs'][step['arm']]:
                raise PermissionError('Fixed smoke schedule mismatch')
            c.execute('INSERT INTO wire_claim VALUES(1,?,?,?,?)', (run_id,input_hash,step['arm'],digest(self._config.model_dump())))

    def reserve(self, run_id, attempt_no, input_hash, msgs, max_tokens):
        if attempt_no != 1 or max_tokens != 4000:
            raise LiveError('configuration_error')
        with self.connection() as c:
            claim = c.execute('SELECT run_id,input_hash,arm,config_hash FROM wire_claim').fetchone()
            m = self.current_manifest(c)
            if not claim or claim[:2] != (run_id,input_hash) or claim[3] != digest(m['configs'][claim[2]]):
                raise PermissionError('Wrong dispatch claim')
            row = next(r for r in m['inputs'] if r['input_hash'] == input_hash)
            if msgs != messages(EmailInput.model_validate(row['email']),claim[2]):
                raise PermissionError('Payload differs from approved prompt/input')
        bound = self.counter.measure(msgs)
        if type(bound['input_token_reserve']) is not int or bound['input_token_reserve'] <= 0 or bound['payload_bytes'] > 50000:
            raise LiveError('configuration_error')
        p = self.pricing()['prices']
        cost = (bound['input_token_reserve']*p['input_cny_per_million']+4000*p['output_cny_per_million'])/1e6
        if not math.isfinite(cost):
            raise ValueError('Nonfinite cost')
        # The original envelope performs the authoritative cumulative cap check
        # and economic reservation. A crash at either boundary keeps wire_claim.
        super().reserve(run_id,cost)
        with self.connection() as c:
            c.execute('INSERT INTO wire_payloads(run_id,bounds) VALUES(?,?)',(run_id,json.dumps(bound)))
        return cost

    def completed(self, run_id, attempt_no):
        if attempt_no != 1:
            raise PermissionError('No automatic retry')
        with self.connection() as c:
            if c.execute('UPDATE wire_payloads SET completed=1 WHERE run_id=?',(run_id,)).rowcount != 1:
                raise ValueError('Missing reserved payload')

    def release(self, run_id):
        super().finish(run_id)
        with self.connection() as c:
            if c.execute('DELETE FROM wire_claim WHERE run_id=?',(run_id,)).rowcount != 1:
                raise ValueError('Wrong dispatch owner')

    def halt(self, reason):
        with self.connection() as c:
            c.execute('INSERT INTO wire_stops(reason,created_at) VALUES(?,?)',(reason,datetime.now(timezone.utc).isoformat()))

    def summary(self):
        result = super().summary()
        with self.connection() as c:
            installed = c.execute("SELECT 1 FROM sqlite_master WHERE name='wire_stops'").fetchone()
            result.update(halted=c.execute('SELECT reason FROM wire_stops ORDER BY id LIMIT 1').fetchone()[0] if installed and c.execute('SELECT 1 FROM wire_stops').fetchone() else None,
                          active_wire_claim=bool(installed and c.execute('SELECT 1 FROM wire_claim').fetchone()))
        return result
