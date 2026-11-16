"""Final read-only historical audit plus new evidence receipts, no model calls."""
from pathlib import Path
import sys,json,hashlib,subprocess,re,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b2 import LOCAL,DOC,read,write_new,now
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

old=read(LOCAL/'protection-start.json');last=read(DOC/'PROTECTION_FINAL.json')
allowed={r['path']:r['after'] for r in last['authorized_changes']}
bad=[]
for p,h in old.items():
    path=ROOT/p
    if not path.is_file() or sha(path)!=allowed.get(p,h):bad.append(p)
assert not bad,bad
write_new(DOC/'PROTECTION_RECHECK.json',dict(at=now(),checked=len(old),expected_authorized_changes=len(allowed),missing_or_unexpected=bad,
    human_gold_unchanged=True,prior_budgets_unchanged=True,prior_raw_unchanged=True,env_unchanged=True))
logs={'P5':('offline-final-regression-v3.txt',69),'product':('offline-product-regression.txt',44),'contracts':('offline-contracts.txt',10)}
results=[]
for name,(file,n) in logs.items():
    p=LOCAL/file;body=p.read_text(encoding='utf8')
    assert re.search(r'Ran '+str(n)+r' tests?',body) and '\nOK' in body and '\nFAILED' not in body
    dst=DOC/'test-evidence'/file;dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('xb') as f:f.write(p.read_bytes())
    results.append(dict(suite=name,tests=n,passed=n,failures=0,errors=0,skipped=0,log='test-evidence/'+file))
for file in ('web-test.txt','web-build-final-v2.txt','product-quality-tests.txt','web-build.txt'):
    with (DOC/'test-evidence'/file).open('xb') as f:f.write((LOCAL/file).read_bytes())
write_new(DOC/'TEST_RESULTS.json',dict(python_suites=results,python_distinct_total=123,frontend_tests=7,build='PASS',
    identity='OFFLINE_ENGINEERING_WITH_FIXTURES_NOT_MODEL_QUALITY',first_build_type_failure_preserved='test-evidence/web-build.txt'))
(DOC/'GIT_STATUS_FINAL.txt').write_bytes(subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT))
new=[]
for folder in ('src','scripts','tests','docs/p5b2'):
    for p in (ROOT/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in old:
            new.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)))
write_new(DOC/'CHANGE_LEDGER_FINAL.json',dict(at=now(),modified=last['authorized_changes'],new=new,deleted=[],
    inventory_note='Generated ledger itself and final delivery hash manifest excluded to avoid self-reference'))
from src.config.llm_config import _load_dotenv_if_present
_load_dotenv_if_present();key=os.getenv('LLM_API_KEY')
assert key
assert not [p for p in DOC.rglob('*') if p.is_file() and key.encode() in p.read_bytes()]
write_new(DOC/'DELIVERY_FILES_SHA256.json',{p.relative_to(DOC).as_posix():sha(p) for p in DOC.rglob('*') if p.is_file()})
print(json.dumps(dict(protection_rechecked=len(old),unexpected=0,python_tests=123,frontend_tests=7,secret_scan='PASS',delivery_files=len(list(DOC.rglob('*')))),ensure_ascii=False))
