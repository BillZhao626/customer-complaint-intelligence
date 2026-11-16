"""Serve a fresh/resumable P5 offline inbox on loopback only."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace',required=True,help='Dedicated new .local/p4/p5-* directory (or resume it)')
    parser.add_argument('--seed',action='store_true',help='Idempotently add authored developer fixtures')
    parser.add_argument('--include-engineering',action='store_true',help='Also add historical P4.7 and intentional bad-analysis fixtures')
    args = parser.parse_args()
    folder = Path(args.workspace).resolve()
    if folder.is_relative_to(ROOT) and (not folder.is_relative_to(ROOT/'.local/p4') or not folder.name.startswith('p5-')):
        parser.error('Use a dedicated .local/p4/p5-* directory; historical workspaces are not accepted')
    from src.app.p5_api import create_app, create_demo
    app = create_app(folder/'product.sqlite3')
    if args.seed:
        from src.application.p5_quality import load_cases
        for case in load_cases()[::3]: create_demo(app.state.store,'p5:'+case['case_id'])
        if args.include_engineering:
            from src.application.service_scenarios import SCENARIOS
            for scenario in SCENARIOS: create_demo(app.state.store,'p47:'+scenario)
            create_demo(app.state.store,'blocked')
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8765,workers=1,access_log=False)


if __name__ == '__main__': main()
