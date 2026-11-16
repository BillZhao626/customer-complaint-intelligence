"""R2 blinded scoring orchestration; all calls share R2's guarded ledger."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b5r2_live import LOCAL,raw_judge
from src.evaluation.p5b5 import read,write_new
from src.evaluation.p5b5r2_judge import JUDGE_SYSTEM,JUDGE_SYSTEM_V31,controls,control_payload,payload_for_pair
from src.domain.contracts import digest

def run_controls():
    rows=controls()
    manifest=dict(controls=rows,system=JUDGE_SYSTEM,system_hash=digest(JUDGE_SYSTEM),control_hash=digest(rows),identity='DEVELOPER_POLICY_NOT_HUMAN_TRUTH')
    if (LOCAL/'judge-controls-freeze.json').exists():
        assert read(LOCAL/'judge-controls-freeze.json')==manifest
    else:write_new(LOCAL/'judge-controls-freeze.json',manifest)
    for row in rows:
        ev=LOCAL/'judge'/('control-'+row['id'])
        if ev.exists():
            if not (ev/'judgment.json').exists():raise ValueError('Incomplete control identity, cannot dispatch')
            continue
        raw_judge(control_payload(row),'control-'+row['id'],JUDGE_SYSTEM)

def pairs(arm):
    left=read(ROOT/'.local/p5b5-live-20261030-v1/B2/results.json');right=read(LOCAL/arm/'results.json')
    gold={g['case_id']:g for g in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    write_new(LOCAL/(arm+'-paired-freeze.json'),dict(arm=arm,n=18,repeat_cases=['CAL-03','CAL-05','CAL-07','CAL-15'],system_hash=digest(JUDGE_SYSTEM_V31),left='historical20261030-B2',identity='DEV_NOT_INDEPENDENT'))
    for i,(a,b) in enumerate(zip(left,right,strict=True)):
        assert (a['case_id'],a['turn'])==(b['case_id'],b['turn'])
        payload,order=payload_for_pair(gold[a['case_id']],a,b,reverse=bool(i%2))
        identity=f'{arm}-{a["case_id"]}-T{a["turn"]}'
        write_new(LOCAL/'judge-keys'/(identity+'.json'),dict(order=order,case_id=a['case_id'],turn=a['turn']))
        raw_judge(payload,identity,JUDGE_SYSTEM_V31)
        if a['case_id'] in ('CAL-03','CAL-05','CAL-07') or (a['case_id']=='CAL-15' and a['turn']==2):
            reverse,rev_order=payload_for_pair(gold[a['case_id']],a,b,reverse=not bool(i%2))
            write_new(LOCAL/'judge-keys'/(identity+'-reverse.json'),dict(order=rev_order,case_id=a['case_id'],turn=a['turn']))
            write_new(LOCAL/'judge-keys'/(identity+'-repeat.json'),dict(order=order,case_id=a['case_id'],turn=a['turn']))
            raw_judge(reverse,identity+'-reverse',JUDGE_SYSTEM_V31);raw_judge(payload,identity+'-repeat',JUDGE_SYSTEM_V31)

def rechecks():
    write_new(LOCAL/'judge-format-amendment.json',dict(semantic_change=False,format='review_findings structured objects only',old_system_hash=digest(JUDGE_SYSTEM),new_system_hash=digest(JUDGE_SYSTEM_V31),new_control_scores_never_replace_old=True))
    for row in controls():
        if row['id'] in ('wrong_action_receipt','danger_ride_en'):raw_judge(control_payload(row),'v31-control-'+row['id'],JUDGE_SYSTEM_V31)
    gold={g['case_id']:g for g in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    left=read(ROOT/'.local/p5b5-live-20261030-v1/B2/results.json');right=read(ROOT/'.local/p5b5-live-20261030-v1/E4/results.json')
    for case in ('CAL-03','CAL-05','CAL-07'):
        a=next(x for x in left if x['case_id']==case);b=next(x for x in right if x['case_id']==case)
        payload,order=payload_for_pair(gold[case],a,b)
        identity='HIST-'+case
        write_new(LOCAL/'judge-keys'/(identity+'.json'),dict(order=order,case_id=case,turn=1))
        raw_judge(payload,identity,JUDGE_SYSTEM_V31)

if __name__=='__main__':
    if sys.argv[1:]==['controls']:run_controls()
    elif sys.argv[1:]==['rechecks']:rechecks()
    elif len(sys.argv)==3 and sys.argv[1]=='pairs':pairs(sys.argv[2])
    else:raise SystemExit('controls | pairs ARM')
