"""Explicit authorized R3 fixed continuation. Offline preflight is the default."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['preflight','run','status'],nargs='?',default='preflight')
    args = parser.parse_args()
    from src.application.p39_continuity import build_runtime,verify_runtime,reconcile,run_fixed
    from src.application.p39_context_live import write_new
    from src.application.p39_experiment import TokenCounter
    from src.infrastructure.p39_continuity_budget import ContinuityBudget
    base = ROOT/'.local/p39/r3'; old = ROOT/'.local/p39/v2/live-delivery-v1'
    load = lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    parent = load(old/'runtime-identity.json')
    rt = build_runtime(parent,(base/'user-request.txt').read_text(encoding='utf-8-sig'),ROOT/'.local/p39/v2/r3-runtime')
    target = base/('runtime-'+rt['runtime_hash']+'.json')
    if target.exists():
        if load(target) != rt:
            raise ValueError('Prepared R3 identity drift')
    elif args.action == 'preflight':
        write_new(target,rt)
    else:
        raise PermissionError('Persist preflight identity first')
    verify_runtime(rt)
    sys.path.insert(0,str(ROOT/'.local/p39/deps'))
    p = rt['price_receipt']
    counter = TokenCounter(ROOT/'.local/p39/tokenizer-v4',p['tokenizer_sha256'],p['tokenizer_config_sha256'])
    budget = ContinuityBudget(ROOT/'.local/p39/v2/shared-envelope.sqlite3',counter)
    # Installing authorizes only the audited quality stop. No old row is edited.
    if args.action == 'preflight':
        print(json.dumps(dict(runtime_hash=rt['runtime_hash'],candidate_manifest_hash=rt['candidate']['manifest_hash'],budget=budget.summary()),ensure_ascii=False))
        return
    acceptance = load(base/'offline-acceptance.json')
    if acceptance.get('runtime_hash') != rt['runtime_hash'] or not acceptance.get('full_pass') or not acceptance.get('portable_pass'):
        raise PermissionError('Full offline engineering acceptance required')
    # Before acknowledging a historical quality stop, independently validate every saved run.
    from src.application.p39_continuity import load_runs,engineering_check
    for run in load_runs(rt):
        engineering_check(run,rt,counter)
    budget.install(rt)
    saved = reconcile(rt,budget)
    if args.action == 'status':
        print(json.dumps(dict(attempted=len(saved),budget=budget.summary()),ensure_ascii=False));return
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    from src.infrastructure.v3_live_settings import V3PilotSettings
    settings = V3PilotSettings.from_env(); settings.validate()
    # Read-only authenticated availability; no inference probe, no retries.
    if not (base/'models-availability.json').exists():
        import httpx
        from datetime import datetime,timezone
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=25) as client:
            response = client.get('https://api.deepseek.com/models',headers={'Authorization':'Bearer '+settings.api_key})
            response.raise_for_status(); ids = [r['id'] for r in response.json()['data']]
        if 'deepseek-flash' not in ids:
            raise PermissionError('Approved model unavailable')
        write_new(base/'models-availability.json',dict(checked_at=datetime.now(timezone.utc).isoformat(),method='GET',model_ids=ids,inference_requests=0))
    result = run_fixed(rt,budget,settings)
    write_new(base/'fixed-execution-result.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
