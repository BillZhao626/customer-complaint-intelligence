"""Unified offline verification; no provider, budget mutation, or report overwrite."""
import os,sys,json,subprocess
from pathlib import Path
from contextlib import closing
import sqlite3
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.evaluation.p5b5 import read,hashfile

def verify():
    from scripts.p5b5 import verify as evidence_verify
    evidence_verify(ROOT/'.local/p5b5/evidence-v1')
    local=ROOT/'.local/p5b5-live-20261030-v1';a=read(local/'authorization.json')
    for p,h in a['source_hashes'].items():assert hashfile(ROOT/p)==h,p
    for name in ('E3-amendment.json','E4-amendment.json','judge-v2-amendment.json'):
        amendment=read(local/name)
        if name=='E3-amendment.json':assert hashfile(ROOT/'scripts/p5b5_e3.py')==amendment['source_sha256']
        if name=='E4-amendment.json':
            for p,h in amendment['source_hashes'].items():assert hashfile(ROOT/p)==h,p
        if name=='judge-v2-amendment.json':assert hashfile(ROOT/'scripts/p5b5_judge_v2.py')==amendment['source_sha256']
    with closing(sqlite3.connect((local/'budget.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        n=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0];assert n==120
        assert c.execute('SELECT COUNT(*) FROM settlements').fetchone()[0]==n
        assert c.execute('SELECT halted FROM policy').fetchone()[0]
        assert c.execute('SELECT COUNT(*) FROM lease').fetchone()[0]==0
        assert c.execute('SELECT MAX(settled_and_pending_before+new_bound) FROM precalls').fetchone()[0]<=5
        assert c.execute('SELECT MAX(n_before) FROM precalls').fetchone()[0]==119
    runs=0;judges=0
    for arm in ('B2','E1','E2','E3','E4'):
        rows=read(local/arm/'results.json');assert len(rows)==18
        for row in rows:
            p=Path(row['run_path']);run=read(p);assert len(run['attempts'])==1
            attempt=run['attempts'][0];provider=read(p.parent/'provider-response.txt')
            assert provider['choices'][0]['message']['content']==attempt['raw_output']
            frozen=read(p.parent/'frozen-input.json');assert frozen['email']==run['email']
            assert frozen['reference_in_prompt'] is False
            assert attempt['metadata']['dispatch']=='response_received'
            runs+=1
    for p in (local/'judge').glob('*/judgment.json'):
        j=read(p);assert j['raw']==read(p.parent/'provider-response.txt')['choices'][0]['message']['content'];judges+=1
    assert runs==90 and judges==30
    baseline=read(ROOT/'.local/p5b5/initial.json')['files'];changed=[];missing=[]
    for p,h in baseline.items():
        source=ROOT/p
        if not source.exists():missing.append(p)
        elif hashfile(source)!=h:changed.append(p)
    assert not missing,missing
    assert set(changed)<={'HANDOFF.md'},changed
    assert (ROOT/'HANDOFF.md').read_bytes().endswith((ROOT/'.local/p5b5/recovery/HANDOFF.md').read_bytes())
    result=dict(status='P5B5_OFFLINE_ENGINEERING_VERIFIED_NOT_QUALITY_CERTIFIED',baseline_files=len(baseline),
        historical_missing=missing,historical_changed=changed,real_first_generations=runs,real_judge_calls=judges,
        total_calls=n,concurrency=1,retries=0,budget_halted=True,external_business_sends=0,human_numeric_labels=0,promoted=False)
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
    subprocess.run([sys.executable,'-B','tests/run_offline.py','test_p5b5.py'],cwd=ROOT,check=True)
    verify()
