"""P3.10 offline preparation. Paid allowance requires a separate explicit receipt."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def write_new(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit');a.add_argument('--out',required=True)
    a=sub.add_parser('prepare-development');a.add_argument('--out',required=True)
    a=sub.add_parser('preflight');a.add_argument('--plan',required=True)
    a=sub.add_parser('create-budget');a.add_argument('--authorization',required=True)
    a=sub.add_parser('run');a.add_argument('--plan',required=True);a.add_argument('--engineering-receipt',default=str(ROOT/'.local/p310/engineering-acceptance.json'))
    args=p.parse_args()
    if args.command=='audit':
        from src.evaluation.p310_audit import build,export
        report=json.loads((ROOT/'.local/p39/r3/fixed-report-delivery/paired-evaluation.json').read_text(encoding='utf8'))
        notes=json.loads((ROOT/'.local/p310/reading-notes.json').read_text(encoding='utf8'))
        summary=export(build(report,notes),args.out);print(json.dumps(summary,ensure_ascii=False,indent=2))
    elif args.command=='prepare-development':
        from src.application.p310_experiment import make_plan,p310_prompt
        report=json.loads((ROOT/'.local/p39/r3/runtime-identity.json').read_text(encoding='utf8'))
        plan=make_plan(report['candidate']['inputs'])
        out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
        write_new(out/'plan.json',plan)
        write_new(out/'candidate.json',p310_prompt.identity())
        (out/'system.txt').write_text(p310_prompt.system(),encoding='utf8')
        write_new(out/'capabilities.json',p310_prompt.CAPABILITIES)
        paths=plan['source_identity']['files']
        for path in paths:
            target=out/'source'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/path).read_bytes())
        print(json.dumps(dict(plan_hash=plan['plan_hash'],candidate=p310_prompt.identity(),requests_planned=len(plan['schedule']),paid_dispatch=False),ensure_ascii=False,indent=2))
    elif args.command=='preflight':
        from src.application.p310_experiment import verify_plan,ByteCounter,messages_for
        from src.domain.contracts import EmailInput
        plan=json.loads(Path(args.plan).read_text(encoding='utf8'));verify_plan(plan)
        bounds=[ByteCounter().measure(messages_for(EmailInput.model_validate(plan['inputs'][s['input_index']]['email']),s['arm'],plan['inputs'][s['input_index']].get('repair_context'))) for s in plan['schedule']]
        if max(b['payload_bytes'] for b in bounds)>50000:raise ValueError('Payload cap exceeded')
        print(json.dumps(dict(plan_hash=plan['plan_hash'],offline_preflight=True,requests_planned=len(bounds),
            reserve_upper_cny=sum((b['input_token_reserve']*2+4000*8)/1e6 for b in bounds),max_payload_bytes=max(b['payload_bytes'] for b in bounds),paid_calls=0),indent=2))
    elif args.command=='create-budget':
        from src.infrastructure.p310_budget import ResearchBudget,CANONICAL
        auth=json.loads(Path(args.authorization).read_text(encoding='utf8'))
        print(json.dumps(ResearchBudget.create(CANONICAL,auth).summary(),indent=2))
    elif args.command=='run':
        # Existing independently authorized envelope only. No automatic allowance,
        # environment mutation, provider initialization before authorization check.
        from src.infrastructure.p310_budget import ResearchBudget,CANONICAL
        budget=ResearchBudget(CANONICAL);budget.verify_root()
        from src.application.p310_experiment import run_plan,source_identity
        from src.domain.contracts import digest
        acceptance=json.loads(Path(args.engineering_receipt).read_text(encoding='utf8'))
        body=dict(acceptance);claim=body.pop('receipt_hash')
        if digest(body)!=claim or acceptance['source_identity_hash']!=digest(source_identity()) or not acceptance['full_success'] or not acceptance['portable_success']:
            raise PermissionError('Current full/portable engineering acceptance required')
        from src.infrastructure.v3_live_settings import V3PilotSettings
        from dataclasses import replace
        plan=json.loads(Path(args.plan).read_text(encoding='utf8'))
        settings=replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000)
        print(json.dumps(run_plan(plan,budget,settings,ROOT/'.local/p310'/('runtime-'+plan['plan_hash'])),indent=2))


if __name__=='__main__':main()
