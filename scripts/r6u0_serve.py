"""Controlled loopback product uses the same application workflow as experiments."""
import sys,json,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.r6u0 import LOCAL,DOC,read,write,dispatcher,invoke
from src.application.r6u0_workflow import generate,product_run
from src.domain.contracts import EmailInput,digest
LOCK=threading.Lock()

class Driver:
 def status_ui(self):
  d=dispatcher();s=d.summary()
  return dict(enabled=not s['halted'],remaining_requests=200-s['paid_requests'],remaining_cny=round(20-s['reserved_or_settled_upper_cny'],6),halted=s['halted'],provider_cap=200,scope='R6-U0 controlled synthetic only')
 def generate_ui(self,subject,body,operation_id):
  if not LOCK.acquire(blocking=False):raise ValueError('Another request in progress; do not retry')
  try:
   key=digest(dict(subject=subject,body=body,operation_id=operation_id));folder=LOCAL/'web-traces'/key
   dest=folder/'GUIDED-reply.json'
   if dest.exists():return product_run(read(dest))
   e=EmailInput(email_id='U0-WEB-'+key[:12],subject=subject,body=body);d=dispatcher()
   r=generate(e,lambda suffix,msg,payload:invoke(d,'WEB-'+key+'-'+suffix,msg,payload),folder,role='WEB_DEV',arms=('GUIDED',),revision='web-v1')
   return product_run(r['GUIDED'])
  finally:LOCK.release()

def setup():
 from src.app.p5b8r5_api import create
 folder=ROOT/'.local/p4/r6u0-20261105-v1';folder.mkdir(exist_ok=True)
 app=create(folder/'product.sqlite3',LOCAL/'web-dist',port=8779,policy_overlays=read(ROOT/'docs/p5b8r6/evidence/policy-overlays.json'),live_driver=Driver())
 selected={}
 for p in sorted((LOCAL/'traces').glob('DEV-v*-*/GUIDED-reply.json')):
  selected[read(p)['email']['email_id']]=p
 for p in selected.values():
  app.state.store.create(product_run(read(p)),'R6-U0 本轮真实首答 · 合成DEV · 待审',origin='new_analysis')
 return app

if __name__=='__main__':
 import uvicorn
 uvicorn.run(setup(),host='127.0.0.1',port=8779)
