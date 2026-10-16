"""P3.9 offline preparation/reporting and explicitly authorized gated dispatch."""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p,data):
    with Path(p).open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','preflight','live','evaluate'])
    p.add_argument('--root',type=Path,default=ROOT/'.local/p39');p.add_argument('--out',type=Path)
    p.add_argument('--phase',choices=['smoke','remaining'],default='smoke');p.add_argument('--smoke-review',type=Path)
    args=p.parse_args();root=args.root.resolve()
    if args.action!='live':
        from scripts.p38 import guard
        guard()
    # Tokenizer is local research tooling, not a project/runtime dependency change.
    sys.path.insert(0,str(root/'deps'))
    from src.application.p39_experiment import build_manifest,preflight,TokenCounter,messages,run_live,system
    from src.domain.contracts import EmailInput,digest
    price=load(root/'price-model-receipt-v1.json')
    counter=TokenCounter(root/'tokenizer-v4',price['tokenizer_sha256'],price['tokenizer_config_sha256'])
    prepared=root/'prepared-v1'
    if args.action=='prepare':
        archive=load(root/'content-adjudication-v1/snapshot.json')
        body=dict(archive);claim=body.pop('archive_hash');assert digest(body)==claim
        parent=load(ROOT/'.local/p38/prepared-final-v4/ab-manifest.json')
        manifest=build_manifest(parent,claim,price['tokenizer_sha256'],price['tokenizer_config_sha256'])
        evidence=(root/'user-request-v1.txt').read_text(encoding='utf8')
        auth=dict(status='researcher_explicitly_authorized',researcher='project owner, current user request',
                  authorization_evidence=evidence,authorization_evidence_sha256=sha256(evidence.encode('utf8')).hexdigest(),
                  experiment_hash=manifest['manifest_hash'],requests=72,cny=10,planned_requests=64,
                  retest_reserve=8,retest_dispatch='explicit separate recorded approval only',
                  prices_verified_at=price['checked_at'],price_source=price['price_source'],model=price['model'],
                  model_availability_verified=price['model_availability_verified'],prices=price['prices'],
                  official_receipt_hash=digest(price),smoke_content_approval=None)
        check=preflight(manifest,auth)
        bounds=[]
        for step in manifest['schedule']:
            email=EmailInput.model_validate(manifest['inputs'][step['input_index']]['email'])
            bound=counter.measure(messages(email,step['arm']))
            bound.update(pair=step['pair'],arm=step['arm'],sample_id=email.email_id,phase=step['phase'])
            bound['reserved_upper_cny']=(bound['input_token_reserve']*price['prices']['input_cny_per_million']+4000*price['prices']['output_cny_per_million'])/1e6
            bounds.append(bound)
        from dotenv import dotenv_values
        env=dotenv_values(ROOT/'.env')
        check.update(payload_bounds=bounds,planned_64_reserve_cny=sum(x['reserved_upper_cny'] for x in bounds),
                     smoke_8_reserve_cny=sum(x['reserved_upper_cny'] for x in bounds[:8]),
                     maximum_72_reserve_estimate_cny=72*max(x['reserved_upper_cny'] for x in bounds),
                     env_inspection=dict(llm_enable_api=env.get('LLM_ENABLE_API'),api_key_present=bool(env.get('LLM_API_KEY')),
                                         env_sha256=sha256((ROOT/'.env').read_bytes()).hexdigest()),
                     pipeline='AnalysisService → original live_execution → P39Analyzer/DeepSeek LangChain → original validate/gate/projection → SQLite → read-only reload',
                     authorization_hash=digest(auth),content_archive_hash=claim,new_inference_requests=0)
        if check['maximum_72_reserve_estimate_cny']>10:raise ValueError('Conservative plan exceeds budget')
        prepared.mkdir(exist_ok=False)
        write(prepared/'manifest.json',manifest);write(prepared/'authorization.json',auth);write(prepared/'preflight.json',check)
        for arm in ('A','B'):
            with (prepared/f'prompt-{arm}.txt').open('x',encoding='utf8',newline='\n') as f:f.write(system(arm))
        print(json.dumps({k:v for k,v in check.items() if k!='payload_bounds'},ensure_ascii=False));return
    manifest=load(prepared/'manifest.json');auth=load(prepared/'authorization.json');preflight(manifest,auth)
    if (auth['official_receipt_hash']!=digest(price) or auth['prices']!=price['prices']
            or manifest['tokenizer_sha256']!=price['tokenizer_sha256']
            or manifest['tokenizer_config_sha256']!=price['tokenizer_config_sha256']):
        raise ValueError('Price/tokenizer receipt drift')
    if args.action=='preflight':print(json.dumps(preflight(manifest,auth),ensure_ascii=False))
    elif args.action=='live':
        # User authorization already frozen and verified; enable only this isolated process.
        os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
        result=run_live(manifest,auth,args.out,counter,args.phase,load(args.smoke_review) if args.smoke_review else None)
        print(json.dumps(result,ensure_ascii=False))
    else:
        from src.evaluation.p39_report import export_report
        result=export_report(manifest,args.out,root/'content-adjudication-v1/snapshot.json')
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
