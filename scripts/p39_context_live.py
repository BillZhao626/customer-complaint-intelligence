"""Explicit approved smoke entry. No remaining-phase or approval synthesis."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','smoke'])
    args=parser.parse_args()
    from src.application.p39_context_live import build_runtime,verify_runtime,run_smoke,write_new
    from src.application.p39_experiment import TokenCounter
    from src.infrastructure.p39_live_context import ContextLiveBudget
    base=ROOT/'.local/p39/v2/live-delivery-v1'
    load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    price=load(base/'price-model-receipt.json')
    sys.path.insert(0,str(ROOT/'.local/p39/deps'))
    counter=TokenCounter(ROOT/'.local/p39/tokenizer-v4',price['tokenizer_sha256'],price['tokenizer_config_sha256'])
    runtime=build_runtime(load(ROOT/'.local/p39/v2/prepared-v3/manifest.json'),load(base/'comparison-approval.json'),price,base/'runtime',counter)
    target=base/'runtime-identity.json'
    if target.exists():
        if load(target)!=runtime:raise ValueError('Prepared live identity drift')
    elif args.action=='preflight':write_new(target,runtime)
    else:raise PermissionError('Persist offline preflight identity first')
    verify_runtime(runtime)
    budget=ContextLiveBudget(ROOT/'.local/p39/v2/shared-envelope.sqlite3',counter)
    if args.action=='preflight':
        print(json.dumps(dict(runtime_hash=runtime['runtime_hash'],candidate_manifest_hash=runtime['candidate']['manifest_hash'],
                             budget=budget.summary(),smoke8_reserve_upper_cny=runtime['smoke8_reserve_upper_cny'],new64_reserve_upper_cny=runtime['new64_reserve_upper_cny']),ensure_ascii=False));return
    # Only an actual saved human message can enter the comparison-approval table.
    # There is deliberately no content/safety approval writer in this executable.
    if not (base/'offline-acceptance.json').exists():raise PermissionError('Full offline acceptance evidence required')
    acceptance=load(base/'offline-acceptance.json')
    if acceptance.get('runtime_hash')!=runtime['runtime_hash'] or not acceptance.get('full_pass') or not acceptance.get('portable_pass'):
        raise PermissionError('Offline acceptance binding mismatch')
    if not budget.summary()['comparison_approved']:budget.approve(runtime['comparison_approval'])
    budget.install(runtime)
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    from src.infrastructure.v3_live_settings import V3PilotSettings
    settings=V3PilotSettings.from_env()
    settings.validate()
    # Read-only authenticated availability check; no inference/probe request.
    if not (base/'models-availability.json').exists():
        import httpx
        from datetime import datetime,timezone
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=25) as client:
            response=client.get('https://api.deepseek.com/models',headers={'Authorization':'Bearer '+settings.api_key})
            response.raise_for_status();data=response.json()
        ids=[row['id'] for row in data['data']]
        if 'deepseek-flash' not in ids:raise PermissionError('Approved model unavailable')
        write_new(base/'models-availability.json',dict(checked_at=datetime.now(timezone.utc).isoformat(),method='GET',endpoint='https://api.deepseek.com/models',model_ids=ids,inference_requests=0))
    print(json.dumps(run_smoke(runtime,budget,settings),ensure_ascii=False))


if __name__=='__main__':main()
