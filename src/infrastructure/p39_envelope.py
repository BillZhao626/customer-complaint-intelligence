"""One append-only P3.9 authorization envelope, inheriting the locked v1 spend.

No network/client creation. Candidate dispatch is blocked without explicit
comparison approval. Planned ceiling is 65, never an automatic use of the other7.
"""
from contextlib import contextmanager,closing
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from src.domain.contracts import digest
from src.application.p39_v2 import require_comparison_approval


def inherited(path):
    path=Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
        c.execute('PRAGMA query_only=ON')
        manifest,halted=c.execute('SELECT manifest,halted FROM policy').fetchone()
        rows=c.execute('SELECT run_id,attempt_no,input_hash,reserved_cny,completed FROM reservations ORDER BY id').fetchall()
        if not halted or c.execute('SELECT COUNT(*) FROM lease').fetchone()[0] or not rows or any(r[4]!=1 for r in rows):raise ValueError('Prior ledger must be locked, settled and lease-free')
    return dict(source_path=str(path),source_sha256=sha256(path.read_bytes()).hexdigest(),policy=json.loads(manifest),halted=halted,rows=rows)


class P39Envelope:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        with self.connection() as c:request=json.loads(c.execute('SELECT request FROM root').fetchone()[0])
        canonical=Path(__file__).resolve().parents[2]/'.local/p39/v2/shared-envelope.sqlite3'
        if not request.get('offline_test_fixture') and self.path!=canonical.resolve():raise PermissionError('Production authorization has exactly one canonical envelope path')

    @contextmanager
    def connection(self):
        c=sqlite3.connect(self.path,timeout=10)
        try:
            with c:yield c
        finally:c.close()

    @classmethod
    def create(cls,path,prior_path,manifest,request):
        prior=inherited(prior_path)
        if len(prior['rows'])!=1 or prior['policy']['authorization']['requests']!=72 or prior['policy']['authorization']['cny']!=10:
            raise ValueError('Expected the one original P3.9 request and shared72/10 root authorization')
        if (not request.get('user_evidence') or sha256(request['user_evidence'].encode('utf8')).hexdigest()!=request.get('user_evidence_sha256')
            or request.get('combined_planned_requests')!=65 or request.get('explicit_extra_allowance')!=1):raise ValueError('Missing real continuation scope evidence')
        if manifest['parent_v1_manifest_hash']!=prior['policy']['experiment']['manifest_hash']:raise ValueError('Wrong prior experiment')
        path=Path(path).resolve();root=Path(__file__).resolve().parents[2]
        if not request.get('offline_test_fixture') and path!=(root/'.local/p39/v2/shared-envelope.sqlite3').resolve():
            raise PermissionError('Cannot clone production allowance into another ledger')
        if path.is_relative_to(root) and not path.is_relative_to(root/'.local/p39/v2'):raise ValueError('Envelope must be isolated from historical ledgers')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb'):pass
        with closing(sqlite3.connect(path)) as c,c:
            c.executescript('''CREATE TABLE root(id INTEGER PRIMARY KEY,prior TEXT,manifest TEXT,request TEXT);
                CREATE TABLE events(id INTEGER PRIMARY KEY,kind TEXT,run_id TEXT UNIQUE,upper_cny REAL,created_at TEXT);
                CREATE TABLE lease(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT);
                CREATE TABLE approvals(kind TEXT PRIMARY KEY,evidence TEXT);''')
            c.execute('INSERT INTO root VALUES(1,?,?,?)',(json.dumps(prior),json.dumps(manifest),json.dumps(request)))
            for r in prior['rows']:c.execute('INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES(?,?,?,?)',('inherited_v1',r[0],r[3],datetime.now(timezone.utc).isoformat()))
        return cls(path)

    def current_manifest(self,c):
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='candidate_revisions'").fetchone():
            row=c.execute('SELECT manifest FROM candidate_revisions ORDER BY id DESC LIMIT 1').fetchone()
            if row:return json.loads(row[0])
        return json.loads(c.execute('SELECT manifest FROM root').fetchone()[0])

    def register_candidate(self,manifest,request):
        """Append an offline candidate identity; never reset root, spend, lease or approval."""
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0] or c.execute('SELECT 1 FROM approvals').fetchone() or c.execute('SELECT 1 FROM lease').fetchone():
                raise PermissionError('Candidate revision forbidden after approval or dispatch')
            old=self.current_manifest(c);original=json.loads(c.execute('SELECT request FROM root').fetchone()[0])
            if (request!=original or any(manifest.get(k)!=old.get(k) for k in ('parent_v1_manifest_hash','inputs_hash','schema_hash','urgency_validation_profile'))
                or manifest.get('schedule')!=old.get('schedule')):raise ValueError('Candidate revision changed inherited scope')
            c.execute('CREATE TABLE IF NOT EXISTS candidate_revisions(id INTEGER PRIMARY KEY,manifest TEXT,created_at TEXT)')
            c.execute('INSERT INTO candidate_revisions(manifest,created_at) VALUES(?,?)',(json.dumps(manifest),datetime.now(timezone.utc).isoformat()))

    def approve(self,review):
        with self.connection() as c:
            m=self.current_manifest(c);require_comparison_approval(m,review)
            c.execute('INSERT INTO approvals VALUES(?,?)',('comparison',json.dumps(review)))

    def reserve(self,run_id,upper_cny):
        if type(upper_cny) not in (int,float) or not 0<upper_cny<10:raise ValueError('Positive finite reserve required')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            prior=c.execute('SELECT prior FROM root').fetchone()[0];prior=json.loads(prior);m=self.current_manifest(c)
            # Tampering or later writes to the inherited ledger never free allowance.
            if sha256(Path(prior['source_path']).read_bytes()).hexdigest()!=prior['source_sha256']:raise PermissionError('Inherited ledger changed')
            approval=c.execute("SELECT evidence FROM approvals WHERE kind='comparison'").fetchone()
            require_comparison_approval(m,json.loads(approval[0]) if approval else None)
            if c.execute('SELECT 1 FROM lease').fetchone():raise PermissionError('Unsettled global request lease')
            n,cost=c.execute("SELECT COUNT(*),COALESCE(SUM(upper_cny),0) FROM events WHERE kind!='settled'").fetchone()
            if n>=65 or n>=72 or cost+upper_cny>10:raise PermissionError('Shared plan/authorization cap reached')
            # After1 inherited +8 smoke, remaining needs a separate human receipt-bound gate.
            if n>=9 and not c.execute("SELECT 1 FROM approvals WHERE kind='smoke'").fetchone():raise PermissionError('Smoke content approval required')
            c.execute('INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES(?,?,?,?)',('v2_reserved',run_id,upper_cny,datetime.now(timezone.utc).isoformat()))
            c.execute('INSERT INTO lease VALUES(1,?)',(run_id,))

    def finish(self,run_id):
        with self.connection() as c:
            if c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,):raise ValueError('Wrong lease owner')
            c.execute('DELETE FROM lease WHERE run_id=?',(run_id,))
            c.execute('INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES(?,?,0,?)',('settled','settled:'+run_id,datetime.now(timezone.utc).isoformat()))

    def summary(self):
        with self.connection() as c:
            n,total=c.execute("SELECT COUNT(*),COALESCE(SUM(upper_cny),0) FROM events WHERE kind!='settled'").fetchone()
            return dict(shared_requests=n,shared_reserved_upper_cny=total,inherited_requests=1,new_reserved_requests=n-1,
                current_candidate_manifest_hash=self.current_manifest(c)['manifest_hash'],
                hard_requests=72,planned_combined_ceiling=65,hard_cny=10,automatic_extra_retests=0,
                comparison_approved=bool(c.execute("SELECT 1 FROM approvals WHERE kind='comparison'").fetchone()),
                active_lease=bool(c.execute('SELECT 1 FROM lease').fetchone()))
