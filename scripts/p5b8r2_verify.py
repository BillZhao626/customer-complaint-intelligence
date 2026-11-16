"""Read-only verification of R2 preparation, offline results and delivered evidence."""
import sys,json,csv,zipfile,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b8r1_experiment import pair_invariant
from src.application.p5b8_research import cases,comparison,insight
from src.domain.contracts import digest
DOC=ROOT/'docs/p5b8r2'
def read(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 checks=[]
 def check(label,ok):
  checks.append(dict(check=label,ok=bool(ok)))
 m=read(DOC/'EXPERIMENT_MANIFEST.json');check('No live authorization, budget or paid calls',not m['live_dispatch_enabled'] and m['new_paid_calls']==0 and m['budget_ledger'] is None)
 ps=[read(p) for p in sorted((DOC/'prepared').glob('*.json'))];check('24 first pair inputs',len(ps)==24)
 check('24 unique exposed DEV input hashes',len({p['input_hash'] for p in ps})==24 and all(p['role']=='EXPOSED_DEV_NOT_INDEPENDENT' for p in ps))
 for p in ps:check('Single explicit-emotion difference '+p['case_id'],pair_invariant(p['messages'])==p['invariant'])
 old=read(ROOT/'.local/p5b8r1/FROZEN_PROTOCOL_v2.json');check('R1 protocol unchanged',sha(ROOT/'.local/p5b8r1/FROZEN_PROTOCOL_v2.json')==m['A']['r1_protocol_sha256'])
 check('R1 selection/order retained',[(p['case_id'],p['order']) for p in ps]==sorted([(p['case_id'],p['order']) for p in old['cases']]))
 rows=cases();check('Historical A endpoint unchanged',comparison(rows,'A')==read(DOC/'HISTORICAL_QUALITY.json')['A']);check('Historical B endpoint unchanged',comparison(rows,'B')==read(DOC/'HISTORICAL_QUALITY.json')['B'])
 check('Deterministic business statistics reproducible',insight([r for r in rows if r['case_id'].startswith('B7')])==read(DOC/'BUSINESS_STATISTICS.json'))
 book=(DOC/'CASEBOOK.md').read_text('utf-8')
 for r in rows:
  if r['case_id'] in ('B7-036','B7-084','B7-035','B7-009','B7-010','B7-085'):check('Full customer body in casebook '+r['case_id'],r['email']['body'] in book)
 check('Historical 94 casebook byte identical',sha(DOC/'HISTORICAL_CASEBOOK_94.md')==sha(ROOT/'docs/p5b8r1/CASEBOOK.md'))
 check('Pre-B8 casebook byte identical',sha(DOC/'HISTORICAL_CASEBOOK_PRE_B8.md')==sha(ROOT/'docs/p5b8r1/HISTORICAL_CASEBOOK_P5B8.md'))
 traces=read(DOC/'TRACE_INDEX.json');check('Actual wire/response/Judge/frozen-source traces preserved',len(traces)>100 and all(sha(DOC/r['packaged'])==r['sha256'] for r in traces))
 with (DOC/'ACCEPTANCE.csv').open(encoding='utf-8-sig',newline='') as f:a=list(csv.DictReader(f))
 valid={'VERIFIED','IMPROVED_NOT_HUMAN_CERTIFIED','REGRESSED','UNKNOWN','HUMAN_PENDING','AUTHORIZATION_BLOCKED','FAILED','NOT_RUN'}
 check('74 individually evidenced acceptance rows',len(a)==74 and len({r['id'] for r in a})==74 and all(r['status'] in valid and r['evidence'] and r['command'] for r in a))
 check('73 original IDs + J aggregate explicitly disclosed',len([r for r in a if r['id']!='J_ALL'])==73)
 for r in a:
  for ref in r['evidence'].split('; '):check('Evidence exists '+ref,(DOC/ref).exists())
 required=['OWNER_POLICY_v2.md','EVAL_CALIBRATION.md','CODE_DIFF_AND_REGR.md','EXPERIMENT_MANIFEST.json','AB_RESULTS.csv','CASEBOOK.md','ALL_BAD_CASES.csv','THESIS_RESULTS.md','STAGE_PORTFOLIO.pdf','ACCEPTANCE.md','HANDOFF.md','PDF_QA.json','UI_ACCEPTANCE.md','PROTECTION_FINAL.json']
 for f in required:check('Deliverable '+f,(DOC/f).is_file() and (DOC/f).stat().st_size>0)
 check('Portfolio 8 pages and visual QA',read(DOC/'PDF_QA.json')['portfolio_pages']==8 and read(DOC/'PDF_QA.json')['visual_review_complete'])
 protection=read(DOC/'PROTECTION_FINAL.json');check('No protected asset change/missing',not protection['unexpected_changes'] and not protection['missing'])
 for name,pattern in [('test-r2-final.txt',r'Ran 8 tests'),('test-b-family.txt',r'Ran 177 tests'),('test-full.txt',r'Ran \d+ tests')]:
  text=(DOC/name).read_text('utf-8-sig');check('Completed offline tests '+name,bool(re.search(pattern,text)) and bool(re.search(r'^OK$',text,re.M)))
 p=DOC/'P5-B8-R2_COMPLETE_REVIEW.zip'
 with zipfile.ZipFile(p) as z:
  check('ZIP CRC',z.testzip() is None)
  idx=json.loads(z.read('PACKAGE_CONTENTS.json'));check('ZIP all internal content hashes',all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in idx.items()))
  check('ZIP package contains no .env/credentials/private keys',not any(Path(n).name=='.env' or n.endswith(('.sqlite3','.db','.pem')) for n in z.namelist()))
  suspicious=[]
  for n in z.namelist():
   if Path(n).suffix in ('.txt','.md','.json','.jsonl','.csv','.py'):
    data=z.read(n)
    if re.search(rb'(?i)(?:Bearer\s+sk-[a-z0-9]{15,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----|["\x27]api_key["\x27]\s*:\s*["\x27]sk-[a-z0-9]{15,})',data):suspicious.append(n)
  check('No embedded credential signatures',not suspicious)
 result=dict(checks=checks,verified=sum(c['ok'] for c in checks),failed=sum(not c['ok'] for c in checks),new_paid_calls=0,model_quality='AUTHORIZATION_BLOCKED_NOT_CERTIFIED')
 print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
 for c in checks:
  if not c['ok']:print('FAILED:',c['check'])
 if result['failed']:raise SystemExit(1)
 return result
if __name__=='__main__':main()
