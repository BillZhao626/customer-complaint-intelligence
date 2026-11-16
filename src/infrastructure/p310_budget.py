"""One independent180/CNY30 envelope. No implicit authorization or reset path."""
from datetime import datetime,timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3

from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import LiveError
from src.domain.contracts import digest,EmailInput

ROOT=Path(__file__).resolve().parents[2]
CANONICAL=(ROOT/'.local/p310/envelope.sqlite3').resolve()


def validate_authorization(auth,fixture=False):
    if (not isinstance(auth,dict) or auth.get('status')!='researcher_explicitly_authorized'
        or type(auth.get('requests')) is not int or auth['requests']!=180
        or type(auth.get('cny')) not in (int,float) or auth['cny']!=30
        or auth.get('model')!='deepseek-flash' or bool(auth.get('offline_fixture'))!=fixture
        or not isinstance(auth.get('user_approval_evidence'),str) or not auth['user_approval_evidence'].strip()
        or sha256(auth['user_approval_evidence'].encode()).hexdigest()!=auth.get('user_approval_sha256')
        or auth.get('price_source')!='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
        or auth.get('prices')!={'input_cny_per_million':2,'output_cny_per_million':8}
        or not auth.get('model_availability_verified') or not auth.get('prior_p39_ledger_sha256')):
        raise PermissionError('Explicit fresh180/CNY30 approval and price/model identity required')
    checked=datetime.fromisoformat(auth['prices_verified_at'])
    if checked.tzinfo is None or (not fixture and not 0<=(datetime.now(timezone.utc)-checked).total_seconds()<86400):
        raise PermissionError('Price/model receipt expired')


