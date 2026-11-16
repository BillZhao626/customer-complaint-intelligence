"""Nine historical DEV regressions through the same production workflow."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.r8 import L,OLD,read,invoke
from src.application.r6u0_workflow import generate
def run():
 for e in read(OLD/'dev-inputs.json'):
  cid=e['email_id'];generate(e,lambda s,m,p:invoke('REGRESSION-'+cid+'-'+s,m,p),L/'traces'/('REGRESSION-'+cid),arms=('GUIDED',),revision='r8-v2-regression')
  print('REGRESSION_DONE',cid,flush=True)
if __name__=='__main__':run()
