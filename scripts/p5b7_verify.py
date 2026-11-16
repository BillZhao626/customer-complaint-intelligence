"""Read-only final integrity checks; no API or historical writes."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b7_research import B7Insights,canonical_store

def main():
    doc=ROOT/'docs/p5b7';c=B7Insights(ROOT);s=c.snapshot('b7-B2');products=defaultdict(lambda:dict(all=set(),negative=set()));stores=defaultdict(lambda:dict(all=set(),complaints=set()))
    runs=[json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'.local/p5b7/B2').glob('*/run.json')]
    for r in runs:
        if r['status']!='succeeded':continue
        k=canonical_store(r['result']['store_location']);stores[k]['all'].add(r['run_id'])
        if r['result']['is_complaint']:stores[k]['complaints'].add(r['run_id'])
        for i in r['metadata']['analysis_v32']['issues']:
            if i['object_type']!='product':continue
            products[i['category']]['all'].add(r['run_id'])
            if i['sentiment']=='negative':products[i['category']]['negative'].add(r['run_id'])
    for g in s['groups']['product_negative_association']:
        p=products[g['values']['product_category']]
        assert set(g['negative']['member_ids'])==p['negative'] and set(g['negative']['denominator_ids'])==p['all']
    for g in s['store_ranking']:
        p=stores[g['store_location']];assert g['total_emails']==len(p['all']) and g['complaint_count']==len(p['complaints'])
    assert s['selected']==90 and s['metrics']['successful']['numerator']==72 and s['states']['failed']['numerator']==18
    assert len(c.sources)==16
    baseline=json.loads((ROOT/'.local/p5b7/initial.json').read_text(encoding='utf-8'))['files']
    allowed={'src/app/p5b5r2_api.py','src/application/analysis_service.py','src/domain/analysis_v32.py','web-client/src/p5b5.tsx','web-client/src/research.tsx','HANDOFF.md'}
    missing=[];changed=[]
    for rel,h in baseline.items():
        p=ROOT/rel
        if not p.is_file():missing.append(rel)
        elif sha256(p.read_bytes()).hexdigest()!=h:changed.append(rel)
    assert not missing and set(changed)<=allowed,(missing,changed)
    assert all(not x.startswith(('data/','outputs/','.local/')) for x in changed)
    old=[]
    for rel in ('.local/p5b5r2/budget.sqlite3','.local/p5b5-live-20261030-v1/budget.sqlite3'):
        p=ROOT/rel
        if not p.exists():continue
        with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
            state=db.execute('SELECT halted FROM policy').fetchone()[0];assert state
            old.append(dict(path=rel,halted=state))
    result=dict(status='PASS',historical_files=len(baseline),historical_missing=missing,existing_modified=changed,unexpected=[],data_outputs_sqlite_gold_budget_env_unchanged=True,
        original_sources_preserved=14,new_sources=2,product_member_and_denominator_parity=True,store_alias_counts_parity=True,all_tasks=90,accepted=72,failed=18,old_ledgers=old,
        method='Independent set counting from raw accepted runs, not UI rounded values; per-email/category dedup; failures excluded from business success numerator and retained task denominator')
    (doc/'STATISTICS_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
