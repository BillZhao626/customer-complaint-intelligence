"""Read-only historical audit and a new immutable R11 baseline. No API calls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/r11-quality-20261109-v1'
DOCS = ROOT / 'docs/r11-quality-20261109-v1'

def read(p):
    return json.loads(Path(p).read_text('utf8'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        assert read(p) == value, str(p)
    else:
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')
    return value

def main():
    if (LOCAL/'baseline.json').exists():
        print('Baseline already frozen'); return
    sources = {}
    for folder in ('src', 'scripts', 'tests', 'configs', 'web-client/src'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                rel=p.relative_to(ROOT).as_posix()
                sources[rel]=sha(p)
                target=LOCAL/'baseline-source'/rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p,target)
    protected={}
    for folder in ('data/raw','data/synthetic','data/golden','outputs','docs/r10-quality-20261109-v1',
                   '.local/r7-20261106-v1','.local/r8-quality-20261109-v1','.local/r9-quality-20261109-v1',
                   '.local/r10-quality-20261109-v1','docs/r8-owner-cal-20261109-v1'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                protected[p.relative_to(ROOT).as_posix()]=sha(p)
    status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    save(LOCAL/'baseline.json',dict(head=head,git_status=status,sources=sources,protected=protected))
    old=ROOT/'.local/r10-quality-20261109-v1'
    freezes={}
    for name in ('fixed-v3','diagnostic-v4'):
        path=old/'freezes'/f'{name}.json'
        if path.exists(): freezes[name]=dict(sha256=sha(path),manifest=read(path))
    save(LOCAL/'historical-freezes.json',freezes)
    env={}
    for line in (ROOT/'.env').read_text('utf8').splitlines():
        if '=' in line:
            k,v=line.split('=',1)
            if k in ('LLM_ENABLE_API','LLM_MODEL','LLM_BASE_URL','DEEPSEEK_MODEL','COMPLAINT_ENABLE_LIVE'):
                env[k]=v
    save(LOCAL/'environment-safe.json',dict(settings=env,env_hash=sha(ROOT/'.env'),secret_values_recorded=False))
    print(json.dumps(dict(head=head,source_files=len(sources),protected_files=len(protected),safe_environment=env)))

if __name__=='__main__': main()
