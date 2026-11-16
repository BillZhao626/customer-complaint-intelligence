"""One frozen DEV pilot. No default paid execution, retries, or policy changes."""
import asyncio
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from src.domain.contracts import EmailInput, digest
from src.infrastructure.pilot_budget import PilotBudget
from src.infrastructure.deepseek import DeepSeekAnalyzer, LiveError
from src.application.p39_experiment import wire_payload, wire_bytes, dependencies
from src.application.p39_v2 import system, ContextOfflineService
from src.application.v31_prompt import messages as base_messages
from src.application.mail_threads import assemble_context

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / '.local/p5b-20261029-v1'
DELIVERY = ROOT / 'docs/p5b_dev_pilot'


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def build_manifest(root=ROOT):
    pack = read(root/'docs/p5q/HUMAN_CALIBRATION_PACK_v1.json')
    cases, schedule = [], []
    for r in pack['packets']:
        o = r['original']; cid = r['record_id']
        if digest(o) != r['source_record_hash']:
            raise ValueError('Source record drift')
        single = 'body' in o
        turns = [dict(subject=o['subject'], body=o['body'])] if single else [
            dict(subject=cid, body=o['turns'][i]['body']) for i in (0, 2)]
        row = dict(calibration_id=r['calibration_id'], source_id=cid,
                   source_record_hash=r['source_record_hash'], turns=turns,
                   input_text_sha256=[sha256(t['body'].encode()).hexdigest() for t in turns],
                   source_kind='CODEX_ORIGINAL_SYNTHETIC_DEV', split='DEV')
        cases.append(row)
        for n in range(len(turns)):
            schedule.append(dict(calibration_id=r['calibration_id'], source_id=cid,
                                 turn=n+1, turn_id=cid if single else cid+'-T'+str(n+1)))
    if len(cases)!=16 or len(schedule)!=18 or sum(len(c['turns'])==1 for c in cases)!=14:
        raise ValueError('Fixed 16/18 sample coverage')
    m = dict(version='p5b-dev-first-generation-v1', source_pack_sha256=sha256(
        (root/'docs/p5q/HUMAN_CALIBRATION_PACK_v1.json').read_bytes()).hexdigest(),
        cases=cases, schedule=schedule, knowledge='K0', protocol='v0.2.1',
        system_prompt_sha256=sha256(system('B').encode()).hexdigest(),
        system_prompt_origin='src/application/p39_v2.py:system(B), unchanged Champion',
        developer_prompt=None, parameters=dict(model='deepseek-flash',temperature=0,max_tokens=4000,
        thinking='disabled',response_format='json_object',max_attempts=1,sdk_max_retries=0,
        concurrency=1,http_timeout=45,deadline=90), limits=dict(provider_calls=40,cny=5,generation_turns=18),
        history_rule='assemble_context; prior customer + this pilot first real suggested_reply only; no authored candidates',
        independent_gold=False, human_calibration='PENDING')
    m['manifest_hash']=digest(m)
    return m


def verify_manifest(m, root=ROOT):
    if m != build_manifest(root):
        raise ValueError('Frozen manifest/source/prompt drift')


def messages(email):
    return [('system', system('B')), base_messages(email, 'B')[1]]


def second_email(case, prior_reply):
    if not isinstance(prior_reply, str) or not prior_reply.strip():
        raise ValueError('Real first reply required')
    t1,t2=case['turns']
    context=[dict(role='customer',at='turn-1',source='P5_SYNTHETIC_DEV',**t1),
             dict(role='assistant',at='turn-1',source='REAL_MODEL_UNSENT_DEV',subject='客服开发回复',body=prior_reply)]
    return EmailInput(email_id=case['source_id']+'-T2',subject=t2['subject'],
                      body=assemble_context(context, **t2)), context