class ResearchBudget(PilotBudget):
    def __init__(self,path,fixture=False):
        self.fixture=fixture;path=Path(path).resolve()
        if fixture and path.is_relative_to(ROOT):raise PermissionError('Offline budgets must use temporary storage outside workspace')
        if not fixture and path!=CANONICAL:raise PermissionError('One canonical P3.10 envelope; no allowance cloning')
        super().__init__(path);self._config=None
        self.verify_root()

    @classmethod
    def create(cls,path,authorization,fixture=False):
        validate_authorization(authorization,fixture)
        path=Path(path).resolve()
        if (fixture and path.is_relative_to(ROOT)) or (not fixture and path!=CANONICAL):
            raise PermissionError('Wrong canonical envelope or offline storage')
        # No filesystem effects before permission checks. Exclusive initialization.
        manifest=dict(version='p310-independent-envelope-v1',authorization=authorization,
                      canonical_path=str(path),prior_requests_consumed=0,prior_p39_requests=71)
        manifest['identity_hash']=digest(manifest)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb'):pass
        from contextlib import closing
        with closing(sqlite3.connect(path)) as c,c:
            c.executescript('''CREATE TABLE policy(id INTEGER PRIMARY KEY,manifest TEXT,allowed TEXT,halted TEXT);
              CREATE TABLE lease(id INTEGER PRIMARY KEY CHECK(id=1),run_id TEXT NOT NULL);
              CREATE TABLE reservations(id INTEGER PRIMARY KEY,run_id TEXT,attempt_no INTEGER,input_hash TEXT,
                reserved_cny REAL,created_at TEXT,completed INTEGER DEFAULT 0,UNIQUE(run_id,attempt_no));
              CREATE TABLE plans(plan_hash TEXT PRIMARY KEY,manifest TEXT);
              CREATE TABLE claims(run_id TEXT PRIMARY KEY,plan_hash TEXT,step_index INTEGER,config_hash TEXT,input_hash TEXT,
                UNIQUE(plan_hash,step_index));
              CREATE TABLE outcomes(run_id TEXT PRIMARY KEY,receipt TEXT);''')
            c.execute('INSERT INTO policy VALUES(1,?,?,NULL)',(json.dumps(manifest),json.dumps([])))
        return cls(path,fixture)

    def verify_root(self):
        with self.connection() as c:
            root=json.loads(c.execute('SELECT manifest FROM policy WHERE id=1').fetchone()[0])
        body=dict(root);claim=body.pop('identity_hash')
        if digest(body)!=claim or root['canonical_path']!=str(self.path):raise PermissionError('Envelope identity drift')
        validate_authorization(root['authorization'],self.fixture)
        if not self.fixture:
            prior=ROOT/'.local/p39/v2/shared-envelope.sqlite3'
            if sha256(prior.read_bytes()).hexdigest()!=root['authorization']['prior_p39_ledger_sha256']:
                raise PermissionError('Historical budget changed')
        return root

    def pricing(self):return self.verify_root()['authorization']

    def estimate_cost(self,metadata):
        p=self.pricing()['prices'];i=metadata.get('input_tokens');o=metadata.get('output_tokens')
        if type(i) is not int or type(o) is not int or min(i,o)<0:return None
        return (i*p['input_cny_per_million']+o*p['output_cny_per_million'])/1e6

    def register_plan(self,plan):
        from src.application.p310_experiment import verify_plan
        self.verify_root();verify_plan(plan)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM lease').fetchone() or c.execute('SELECT halted FROM policy').fetchone()[0]:raise PermissionError('Stopped or unsettled envelope')
            old=c.execute('SELECT manifest FROM plans WHERE plan_hash=?',(plan['plan_hash'],)).fetchone()
            if old:
                if json.loads(old[0])!=plan:raise ValueError('Plan identity drift')
                return
            prior=[json.loads(r[0]) for r in c.execute('SELECT manifest FROM plans')]
            if plan['phase']=='development':
                dev=[p for p in prior if p['phase']=='development']
                if any(p['phase']=='new40' for p in prior) or len(dev)>=3 or sum(len(p['schedule']) for p in dev)+len(plan['schedule'])>72:
                    raise PermissionError('Development iteration or exposure limit')
            elif plan['phase']=='new40':
                if any(p['phase']=='new40' for p in prior):raise PermissionError('New40 evaluation frozen once')
                if not any(p['candidate_identity']['candidate_hash']==plan['candidate_identity']['candidate_hash'] for p in prior):
                    raise PermissionError('Candidate must have a registered development identity')
            elif plan['phase']=='correction':
                identities={p['candidate_identity']['candidate_hash'] for p in prior if p['phase'] in ('development','correction')}
                if len(identities|{plan['candidate_identity']['candidate_hash']})>3:raise PermissionError('At most three distinct development hypotheses')
                evaluations=[p for p in prior if p['phase']=='new40']
                if evaluations and any(p['candidate_identity']['candidate_hash']!=plan['candidate_identity']['candidate_hash'] for p in evaluations):
                    raise PermissionError('Frozen evaluation correction identity cannot be tuned')
                parents={r['repair_context']['parent_run_id'] for p in prior if p['phase']=='correction' for r in p['inputs']}
                incoming=[r['repair_context']['parent_run_id'] for r in plan['inputs']]
                if parents.intersection(incoming) or len(set(incoming))!=len(incoming):raise PermissionError('At most one explicit correction per initial parent')
            else:raise PermissionError('Unregistered experimental phase')
            if sum(len(p['schedule']) for p in prior)+len(plan['schedule'])>180:raise PermissionError('Plan exceeds shared request limit')
            c.execute('INSERT INTO plans VALUES(?,?)',(plan['plan_hash'],json.dumps(plan)))
            allowed=set(json.loads(c.execute('SELECT allowed FROM policy').fetchone()[0]))
            allowed.update(r['input_hash'] for r in plan['inputs'])
            c.execute('UPDATE policy SET allowed=?',(json.dumps(sorted(allowed)),))

    def verify_config(self,config):
        self.verify_root()
        with self.connection() as c:
            matches=[json.loads(r[0]) for r in c.execute('SELECT manifest FROM plans') if config.model_dump() in json.loads(r[0])['configs'].values()]
        if len(matches)!=1:raise LiveError('configuration_error')
        from src.application.p310_experiment import verify_plan
        verify_plan(matches[0]);self._config=config;self._plan=matches[0]

    def acquire(self,run_id,input_hash):
        if self._config is None:raise LiveError('configuration_error')
        self.verify_root()
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            allowed,halted=c.execute('SELECT allowed,halted FROM policy').fetchone()
            if halted or input_hash not in json.loads(allowed):raise PermissionError('Stopped or unknown input')
            if c.execute('SELECT 1 FROM lease').fetchone():raise PermissionError('Unsettled request')
            count=c.execute('SELECT COUNT(*) FROM claims WHERE plan_hash=?',(self._plan['plan_hash'],)).fetchone()[0]
            if count>=len(self._plan['schedule']):raise PermissionError('Plan complete')
            step=self._plan['schedule'][count];row=self._plan['inputs'][step['input_index']]
            if row['input_hash']!=input_hash or self._config.model_dump()!=self._plan['configs'][step['arm']]:raise PermissionError('Fixed schedule identity mismatch')
            c.execute('INSERT INTO lease VALUES(1,?)',(run_id,))
            c.execute('INSERT INTO claims VALUES(?,?,?,?,?)',(run_id,self._plan['plan_hash'],count,digest(self._config.model_dump()),input_hash))

    def reserve(self,run_id,attempt_no,input_hash,messages,max_tokens):
        from src.application.p310_experiment import messages_for,ByteCounter
        if attempt_no!=1 or max_tokens!=4000:raise PermissionError('No retries or changed cap')
        auth=self.verify_root()['authorization']
        bound=ByteCounter().measure(messages);size=bound['input_token_reserve']
        if bound['payload_bytes']>50000:raise PermissionError('Payload exceeds byte cap')
        p=auth['prices'];cost=(size*p['input_cny_per_million']+4000*p['output_cny_per_million'])/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            claim=c.execute('SELECT plan_hash,step_index,config_hash,input_hash FROM claims WHERE run_id=?',(run_id,)).fetchone()
            if not claim or claim[3]!=input_hash or c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or c.execute('SELECT halted FROM policy').fetchone()[0]:raise PermissionError('Wrong claim or halted')
            plan=json.loads(c.execute('SELECT manifest FROM plans WHERE plan_hash=?',(claim[0],)).fetchone()[0]);step=plan['schedule'][claim[1]]
            config=plan['configs'][step['arm']];email=EmailInput.model_validate(plan['inputs'][step['input_index']]['email'])
            if claim[2]!=digest(config) or messages!=messages_for(email,step['arm'],plan['inputs'][step['input_index']].get('repair_context')) or email.input_hash!=input_hash:raise PermissionError('Payload/config identity drift')
            n,total=c.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            if n>=auth['requests'] or not math.isfinite(cost) or total+cost>auth['cny']:raise PermissionError('Authorization limit reached')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',(run_id,1,input_hash,cost,datetime.now(timezone.utc).isoformat()))
        return cost

    def completed(self,run_id,attempt_no):
        if attempt_no!=1:raise PermissionError('No retry settlement')
        with self.connection() as c:
            if c.execute('UPDATE reservations SET completed=1 WHERE run_id=? AND attempt_no=1',(run_id,)).rowcount!=1:raise ValueError('Missing reservation')

    def release(self,run_id):
        # Keep the global lease until runner engineering checks and read-only
        # reload reconcile this outcome; live_execution cannot silently unlock.
        with self.connection() as c:
            if c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,):raise ValueError('Wrong lease')

    def settle(self,run_id,receipt):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT run_id FROM lease').fetchone()!=(run_id,) or c.execute('SELECT completed FROM reservations WHERE run_id=?',(run_id,)).fetchone()!=(1,):
                raise PermissionError('Missing completed request/lease')
            c.execute('INSERT INTO outcomes VALUES(?,?)',(run_id,json.dumps(receipt)))
            c.execute('DELETE FROM lease WHERE run_id=?',(run_id,))
