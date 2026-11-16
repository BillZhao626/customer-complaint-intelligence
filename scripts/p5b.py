"""Explicit P5-B single-run entry; imports do not enable API calls."""
import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['verify','run'])
    a=p.parse_args()
    from src.evaluation.p5b_pilot import read,verify_manifest,DELIVERY,run
    manifest=read(DELIVERY/'pilot_manifest_16.json')
    verify_manifest(manifest)
    if a.command=='verify':
        print('Frozen manifest verified: 16 cases, 18 turns; paid calls=0')
        return
    from hashlib import sha256
    preflight=read(DELIVERY/'PRECALL_PREFLIGHT.json')
    if preflight['manifest_hash']!=manifest['manifest_hash'] or not preflight['offline_verified']:
        raise ValueError('Offline engineering preflight required')
    for path,expected in preflight['source_hashes'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen source drift: '+path)
    import os
    # Only this explicit command enables this authorized experiment, never .env writes.
    for key in ('LANGSMITH_TRACING','LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2'):
        os.environ[key]='false'
    os.environ['COMPLAINT_ENABLE_LIVE']='true'
    from src.infrastructure.v3_live_settings import V3PilotSettings
    settings=replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000)
    print(run(manifest,settings))


if __name__=='__main__':main()
