"""Explicit offline context-profile repository. Historical read dispatch is untouched."""
import json
import sqlite3
from pathlib import Path
from src.infrastructure.repository import Repository
from src.infrastructure.dashboard_sources import ReadOnlyRepository
from src.domain.contracts import AnalysisRun,digest,idempotency_key
from src.domain.analysis_v31_context import stored_context_analysis
from src.application.urgency_context_v1 import PROFILE


class ContextRepository(Repository):
    def __init__(self,path):
        path=Path(path).resolve();root=Path(__file__).resolve().parents[2]
        if path.is_relative_to(root) and not path.is_relative_to(root/'.local/p39/v2'):raise ValueError('Only isolated v2 context runtime allowed')
        super().__init__(path)

    def save(self,run):
        if run.config.backend!='offline_fake' or run.config.parameters.get('urgency_validation_profile')!=PROFILE:
            raise PermissionError('Candidate storage supports explicit offline profile only')
        if run.result:stored_context_analysis(run)
        if (run.status=='succeeded')!=(run.result is not None):raise ValueError('Run status/result mismatch')
        if run.input_hash!=run.email.input_hash or run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config):raise ValueError('Run/input/version binding mismatch')
        if not run.attempts or (run.result and (run.attempts[-1].error or run.attempts[-1].contract_status!='passed')):raise ValueError('Run/attempt outcome mismatch')
        input_id=digest(dict(email_id=run.email.email_id,input_hash=run.input_hash))
        try:
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute('INSERT OR IGNORE INTO emails VALUES(?,?,?,?,?)',(input_id,run.email.email_id,run.input_hash,run.email.subject,run.email.body))
                c.execute('INSERT INTO runs(run_id,input_id,idempotency_key,cohort_id,config_json,status,created_at) VALUES(?,?,?,?,?,?,?)',(run.run_id,input_id,run.idempotency_key,run.cohort_id,run.config.model_dump_json(),run.status,run.created_at))
                c.execute('UPDATE runs SET metadata_json=? WHERE run_id=?',(json.dumps(run.metadata,ensure_ascii=False),run.run_id))
                if run.result:c.execute('INSERT INTO results VALUES(?,?)',(run.run_id,run.result.model_dump_json()))
                for attempt in run.attempts:c.execute('INSERT INTO attempts VALUES(?,?,?)',(run.run_id,attempt.attempt_no,attempt.model_dump_json()))
        except sqlite3.IntegrityError:
            existing=self.successful(run.idempotency_key)
            if existing and run.status=='succeeded':return existing
            raise
        return self.get(run.run_id)

    def get(self,run_id):
        with self.connect() as c:
            row=c.execute('SELECT r.*,e.email_id,e.input_hash,e.subject,e.body FROM runs r JOIN emails e USING(input_id) WHERE run_id=?',(run_id,)).fetchone()
            if row is None:return None
            result=c.execute('SELECT normalized_json FROM results WHERE run_id=?',(run_id,)).fetchone()
            attempts=c.execute('SELECT detail_json FROM attempts WHERE run_id=? ORDER BY attempt_no',(run_id,)).fetchall()
        run=AnalysisRun.model_validate(dict(run_id=row['run_id'],idempotency_key=row['idempotency_key'],email=dict(email_id=row['email_id'],subject=row['subject'],body=row['body']),
            input_hash=row['input_hash'],config=json.loads(row['config_json']),cohort_id=row['cohort_id'],status=row['execution_state'] or row['status'],created_at=row['created_at'],
            metadata=json.loads(row['metadata_json']),result=json.loads(result[0]) if result else None,attempts=[json.loads(a[0]) for a in attempts]))
        if run.config.parameters.get('urgency_validation_profile')!=PROFILE:raise ValueError('Wrong stored profile')
        if run.result:stored_context_analysis(run)
        return run

    def claim_live(self,*args,**kwargs):raise PermissionError('Candidate repository has no paid dispatch path')
    def finish_live(self,*args,**kwargs):raise PermissionError('Candidate repository has no paid dispatch path')


class ReadOnlyContextRepository(ContextRepository):
    def __init__(self,path):ReadOnlyRepository.__init__(self,path)
    def connect(self):return ReadOnlyRepository.connect(self)
    def save(self,*args,**kwargs):raise PermissionError('Read-only context repository')