class Budget(PilotBudget):
    """Fresh envelope, cumulative reservations retained; no allowance cloning."""
    def pricing(self):
        with self.connection() as c:
            return json.loads(c.execute('SELECT manifest FROM policy').fetchone()[0])['pricing']

    def verify_config(self, config):
        if config.model_dump() != self.config.model_dump():
            raise LiveError('configuration_error')

    def reserve(self, run_id, attempt_no, input_hash, msgs, max_tokens):
        if attempt_no!=1 or max_tokens!=4000 or input_hash!=self.expected.input_hash or msgs!=messages(self.expected):
            raise LiveError('configuration_error')
        size=len(wire_bytes(msgs))+1024
        if size>100000 or size+max_tokens>1000000:
            raise LiveError('configuration_error')
        cost=(size*2+max_tokens*8)/1e6
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            lease=c.execute('SELECT run_id FROM lease').fetchone()
            n,total=c.execute('SELECT COUNT(*),COALESCE(SUM(reserved_cny),0) FROM reservations').fetchone()
            if lease!=(run_id,) or n>=18 or n>=40 or total+cost>5:
                raise LiveError('configuration_error')
            c.execute('INSERT INTO reservations(run_id,attempt_no,input_hash,reserved_cny,created_at) VALUES(?,?,?,?,?)',
                      (run_id,attempt_no,input_hash,cost,now()))
        return cost

    def estimate_cost(self, meta):
        i,o,t=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
        if any(type(v) is not int or v<0 for v in (i,o,t)) or i+o!=t or o>4000 or i>len(wire_bytes(messages(self.expected)))+1024:
            self.halt('UNKNOWN_BILLING')
            return None
        return (i*2+o*8)/1e6

    def bind(self, email, config):
        self.expected=email; self.config=config
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            allowed,halted=c.execute('SELECT allowed,halted FROM policy').fetchone()
            if halted or c.execute('SELECT 1 FROM lease').fetchone():
                raise LiveError('interrupted_or_unknown')
            values=set(json.loads(allowed)); values.add(email.input_hash)
            c.execute('UPDATE policy SET allowed=?',(json.dumps(sorted(values)),))


class Analyzer(DeepSeekAnalyzer):
    def __init__(self, settings, evidence, *, mock_http_transport=None):
        super().__init__(settings,prompt_profile='multi-issue-v31-B',mock_http_transport=mock_http_transport)
        self.evidence=Path(evidence)
        self.messages=lambda email,repair=False: messages(email)
        self.config=self.config.model_copy(update=dict(prompt_version='p5b-existing-champion-context-B-1',
            prompt_hash=sha256(system('B').encode()).hexdigest(),parameters=dict(self.config.parameters,
            urgency_validation_profile='urgency-context-evidence-v1',knowledge='K0',pilot_manifest_hash=None)))

    async def request(self, email, repair, remaining):
        from langsmith import tracing_context
        self.settings.validate()
        client,transport=self.make_client(min(self.settings.http_timeout,remaining))
        expected=wire_payload(messages(email)); observed={}
        async def audit(request):
            body=await request.aread()
            if str(request.url)!='https://api.deepseek.com/chat/completions' or request.method!='POST' or json.loads(body)!=expected:
                raise LiveError('configuration_error')
            write_new(self.evidence/'wire-request.json',json.loads(body))
            observed.update(payload_sha256=sha256(body).hexdigest(),payload_bytes=len(body),dispatch_at=now())
        async def capture(response):
            body=await response.aread()
            write_new(self.evidence/'provider-response.txt',body.decode('utf-8'))
            write_new(self.evidence/'provider-http.json',dict(status=response.status_code,received_at=now(),
                body_sha256=sha256(body).hexdigest(),headers={k:v for k,v in response.headers.items()
                    if k in ('x-request-id','x-ds-request-id','date','content-type')}))
        transport.event_hooks.update(request=[audit],response=[capture])
        try:
            with tracing_context(enabled=False):
                response=await asyncio.wait_for(client.ainvoke(messages(email),config={'callbacks':[]}),timeout=remaining)
            meta=response.response_metadata or {}; usage=response.usage_metadata or {}
            write_new(self.evidence/'langchain-response.json',response.model_dump(mode='json'))
            return response.content,dict(resolved_model=meta.get('model_name'),model_snapshot='unavailable',
                provider_response_id=meta.get('id'),response_id=response.id,finish_reason=meta.get('finish_reason'),
                input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),total_tokens=usage.get('total_tokens'),
                usage=usage,token_usage=meta.get('token_usage'),**observed)
        finally:
            await transport.aclose()


class Service(ContextOfflineService):
    def __init__(self, repository, analyzer, budget):
        # Reuse exact existing validator; its old constructor was offline-only.
        from src.application.analysis_service import AnalysisService
        AnalysisService.__init__(self,repository,analyzer,budget=budget)


