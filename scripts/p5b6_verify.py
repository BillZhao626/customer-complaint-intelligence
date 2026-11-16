"""Verify P5-B6 against its own opening SHA inventory, without any asset write."""
import argparse
import json
import os
import sys
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
ALLOWED={'HANDOFF.md','web-client/src/p5b5.tsx','src/app/p5b5r2_api.py'}


def verify():
    baseline=json.loads((ROOT/'.local/p5b6/baseline.json').read_text(encoding='utf-8'))
    changed=[];missing=[]
    for rel,expected in baseline['files'].items():
        p=ROOT/rel
        if not p.is_file():missing.append(rel);continue
        observed=sha256(p.read_bytes()).hexdigest()
        if observed!=expected:changed.append(dict(path=rel,before=expected,after=observed,allowed=rel in ALLOWED))
    unexpected=[c for c in changed if not c['allowed']]
    from src.application.research_insights import ResearchInsights
    from src.evaluation.classification_research import build_report
    c=ResearchInsights(ROOT);r=build_report(ROOT,c)
    assert r['reports'][0]['fields']['sentiment']['correct']==78
    assert sum(m['correct'] for m in r['reports'][0]['fields'].values())==494
    assert len(c.records['r2-R3'])==18 and r['overlap']['n']==0 and not r['overlap']['hash_matches']
    assert json.loads((ROOT/'docs/p5b5r2/grader-v4/RESULTS.json').read_text(encoding='utf-8'))['champion']=='B2'
    import sqlite3
    from contextlib import closing
    budget_path=ROOT/'.local/p5b5r2/budget.sqlite3'
    with closing(sqlite3.connect(budget_path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        calls=db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
        halted=db.execute('SELECT halted FROM policy').fetchone()[0]
        assert calls==141 and halted=='R2_EXPERIMENT_COMPLETED'
    return dict(status='PASS' if not missing and not unexpected else 'FAILED',original_files=len(baseline['files']),
        unchanged=len(baseline['files'])-len(missing)-len(changed),changed=changed,missing=missing,unexpected=unexpected,
        env_unchanged=not any(c['path']=='.env' for c in changed) and '.env' not in missing,
        source_count=len(c.sources),new_paid_calls=0,old_ledger_calls=calls,old_ledger_halted=halted,champion='B2',r3_promotion='NOT_PROMOTED',
        scope='All files existing at task opening outside .git/.venv/node_modules/__pycache__; historical assets including .local/ compared byte-for-byte. New derived workspace excluded by time of creation.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out');a=p.parse_args();r=verify()
    if a.out:
        with Path(a.out).open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
    print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(r['status']!='PASS')
