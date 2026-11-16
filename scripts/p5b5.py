"""Prepare P5B5 evidence once, or verify read-only. No paid entry point."""
import argparse
from pathlib import Path
import json
import os
import sys
import socket
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.evaluation.p5b5 import read,write_new,hashfile,policy_overlay,registry,calibration,blinded_pairs,input_audit,diagnose,VERSION

def prepare(package,out):
    package=Path(package);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    gold=policy_overlay(package);reg=registry(package,gold);cal=calibration(gold)
    write_new(out/'owner-policy-overlay.json',gold);write_new(out/'case-registry.json',reg)
    write_new(out/'calibration.json',cal);write_new(out/'input-audit.json',input_audit())
    config=read(ROOT/'.local/p5b4/experiment-config-v3.json');pairs,key=blinded_pairs(config)
    write_new(out/'blinded-pairs.json',pairs);write_new(out/'blinding-key-private.json',key)
    original=read(ROOT/'.local/p5b4/run-003/summary.json')
    rows=[]
    for c in config['cases']:
        owner=next((g for g in gold if g['case_id']==c['thread_id']),None)
        row=dict(case_id=c['case_id'],thread_id=c['thread_id'],input=c['current'],family=c['family_id'],
            gold=owner,reference_status='OWNER_DEV_GOLD' if owner else 'B4_CANDIDATE_PENDING',runs={})
        for arm in ('b2','b3'):
            p=ROOT/c[arm+'_path'];run=read(p);assert hashfile(p)==c[arm+'_sha256']
            raw=run['attempts'][0]['raw_output'];parsed=json.loads(raw)
            row['runs'][arm]=dict(run_id=run['run_id'],reply=parsed['suggested_reply'],raw=raw,path=str(p),
                input_hash=run['input_hash'],first_contract=run['status']=='succeeded',elapsed_ms=run['attempts'][0].get('elapsed_ms'),
                usage=run['attempts'][0].get('metadata',{}),config=run['config'],
                diagnostic=diagnose(parsed['suggested_reply'],required_points=owner['required_points'] if owner else []))
        rows.append(row)
    for arm in ('b2','b3'):
        old=read(ROOT/'.local/p5b4/run-003'/('b2-revised.json' if arm=='b2' else 'best.json'))
        for row in rows:
            trace=next(x for x in old if x['case_id']==row['case_id'])
            row['runs'][arm]['historical_guard']=trace
    source_files=['src/evaluation/p5b5.py','src/application/p5b2_prompt.py','src/domain/analysis_v32.py',
        'src/application/p5b3_actions.py','src/application/analysis_service.py','src/infrastructure/deepseek.py']
    manifest=dict(version='p5b5-evidence-1',package=str(package),package_files={str(p.relative_to(package)):hashfile(p) for p in package.rglob('*') if p.is_file()},
        source_hashes={p:hashfile(ROOT/p) for p in source_files},dataset_hash=config['dataset_hash'],grader=VERSION,
        mode='HISTORICAL_RAW_PLUS_OWNER_OVERLAY_NOT_NEW_GENERATION',live_dispatch='LIVE_DISPATCH_DISABLED',
        budget=dict(authorized_cny=0,max_requests=0,actual_requests=0,spent_cny=0),champion='B2',promotion='NOT_PROMOTED')
    write_new(out/'manifest.json',manifest)
    write_new(out/'view-data.json',dict(manifest=manifest,counts=reg['counts'],calibration=cal,cases=rows,
        historical_metrics=dict(b2=original['b2_revised'],b3=original['candidate_full']),new_experiments=[],
        live_status='NOT_RUN_NO_NEW_BUDGET',human_status='NO_NUMERICAL_HUMAN_LABELS'))
    print(json.dumps(dict(counts=reg['counts'],controls=cal['new_controls'],output=str(out)),ensure_ascii=False))

def verify(out):
    out=Path(out);m=read(out/'manifest.json');g=read(out/'owner-policy-overlay.json');r=read(out/'case-registry.json')
    assert len(g)==16 and len(r['b4_reconciliation'])==28
    for rel,h in m['package_files'].items():assert hashfile(Path(m['package'])/rel)==h
    for rel,h in m['source_hashes'].items():assert hashfile(ROOT/rel)==h
    assert json.dumps(calibration(g),sort_keys=True)==json.dumps(read(out/'calibration.json'),sort_keys=True)
    assert m['budget']['actual_requests']==m['budget']['spent_cny']==0
    assert r['counts']['classification_i4']==80 and r['counts']['classification_p35']==24
    assert all(c['status']=='PENDING_HUMAN' for c in r['b4_reconciliation'])
    print('PASS: 16 Gold provenance, 28 pending, 24/80 classification, controls, immutable hashes, no live dispatch')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','verify']);p.add_argument('--package');p.add_argument('--out',default=str(ROOT/'.local/p5b5/evidence-v1'));a=p.parse_args()
    def blocked(*args,**kwargs):raise RuntimeError('P5B5 offline: external network forbidden')
    socket.socket.connect=blocked;socket.create_connection=blocked
    if a.action=='prepare':prepare(a.package,a.out)
    else:verify(a.out)
