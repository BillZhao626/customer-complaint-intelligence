"""Offline R6 repair verification/readiness. No live option or implicit authorization."""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
DOC=ROOT/'docs/p5b8r6/offline-fix-v1';LOCAL=ROOT/'.local/p5b8r6-offline-fix-v1'

def read(path):return json.loads(Path(path).read_text('utf8'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

ALIASES={'accessible_manual_after_positive_visit':'accessible-digital-instructions'}
def history_registry():
    from src.domain.contracts import EmailInput
    rows=[]
    for folder in ('.local/p5b7/dataset','.local/p5b8/new-dataset','.local/p5b8r3/quality-final-v1/dataset'):
        for p in sorted((ROOT/folder).glob('*.json')):
            d=read(p)
            if 'email' in d:
                e=EmailInput.model_validate(d['email']);family=d.get('spec',{}).get('family',d.get('family'))
            elif 'subject' in d and 'body' in d:
                e=EmailInput(email_id=p.stem,subject=d['subject'],body=d['body']);family=d.get('family')
            else:continue
            if not family:raise ValueError('Missing historical family: '+str(p))
            rows.append(dict(case_id=e.email_id,input_hash=e.input_hash,family=family,canonical_family=ALIASES.get(family,family),role='EXPOSED_HISTORY',source=p.relative_to(ROOT).as_posix(),source_sha256=sha(p)))
    for d in read(ROOT/'.local/p5b8r6-20261104/UNSEEN_DATASET.json'):
        rows.append(dict(case_id=d['email']['email_id'],input_hash=d['input_hash'],family=d['family'],canonical_family=ALIASES.get(d['family'],d['family']),role='EXPOSED_R6_EXPLORATORY_NOT_INDEPENDENT',source='.local/p5b8r6-20261104/UNSEEN_DATASET.json',source_sha256=sha(ROOT/'.local/p5b8r6-20261104/UNSEEN_DATASET.json')))
    return rows

def verify_offline():
    from src.domain.contracts import EmailInput
    from src.application import service_response as service
    from src.evaluation import p5b8r4_judge as judge
    fixtures=read(ROOT/'tests/fixtures/service_response_r6_regressions.json');results=[]
    with tempfile.TemporaryDirectory(prefix='r6_repair_') as t:
        for eid,f in fixtures.items():
            e=EmailInput.model_validate(f['email']);actions=service.plan_actions(f['analysis'],email=e)
            arms=[]
            for arm in ('DIRECT','GUIDED'):
                # Planning fake is explicitly the same final source plan here;
                # there is no new model analysis or composed reply in this step.
                rt=service.execute(e,service.reconcile_plan(e,actions),Path(t)/eid/arm/'actions.sqlite3')
                arms.append(dict(arm=arm,runtime=rt,service_brief=service.brief(e,rt,f['analysis'])))
            assert not {x['event_id'] for x in arms[0]['runtime']['events']}&{x['event_id'] for x in arms[1]['runtime']['events']}
            results.append(dict(case_id=eid,input_hash=e.input_hash,plan=actions,arms=arms,identity='OFFLINE_CURRENT_CODE_WITH_HISTORICAL_SYNTHETIC_ANALYSIS_NOT_NEW_REPLY'))
    write(DOC/'offline-chain-proof.json',results)
    screens=[]
    for p in sorted((ROOT/'.local/p5b8r6-20261104/traces').glob('*/*-reply.json')):
        r=read(p)
        if not r['slot']['parse_ok']:continue
        audit=judge.audit_slot(r['slot'],EmailInput.model_validate(r['email']))
        screens.append(dict(source=p.relative_to(ROOT).as_posix(),original_guard=r['guard'],current_rule_screen=audit,identity='SAME_TEXT_RULE_RESCREEN_NOT_NEW_GENERATION',old_scores_unchanged=True))
    write(DOC/'same-text-rescreen.json',screens)
    registry=history_registry();write(DOC/'history-registry.json',registry);write(DOC/'family-aliases.json',ALIASES)
    from src.evaluation.experiment_integrity import family_preflight,IntegrityError
    probe=dict(case_id='R6U-002-relabel-control',input_hash='0'*64,family='accessible_manual_after_positive_visit',family_review=dict(reviewed_against_full_registry=True))
    try:family_preflight([probe],registry,ALIASES)
    except IntegrityError as ex:leak=dict(status='REJECTED_BEFORE_DISPATCH',error=str(ex))
    else:raise AssertionError('Known R3/R6 family contamination was not blocked')
    write(DOC/'known-family-leak-rejection.json',leak)
    print('Offline chain proof:',len(results),'cases, independent fake arms; same-text screens:',len(screens),'history:',len(registry))

def prepare(version='v2'):
    from src.evaluation.experiment_integrity import freeze,verify
    verify_offline()
    inputs=[DOC/'history-registry.json',DOC/'family-aliases.json',ROOT/'tests/fixtures/service_response_r6_regressions.json']
    frozen=freeze(ROOT,inputs=inputs)
    if not re.fullmatch(r'v\d+',version):raise ValueError('Candidate version must be v followed by digits')
    target=LOCAL/('unified-ready-'+version);target.mkdir(exist_ok=True)
    # Archive source bytes for inspection. Requests still check the pinned
    # working root and loaded code immediately before each dispatch.
    for n,h in frozen['source_hashes'].items():
        p=target/'source'/n;p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists() and sha(p)!=h:raise ValueError('Previous readiness snapshot differs; create a new readiness version')
        if not p.exists():p.write_bytes((ROOT/n).read_bytes())
    manifest=target/'execution-integrity.json'
    if manifest.exists() and read(manifest)!=frozen:raise ValueError('Frozen readiness drift; never overwrite an old candidate snapshot')
    if not manifest.exists():write(manifest,frozen)
    proof=verify(frozen)
    plan=dict(status='OFFLINE_REPAIRS_VERIFIED_AWAITING_SEPARATE_LIVE_AUTHORIZATION',paid_requests_this_round=0,old_budget='R6 permanently closed; 120/120',candidate=service_identity(),execution_integrity_path=str(manifest),preflight_proof=proof,
              proposed_scope=dict(dev_families=6,dev_requests=24,fresh_synthetic_families=6,fresh_requests=24,judge_controls=15,paired_judgments_and_stability=20,total_provider_requests_proposed=83),
              authorization=dict(status='NOT_GRANTED',new_cny_cap=None,new_request_cap=None),
              independent_dataset=dict(status='NOT_CREATED',rules='Create only after candidate freeze; verify against pinned full history/aliases, exact input and family-review evidence before each dispatch; R6U-002 and all exposed R6 families are DEV now.'),
              acceptance=['Owner six-family core objective and both independent-arm receipts','First raw failures stay in denominator; one attempt, no automatic best retry','Water acknowledgement and nonrepeated bounded knowledge','No invented attachment viewing/payment obligations/external completion','Judge hard recall, normal false positives, qualitative directions, AB/BA and repeat separately','Immediate source/runtime/input integrity stop; final freeze verified before quality claims'],
              replay_policy='Historical replay is offline rule evidence only, not new model quality; do not overwrite R6 outputs or Gold.')
    write(DOC/'UNIFIED_E2E_READY.json',plan)
    print('Unified E2E ready; no Provider or budget constructed:',manifest)

def service_identity():
    from src.application.service_response import identity
    return identity()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['verify','prepare','check']);p.add_argument('--candidate-version',default='v2');args=p.parse_args()
    if args.action=='verify':verify_offline()
    elif args.action=='prepare':prepare(args.candidate_version)
    else:
        from src.evaluation.experiment_integrity import verify
        if not re.fullmatch(r'v\d+',args.candidate_version):raise ValueError('Invalid candidate version')
        print(verify(read(LOCAL/('unified-ready-'+args.candidate_version)/'execution-integrity.json')))
