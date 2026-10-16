"""Only offline preparation/rehearsal for the acceptance-change decision package."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p,value):
    with Path(p).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','rehearse','preflight']);p.add_argument('--out',type=Path)
    p.add_argument('--prepared',default='prepared-v2',choices=['prepared-v2','prepared-v3'])
    args=p.parse_args()
    from scripts.p38 import guard
    guard()
    research=ROOT/'.local/p39/v2'
    def protect(event,a):
        if event=='open':
            path,mode,flags=a
            if isinstance(path,(str,bytes,os.PathLike)) and ((mode and any(c in mode for c in 'wax+')) or isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                f=Path(os.fsdecode(path)).resolve()
                if f.is_relative_to(ROOT/'.local/p39') and not f.is_relative_to(research):raise PermissionError('All prior P3.9 assets are immutable')
    sys.addaudithook(protect)
    from src.domain.contracts import EmailInput,digest
    from src.application.p39_v2 import manifest,system,messages,source_hash,ContextOfflineService
    prepared=research/args.prepared
    if args.action=='prepare':
        parent=load(ROOT/'.local/p39/prepared-v1/manifest.json');old_auth=load(ROOT/'.local/p39/prepared-v1/authorization.json')
        from src.application.p39_experiment import preflight as old_preflight,TokenCounter
        old_preflight(parent,old_auth)
        evidence=(research/'user-request-v2.txt').read_text(encoding='utf8');evidence_hash=sha256(evidence.encode('utf8')).hexdigest()
        m=manifest(parent,evidence_hash)
        m.pop('manifest_hash');m['artifact_revision']=args.prepared;m['manifest_hash']=digest(m)
        price=load(ROOT/'.local/p39/price-model-receipt-v1.json')
        sys.path.insert(0,str(ROOT/'.local/p39/deps'))
        counter=TokenCounter(ROOT/'.local/p39/tokenizer-v4',price['tokenizer_sha256'],price['tokenizer_config_sha256'])
        bounds=[]
        for step in m['schedule']:
            e=EmailInput.model_validate(m['inputs'][step['input_index']]['email']);b=counter.measure(messages(e,step['arm']))
            if b['payload_bytes']>50000:raise ValueError('Payload cap exceeded')
            b.update(pair=step['pair'],arm=step['arm'],reserve_cny=(b['input_token_reserve']*price['prices']['input_cny_per_million']+4000*price['prices']['output_cny_per_million'])/1e6)
            bounds.append(b)
        from tests.test_urgency_context import CASES,fixture
        from src.domain.analysis_v31 import AnalysisV31
        from src.domain.analysis_v31_context import ContextAnalysisV31
        comparisons=[]
        for name,body,u,basis,risk in CASES:
            e,d=fixture(body,u,basis,risk);states={}
            for key,model in [('legacy',AnalysisV31),('candidate',ContextAnalysisV31)]:
                try:model.model_validate(d).validate_input(e);states[key]=dict(accepted=True,error=None)
                except ValueError as ex:states[key]=dict(accepted=False,error=str(ex).splitlines()[0])
            comparisons.append(dict(case=name,email=e.model_dump(),raw_fixture=d,**states,acceptance_changed=states['legacy']['accepted']!=states['candidate']['accepted']))
        prior=load(ROOT/'.local/p39/runtime-v1/stop-receipt-v1.json')
        check=dict(manifest_hash=m['manifest_hash'],schema_hash_unchanged=m['schema_hash']==parent['schema_hash'],acceptance_semantics_changed=True,
            comparison_approval_required=True,paid_dispatch_allowed=False,new_provider_calls=0,prior_calls=1,new_plan=64,combined_plan=65,
            max_payload_bytes=max(b['payload_bytes'] for b in bounds),new64_reserve_cny=sum(b['reserve_cny'] for b in bounds),
            combined_reserve_cny=prior['budget']['reserved_upper_cny']+sum(b['reserve_cny'] for b in bounds),
            price_receipt_checked_at=price['checked_at'],official_prices=price['prices'],price_receipt_hash=digest(price),payload_bounds=bounds,
            differing_fixture_cases=[r['case'] for r in comparisons if r['acceptance_changed']],fixture_count=len(comparisons))
        if check['combined_reserve_cny']>10:raise ValueError('Shared budget exceeds10')
        prepared.mkdir(exist_ok=False)
        for name,value in [('manifest.json',m),('preflight.json',check),('validation-differences.json',comparisons)]:write(prepared/name,value)
        for arm in ('A','B'):
            with (prepared/f'prompt-{arm}.txt').open('x',encoding='utf8',newline='\n') as f:f.write(system(arm))
        request=dict(user_evidence=evidence,user_evidence_sha256=evidence_hash,combined_planned_requests=65,explicit_extra_allowance=1,
            status='CONDITIONAL_SCOPE_APPROVED_COMPARISON_CHANGE_REVIEW_REQUIRED',comparison_approval=None)
        write(prepared/'continuation-evidence.json',request)
        from src.infrastructure.p39_envelope import P39Envelope
        envelope=research/'shared-envelope.sqlite3'
        if envelope.exists():
            ledger=P39Envelope(envelope);ledger.register_candidate(m,request)
        else:ledger=P39Envelope.create(envelope,ROOT/'.local/p39/runtime-v1/budget.sqlite3',m,request)
        write(prepared/'envelope-preflight.json',ledger.summary())
        print(json.dumps({k:v for k,v in check.items() if k!='payload_bounds'},ensure_ascii=False))
    else:
        m=load(prepared/'manifest.json')
        if m['processing_chain_hash']!=source_hash():raise ValueError('Candidate source drift')
        if args.action=='preflight':
            print(json.dumps(dict(manifest_hash=m['manifest_hash'],schema_unchanged=True,comparison_approval_required=True,paid_dispatch_allowed=False),ensure_ascii=False));return
        from src.application.v31_demo import ReplayV31,pipeline_probe
        from src.infrastructure.context_repository import ContextRepository,ReadOnlyContextRepository
        from src.domain.analysis_v31_context import stored_context_analysis
        args.out.mkdir(parents=True,exist_ok=False)
        emails=[EmailInput.model_validate(r['email']) for r in m['inputs']]
        outputs={e.input_hash:pipeline_probe(e).model_dump() for e in emails}
        analyzers={}
        for arm in ('A','B'):
            a=ReplayV31(outputs,dataset_id='p39-v2-explicit-offline-placeholder',dataset_hash=m['inputs_hash'],arm=arm)
            a.config=a.config.model_copy(update={'prompt_hash':m['configs'][arm]['prompt_hash'],'parameters':dict(a.config.parameters,
                urgency_validation_profile=m['urgency_validation_profile'],processing_chain_hash=m['processing_chain_hash'])})
            analyzers[arm]=a
        path=args.out/'runs.sqlite3';repo=ContextRepository(path);bindings=[]
        for step in m['schedule']:
            e=emails[step['input_index']];s=ContextOfflineService(repo,analyzers[step['arm']]);r=s.analyze(e)
            if r.status!='succeeded':raise ValueError('Offline fixture rejected: '+e.email_id)
            reloaded=ReadOnlyContextRepository(path).get(r.run_id);stored_context_analysis(reloaded)
            if reloaded.model_dump()!=r.model_dump() or s.analyze(e).run_id!=r.run_id:raise ValueError('Reload/idempotency mismatch')
            bindings.append(dict(run_id=r.run_id,arm=step['arm'],input_hash=e.input_hash,output_hash=r.metadata['analysis_v31_hash']))
        result=dict(kind='OFFLINE_EXPLICIT_PLACEHOLDER_NOT_MODEL_QUALITY',manifest_hash=m['manifest_hash'],steps=len(bindings),new_provider_calls=0,
                    new_cost_cny=0,semantic_accuracy=None,wire_schema_version='analysis-v3.1',sqlite_version=2,bindings=bindings)
        write(args.out/'rehearsal.json',result);print(json.dumps({k:v for k,v in result.items() if k!='bindings'},ensure_ascii=False))


if __name__=='__main__':main()
