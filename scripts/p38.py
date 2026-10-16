"""P3.8 preparation is offline; live needs a separate fresh researcher authorization."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,data):
    with Path(path).open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)


def guard():
    os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    def blocked(*a,**k):raise RuntimeError('P3.8 offline budget: 0 requests / 0 CNY')
    socket.socket.connect=socket.socket.connect_ex=socket.create_connection=blocked
    protected=[ROOT/p for p in ('data','outputs','.local/p36','.local/p37','.local/p35','.local/p3','.local/p2-pilot-v1')]
    def deny(raw):
        if isinstance(raw,(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(raw)).resolve()
            if any(path.is_relative_to(p.resolve()) for p in protected):raise PermissionError('Historical research assets are read-only')
    def audit(event,args):
        if event=='open':
            p,mode,flags=args
            if (mode and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):deny(p)
        elif event in ('os.remove','os.rmdir','os.rename','os.replace'):
            for p in args[:2]:deny(p)
        elif event=='os.mkdir':deny(args[0])
        elif event=='sqlite3.connect':
            from urllib.parse import urlsplit,parse_qs,unquote
            db=str(args[0])
            if db.startswith('file:'):
                if parse_qs(urlsplit(db).query).get('mode')==['ro']:return
                raise PermissionError('SQLite write URI forbidden in offline preparation')
            deny(db)
    sys.addaudithook(audit)


def prepare(out):
    from src.dataset.adoption_v3 import build,current_candidates,leakage_audit
    from src.evaluation.p37_replay import audit_p36
    from src.evaluation.semantic_review_v2 import build_review
    from src.evaluation.p38_ab import build_manifest,preflight,evaluate
    from src.application.research_policy_v2 import LEDGER,POLICY_HASH
    from src.application.v31_prompt import system
    dataset=build(load(ROOT/'.local/p35/dataset-candidate-v2/candidates.json'),load(ROOT/'.local/p37/dataset-review-v1/review32.json'),load(ROOT/'.local/p37/dataset-review-v1/revision-proposals.json'))
    frozen=[f for f in load(ROOT/'.local/p36/inputs-v1.json')['inputs'] if f['group']=='calibration24']
    lineage={r['sample_id']:r for r in load(ROOT/'.local/p35/calibration-decision-v1.1/snapshot.json')['records']}
    historical,groups=audit_p36(ROOT/'.local/p36')
    parents={p['run_id']:p for p in load(ROOT/'.local/p37/review-v1/semantic-review24.json')}
    reviews=[build_review(r,parents[r.run_id]) for r in groups['draft-v3'] if r.run_id in parents]
    manifest=build_manifest(dataset,frozen);check=preflight(manifest)
    out=Path(out).resolve()
    if out.is_relative_to(ROOT/'.local/p36') or any(out.is_relative_to(ROOT/p) for p in ('data','outputs','.local/p35','.local/p37')):
        raise ValueError('Output must be a new P3.8 directory')
    out.mkdir(parents=True,exist_ok=False)
    for name,data in [('policy-v2.json',dict(LEDGER,policy_hash=POLICY_HASH)),('dataset-v3.json',dataset),
        ('natural-candidates-v3.json',current_candidates(dataset)),('receipts32.json',dataset['receipts']),
        ('leakage-audit.json',leakage_audit(dataset,frozen,lineage)),('historical-audit.json',historical),
        ('semantic-review-v2.json',reviews),('ab-manifest.json',manifest),('ab-whitelist.json',[dict(email_id=r['email']['email_id'],input_hash=r['input_hash'],group=r['group']) for r in manifest['inputs']]),
        ('ab-preflight.json',check),('old-reference-v1.1.json',{f['email']['email_id']:f for f in frozen}),
        ('paired-evaluation-pending.json',evaluate(manifest,[],{f['email']['email_id']:f for f in frozen}))]:write(out/name,data)
    for a in ('A','B'):
        with (out/f'prompt-{a}.txt').open('x',encoding='utf8',newline='\n') as f:f.write(system(a))
    return dict(counts=dataset['counts'],historical_requests=historical['runs'],reviews=len(reviews),ab=check)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','preflight','evaluate','live','demo','rehearse'])
    p.add_argument('--out',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--authorization',type=Path)
    p.add_argument('--runtime',type=Path);p.add_argument('--references',type=Path);p.add_argument('--phase',choices=['smoke','remaining'],default='smoke')
    p.add_argument('--smoke-review',type=Path)
    args=p.parse_args()
    if args.action=='live':
        # Missing/zero authorization rejected before environment/network/database initialization.
        from src.application.p38_execution import run_live
        result=run_live(load(args.manifest),load(args.authorization) if args.authorization else None,args.out,args.phase,
            load(args.smoke_review) if args.smoke_review else None)
    else:
        guard()
        if args.action=='prepare':result=prepare(args.out)
        elif args.action=='preflight':
            from src.evaluation.p38_ab import preflight
            result=preflight(load(args.manifest))
        elif args.action=='evaluate':
            from src.evaluation.p38_ab import evaluate
            from src.infrastructure.dashboard_sources import ReadOnlyRepository
            runs=ReadOnlyRepository(args.runtime/'runs.sqlite3').list_runs() if args.runtime else []
            result=evaluate(load(args.manifest),runs,load(args.references) if args.references else None)
            write(args.out,result)
        elif args.action=='rehearse':
            from src.evaluation.p38_ab import preflight
            from src.application.v31_demo import pipeline_probe,ReplayV31
            from src.application.analysis_service import AnalysisService
            from src.infrastructure.repository import Repository
            from src.application.v3_statistics import snapshot
            from src.domain.contracts import EmailInput
            manifest=load(args.manifest);preflight(manifest)
            args.out.mkdir(parents=True,exist_ok=False)
            emails=[EmailInput.model_validate(r['email']) for r in manifest['inputs']]
            outputs={e.input_hash:pipeline_probe(e).model_dump() for e in emails}
            analyzers={a:ReplayV31(outputs,dataset_id='p38-offline-ab-rehearsal',dataset_hash=manifest['inputs_hash'],arm=a) for a in ('A','B')}
            repo=Repository(args.out/'runs.sqlite3');groups={a:[] for a in ('A','B')}
            for step in manifest['schedule']:
                a=step['arm'];r=AnalysisService(repo,analyzers[a]).analyze(emails[step['input_index']]);groups[a].append(r)
                write(args.out/f'run-{r.run_id}.json',r.model_dump())
            result=dict(kind='OFFLINE_FAKE_REHEARSAL_NOT_REAL_AB',manifest_hash=manifest['manifest_hash'],new_provider_requests=0,new_cost_cny=0,
                semantic_accuracy=None,warning='One unknown placeholder per input; no semantic quality claim.',
                arms={a:snapshot(groups[a],analyzers[a].config.cohort_id,'p38-offline-ab-rehearsal') for a in ('A','B')})
            write(args.out/'rehearsal.json',result)
        else:
            from src.application.v31_demo import EMAIL,fixture,ReplayV31
            from src.application.analysis_service import AnalysisService
            from src.infrastructure.repository import Repository
            from src.application.v3_statistics import snapshot
            args.out.mkdir(parents=True,exist_ok=False)
            a=ReplayV31({EMAIL.input_hash:fixture().model_dump()})
            r=AnalysisService(Repository(args.out/'runs.sqlite3'),a).analyze(EMAIL)
            result=snapshot([r],r.cohort_id,a.config.parameters['dataset_id']);write(args.out/'statistics.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
