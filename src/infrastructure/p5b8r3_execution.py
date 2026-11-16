"""Independent, serial, first-attempt ledger. No implicit paid authorization."""
import json,sqlite3,time
import hashlib
from threading import Lock
from pathlib import Path
from uuid import uuid4
from decimal import Decimal,ROUND_CEILING
from contextlib import contextmanager
from src.domain.contracts import digest
from src.application.p5b8r1_experiment import MODEL,write_first
from src.application.p39_experiment import wire_bytes

def read(p):return json.loads(Path(p).read_text('utf-8'))
def micros(cny):return int((Decimal(str(cny))*1000000).to_integral_value(rounding=ROUND_CEILING))

class Dispatcher:
    def __init__(self,root,plan,*,authorization=None,provider=None,mode='OFFLINE_MOCK',max_inflight=1):
        self.root=Path(root);self.plan=plan;self.mode=mode;self.provider=provider
        if type(max_inflight) is not int or not 1 <= max_inflight <= 8:
            raise ValueError('Invalid in-process dispatch limit')
        self.max_inflight=max_inflight
        self._reservation_lock=Lock()
        self._inflight=set()
        if mode not in ('OFFLINE_MOCK','LIVE'):raise ValueError('Unknown execution mode')
        if mode=='LIVE':
            # Authorization must be supplied only after an actual user approval.
            if not authorization or authorization.get('plan_hash')!=digest(plan) or authorization.get('scope')!=plan.get('authorization_scope','P5-B8-R3-DEV'):raise PermissionError('AUTHORIZATION_BLOCKED: explicit new CNY/request approval required')
            request_only=(authorization.get('budget_mode')=='REQUEST_ONLY'
                          and plan.get('budget_mode')=='REQUEST_ONLY'
                          and authorization.get('cny') is None and plan.get('proposed_cny_cap') is None
                          and authorization.get('monetary_cap_explicitly_waived') is True)
            if not authorization.get('user_approval_verbatim') or type(authorization.get('provider_requests')) is not int or authorization['provider_requests']<=0 or authorization.get('provider_requests')!=plan['planned_requests'] or (not request_only and Decimal(str(authorization.get('cny') or 0))<=0):raise PermissionError('Invalid explicit authorization')
        self.auth=authorization or dict(scope='OFFLINE_MOCK',provider_requests=plan['planned_requests'],cny=plan['proposed_cny_cap'],plan_hash=digest(plan))
        self.parents=self.auth.get('parent_ledgers',[])
        self.verify_parent_caps()
        self.root.mkdir(parents=True,exist_ok=True);self.db=self.root/'budget.sqlite3'
        with self.connect() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL, halted TEXT); CREATE TABLE IF NOT EXISTS calls (identity TEXT PRIMARY KEY, request_hash TEXT NOT NULL, run_id TEXT UNIQUE NOT NULL, state TEXT NOT NULL, reserved_micro INTEGER NOT NULL, settled_micro INTEGER, metadata TEXT);')
            frozen=json.dumps(dict(authorization=self.auth,mode=mode,model=MODEL),sort_keys=True)
            row=c.execute('SELECT identity FROM policy WHERE id=1').fetchone()
            if row and row[0]!=frozen:
                # An explicitly linked request-only extension is append-only.
                # The original policy identity and every prior call remain intact.
                c.execute('CREATE TABLE IF NOT EXISTS policy_extensions (id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL, predecessor_hash TEXT NOT NULL)')
                latest=c.execute('SELECT identity FROM policy_extensions ORDER BY id DESC LIMIT 1').fetchone()
                predecessor=latest[0] if latest else row[0]
                if predecessor!=frozen:
                    previous=json.loads(predecessor);old_auth=previous['authorization']
                    valid=(mode=='LIVE' and previous.get('mode')==mode and previous.get('model')==MODEL
                        and self.auth.get('extends_authorization_hash')==digest(old_auth)
                        and self.auth.get('extends_plan_hash')==old_auth.get('plan_hash')
                        and self.auth.get('scope')==old_auth.get('scope')
                        and self.auth.get('budget_mode')==old_auth.get('budget_mode')=='REQUEST_ONLY'
                        and self.auth.get('monetary_cap_explicitly_waived') is True
                        and old_auth.get('monetary_cap_explicitly_waived') is True
                        and self.auth.get('cny') is None and old_auth.get('cny') is None
                        and self.auth['provider_requests']>old_auth['provider_requests'])
                    if not valid:raise ValueError('Ledger authorization/configuration drift')
                    unsettled=c.execute("SELECT COUNT(*) FROM calls WHERE state NOT IN ('COMPLETED','REJECTED_HTTP_429','REJECTED_429','REJECTED_402','REJECTED_NOT_DISPATCHED')").fetchone()[0]
                    if unsettled:raise RuntimeError('Cannot extend an unsettled ledger')
                    c.execute('INSERT INTO policy_extensions(identity,predecessor_hash) VALUES (?,?)',(frozen,digest(old_auth)))
            c.execute('INSERT OR IGNORE INTO policy VALUES(1,?,NULL)',(frozen,))
    def verify_parent_caps(self):
        if not self.parents:return
        count=upper=0
        for p in self.parents:
            path=Path(p['path'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=p['sha256']:raise RuntimeError('Parent authorization ledger changed')
            with sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True) as c:
                n,cost=c.execute('SELECT COUNT(*),COALESCE(SUM(COALESCE(settled_micro,reserved_micro)),0) FROM calls').fetchone()
            count+=n;upper+=cost
        if count+self.auth['provider_requests']>self.auth['global_authorized_provider_requests'] or upper+micros(self.auth['cny'])>micros(self.auth['global_authorized_cny']):raise PermissionError('Combined revision budget exceeds actual user authorization')
    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.db,timeout=5)
        try:
            with connection:yield connection
        finally:connection.close()
    def summary(self):
        with self.connect() as c:
            rows=c.execute('SELECT state,COUNT(*) FROM calls GROUP BY state').fetchall()
            upper=c.execute('SELECT COALESCE(SUM(COALESCE(settled_micro,reserved_micro)),0) FROM calls').fetchone()[0]
            halt=c.execute('SELECT halted FROM policy').fetchone()[0]
        return dict(mode=self.mode,states=dict(rows),reserved_or_settled_upper_cny=upper/1e6,actual_bill_cny=None,halted=halt,paid_requests=sum(n for _,n in rows) if self.mode=='LIVE' else 0)
    def halt(self,reason):
        with self.connect() as c:c.execute('UPDATE policy SET halted=?',(reason,))
    def acknowledge_unknown_transport(self,identity,*,reason,evidence):
        """Keep ambiguity charged and non-replayable; permit only new identities.

        Explicit operator reconciliation after diagnosis, never an automatic
        response retry or a claim of no dispatch/no charge.
        """
        if not reason or not evidence:raise ValueError('Transport diagnosis and evidence required')
        folder=self.root/'calls'/digest(identity)
        error=read(folder/'error.json')
        if error.get('type') not in ('APIConnectionError','ConnectionError','TimeoutError'):
            raise ValueError('Not an eligible diagnosed transport uncertainty')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT state FROM calls WHERE identity=?',(identity,)).fetchone()
            if not row or row[0]!='UNKNOWN':raise ValueError('Not unresolved transport')
            write_first(folder/'transport-reconciliation.json',dict(identity=identity,disposition='UNKNOWN_COUNTED_NO_REPLAY',reason=reason,evidence=evidence,actual_dispatch='UNKNOWN',actual_charge='UNKNOWN',reservation_retained=True))
            c.execute("UPDATE calls SET state='UNKNOWN_COUNTED_NO_REPLAY' WHERE identity=?",(identity,))
            remaining=c.execute("SELECT COUNT(*) FROM calls WHERE state NOT IN ('COMPLETED','UNKNOWN_COUNTED_NO_REPLAY','REJECTED_HTTP_429','REJECTED_429','REJECTED_402','REJECTED_NOT_DISPATCHED')").fetchone()[0]
            if not remaining:c.execute('UPDATE policy SET halted=NULL')
    def reconcile_rate_rejection(self,identity):
        return self.reconcile_rejection(identity,429)
    def reconcile_rejection(self,identity,status):
        """Explicit recovery after inspecting a definitive HTTP rejection.

        Preserve the slot and its full reservation; never make it replayable.
        Unknown transport or successful output cannot use this recovery path.
        """
        folder=self.root/'calls'/digest(identity)
        if status not in (402,429,'NOT_DISPATCHED'):raise ValueError('Unsupported recovery')
        if status=='NOT_DISPATCHED':
            if any((folder/n).exists() for n in ('wire-request.json','provider-response.txt','response.json')) or read(folder/'error.json')['type'] not in ('RuntimeError','LiveError'):
                raise ValueError('Outbound absence not established')
            response_hash=None
        else:
            http=read(folder/'provider-http.json')
            wire=read(folder/'provider-response.txt')
            if isinstance(wire,str):wire=json.loads(wire)
            if http.get('status')!=status or not wire.get('error') or wire.get('choices') or wire.get('usage'):
                raise ValueError('Not a definitive HTTP rejection')
            response_hash=hashlib.sha256((folder/'provider-response.txt').read_bytes()).hexdigest()
        record=dict(identity=identity,http_status=status,response_hash=response_hash,
                    disposition='REJECTED_NO_MODEL_OUTPUT_NO_RETRY',billing='UNKNOWN_FULL_RESERVATION_RETAINED')
        with self.connect() as c:
            row=c.execute('SELECT state FROM calls WHERE identity=?',(identity,)).fetchone()
            if not row or row[0]!='UNKNOWN':raise ValueError('Not an unresolved rejected request')
            write_first(folder/'reconciliation.json',record)
            c.execute("UPDATE calls SET state=? WHERE identity=?",('REJECTED_'+str(status),identity))
            unresolved=c.execute("SELECT COUNT(*) FROM calls WHERE state NOT IN ('COMPLETED','REJECTED_HTTP_429','REJECTED_429','REJECTED_402','REJECTED_NOT_DISPATCHED')").fetchone()[0]
            if not unresolved:c.execute('UPDATE policy SET halted=NULL')
        return record
    def call(self,identity,messages,payload=None):
        integrity=self.plan.get('execution_integrity')
        proof=None
        if integrity:
            from src.evaluation.experiment_integrity import verify
            if (payload or {}).get('dataset_role') in ('UNSEEN','INDEPENDENT_TEST') and not integrity.get('independent_dataset'):
                raise ValueError('Independent dispatch requires pinned dataset/history/family preflight inputs')
            proof=verify(integrity)
        self.verify_parent_caps()
        if identity not in self.plan['allowed_call_ids']:raise ValueError('Unplanned provider request')
        req_hash=digest(dict(messages=messages,model=MODEL,payload=payload));folder=self.root/'calls'/digest(identity)
        with self._reservation_lock:
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                row=c.execute('SELECT request_hash,run_id,state,metadata FROM calls WHERE identity=?',(identity,)).fetchone()
                if row:
                    if row[0]!=req_hash:raise ValueError('Immutable request input drift')
                    if row[2]!='COMPLETED':raise RuntimeError('UNKNOWN_DO_NOT_RETRY')
                    result=read(folder/'response.json')
                    if result['run_id']!=row[1] or result['request_hash']!=req_hash or digest(result)!=json.loads(row[3])['response_hash']:raise ValueError('Stored response identity/content drift')
                    return result
                unsettled=c.execute("SELECT identity,state FROM calls WHERE state NOT IN ('COMPLETED','UNKNOWN_COUNTED_NO_REPLAY','REJECTED_HTTP_429','REJECTED_429','REJECTED_402','REJECTED_NOT_DISPATCHED')").fetchall()
                unresolved=any(state!='RESERVED' or key not in self._inflight for key,state in unsettled)
                if c.execute('SELECT halted FROM policy').fetchone()[0] or unresolved:raise RuntimeError('Halted or unresolved reservation; no redispatch')
                if len(self._inflight)>=self.max_inflight:raise RuntimeError('In-process dispatch limit reached')
                size=len(wire_bytes(messages))+1024
                if size>100000:raise ValueError('Input byte bound exceeded')
                pricing=self.plan['pricing'];bound=micros((Decimal(size)*Decimal(str(pricing['input_cny_per_million']))+Decimal(MODEL['max_tokens'])*Decimal(str(pricing['output_cny_per_million'])))/1000000)
                count,spent=c.execute('SELECT COUNT(*),COALESCE(SUM(COALESCE(settled_micro,reserved_micro)),0) FROM calls').fetchone()
                monetary_cap=self.auth.get('cny')
                if count>=self.auth['provider_requests'] or (monetary_cap is not None and spent+bound>micros(monetary_cap)):raise RuntimeError('Budget/request cap exceeded before Provider construction')
                rid=str(uuid4());c.execute('INSERT INTO calls VALUES(?,?,?,?,?,?,?)',(identity,req_hash,rid,'RESERVED',bound,None,None))
            self._inflight.add(identity)
        start=time.perf_counter()
        try:
            write_first(folder/'frozen-input.json',dict(identity=identity,run_id=rid,request_hash=req_hash,messages=messages,model=MODEL,payload=payload,mode=self.mode))
            if integrity:
                # Recheck immediately before the single outbound call. A source
                # change after reservation halts; it never triggers another call.
                proof=verify(integrity)
                write_first(folder/'execution-integrity.json',proof)
            with self.connect() as c:
                if c.execute('SELECT halted FROM policy').fetchone()[0]:
                    raise RuntimeError('Dispatch halted before outbound request')
            if self.provider is None:raise RuntimeError('Provider adapter required')
            raw,metadata=self.provider(messages,folder,payload)
            # Store raw BEFORE validating billing, JSON or business meaning.
            response=dict(identity=identity,run_id=rid,request_hash=req_hash,raw=raw,metadata=metadata,elapsed_ms=(time.perf_counter()-start)*1000,mode=self.mode)
            write_first(folder/'response.json',response)
            i,o,t=[metadata.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
            if any(type(v)is not int or v<0 for v in (i,o,t)) or i+o!=t or o>MODEL['max_tokens'] or i>size:raise RuntimeError('UNKNOWN_BILLING')
            cost=micros((Decimal(i)*Decimal(str(pricing['input_cny_per_million']))+Decimal(o)*Decimal(str(pricing['output_cny_per_million'])))/1000000)
            if cost>bound:raise RuntimeError('UNKNOWN_BILLING_BOUND')
            with self.connect() as c:c.execute("UPDATE calls SET state='COMPLETED',settled_micro=?,metadata=? WHERE identity=?",(cost,json.dumps(dict(provider=metadata,response_hash=digest(response))),identity))
            if integrity:write_first(folder/'post-response-integrity.json',verify(integrity))
            if self.mode=='LIVE':print(identity+' FIRST_RESPONSE_SAVED',flush=True)
            return response
        except BaseException as exc:
            integrity_failure=False
            if integrity:
                from src.evaluation.experiment_integrity import IntegrityError
                integrity_failure=isinstance(exc,IntegrityError)
            state='INTEGRITY_FAILED' if integrity_failure else 'UNKNOWN'
            halt='SOURCE_OR_INPUT_DRIFT_NO_REDISPATCH' if integrity_failure else 'UNKNOWN_TRANSPORT_BILLING_OR_STORAGE'
            with self.connect() as c:
                c.execute('UPDATE calls SET state=? WHERE identity=?',(state,identity));c.execute('UPDATE policy SET halted=?',(halt,))
            if not (folder/'error.json').exists():write_first(folder/'error.json',dict(status=state+'_DO_NOT_RETRY',type=type(exc).__name__))
            raise
        finally:
            with self._reservation_lock:
                self._inflight.discard(identity)

class LangChainProvider:
    """Existing observable SDK adapter; created only after authorization preflight."""
    def __call__(self,messages,folder,payload):
        import asyncio,os
        from dataclasses import replace
        from src.application.p5b3_runtime import Analyzer
        from src.infrastructure.v3_live_settings import V3PilotSettings
        from src.domain.contracts import EmailInput
        os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
        settings=replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=MODEL['max_tokens'])
        analyzer=Analyzer(settings,folder,candidate=False);analyzer.messages=lambda e,repair=False:messages
        email=EmailInput(email_id='R3-provider-envelope',subject='R3',body=json.dumps(messages,ensure_ascii=False))
        return asyncio.run(analyzer.request(email,False,MODEL['deadline_seconds']))
