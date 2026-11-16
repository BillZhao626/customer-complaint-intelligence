"""R2 additions over the existing product, sharing its review/simulation gates.

Only a supplied R2 live driver can dispatch. Historical paid routes stay closed.
Review decisions are append-only local opinions, never Gold or promotion writes.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import re
import threading
from typing import Literal
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from src.app.p5_api import create_app as base_app, detail, summary
from src.app.p5b5_api import Prepare
from src.application.p5b5r2_pipeline import ActionStore, ConversationState
from src.application.mail_threads import MailThreads, assemble_context
from src.application.product_workflow import Conflict, timestamp
from src.domain.contracts import AnalysisRun, digest

ROOT = Path(__file__).resolve().parents[2]

def state_for(store,case_id):
    state=ConversationState(case_id)
    for message in MailThreads(store).messages(case_id):
        body=message['body']
        if message['role']=='customer' and '[customer' in body:
            pieces=re.split(r'\[(customer|assistant)[^\]]*\]\n',body)
            for i in range(1,len(pieces),2):state.update(pieces[i],pieces[i+1].strip())
        else:state.update('customer' if message['role']=='customer' else 'assistant',body)
    return state

def supersede_local_requests(actions,parent,child,source_events):
    """Append operational revisions; original model experiment receipts stay intact."""
    from uuid import uuid4
    with actions.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for event in source_events:
            if event.get('status') not in ('created','handoff_pending'):continue
            if event.get('input_hash')!=parent['run'].input_hash:continue
            operation=digest(dict(version='r2-product-supersession-1',event_id=event['event_id'],child_input=child['run'].input_hash))
            payload=dict(action=event.get('payload',{}).get('action'),previous_event_id=event['event_id'],previous_input_hash=parent['run'].input_hash,
                parent_case_id=parent['case_id'],child_case_id=child['case_id'],replacement_input_hash=child['run'].input_hash,
                local_only=True,external_execution=False,external_cancellation=False,
                reason='已确认的新续信替代上一轮内部请求，原实验事件保留；不表示任何外部取消成功。')
            conn.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),parent['run'].input_hash,parent['case_id'],operation,
                event['kind'],'superseded',json.dumps(payload,ensure_ascii=False),timestamp()))

class LiveMail(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=12000)
    synthetic_confirmed: bool
    operation_id: str = Field(min_length=8, max_length=80)

class FollowupMail(LiveMail):
    revision: int = Field(ge=0)

class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    item_id: str = Field(min_length=1, max_length=160)
    decision: str = Field(pattern='^(agree|modify|reject|unable)$')
    reviewer: str = Field(min_length=1, max_length=120)
    comment: str = Field(max_length=6000)
    package_hash: str = Field(min_length=64, max_length=64)
    operation_id: str = Field(min_length=8, max_length=80)
    score_target: Literal['R3','FINAL'] | None = None
    scores: dict[Literal['B1','B2','B3','B4','B5'], int | None] | None = None

REFERENCE=ROOT/'resources/optional-design-references'
MEDIA={
    'reference-chatwoot':(REFERENCE/'chatwoot_inbox_reference.png','Chatwoot 原参考','OWNER_REFERENCE_NOT_PRODUCT'),
    'reference-intercom':(REFERENCE/'intercom_copilot_reference.png','Intercom 原参考','OWNER_REFERENCE_NOT_PRODUCT'),
    'reference-langfuse':(REFERENCE/'langfuse_eval_reference.png','Langfuse 原参考','OWNER_REFERENCE_NOT_PRODUCT'),
    'before-inbox':(ROOT/'docs/p5b5/browser/inbox-final-1440.jpg','改造前 B5 工作台','HISTORICAL_B5_BROWSER_CAPTURE'),
    'before-quality':(ROOT/'docs/p5b5/browser/quality-final-1440.jpg','改造前 B5 质量台','HISTORICAL_B5_BROWSER_CAPTURE'),
    'final-inbox':(ROOT/'docs/p5b5r2/browser/inbox-final-1440.jpg','本轮最终工作台','R2_REAL_BROWSER_CAPTURE'),
    'final-quality':(ROOT/'docs/p5b5r2/browser/quality-final-1440.jpg','本轮最终质量台','R2_REAL_BROWSER_CAPTURE'),
}

def media_manifest():
    return [dict(label=label,url='/api/p5b5r2/media/'+key,sha256=sha256(path.read_bytes()).hexdigest(),identity=identity)
            for key,(path,label,identity) in MEDIA.items() if path.is_file()]

def create(db_path, *, web_directory=None, evidence=None, live_driver=None, review_package=None, local_origin_port=8770, b8_planner=None):
    app = base_app(db_path, serve_web=False, live_generate=False, local_origin_port=local_origin_port)
    store = app.state.store
    actions = ActionStore(store.path.with_name('p5b5r2-actions.sqlite3'))
    use_current_evidence=evidence is None
    evidence = Path(evidence or ROOT/'docs/p5b5r2/RESULTS.json')
    review_package = Path(review_package or ROOT/'docs/p5b5r2/HUMAN_REVIEW.json')
    decisions_path = store.path.with_name('human-review-decisions.jsonl')
    review_lock = threading.Lock()
    followup_lock = threading.Lock()

    def runtime_records(run):
        params=run.config.parameters;arm=(params.get('arm') or 'B2')
        roots=[ROOT/'.local/p5b5r2'/arm/run.email.email_id/'evaluation.json']
        if params.get('experiment')=='p5b7':roots=[ROOT/'.local/p5b7'/arm/run.email.email_id/'evaluation.json']
        if params.get('experiment')=='p5b5-live-v1':roots.append(ROOT/'.local/p5b5-live-20261030-v1'/arm/run.email.email_id/'evaluation.json')
        events=[]
        for path in roots:
            if not path.exists():continue
            record=json.loads(path.read_text(encoding='utf-8'))
            if record.get('input_hash')==run.input_hash:events+=record.get('runtime',{}).get('events',[])
        return events

    def scoped_quality(run,data,reply,accepted):
        params=run.config.parameters
        if data is not None and params.get('experiment') in ('p5b5r2','p5b7') and params.get('arm')!='B2':
            from src.application.p5b5r2_guard import inspect
            return inspect(run.email,data,reply,accepted=accepted,events=runtime_records(run)+actions.list(run.input_hash))
        from src.application.product_quality import inspect
        return inspect(run.email,data,reply,accepted=accepted)

    store.quality_inspector=scoped_quality

    def driver():
        if live_driver is not None:
            return live_driver
        from scripts import p5b5r2_live
        return p5b5r2_live

    @app.get('/api/p5b5r2/live/status')
    def live_status():
        try:
            return driver().status_ui()
        except (ImportError, FileNotFoundError):
            return dict(enabled=False, remaining_requests=None, remaining_cny=None, halted='NOT_INITIALIZED')

    @app.post('/api/p5b5r2/live')
    def live(body: LiveMail):
        if not body.synthetic_confirmed or not body.body.strip() or not body.subject.strip():
            raise ValueError('Explicit synthetic confirmation required')
        # The driver owns a durable request identity and every provider preflight.
        # This route never retries, including network loss after a dispatch.
        try:
            run = driver().generate_ui(body.subject.strip(), body.body.strip(), body.operation_id)
        except (ImportError, FileNotFoundError):
            return JSONResponse(dict(message='本轮模型预算尚未初始化，未派发请求。', code='not_initialized'),status_code=409)
        except PermissionError:
            return JSONResponse(dict(message='本轮付费派发已关闭。现有结果仍可审核和本地模拟。', code='live_closed'),status_code=409)
        except Exception:
            return JSONResponse(dict(message='本次分析未能确认完成。请核对账本与已保存结果；不会自动重发。', code='dispatch_unconfirmed'),status_code=409)
        created = store.create(run, 'P5-B5-R2 UI synthetic first output',origin='new_analysis')
        return read_case(created['case_id'])

    @app.get('/api/p5b5r2/inbox')
    def inbox():
        cases = store.list_cases(); threads = MailThreads(store); rows=[]
        refs = {((c['run'].config.parameters.get('arm') or 'B2'),c['run'].email.email_id) for c in cases}
        for c in cases:
            if threads.child(c['case_id']): continue
            email_id=c['run'].email.email_id;arm=(c['run'].config.parameters.get('arm') or 'B2')
            if email_id.endswith('-T1') and (arm,email_id[:-3]+'-T2') in refs: continue
            state = state_for(store,c['case_id']); row=summary(c,state.extract()['latest_request'])
            row['search_text']=state.customers
            row['model_arm']=(c['run'].config.parameters.get('arm') or '历史 B2')
            row['analysis_experiment']=c['run'].config.parameters.get('experiment')
            rows.append(row)
        return dict(cases=sorted(rows,key=lambda c:c['updated_at'],reverse=True))

    @app.post('/api/p5b5r2/cases/{case_id}/followup')
    def followup(case_id,body:FollowupMail):
        if not body.synthetic_confirmed or not body.body.strip():raise ValueError('Explicit synthetic source required')
        with followup_lock:
            threads=MailThreads(store);parent=store.get(case_id)
            if not parent:raise KeyError(case_id)
            current=dict(subject=body.subject.strip(),body=body.body.strip())
            existing=threads.child(case_id)
            if existing:
                if threads.link(existing)['current']!=current:raise Conflict('A different followup already exists')
                supersede_local_requests(actions,parent,store.get(existing),runtime_records(parent['run'])+actions.list(parent['run'].input_hash))
                return read_case(existing)
            if parent['revision']!=body.revision:raise Conflict('Stale revision')
            if parent['state']!='simulated_sent' or not parent['receipt']:raise Conflict('Simulate the approved parent first')
            if parent['quality']['status']=='blocked':raise Conflict('Blocking quality')
            if not callable(getattr(driver(),'generate_followup_ui',None)):
                return JSONResponse(dict(message='本轮实时续信入口尚未就绪，未派发请求。',code='followup_not_ready'),status_code=409)
            context=threads.messages(case_id);context_hash=digest(context)
            # A tiny immutable request receipt prevents UNKNOWN redispatch after a restart.
            journal=store.path.with_name('r2-followup-requests');journal.mkdir(exist_ok=True)
            identity=journal/(case_id+'.json');result_path=journal/(case_id+'-result.json')
            request=dict(parent_id=case_id,current=current,context_hash=context_hash,operation_id=body.operation_id)
            if identity.exists():
                old=json.loads(identity.read_text(encoding='utf-8'))
                if old['current']!=current or old['context_hash']!=context_hash:raise Conflict('Followup identity changed')
                if not result_path.exists():
                    return JSONResponse(dict(message='此前续信请求结果未确认，已保留身份，禁止自动重发。请先核查实验账本。',code='followup_unknown'),status_code=409)
                run=AnalysisRun.model_validate_json(result_path.read_text(encoding='utf-8'))
            else:
                if not driver().status_ui().get('enabled'):
                    return JSONResponse(dict(message='本轮付费派发已关闭，已有多轮记录仍可查看。',code='live_closed'),status_code=409)
                with identity.open('x',encoding='utf-8') as f:f.write(json.dumps(request,ensure_ascii=False))
                try:
                    run=driver().generate_followup_ui(parent['run'],current['body'],body.operation_id,context_messages=context,subject=current['subject'])
                except Exception:
                    return JSONResponse(dict(message='续信分析结果未确认，已保存请求身份，不会自动重发。',code='followup_unknown'),status_code=409)
                if run.email.body!=assemble_context(context,**current) or run.config.parameters.get('context_hash')!=context_hash:
                    raise Conflict('Followup source context mismatch')
                with result_path.open('x',encoding='utf-8') as f:f.write(run.model_dump_json())
            child=store.create(run,'P5-B5-R2 live followup '+case_id,origin='new_analysis')
            with threads.connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('INSERT INTO thread_links VALUES(?,?,?,?,?,?,?,?)',(child['case_id'],case_id,json.dumps(context,ensure_ascii=False),context_hash,
                    json.dumps(current,ensure_ascii=False),digest(current),digest(parent['receipt']),timestamp()))
            supersede_local_requests(actions,parent,child,runtime_records(parent['run'])+actions.list(parent['run'].input_hash))
            return read_case(child['case_id'])

    @app.get('/api/p5b5r2/cases/{case_id}')
    def read_case(case_id):
        c=store.get(case_id)
        if not c: raise KeyError(case_id)
        result=detail(store,case_id); state=state_for(store,case_id)
        result['local_events']=actions.list(c['run'].input_hash)
        params=c['run'].config.parameters
        if params.get('experiment')=='p5b8r6':
            scope=dict(product_case_id=case_id,run_id=c['run'].run_id,arm=params.get('arm','GUIDED'))
            initial=[dict(e,evidence_role='GENERATION_RECEIPT') for e in c['run'].metadata.get('runtime',{}).get('events',[]) if e.get('input_hash')==c['run'].input_hash]
            operational=[dict(e,evidence_role='POST_GENERATION_LOCAL_TASK_NOT_RETROACTIVE') for e in result['local_events'] if e.get('payload',{}).get('execution_scope')==scope]
            result['local_events']=initial+operational
        arm=(params.get('arm') or 'B2')
        result['source_label']=f'已保存真实 {arm} 首次输出 · 合成实验' if c['run'].config.backend=='deepseek_live' else '离线演示记录'
        result['conversation_state']=state.extract()
        result['timeline']=[dict(role=m['role'],body=m['text'],source='source_context_not_delivery_receipt') for m in state.messages]
        result['live_dispatch']='EXPLICIT_NEW_MAIL_ONLY'
        # Read only matching experiment receipts; do not open prior SQLite files.
        if params.get('experiment')!='p5b8r6':result['local_events']=runtime_records(c['run'])+result['local_events']
        with actions.connect() as conn:
            previous=[dict(r,payload=json.loads(r['payload'])) for r in conn.execute("SELECT * FROM events WHERE status='superseded' ORDER BY rowid")]
        inherited=[e for e in previous if e['payload'].get('replacement_input_hash')==c['run'].input_hash]
        if params.get('experiment')=='p5b8r6':inherited=[e for e in inherited if e['payload'].get('child_case_id')==case_id]
        result['local_events']=inherited+result['local_events']
        superseded={e['payload']['previous_event_id'] for e in previous}
        result['local_events']=[dict(e,operational_status='superseded') if e['event_id'] in superseded else e for e in result['local_events']]
        return result

    @app.post('/api/p5b5r2/cases/{case_id}/prepare')
    def prepare(case_id,body:Prepare):
        c=store.get(case_id)
        if not c: raise KeyError(case_id)
        if c['revision']!=body.revision: raise Conflict('Stale revision')
        if c['run'].config.parameters.get('experiment') in ('p5b8','p5b8r6'):
            if c['run'].status!='succeeded':raise Conflict('分析未通过，不创建新任务；首次事件保持可审计')
            from src.application.p5b8_pipeline import execute, guided_actions
            if c['run'].config.parameters.get('experiment')=='p5b8r6':
                from src.application.service_response import plan_actions,missing_actions
                planned=plan_actions(c['run'].metadata['p5b8'],email=c['run'].email)
                scope=dict(product_case_id=case_id,run_id=c['run'].run_id,arm=c['run'].config.parameters.get('arm','GUIDED'))
                previous=c['run'].metadata.get('runtime',{}).get('events',[])+[e for e in actions.list(c['run'].input_hash) if e.get('payload',{}).get('execution_scope')==scope]
                planned=missing_actions(c['run'].email,planned,previous)
                runtime=execute(c['run'].email,planned,actions.path,execution_scope=scope)
            else:planned=(b8_planner or guided_actions)(c['run'].metadata['p5b8'])
            if c['run'].config.parameters.get('experiment')!='p5b8r6':runtime=execute(c['run'].email,planned,actions.path)
        elif c['run'].config.parameters.get('experiment')=='p5b7':
            from src.application.p5b7_actions import execute as native_tasks
            runtime=native_tasks(actions,c['run'],state_for(store,case_id))
        else:
            runtime=actions.execute(state_for(store,case_id),c['run'].input_hash)
        if any(e['kind']=='handoff_request' and e['status']=='handoff_pending' for e in runtime['events']):
            if not any(e['action']=='request_handoff' for e in c['events']):
                store.act(case_id,'request_handoff',expected_revision=c['revision'],actor='p5b5r2_local_rule',actor_type='demo_test',
                    reason='本地人工协调请求，等待接入',operation_id='r2-handoff:'+case_id)
        return read_case(case_id)

    @app.get('/api/p5b5r2/quality')
    def quality():
        from src.evaluation.p5b5_live_report import summary as old_summary
        old=old_summary()
        # All historical arms remain selectable with their own first outputs.
        history_root=ROOT/'.local/p5b5-live-20261030-v1'
        historical_pairs={}; historical_arms=[]
        gold_path=ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json'
        gold={g['case_id']:g for g in json.loads(gold_path.read_text(encoding='utf-8'))} if gold_path.exists() else {}
        for arm in ('B2','E1','E2','E3','E4'):
            records_path=history_root/arm/'results.json'
            if not records_path.exists(): continue
            records=json.loads(records_path.read_text(encoding='utf-8'))
            metrics=old.get('arms',{}).get(arm,{})
            historical_arms.append(dict(arm=arm,n=len(records),contract=sum(bool(r['first_contract']) for r in records),guard=None,
                hard_errors=None,latency=dict(p50=metrics.get('p50_ms'),p95=metrics.get('p95_ms')),tokens=metrics.get('tokens'),cost=None,identity='HISTORICAL_NOT_R2'))
            for r in records:
                key=(r['case_id'],r['turn']); run_path=Path(r['run_path'])
                saved=json.loads(run_path.read_text(encoding='utf-8'))
                pair=historical_pairs.setdefault(key,dict(case_id=r['case_id'],turn=r['turn'],input=saved['email'],gold=gold.get(r['case_id']),runs={}))
                pair['runs'][arm]=dict(r,raw=(saved.get('attempts') or [{}])[0].get('raw_output'),config=saved.get('config'),path=str(run_path))
        old['r2_compatible']=dict(arms=historical_arms,pairs=list(historical_pairs.values()),champion='B2',promotion='NOT_PROMOTED',
            budget=dict(calls=120,cost_upper_cny=old.get('cost_upper_cny')),judge=old.get('judge_audit'),
            identity='HISTORICAL_DIFFERENT_GRADER_NOT_R2_RESULT')
        candidates=[ROOT/'docs/p5b5r2/grader-v4/RESULTS.json',ROOT/'docs/p5b5r2/grader-v3/RESULTS.json',evidence]
        result_path=next((p for p in candidates if p.exists()),evidence) if use_current_evidence else evidence
        result=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else None
        diffs=ROOT/'docs/p5b5r2/VERSION_CHANGES.json'
        if result is not None and diffs.is_file():result['source_diffs']=json.loads(diffs.read_text(encoding='utf-8'))
        return dict(r2=result, historical=old, budget=live_status())

    def package():
        if not review_package.exists(): return dict(items=[],status='PREPARING',package_hash=None)
        raw=review_package.read_bytes();content=json.loads(raw)
        if isinstance(content,list): content=dict(items=content)
        content['media']=media_manifest()
        return dict(content,package_hash=sha256(raw).hexdigest())

    @app.get('/api/p5b5r2/media/{media_id}')
    def media(media_id):
        if media_id not in MEDIA or not MEDIA[media_id][0].is_file():raise KeyError(media_id)
        return FileResponse(MEDIA[media_id][0])

    @app.get('/api/p5b5r2/review')
    def review():
        decisions=[json.loads(line) for line in decisions_path.read_text(encoding='utf-8').splitlines()] if decisions_path.exists() else []
        return dict(package(),decisions=decisions)

    @app.post('/api/p5b5r2/review')
    def save_review(body:ReviewDecision):
        with review_lock:
            p=package()
            if body.package_hash!=p['package_hash']: raise Conflict('Package changed')
            if body.item_id not in {x.get('item_id',x.get('id')) for x in p['items']}: raise KeyError(body.item_id)
            item=next(x for x in p['items'] if x.get('item_id',x.get('id'))==body.item_id)
            if body.scores is not None:
                if any(type(v) is not int or v not in (0,1,2) for v in body.scores.values() if v is not None):raise ValueError('Invalid score')
                if body.score_target!=item.get('score_target') or body.score_target is None:raise ValueError('Score target mismatch')
            previous=review()['decisions']
            matched=next((d for d in previous if d['operation_id']==body.operation_id),None)
            if matched:
                if any(matched.get(k)!=v for k,v in body.model_dump().items()): raise Conflict('Operation identity changed')
                return matched
            row=dict(body.model_dump(),at=datetime.now(timezone.utc).isoformat(),identity='LOCAL_REVIEW_OPINION_NOT_GOLD_OR_PROMOTION')
            with decisions_path.open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
            return row

    if web_directory: app.mount('/',StaticFiles(directory=web_directory,html=True),name='p5b5r2-product')
    return app
