"""Explicit actions only; paid dispatch requires the new durable authorization."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['replay','freeze-explore','freeze-formal','explore','formal'])
    a=p.parse_args()
    from src.evaluation.p5b2 import replay,freeze,run
    if a.command=='replay':print(replay());return
    if a.command.startswith('freeze-'):print(freeze(a.command.split('-')[1])['prompt_sha256']);return
    import os
    from dataclasses import replace
    os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    from src.infrastructure.v3_live_settings import V3PilotSettings
    settings=replace(V3PilotSettings.from_env(),max_attempts=1,max_tokens=4000)
    print(run(a.command,settings))

if __name__=='__main__':main()
