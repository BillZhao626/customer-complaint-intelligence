"""R8 isolated loopback UI; paid dispatch is disabled in the product."""
import json,os,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
L=ROOT/'.local/r8-quality-20261109-v1';D=ROOT/'docs/r8-quality-20261109-v1'
def read(p):return json.loads(Path(p).read_text('utf8'))
class NoPaidDriver:
 def status_ui(self):return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='R8研究请求由独立账本执行；网站浏览、编辑与审核不调用模型',provider_cap=600,scope='R8 UI READ SAVED RESULTS')
 def generate_ui(self,*a,**kw):raise PermissionError('R8_UI_PAID_DISABLED')
 generate_followup_ui=generate_ui
def setup():
 from fastapi.responses import FileResponse
 from src.app.p5b8r5_api import create
 from src.application.r6u0_workflow import product_run
 from src.application.p5b5r2_pipeline import ActionStore
 folder=ROOT/'.local/p4/r8-quality-20261109-v1';folder.mkdir(parents=True,exist_ok=True)
 for name in ['product.sqlite3','p5b5r2-actions.sqlite3']:
  target=folder/name;source=ROOT/'.local/p4/r7-20261106-v1'/name
  if not target.exists():
   with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True) as a,sqlite3.connect(target) as b:a.backup(b)
 traces={};app=create(folder/'product.sqlite3',L/'web-dist',port=8781,policy_overlays=read(ROOT/'docs/p5b8r6/evidence/policy-overlays.json'),trace_cases=traces,live_driver=NoPaidDriver())
 actions=ActionStore(folder/'p5b5r2-actions.sqlite3')
 for p in sorted((L/'traces').glob('*/GUIDED-reply.json')):
  r=read(p);run=product_run(r);c=app.state.store.create(run,'R8真实首答 · 合成研究 · 待人工审核',origin='new_analysis')
  traces[run.email.email_id]=dict(case_id=c['case_id'],run_id=run.run_id,reply=r['slot']['reply'],identity=dict(prompt=r['composer']['version'],human_approved=False))
  with actions.connect() as conn:
   for e in r['runtime']['events']:conn.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(e['event_id'],e['input_hash'],e['conversation_id'],e['operation_id'],e['kind'],e['status'],json.dumps(e['payload'],ensure_ascii=False),e['created_at']))
 static=app.router.routes.pop()
 @app.get('/api/r8/health')
 def health():return dict(status='ok',project='complaint_llm_system',version='R8',paid_ui_enabled=False,storage=str(folder))
 @app.get('/api/r8/traces')
 def trace():return traces
 @app.get('/api/r8/quality')
 def quality():
  path=D/'quality-ui.json';data=read(path) if path.exists() else dict(cases=[],summary={})
  for row in data.get('cases',[]):row['product_case_id']=traces.get(row['case_id'],{}).get('case_id')
  return data
 @app.get('/api/r8/human')
 def human():return FileResponse(D/'R8_HUMAN_REVIEW_PACK/index.html')
 app.router.routes.append(static);return app
if __name__=='__main__':
 import uvicorn
 os.environ.update(COMPLAINT_ENABLE_LIVE='false',LLM_ENABLE_API='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
 uvicorn.run(setup(),host='127.0.0.1',port=8781)
