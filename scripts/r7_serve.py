"""R7 loopback workspace, using the exact shared experiment application generate."""
import json,os,sqlite3,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r7 import LOCAL,DOC,read,save,invoke,batch
from src.application.r6u0_workflow import generate,product_run
from src.domain.contracts import EmailInput,digest,idempotency_key
LOCK=threading.Lock()
class Driver:
 def status_ui(self):
  if (LOCAL/'CLOSED.json').exists():return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='R7交付账本已关闭；默认浏览与审核不付费，新付费需新的有效授权',provider_cap=380,scope='R7 CLOSED')
  d,n=batch();s=d.summary()
  return dict(enabled=not s['halted'],remaining_requests=380-s['paid_requests'],remaining_cny=20-s['reserved_or_settled_upper_cny'],halted=s['halted'],provider_cap=380,scope=f'R7 batch {n}; synthetic research only; PAID DeepSeek')
 def generate_ui(self,subject,body,operation_id):
  if not self.status_ui()['enabled']:raise PermissionError('R7_CLOSED_NO_PAID_DISPATCH')
  if not LOCK.acquire(False):raise ValueError('Request running; no retry')
  try:
   key=digest(dict(subject=subject,body=body,operation_id=operation_id));folder=LOCAL/'web-traces'/key
   if (folder/'GUIDED-reply.json').exists():return product_run(read(folder/'GUIDED-reply.json'))
   e=EmailInput(email_id='R7-WEB-'+key[:12],subject=subject,body=body)
   r=generate(e,lambda s,m,p:invoke('WEB-'+key+'-'+s,m,p),folder,role='WEB_DEV',arms=('GUIDED',),revision='r7-web-v1')['GUIDED']
   return product_run(r)
  finally:LOCK.release()
 generate_followup_ui=generate_ui

def setup():
 from src.app.p5b8r5_api import create
 from src.application.p5b5r2_pipeline import ActionStore
 folder=ROOT/'.local/p4/r7-20261106-v1';folder.mkdir(exist_ok=True)
 for n in ['product.sqlite3','p5b5r2-actions.sqlite3']:
  if not (folder/n).exists():
   source=ROOT/'.local/p4/r6u0-20261105-v1'/n
   with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True) as a,sqlite3.connect(folder/n) as b:a.backup(b)
 trace={};app=create(folder/'product.sqlite3',LOCAL/'web-dist',port=8779,policy_overlays=read(ROOT/'docs/p5b8r6/evidence/policy-overlays.json'),trace_cases=trace,live_driver=Driver())
 actions=ActionStore(folder/'p5b5r2-actions.sqlite3')
 for p in sorted((LOCAL/'traces').glob('DEV-v3-*/GUIDED-reply.json')):
  r=read(p);run=product_run(r)
  config=run.config.model_copy(update=dict(parameters=dict(run.config.parameters,current_experiment='R7',dataset_role='EXPOSED_SYNTHETIC_DEV')))
  run=run.model_copy(update=dict(config=config,cohort_id=config.cohort_id,idempotency_key=idempotency_key(run.email,config)))
  c=app.state.store.create(run,'R7真实首答 · 合成研究 · 本地待办待审',origin='new_analysis')
  trace[run.email.email_id]=dict(case_id=c['case_id'],reply=r['slot']['reply'],identity=dict(run_id=run.run_id,prompt=r['composer']['version'],human_approved=False))
  with actions.connect() as conn:
   for e in r['runtime']['events']:conn.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(e['event_id'],e['input_hash'],e['conversation_id'],e['operation_id'],e['kind'],e['status'],json.dumps(e['payload'],ensure_ascii=False),e['created_at']))
 static=app.router.routes.pop()
 @app.get('/api/r7/traces')
 def traces():return dict(cases=trace,external_actions=0)
 @app.get('/api/r7/health')
 def health():return dict(status='ok',project='complaint_llm_system',version='R7',loopback_only=True,paid_closed=(LOCAL/'CLOSED.json').exists())
 app.router.routes.append(static);return app
if __name__=='__main__':
 import uvicorn
 uvicorn.run(setup(),host='127.0.0.1',port=8779)
