"""P3.6 authorization only; never opens or extends the historical P2 budget."""
import json
from datetime import datetime, timezone
from src.domain.contracts import digest
from src.infrastructure.deepseek import LiveError
from src.infrastructure.pilot_budget import PilotBudget


class DevelopmentBudget(PilotBudget):
    @classmethod
    def create(cls, path, allowed_inputs, manifest):
        if manifest.get('authorization') != 'P3.6-40-requests-15-CNY-fictional-development-only':
            raise LiveError('configuration_error')
        budget = super().create(path, allowed_inputs, manifest)
        with budget.connection() as conn:
            conn.execute('CREATE TABLE configurations(cohort TEXT PRIMARY KEY, config TEXT, experiment_hash TEXT)')
        return budget

    def register(self, config, experiment_hash):
        if config.backend != 'deepseek_live' or config.schema_version != 'analysis-v3':
            raise LiveError('configuration_error')
        with self.connection() as conn:
            conn.execute('INSERT INTO configurations VALUES(?,?,?)',
                         (config.cohort_id, json.dumps(config.model_dump(), sort_keys=True), experiment_hash))

    def verify_config(self, config):
        with self.connection() as conn:
            row = conn.execute('SELECT config FROM configurations WHERE cohort=?', (config.cohort_id,)).fetchone()
        if not row or json.loads(row[0]) != config.model_dump():
            raise LiveError('configuration_error')

    def reserve(self, run_id, attempt_no, input_hash, messages, max_tokens):
        size = len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) + 1024
        if size > 50000 or not 1 <= max_tokens <= 6000:
            raise LiveError('configuration_error')
        # Peak cache-miss prices checked 2026-10-15: 2/8 CNY per million.
        # Reserve the full worst case, including failed/unknown requests; never refund.
        cost = (size * 2 + max_tokens * 8) / 1e6
        exhausted = False
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            policy = conn.execute('SELECT allowed,halted FROM policy WHERE id=1').fetchone()
            lease = conn.execute('SELECT run_id FROM lease WHERE id=1').fetchone()
            if lease != (run_id,) or policy[1] or input_hash not in json.loads(policy[0]):
                raise LiveError('configuration_error')
            count, total = conn.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            if count >= 40 or total + cost > 15:
                conn.execute("UPDATE policy SET halted='authorization_limit' WHERE id=1")
                exhausted = True
            else:
                conn.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',
                             (run_id, attempt_no, input_hash, cost, datetime.now(timezone.utc).isoformat()))
                if count + 1 == 40:
                    conn.execute("UPDATE policy SET halted='authorization_limit' WHERE id=1")
        if exhausted:
            raise LiveError('configuration_error')
        return cost