def run(m, settings):
    """Single invocation only. A crash leaves durable evidence; never auto-resend."""
    verify_manifest(m)
    settings.validate()
    if not settings.enabled or settings.model!='deepseek-flash' or settings.max_attempts!=1 or settings.max_tokens!=4000:
        raise ValueError('Settings drift')
    authorization=read(LOCAL/'authorization.json')
    if authorization['manifest_hash']!=m['manifest_hash'] or authorization['limits']!=m['limits']:
        raise ValueError('Authorization drift')
    checked=datetime.fromisoformat(authorization['pricing']['prices_verified_at'])
    if not 0<=(datetime.now(timezone.utc)-checked).total_seconds()<86400:
        raise ValueError('Price receipt expired')
    write_new(LOCAL/'run-start.json',dict(started_at=now(),manifest_hash=m['manifest_hash']))
    budget=Budget.create(LOCAL/'budget.sqlite3',[],authorization)
    from src.infrastructure.repository import Repository
    from src.application.product_workflow import ProductStore
    from src.application.service_triage import explicit_human_request
    from src.application.live_execution import strict_json
    repo=Repository(LOCAL/'runs.sqlite3')
    product=ProductStore(ROOT/'.local/p4/p5b-dev-20261029-v1/product.sqlite3')
    results=[]; stopped=None
    for case in m['cases']:
        prior=None
        for n,t in enumerate(case['turns'],1):
            turn_id=case['source_id'] if len(case['turns'])==1 else case['source_id']+'-T'+str(n)
            context=[]
            if n==2 and not prior:
                results.append(dict(turn_id=turn_id,calibration_id=case['calibration_id'],status='DEPENDENCY_FAILED',reply=None))
                continue
            if n==2:
                email,context=second_email(case,prior)
            else:
                email=EmailInput(email_id=turn_id,**t)
            ev=LOCAL/'turns'/turn_id
            analyzer=Analyzer(settings,ev)
            analyzer.config=analyzer.config.model_copy(update=dict(parameters=dict(analyzer.config.parameters,pilot_manifest_hash=m['manifest_hash'])))
            write_new(ev/'frozen-input.json',dict(email=email.model_dump(),input_hash=email.input_hash,
                current_customer=t,history=context,messages=messages(email),config=analyzer.config.model_dump(),frozen_at=now()))
            budget.bind(email,analyzer.config)
            run_result=Service(repo,analyzer,budget).analyze(email)
            write_new(ev/'run.json',run_result.model_dump(mode='json'))
            a=run_result.attempts[-1] if run_result.attempts else None
            raw=a.raw_output if a else None
            try:
                parsed=strict_json(raw); reply=parsed.get('suggested_reply')
            except (ValueError,TypeError,AttributeError):
                parsed=None;reply=None
            if not isinstance(reply,str) or not reply.strip(): reply=None
            prior=reply
            events=[]; event_error=None
            try:
                saved=product.create(run_result,'P5B frozen first generation',origin='new_analysis')
                if explicit_human_request(t['body']):
                    saved=product.act(saved['case_id'],'request_handoff',expected_revision=saved['revision'],
                        actor='p5b_dev_runner',actor_type='demo_test',reason='客户明确请求人工；本地开发转交，未接管',operation_id='p5b-handoff:'+run_result.run_id)
                events=saved['events']
                write_new(ev/'product-events.json',dict(case_id=saved['case_id'],events=events,quality=saved['quality']))
            except Exception as exc:
                event_error=type(exc).__name__
                write_new(ev/'event-error.json',dict(error_type=event_error,execution='NOT_VERIFIED'))
            meta=a.metadata if a else {}
            row=dict(turn_id=turn_id,calibration_id=case['calibration_id'],run_id=run_result.run_id,
                status=run_result.status,reply=reply,parse_status=a.parse_status if a else 'not_run',
                contract_status=a.contract_status if a else 'not_run',provider=meta,history=context,
                input_hash=email.input_hash,reply_sha256=sha256(reply.encode()).hexdigest() if reply else None,
                handoff_requested=any(e['action']=='request_handoff' for e in events),
                handoff_accepted=any(e['action']=='take_over' for e in events),
                event_error=event_error,event_refs=[e['event_id'] for e in events],human_scores=None)
            results.append(row)
            write_new(ev/'receipt.json',row)
            print(json.dumps(dict(turn_id=turn_id,status=row['status'],tokens=meta.get('total_tokens'),cost_upper_cny=meta.get('cost_cny')),ensure_ascii=False),flush=True)
            if (not a or meta.get('dispatch')!='response_received' or meta.get('cost_cny') is None
                    or meta.get('resolved_model')!='deepseek-flash' or not (ev/'provider-response.txt').exists()):
                stopped='UNKNOWN_BILLING';budget.halt(stopped);break
        if stopped: break
    if not stopped:
        stopped='planned_generation_complete';budget.halt(stopped)
    existing={r['turn_id'] for r in results}
    results.extend(dict(**s,status='NOT_RUN',reply=None) for s in m['schedule'] if s['turn_id'] not in existing)
    write_new(LOCAL/'results.json',dict(manifest_hash=m['manifest_hash'],stop_reason=stopped,results=results,budget=budget.summary()))
    return dict(completed=sum(bool(r.get('reply')) for r in results),planned=18,stop_reason=stopped,budget=budget.summary())
