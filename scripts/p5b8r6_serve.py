"""Existing React/API product, isolated R6 DB; saved model replies only, live closed."""
import os,sys,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.app.p5b8r5_api import create
from src.application.service_response import plan_actions
from src.application.p5b8_product import make_run
from src.application.p5b5r2_pipeline import ActionStore
from src.domain.contracts import idempotency_key
LOCAL=ROOT/'.local/p5b8r6-20261104';DOC=ROOT/'docs/p5b8r6'
def read(p):return json.loads(p.read_text('utf8'))
def setup(*,folder=None,web=None,port=8777,snapshot_from=None):
 folder=folder or ROOT/'.local/p4/p5b8r6-20261104';folder.mkdir(exist_ok=True)
 for n in ('product.sqlite3','p5b5r2-actions.sqlite3'):
  dest=folder/n
  if not dest.exists():
   source=(snapshot_from or ROOT/'.local/p4/p5b8r5-20261102')/n
   with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True) as a,sqlite3.connect(dest) as b:a.backup(b)
 trace_cases={};app=create(folder/'product.sqlite3',web or LOCAL/'web-dist',port=port,policy_overlays=read(DOC/'evidence/policy-overlays.json'),planner=plan_actions,trace_cases=trace_cases);store=app.state.store;actions=ActionStore(folder/'p5b5r2-actions.sqlite3')
 paths=sorted((LOCAL/'traces').glob('DEV-v4-*/GUIDED-reply.json'))
 paths=[LOCAL/'traces/DEV-v5-B7-035/GUIDED-reply.json' if 'B7-035' in str(p) else p for p in paths]
 for p in paths:
  r=read(p);case=dict(email=r['email'],analysis=dict(data=r['analysis'],call=r['analysis_call']),replies={'A_GUIDED':dict(reply=r['slot']['reply'],runtime=r['runtime'],call=r['call'],error=r['parse']['error'])},dataset_role='DEV_REGRESSION_SYNTHETIC',annotation_status='AI_PROVISIONAL_NOT_HUMAN_APPROVED')
  run=make_run(case);config=run.config.model_copy(update=dict(prompt_version=r['composer']['version'],parameters=dict(run.config.parameters,experiment='p5b8r6',arm='GUIDED',upstream_reuse=r['upstream_reuse'],contract='strict-tool-arguments')))
  run=run.model_copy(update=dict(config=config,idempotency_key=idempotency_key(run.email,config),cohort_id=config.cohort_id))
  c=store.create(run,'R6新模型首答 · 本地待办 · 等待人工审核',origin='new_analysis')
  trace_cases[run.email.email_id]=dict(case_id=c['case_id'],reply=r['slot']['reply'],identity=dict(run_id=run.run_id,model=run.config.model_id,prompt=r['composer']['version'],human_approved=False,dataset_role='DEV_REGRESSION'))
  with actions.connect() as conn:
   for e in r['runtime']['events']:conn.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(e['event_id'],e['input_hash'],e['conversation_id'],e['operation_id'],e['kind'],e['status'],json.dumps(e['payload'],ensure_ascii=False),e['created_at']))
 @app.get('/api/r6/traces')
 def traces():return dict(cases=trace_cases,live_enabled=False,external_actions=0)
 route=app.router.routes.pop();app.router.routes.insert(len(app.router.routes)-1,route)
 return app
if __name__=='__main__':
 import uvicorn,argparse
 parser=argparse.ArgumentParser();parser.add_argument('--offline-fix',action='store_true');args=parser.parse_args()
 kwargs=dict(folder=ROOT/'.local/p4/p5b8r6-offline-fix-v1',web=ROOT/'.local/p5b8r6-offline-fix-v1/web-dist',port=8778,snapshot_from=ROOT/'.local/p4/p5b8r6-20261104') if args.offline_fix else {}
 uvicorn.run(setup(**kwargs),host='127.0.0.1',port=kwargs.get('port',8777))
