"""SQLite new-runs only; historical assets are never imported or overwritten."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from src.domain.contracts import AnalysisRun


class Repository:
    def __init__(self,path):
        self.path=Path(path).expanduser().resolve()
        root=Path(__file__).resolve().parents[2]
        for protected in ('data','outputs','docs'):
            if self.path.is_relative_to(root/protected):
                raise ValueError('Database must be outside protected data, outputs and docs')
        if self.path.suffix not in ('.sqlite3','.sqlite','.db'):
            raise ValueError('Use a dedicated .sqlite3 database path')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as conn:
            version=conn.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1,2):
                raise ValueError('Unsupported database version; no automatic migration')
            if version==1:
                from uuid import uuid4
                backup=self.path.with_name(self.path.name+'.p1-backup-'+str(uuid4())+'.sqlite3')
                with closing(sqlite3.connect(backup)) as target:
                    conn.backup(target)
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS emails (
                    input_id TEXT PRIMARY KEY, email_id TEXT NOT NULL, input_hash TEXT NOT NULL,
                    subject TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(email_id,input_hash));
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, input_id TEXT NOT NULL REFERENCES emails(input_id),
                    idempotency_key TEXT NOT NULL, cohort_id TEXT NOT NULL, config_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('succeeded','failed')), created_at TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS successful_key ON runs(idempotency_key) WHERE status='succeeded';
                CREATE TABLE IF NOT EXISTS results (
                    run_id TEXT PRIMARY KEY REFERENCES runs(run_id), normalized_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    run_id TEXT NOT NULL REFERENCES runs(run_id), attempt_no INTEGER NOT NULL,
                    detail_json TEXT NOT NULL, PRIMARY KEY(run_id,attempt_no));

            ''')
            if version in (0,1):
                conn.execute('BEGIN IMMEDIATE')
                # Another initializer may have completed migration while we waited.
                if conn.execute('PRAGMA user_version').fetchone()[0]==2:
                    return
                conn.execute('ALTER TABLE runs ADD COLUMN execution_state TEXT')
                conn.execute("ALTER TABLE runs ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
                conn.execute("CREATE UNIQUE INDEX live_claim ON runs(idempotency_key) WHERE json_extract(config_json,'$.backend')='deepseek_live'")
                conn.execute('PRAGMA user_version=2')
        from datetime import datetime,timedelta,timezone
        self.mark_stale_live((datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat())

    def connect(self):
        from contextlib import contextmanager
        @contextmanager
        def connection():
            conn=sqlite3.connect(self.path,timeout=10)
            conn.row_factory=sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            try:
                with conn:
                    yield conn
            finally:
                conn.close()
        return connection()

    def successful(self,key):
        with self.connect() as conn:
            row=conn.execute("SELECT run_id FROM runs WHERE idempotency_key=? AND status='succeeded'",(key,)).fetchone()
        return self.get(row['run_id']) if row else None

    def save(self,run: AnalysisRun):
        from src.domain.contracts import digest, idempotency_key
        if run.config.schema_version=='analysis-v3' and run.result:
            from src.domain.analysis_v3 import stored_analysis
            stored_analysis(run)
        if (run.status=='succeeded') != (run.result is not None):
            raise ValueError('Run status/result mismatch')
        if run.input_hash!=run.email.input_hash or run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config):
            raise ValueError('Run/input/version binding mismatch')
        if not run.attempts or (run.status=='succeeded' and (run.attempts[-1].error or run.attempts[-1].contract_status!='passed')):
            raise ValueError('Run/attempt outcome mismatch')
        input_id=digest(dict(email_id=run.email.email_id,input_hash=run.input_hash))
        try:
            with self.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('INSERT OR IGNORE INTO emails VALUES(?,?,?,?,?)',(input_id,run.email.email_id,run.input_hash,run.email.subject,run.email.body))
                conn.execute('INSERT INTO runs(run_id,input_id,idempotency_key,cohort_id,config_json,status,created_at) VALUES(?,?,?,?,?,?,?)',(run.run_id,input_id,run.idempotency_key,run.cohort_id,run.config.model_dump_json(),run.status,run.created_at))
                conn.execute('UPDATE runs SET metadata_json=? WHERE run_id=?',(json.dumps(run.metadata,ensure_ascii=False),run.run_id))
                if run.result:
                    conn.execute('INSERT INTO results VALUES(?,?)',(run.run_id,run.result.model_dump_json()))
                for attempt in run.attempts:
                    conn.execute('INSERT INTO attempts VALUES(?,?,?)',(run.run_id,attempt.attempt_no,attempt.model_dump_json()))
        except sqlite3.IntegrityError:
            existing=self.successful(run.idempotency_key)
            if existing and run.status=='succeeded':
                return existing
            raise
        return self.get(run.run_id)

    def get(self,run_id):
        with self.connect() as conn:
            row=conn.execute('SELECT r.*,e.email_id,e.input_hash,e.subject,e.body FROM runs r JOIN emails e USING(input_id) WHERE run_id=?',(run_id,)).fetchone()
            if row is None:
                return None
            result=conn.execute('SELECT normalized_json FROM results WHERE run_id=?',(run_id,)).fetchone()
            attempts=conn.execute('SELECT detail_json FROM attempts WHERE run_id=? ORDER BY attempt_no',(run_id,)).fetchall()
        run=AnalysisRun.model_validate(dict(run_id=row['run_id'],idempotency_key=row['idempotency_key'],
            email=dict(email_id=row['email_id'],subject=row['subject'],body=row['body']),input_hash=row['input_hash'],
            config=json.loads(row['config_json']),cohort_id=row['cohort_id'],status=row['execution_state'] or row['status'],created_at=row['created_at'],metadata=json.loads(row['metadata_json']),
            result=json.loads(result[0]) if result else None,attempts=[json.loads(a[0]) for a in attempts]))
        if run.config.schema_version=='analysis-v3' and run.result:
            from src.domain.analysis_v3 import stored_analysis
            stored_analysis(run)
        return run

    def list_runs(self,cohort_id=None,status=None,store=None,product=None):
        with self.connect() as conn:
            rows=conn.execute('SELECT run_id FROM runs ORDER BY created_at DESC, run_id').fetchall()
        runs=[self.get(row['run_id']) for row in rows]
        return [r for r in runs if (cohort_id is None or r.cohort_id==cohort_id) and (status is None or r.status==status)
                and (store is None or (r.result and r.result.store_location==store))
                and (product is None or (r.result and r.result.product_category==product))]

    def claim_live(self,email,config):
        """Reserve once, including failed/unknown outcomes. Never automatically replay."""
        from uuid import uuid4
        from src.application.analysis_service import now
        from src.domain.contracts import digest,idempotency_key
        key=idempotency_key(email,config)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT run_id FROM runs WHERE idempotency_key=?',(key,)).fetchone()
            if row:
                run_id=row[0];owned=False
            else:
                run_id=str(uuid4());owned=True
                input_id=digest(dict(email_id=email.email_id,input_hash=email.input_hash))
                conn.execute('INSERT OR IGNORE INTO emails VALUES(?,?,?,?,?)',(input_id,email.email_id,email.input_hash,email.subject,email.body))
                conn.execute("INSERT INTO runs(run_id,input_id,idempotency_key,cohort_id,config_json,status,created_at,execution_state) VALUES(?,?,?,?,?,'failed',?,'running')",
                             (run_id,input_id,key,config.cohort_id,config.model_dump_json(),now()))
        return self.get(run_id),owned

    def put_attempt(self,run_id,attempt):
        with self.connect() as conn:
            conn.execute('INSERT INTO attempts VALUES(?,?,?) ON CONFLICT(run_id,attempt_no) DO UPDATE SET detail_json=excluded.detail_json',
                         (run_id,attempt.attempt_no,attempt.model_dump_json()))

    def finish_live(self,run_id,status,result,metadata):
        if status not in ('succeeded','failed','interrupted_or_unknown') or (status=='succeeded')!=(result is not None):
            raise ValueError('Invalid terminal state')
        current=self.get(run_id)
        if current and current.config.schema_version=='analysis-v3' and result:
            from src.domain.analysis_v3 import stored_analysis
            stored_analysis(current.model_copy(update={'status':status,'result':result,'metadata':metadata}))
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if result:
                conn.execute('INSERT INTO results VALUES(?,?)',(run_id,result.model_dump_json()))
            conn.execute('UPDATE runs SET status=?,execution_state=?,metadata_json=? WHERE run_id=?',
                         ('succeeded' if result else 'failed',status,json.dumps(metadata),run_id))
        return self.get(run_id)

    def mark_stale_live(self,older_than):
        """No replay: only mark expired started rows, retaining pending attempts."""
        with self.connect() as conn:
            conn.execute("UPDATE runs SET execution_state='interrupted_or_unknown' WHERE execution_state='running' AND created_at<?",(older_than,))
