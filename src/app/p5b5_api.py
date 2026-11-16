"""Additive local product routes. Existing review and simulation gates own writes."""
from pathlib import Path
import json
import re
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from src.app.p5_api import create_app as base_app,detail,summary as case_summary
from src.application.p5b5_pipeline import ActionStore
from src.application.p5b5_state_v3 import ConversationState
from src.application.product_workflow import Conflict
from src.application.mail_threads import MailThreads

ROOT=Path(__file__).resolve().parents[2]

class Prepare(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    revision:int=Field(ge=0)

def state_for(store,case_id):
    state=ConversationState(case_id)
    for m in MailThreads(store).messages(case_id):
        body=m['body']
        if m['role']=='customer' and '[customer' in body:
            pieces=re.split(r'\[(customer|assistant)[^\]]*\]\n',body)
            for i in range(1,len(pieces),2):state.update(pieces[i],pieces[i+1].strip())
        else:state.update('customer' if m['role']=='customer' else 'assistant',body)
    return state

def create(db_path,*,web_directory=None,evidence=None):
    app=base_app(db_path,serve_web=False,live_generate=False,local_origin_port=8769)
    store=app.state.store
    actions=ActionStore(store.path.with_name('p5b5-actions.sqlite3'))
    evidence=Path(evidence or ROOT/'.local/p5b5/evidence-v1')

    @app.get('/api/p5b5/inbox')
    def inbox():
        cases=store.list_cases();threads=MailThreads(store);rows=[]
        refs={c['source_ref'] for c in cases}
        for c in cases:
            if threads.child(c['case_id']):continue
            if c['source_ref'].endswith('-T1') and c['source_ref'][:-3]+'-T2' in refs:continue
            state=state_for(store,c['case_id']);row=case_summary(c,state.extract()['latest_request'])
            row['search_text']=state.customers
            row['model_arm']=c['run'].config.parameters.get('arm','历史 B2')
            rows.append(row)
        return dict(cases=sorted(rows,key=lambda c:c['updated_at'],reverse=True))

    @app.get('/api/p5b5/quality')
    def quality():
        if not (evidence/'view-data.json').exists():return JSONResponse(dict(message='尚无可用评测记录。',code='no_evidence'),status_code=404)
        result=json.loads((evidence/'view-data.json').read_text(encoding='utf-8'))
        from src.evaluation.p5b5_live_report import summary
        result['live']=summary()
        return result

    @app.get('/api/p5b5/cases/{case_id}')
    def read_case(case_id):
        c=store.get(case_id)
        if not c:raise KeyError(case_id)
        result=detail(store,case_id);state=state_for(store,case_id)
        result['local_events']=actions.list(c['run'].input_hash)
        if c['run'].config.parameters.get('experiment')=='p5b5-live-v1':
            from src.evaluation.p5b5_live_report import LOCAL
            arm=c['run'].config.parameters['arm']
            source=LOCAL/arm/(c['run'].email.email_id)/'evaluation.json'
            if source.exists():
                runtime=json.loads(source.read_text(encoding='utf-8'))['runtime']
                result['local_events']=runtime['events']+result['local_events']
            result['source_label']='本轮真实 '+arm+' 首次输出 · 保存重读'
        result['conversation_state']=state.extract()
        result['timeline']=[dict(role=m['role'],body=m['text'],source='source_context_not_delivery_receipt') for m in state.messages]
        result['live_dispatch']='LIVE_DISPATCH_DISABLED'
        return result

    @app.post('/api/p5b5/cases/{case_id}/prepare')
    def prepare(case_id,body:Prepare):
        c=store.get(case_id)
        if not c:raise KeyError(case_id)
        if c['revision']!=body.revision:raise Conflict('Stale revision')
        state=state_for(store,case_id)
        runtime=actions.execute(state,c['run'].input_hash)
        if any(e['kind']=='handoff_request' and e['status']=='handoff_pending' for e in runtime['events']):
            if not any(e['action']=='request_handoff' for e in c['events']):
                store.act(case_id,'request_handoff',expected_revision=c['revision'],actor='p5b5_local_rule',actor_type='demo_test',
                    reason='本地人工协调请求，尚未接入；无对外动作',operation_id='b5-handoff:'+case_id)
        return read_case(case_id)

    if web_directory:
        app.mount('/',StaticFiles(directory=web_directory,html=True),name='p5b5-product')
    return app
