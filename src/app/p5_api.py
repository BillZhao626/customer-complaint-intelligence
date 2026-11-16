"""Loopback-only P5 thin adapter. Existing stores own all business transitions.

No .env loading, provider construction, SMTP, policy approval or DB migration.
Use create_app with a fresh dedicated product path; import has no storage IO.
"""
import os
from pathlib import Path
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from src.application.analysis_service import AnalysisService
from src.application.copilot_drafts import insert_suggestion
from src.application.mail_threads import MailThreads
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore, Conflict
from src.application.service_triage import triage, quick_confirm_and_simulate
from src.domain.contracts import digest
from src.infrastructure.repository import Repository

ROOT = Path(__file__).resolve().parents[2]


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: str
    revision: int = Field(ge=0)
    operation_id: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=30000)
    reason: str = Field(default='', max_length=10000)
    checks: dict = Field(default_factory=dict)
    confirmed: bool = False
    mode: str = 'replace'


class Followup(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    body: str = Field(max_length=30000)
    revision: int = Field(ge=0)
    operation_id: str = Field(min_length=1, max_length=200)


class Demo(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    scenario: str


class LiveMail(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    subject: str = Field(min_length=1,max_length=500)
    body: str = Field(min_length=1,max_length=20000)
    synthetic_confirmed: bool


class KnowledgeNote(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=0)
    operation_id: str = Field(min_length=1,max_length=200)
    kind: str
    body: str = Field(min_length=1,max_length=10000)


def catalog():
    from src.application.service_scenarios import SCENARIOS
    from src.application.service_scenarios_v2 import SCENARIOS as V2
    result = [dict(id='p47:'+s, label='P4.7 · '+s) for s in SCENARIOS]
    result += [dict(id='p47v2:'+s, label='P4.7 · '+s) for s in V2]
    result.append(dict(id='blocked', label='工程反例 · 安全风险低估（必须阻断）'))
    try:
        from src.application.p5_quality import load_cases
        result = [dict(id='p5:'+c['case_id'], label='P5 · '+c.get('subject', c['case_id'])) for c in load_cases()] + result
    except ImportError:
        pass
    return result


def create_demo(store, scenario):
    if scenario.startswith('p5:'):
        from src.application.p5_quality import example, P5CandidateAnalyzer
        key = scenario[3:]
        email, _ = example(key)
        analyzer = P5CandidateAnalyzer(email, key)
    elif scenario == 'blocked':
        from src.application.copilot_demo import SCENARIOS, example, CopilotFake
        email, _ = example(SCENARIOS[8]); analyzer = CopilotFake(email, SCENARIOS[8])
    elif scenario.startswith('p47v2:'):
        from src.application.service_scenarios_v2 import example, ServiceCopilotFake
        key = scenario[6:]; email, _ = example(key); analyzer = ServiceCopilotFake(email, key)
    elif scenario.startswith('p47:'):
        from src.application.service_scenarios import example, ServiceCopilotFake
        key = scenario[4:]; email, _ = example(key); analyzer = ServiceCopilotFake(email, key)
    else:
        raise ValueError('Unknown demo')
    repo = Repository(store.path.with_name(store.path.stem+'-analysis.sqlite3'))
    return ProductAnalysis(AnalysisService(repo, analyzer), store).submit(email)


def status(case, route):
    if case['state'] == 'analysis_failed': return '分析未通过'
    if case['quality']['status'] == 'blocked': return '安全阻断'
    if case['state'] == 'simulated_sent': return '已本地模拟'
    if case['state'] == 'approved': return '已确认待模拟'
    if route['handoff'] == 'requested': return '等待人工'
    if route['handoff'] == 'taken_over':
        event=next((e for e in reversed(case['events']) if e['action']=='take_over'),None)
        return '本地演示接管' if event and event['actor_type']=='demo_test' else '人工已接管'
    return {'changes_requested':'需要修改', 'rejected':'已拒绝', 'analysis_failed':'分析待人工'}.get(case['state'], route['label'])


def summary(case, customer_body):
    route = triage(case)
    return dict(case_id=case['case_id'], subject=case['run'].email.subject,
                preview=' '.join(customer_body.split())[:90], status=status(case, route), state=case['state'],
                revision=case['revision'], updated_at=case['events'][-1]['created_at'],
                blocked=case['quality']['status']=='blocked', source_kind=case['source_kind'])


def detail(store, case_id):
    case = store.get(case_id)
    if not case: raise KeyError(case_id)
    route = triage(case)
    messages = MailThreads(store).messages(case_id)
    customer_body = next(m['body'] for m in reversed(messages) if m['role']=='customer')
    source = [dict(id='email', label='客户原文', body=customer_body)]
    for issue in (case['analysis'] or {}).get('issues', []):
        source.append(dict(id=issue['issue_id'], label=issue['object_name'],
                           body='\n'.join(e['quote'] for e in issue['evidence'])))
    actions = []
    if case['state'] != 'simulated_sent':
        if route['handoff'] == 'none': actions.append('request_handoff')
        if route['handoff'] != 'taken_over': actions.append('take_over')
        if case['draft']:
            actions += ['save_edit','insert_suggestion','request_changes','reject']
            if case['quality']['status'] != 'blocked' and (not route['requires_takeover'] or route['takeover_complete']):
                actions.append('simulate_send' if case['state']=='approved' else 'approve')
            if route['can_quick_confirm']: actions.append('quick_confirm')
    else: actions.append('followup')
    result = dict(**summary(case, customer_body), current_version=case['current_version'], draft=case['draft'],
                  suggestion=case['run'].result.suggested_reply if case['run'].result else '',
                  summary=(case['analysis'] or {}).get('summary', '尚无可用分析，请人工阅读原文。'),
                  messages=messages, triage=route, quality=case['quality'],
                  sources=source, events=case['events'], drafts=case['drafts'], receipt=case['receipt'],
                  allowed_actions=actions, source_label=('真实模型生成 · 未发送草稿' if case['source_kind']=='real_new_analysis'
                    else '真实历史回复重放' if case['source_kind']=='real_replay' else '离线预写 · 非实时模型'), simulation_only=True)
    key = (case['run'].config.parameters or {}).get('p5_case_id')
    if key:
        from src.application.p5_quality import get_case, p5_strategy
        if p5_strategy(case) is not None:
            result['pilot'] = get_case(key)
    from src.application.p5_knowledge_tasks import KnowledgeTasks
    result['knowledge_tasks'] = KnowledgeTasks(store).list(case_id)
    from src.application.p5b3_actions import journal
    action_path=store.path.with_name(store.path.stem+'-actions.sqlite3')
    result['business_tasks']=journal(store).list(case['run'].input_hash) if action_path.exists() else []
    result['run_trace']=dict(run_id=case['run'].run_id,input_hash=case['run'].input_hash,
        model=case['run'].config.model_id,prompt=case['run'].config.prompt_version,
        status=case['run'].status,metadata=case['run'].metadata,
        attempts=[dict(number=a.attempt_no,parse=a.parse_status,contract=a.contract_status,elapsed_ms=a.elapsed_ms,metadata=a.metadata) for a in case['run'].attempts])
    result['ai'] = dict(summary=result['summary'], next_step=route['next_step'], suggestion=result['suggestion'],
                        source_label=result['source_label'], references=[dict(id=s['id'],title=s['label'],excerpt=s['body']) for s in source])
    if case['state']=='analysis_failed' and case['run'].config.schema_version=='analysis-v3.2':
        from src.domain.analysis_v32 import validate
        from src.application.live_execution import strict_json
        from pydantic import ValidationError
        reason='AI分析的字段或证据未通过校验，请人工核实原文；当前不能审核或模拟发送。'
        try:
            validate(strict_json(case['run'].attempts[-1].raw_output),case['run'].email)
        except ValidationError as exc:
            missing=[e for e in exc.errors(include_input=False) if e['type']=='missing']
            for e in missing:
                loc=e['loc']
                if len(loc)==3 and loc[0]=='issues' and loc[2]=='urgency':
                    reason=f'AI分析缺少第{loc[1]+1}项问题的紧急程度，当前不能审核或模拟发送。'
        except (ValueError,TypeError,IndexError):
            pass
        result['validation_reason']=reason
    if result.get('pilot'):
        plan = result['pilot']['policy_decision']
        result['ai'].update(next_step='；'.join(result['pilot']['reply_plan']['next_actions']),
                            missing_facts=plan['internal_questions'],
                            knowledge_status='业务知识待内部核实；草案尚未批准' if plan['internal_questions'] else '开发候选，不代表商家政策已批准')
    return result


def create_app(db_path, *, serve_web=True, web_directory=None, live_generate=False, local_origin_port=None):
    if local_origin_port is not None and (type(local_origin_port) is not int or not 1024 <= local_origin_port <= 65535):
        raise ValueError('Explicit local development port required')
    # Explicitly close inherited environment switches, including tracing.
    os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false', LANGSMITH_TRACING='false',
                      LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')
    store = ProductStore(db_path)
    app = FastAPI(title='P5 local development inbox', docs_url=None, redoc_url=None)
    token = secrets.token_urlsafe(32)
    app.state.store = store

    def paid_closed():
        if live_generate:
            from src.application.p5b3_runtime import Budget,LOCAL
            if Budget(LOCAL/'budget.sqlite3').summary()['halted']:
                return JSONResponse(dict(message='本轮付费实验已关闭。可查看、审核已有结果；新模型实验需要新的明确授权。',code='experiment_closed'),status_code=409)
        return None

    @app.middleware('http')
    async def loopback_boundary(request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        origin = request.headers.get('origin')
        allowed = {'http://127.0.0.1:8765','http://localhost:8765','http://127.0.0.1:8766','http://localhost:8766','http://127.0.0.1:8767','http://localhost:8767','http://127.0.0.1:5173','http://localhost:5173'}
        if local_origin_port is not None:
            allowed.update({f'http://127.0.0.1:{local_origin_port}', f'http://localhost:{local_origin_port}'})
        if host not in ('127.0.0.1','localhost','testserver') or (origin and origin not in allowed):
            return JSONResponse(dict(message='仅限本机客服开发入口。', code='local_only'), status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(request.headers.get('x-p5-token',''), token):
            return JSONResponse(dict(message='操作会话已失效，请刷新页面后重试。', code='session_required'), status_code=403)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(dict(message='请检查输入：正文不能为空，操作需绑定当前版本。',code='invalid_input'),status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(dict(message='未找到该会话，请刷新收件箱。',code='not_found'),status_code=404)

    @app.exception_handler(ValueError)
    async def conflict(request, exc):
        # Do not echo provider payloads or Pydantic's original input.
        text = str(exc)
        if isinstance(exc, Conflict):
            message = ('当前分析存在安全阻断，改写或接管不能解除。' if 'Blocking quality' in text else
                       '请先由本地操作者接管，再审核回复。' if '接管' in text else
                       '当前版本或操作状态已变化，请刷新后核对；未自动重试。')
            return JSONResponse(dict(message=message,code='conflict'),status_code=409)
        return JSONResponse(dict(message='输入无效，请核对正文和所选演示。',code='invalid_input'),status_code=422)

    @app.get('/api/session')
    def session(): return dict(token=token, mode='bounded_live' if live_generate else 'offline_development', simulation_only=True)

    @app.post('/api/live')
    def live(body: LiveMail):
        if not live_generate or not body.synthetic_confirmed or not body.body.strip(): raise ValueError('Live synthetic entry disabled')
        closed=paid_closed()
        if closed is not None:return closed
        from src.application.p5b3_runtime import generate
        from src.domain.contracts import EmailInput
        identity=digest(dict(subject=body.subject,body=body.body))
        candidate=(ROOT/'docs/p5b3/candidate-freeze.json').exists()
        case=generate(EmailInput(email_id='p5b3-ui-'+identity[:16],subject=body.subject,body=body.body),stage='ui-final' if candidate else 'ui-initial',candidate=candidate,store=store)
        return detail(store,case['case_id'])

    @app.get('/api/cases')
    def cases():
        threads = MailThreads(store)
        rows = []
        for case in store.list_cases():
            if not threads.child(case['case_id']):
                current_body = next(m['body'] for m in reversed(threads.messages(case['case_id'])) if m['role']=='customer')
                rows.append(summary(case, current_body))
        return dict(cases=sorted(rows, key=lambda c:c['updated_at'], reverse=True))

    @app.get('/api/cases/{case_id}')
    def read(case_id): return detail(store,case_id)

    @app.get('/api/demo')
    def demos(): return dict(scenarios=catalog())

    @app.post('/api/demo')
    def demo(body: Demo): return detail(store,create_demo(store,body.scenario)['case_id'])

    @app.post('/api/cases/{case_id}/actions')
    def act(case_id, body: Command):
        actor = dict(actor='p5_local_operator', actor_type='demo_test')
        if body.action == 'quick_confirm':
            result = quick_confirm_and_simulate(store,case_id,expected_revision=body.revision,confirmed=body.confirmed,operation_id=body.operation_id,**actor)
        elif body.action == 'insert_suggestion':
            if body.body is None: raise ValueError('Missing editor')
            result = insert_suggestion(store,case_id,expected_revision=body.revision,editor_text=body.body,
                expected_editor_hash=digest(body.body),mode=body.mode,operation_id=body.operation_id,**actor)
        else:
            result = store.act(case_id,'save_edit' if body.action=='save_draft' else body.action,
                expected_revision=body.revision,reason=body.reason,body=body.body,checks=body.checks,operation_id=body.operation_id,**actor)
        return detail(store,result['case_id'])

    @app.post('/api/cases/{case_id}/followup')
    def followup(case_id, body: Followup):
        if not body.body.strip():
            return JSONResponse(dict(message='请填写客户后续邮件正文。',code='empty_body'),status_code=422)
        parent = store.get(case_id)
        if not parent: raise KeyError(case_id)
        if parent['revision'] != body.revision: raise Conflict('Stale revision')
        if live_generate and (ROOT/'docs/p5b3/candidate-freeze.json').exists():
            closed=paid_closed()
            if closed is not None:return closed
            from src.application.p5b3_product import follow_up
            result=follow_up(store,case_id,body.body)
        else:
            result = MailThreads(store).follow_up(case_id,'Re: '+parent['run'].email.subject,body.body)
        return detail(store,result['case_id'])

    @app.post('/api/cases/{case_id}/tasks/{task_id}')
    def supply_knowledge(case_id,task_id,body: KnowledgeNote):
        from src.application.p5b3_actions import journal
        case=store.get(case_id)
        if not case: raise KeyError(case_id)
        if case['revision']!=body.revision: raise Conflict('Stale revision')
        tasks=journal(store).list(case['run'].input_hash)
        if task_id not in {t['task_id'] for t in tasks}: raise ValueError('Wrong scope')
        journal(store).supply(task_id,body=body.body,source=body.kind,operation_id=body.operation_id)
        return detail(store,case_id)

    @app.post('/api/cases/{case_id}/continue')
    def continue_knowledge(case_id):
        if not live_generate: raise ValueError('Disabled')
        closed=paid_closed()
        if closed is not None:return closed
        from src.application.p5b3_product import continue_with_knowledge
        case=continue_with_knowledge(store,case_id)
        return detail(store,case['case_id'])

    @app.get('/api/cases/{case_id}/sources')
    def sources(case_id): return dict(sources=detail(store,case_id)['sources'])

    @app.post('/api/cases/{case_id}/knowledge-notes')
    def knowledge_note(case_id, body: KnowledgeNote):
        from src.application.p5_knowledge_tasks import KnowledgeTasks
        KnowledgeTasks(store).append(case_id,revision=body.revision,operation_id=body.operation_id,kind=body.kind,body=body.body)
        return detail(store,case_id)

    web_path = Path(web_directory) if web_directory else ROOT/'web-client/dist'
    if serve_web and web_path.is_dir():
        app.mount('/',StaticFiles(directory=web_path,html=True),name='web')
    return app
