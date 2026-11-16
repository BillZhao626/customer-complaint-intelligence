"""Append-only continuation authority on the one existing economic envelope."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from src.application.p39_continuity import verify_runtime, binding
from src.domain.contracts import digest
from src.infrastructure.p39_live_context import ContextLiveBudget


class ContinuityBudget(ContextLiveBudget):
    def install(self, rt):
        verify_runtime(rt)
        from src.application.p39_continuity import ordered_runs
        audited = ordered_runs(rt,self)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if self.current_manifest(c) != rt['candidate']:
                raise ValueError('Frozen manifest drift')
            old = c.execute('SELECT runtime FROM live_wiring').fetchone()
            if not old or json.loads(old[0]) != rt['parent_runtime']:
                raise ValueError('Parent execution drift')
            request = json.loads(c.execute('SELECT request FROM root').fetchone()[0])
            if bool(request.get('offline_test_fixture')) != rt['offline_test_fixture']:
                raise PermissionError('Fixture cannot attach production authorization')
            if c.execute('SELECT 1 FROM lease').fetchone() or c.execute('SELECT 1 FROM wire_claim').fetchone():
                raise PermissionError('Unsettled send cannot resume')
            if c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0] != len(audited):
                raise PermissionError('Dispatch changed during recovery audit')
            stops = c.execute('SELECT id,reason,created_at FROM wire_stops ORDER BY id').fetchall()
            if any(r[1] != 'failure_requires_review' for r in stops):
                raise PermissionError('Engineering stop requires explicit resolution')
            c.execute('CREATE TABLE IF NOT EXISTS r3_policy(id INTEGER PRIMARY KEY CHECK(id=1),runtime TEXT,acknowledged_stops TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS r3_receipts(run_id TEXT PRIMARY KEY,receipt TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS r3_checkpoints(kind TEXT PRIMARY KEY,receipt TEXT)')
            existing = c.execute('SELECT runtime,acknowledged_stops FROM r3_policy').fetchone()
            if existing:
                if json.loads(existing[0]) != rt:
                    raise PermissionError('Existing continuity identity cannot be replaced')
            else:
                c.execute('INSERT INTO r3_policy VALUES(1,?,?)',(json.dumps(rt),json.dumps(stops)))

    def runtime(self):
        with self.connection() as c:
            row = c.execute('SELECT runtime FROM r3_policy').fetchone()
            if not row:
                raise PermissionError('No continuity authorization')
            return json.loads(row[0])

    def summary(self):
        result = super().summary()
        with self.connection() as c:
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='r3_policy'").fetchone():
                row = c.execute('SELECT acknowledged_stops FROM r3_policy').fetchone()
                acknowledged = {r[0] for r in json.loads(row[0])} if row else set()
                stops = c.execute('SELECT id,reason FROM wire_stops ORDER BY id').fetchall()
                result['halted'] = next((reason for sid,reason in stops if sid not in acknowledged),None)
                result['historical_stops_retained'] = len(acknowledged)
                result['execution_policy'] = 'evaluation-continuity-v1'
        return result

    def verify_config(self, config):
        rt = self.runtime(); verify_runtime(rt)
        if config.model_dump() not in rt['candidate']['configs'].values():
            raise PermissionError('Frozen config drift')
        self._config = config

    def _check(self,c):
        row = c.execute('SELECT runtime,acknowledged_stops FROM r3_policy').fetchone()
        if not row:
            raise PermissionError('Missing continuity policy')
        rt = json.loads(row[0]); verify_runtime(rt)
        acknowledged = {r[0] for r in json.loads(row[1])}
        if any(r[0] not in acknowledged for r in c.execute('SELECT id FROM wire_stops')):
            raise PermissionError('Engineering safety stop')
        prior = json.loads(c.execute('SELECT prior FROM root').fetchone()[0])
        if sha256(Path(prior['source_path']).read_bytes()).hexdigest() != prior['source_sha256']:
            raise PermissionError('Inherited ledger drift')
        inherited = c.execute("SELECT run_id,upper_cny FROM events WHERE kind='inherited_v1'").fetchall()
        if inherited != [(r[0],r[3]) for r in prior['rows']]:
            raise PermissionError('Inherited economic reservation drift')
        if self.current_manifest(c) != rt['candidate']:
            raise PermissionError('Manifest drift')
        return rt

    def acquire(self,run_id,input_hash):
        if self._config is None:
            raise PermissionError('Configuration required')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE'); rt = self._check(c)
            if c.execute('SELECT 1 FROM wire_claim').fetchone() or c.execute('SELECT 1 FROM lease').fetchone():
                raise PermissionError('Global dispatch busy or uncertain')
            n = c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0]
            if n >= 64:
                raise PermissionError('Fixed experiment complete')
            if n >= 8 and not c.execute("SELECT 1 FROM r3_checkpoints WHERE kind='smoke8'").fetchone():
                raise PermissionError('Engineering checkpoint required')
            if c.execute('SELECT COUNT(*) FROM r3_receipts').fetchone()[0] != n:
                raise PermissionError('Reconcile every prior attempt before dispatch')
            step = rt['candidate']['schedule'][n]; row = rt['candidate']['inputs'][step['input_index']]
            if row['input_hash'] != input_hash or self._config.model_dump() != rt['candidate']['configs'][step['arm']]:
                raise PermissionError('Fixed schedule drift')
            c.execute('INSERT INTO wire_claim VALUES(1,?,?,?,?)',(run_id,input_hash,step['arm'],digest(self._config.model_dump())))

    def reserve(self,run_id,attempt_no,input_hash,msgs,max_tokens):
        from src.application.p39_v2 import messages
        from src.domain.contracts import EmailInput
        if attempt_no != 1 or max_tokens != 4000:
            raise PermissionError('No retries or output allowance drift')
        bound = self.counter.measure(msgs)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE'); rt = self._check(c)
            claim = c.execute('SELECT run_id,input_hash,arm,config_hash FROM wire_claim').fetchone()
            if not claim or claim[:2] != (run_id,input_hash) or claim[3] != digest(rt['candidate']['configs'][claim[2]]):
                raise PermissionError('Wrong request owner')
            row = next(r for r in rt['candidate']['inputs'] if r['input_hash'] == input_hash)
            if msgs != messages(EmailInput.model_validate(row['email']),claim[2]):
                raise PermissionError('Payload drift')
            if type(bound['input_token_reserve']) is not int or bound['input_token_reserve'] <= 0 or bound['payload_bytes'] > 50000:
                raise ValueError('Unsafe payload bounds')
            p = rt['price_receipt']['prices']
            cost = (bound['input_token_reserve']*p['input_cny_per_million']+4000*p['output_cny_per_million'])/1e6
            n,total = c.execute("SELECT COUNT(*),COALESCE(SUM(upper_cny),0) FROM events WHERE kind!='settled'").fetchone()
            fixed = c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0]
            if (not math.isfinite(cost) or not 0 < cost < 10 or fixed >= 64 or n >= 65 or n >= 72 or total+cost > 10
                or c.execute('SELECT 1 FROM lease').fetchone()):
                raise PermissionError('Shared hard cap, plan cap or lease blocked')
            c.execute('INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES(?,?,?,?)',('v2_reserved',run_id,cost,datetime.now(timezone.utc).isoformat()))
            c.execute('INSERT INTO lease VALUES(1,?)',(run_id,))
            c.execute('INSERT INTO wire_payloads(run_id,bounds) VALUES(?,?)',(run_id,json.dumps(bound)))
        return cost

    def record(self,receipt):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT receipt FROM r3_receipts WHERE run_id=?',(receipt['run_id'],)).fetchone()
            if old:
                if json.loads(old[0]) != receipt:
                    raise ValueError('Attempt receipt drift')
            else:
                c.execute('INSERT INTO r3_receipts VALUES(?,?)',(receipt['run_id'],json.dumps(receipt)))

    def checkpoint(self,runs):
        rt = self.runtime()
        if len(runs) != 8:
            raise ValueError('Eight actual attempts required')
        receipts = [binding(r,rt,self.counter) for r in runs]
        receipt = dict(version='continuity-smoke8-engineering-v1',runtime_hash=rt['runtime_hash'],attempts=8,
                       accepted=sum(r.result is not None for r in runs),failed=sum(r.result is None for r in runs),
                       bindings=receipts,engineering_safe=True,human_content_approval=None,reply_status='unreviewed_unsent')
        receipt['receipt_hash'] = digest(receipt)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE'); self._check(c)
            if c.execute('SELECT 1 FROM lease').fetchone() or c.execute('SELECT 1 FROM wire_claim').fetchone():
                raise PermissionError('Checkpoint has unsettled dispatch')
            old = c.execute("SELECT receipt FROM r3_checkpoints WHERE kind='smoke8'").fetchone()
            if old:
                if json.loads(old[0]) != receipt:
                    raise ValueError('Checkpoint drift')
            else:
                c.execute('INSERT INTO r3_checkpoints VALUES(?,?)',('smoke8',json.dumps(receipt)))
        target = Path(rt['runtime_directory'])/'smoke8-checkpoint.json'
        if not target.exists():
            from src.application.p39_context_live import write_new
            write_new(target,receipt)
        elif json.loads(target.read_text(encoding='utf8')) != receipt:
            raise ValueError('Checkpoint export drift')
        return receipt
