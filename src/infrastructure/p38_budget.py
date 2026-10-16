"""Separate future authorization ledger. No P3.6 path, reset, or borrowed allowance."""
from datetime import datetime,timezone
import json
from pathlib import Path
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.evaluation.p38_ab import preflight


class P38Budget(PilotBudget):
    def __init__(self,path):
        path=Path(path).resolve();root=Path(__file__).resolve().parents[2]
        if any(path.is_relative_to(root/p) for p in ('data','outputs','docs','.local/p36','.local/p37','.local/p35','.local/p2-pilot-v1')):
            raise ValueError('Historical budget/asset directory is read-only')
        super().__init__(path)

    def pricing(self):
        with self.connection() as conn:m=json.loads(conn.execute('SELECT manifest FROM policy WHERE id=1').fetchone()[0])
        return m['authorization']

    def estimate_cost(self,metadata):
        auth=self.pricing();i,o=metadata.get('input_tokens'),metadata.get('output_tokens');prices=auth['prices']
        return (i*prices['input_cny_per_million']+o*prices['output_cny_per_million'])/1e6 if i is not None and o is not None else None

    @classmethod
    def create(cls,path,experiment,authorization):
        if authorization is None:raise ValueError('Fresh explicit P3.8 authorization required; current budget is zero')
        preflight(experiment,authorization)  # Reject before any filesystem write.
        path=Path(path).resolve()
        root=Path(__file__).resolve().parents[2]
        if any(path.is_relative_to(root/p) for p in ('data','outputs','docs','.local/p36','.local/p37','.local/p35','.local/p2-pilot-v1')):
            raise ValueError('Historical budget/asset directory is read-only')
        return super().create(path,[r['input_hash'] for r in experiment['inputs']],dict(experiment=experiment,authorization=authorization))

    def verify_config(self,config):
        with self.connection() as conn:m=json.loads(conn.execute('SELECT manifest FROM policy WHERE id=1').fetchone()[0])
        preflight(m['experiment'],m['authorization'])
        if config.model_dump() not in m['experiment']['configs'].values():raise LiveError('configuration_error')

    def reserve(self,run_id,attempt_no,input_hash,messages,max_tokens):
        size=len(json.dumps(messages,ensure_ascii=False).encode('utf8'))+1024
        if size>50000 or max_tokens!=4000:raise LiveError('configuration_error')
        exhausted=False
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            manifest,allowed,halted=conn.execute('SELECT manifest,allowed,halted FROM policy WHERE id=1').fetchone()
            m=json.loads(manifest);auth=m['authorization'];preflight(m['experiment'],auth)
            if halted or input_hash not in json.loads(allowed) or conn.execute('SELECT run_id FROM lease').fetchone()!=(run_id,):
                raise LiveError('configuration_error')
            from src.evaluation.p38_ab import messages as expected_messages
            from src.domain.contracts import EmailInput
            row=next(r for r in m['experiment']['inputs'] if r['input_hash']==input_hash)
            email=EmailInput.model_validate(row['email'])
            if messages not in [expected_messages(email,arm) for arm in ('A','B')]:raise LiveError('configuration_error')
            prices=auth['prices'];cost=(size*prices['input_cny_per_million']+max_tokens*prices['output_cny_per_million'])/1e6
            count,total=conn.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            if count>=auth['requests'] or total+cost>auth['cny']:
                conn.execute("UPDATE policy SET halted='authorization_limit' WHERE id=1");exhausted=True
            else:
                conn.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',
                    (run_id,attempt_no,input_hash,cost,datetime.now(timezone.utc).isoformat()))
                if count+1==auth['requests']:conn.execute("UPDATE policy SET halted='authorization_limit' WHERE id=1")
        if exhausted:raise LiveError('configuration_error')
        return cost
