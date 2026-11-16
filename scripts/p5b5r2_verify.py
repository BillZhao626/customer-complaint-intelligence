"""Read-only R2 delivery verification: no paid dispatch or historical DB writes."""
from pathlib import Path
import csv
import json
import os
import socket
import sqlite3
from contextlib import closing
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.evaluation.p5b5 import read,hashfile

def verify(asset_report=None):
    doc=ROOT/'docs/p5b5r2';local=ROOT/'.local/p5b5r2'
    path=next((doc/p for p in ('grader-v4/RESULTS.json','grader-v3/RESULTS.json','RESULTS.json') if (doc/p).is_file()))
    result=read(path);budget=result['budget']
    with closing(sqlite3.connect((local/'budget.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        assert c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]==budget['calls']==141
        assert c.execute('SELECT halted FROM policy').fetchone()[0]=='R2_EXPERIMENT_COMPLETED'
        assert c.execute('SELECT COUNT(*) FROM lease').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM precalls WHERE n_before>=300 OR settled_and_pending_before+new_bound>10.000000001').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM reservations WHERE attempt_no<>1 OR completed<>1').fetchone()[0]==0
    assert budget['true_response_unknown']==0 and budget['cost_upper_cny']==2.231408
    assert budget['actual_bill']=='UNKNOWN' and result['promotion']=='NOT_PROMOTED' and result['champion']=='B2'
    previous_handoff=local/'resume-20261030/recovery/HANDOFF.md'
    assert (ROOT/'HANDOFF.md').read_bytes().endswith(previous_handoff.read_bytes())
    assert result['human_numeric_labels']==result['independent_human_gold']==0
    assert result['budget']['provider_wire_records']==result['budget']['provider_response_records']==141
    for arm in ('R1','R2','R3','UI','UI-FOLLOWUP','B2-SCENARIO','FINAL'):
        f=read(local/arm/'freeze.json')
        for rel,h in f['sources'].items():assert hashfile(local/arm/'source'/rel)==h,(arm,rel)
    for pair in result['pairs']:
        for arm,r in pair['runs'].items():
            assert hashfile(ROOT/r['run_ref']['path'])==r['run_ref']['sha256']
            assert r['semantic_pass'] is None
            assert r['first_attempt']['attempt_no']==1
            assert r['metadata']['dispatch']=='response_received'
    for key,h in read(doc/'HUMAN_REVIEW.json')['source_hashes'].items():
        target=ROOT/key if Path(key).parts[0]=='docs' else doc/key
        assert hashfile(target)==h,key
    pack=read(doc/'HUMAN_REVIEW.json')
    assert not pack['human_signed'] and not pack['prior_gold_needs_resigning']
    assert len({i['id'] for i in pack['items']})==len(pack['items'])
    assert all(i.get('decision') is None and i.get('comment')=='' for i in pack['items'])
    amendment=read(doc/'JUDGE_RULE_AMENDMENT.json')
    judge=read(doc/'JUDGE_REAL.json')
    assert len(judge['paired_judgments'])==18 and len(judge['scenario_judgments'])==10
    from scripts.p5b5r2_protect import audit
    assets=asset_report if asset_report is not None else audit()
    assert assets['status']=='PASS',assets['unexpected_changes']
    manifest=doc/'DELIVERY_MANIFEST.json'
    if manifest.exists():
        for rel,h in read(manifest)['files'].items():assert hashfile(ROOT/rel)==h,rel
    return dict(status='PASS',calls=141,cost_upper_cny=budget['cost_upper_cny'],live_dispatch='CLOSED',
                protected_original_files=assets['original_files'],historical_assets_unchanged=assets['historical_files_checked'],
                human_review_items=len(pack['items']),champion='B2',candidate='R3',promotion='NOT_PROMOTED',results=str(path.relative_to(ROOT)))

if __name__=='__main__':
    def blocked(*a,**k):raise RuntimeError('R2 verification forbids network')
    socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
    print(json.dumps(verify(),ensure_ascii=False))
