"""Run `python -B scripts/p5b4_loop.py --help`; network is always blocked."""
import os, socket, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
def blocked(*args,**kwargs): raise RuntimeError('P5-B4 zero-budget runner blocks network')
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked

def main():
    import argparse,json
    from src.evaluation.p5b4 import freeze_config,preflight,loop,read,write
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','preflight','run']);p.add_argument('--config',default='.local/p5b4/experiment-config-v1.json');p.add_argument('--out');a=p.parse_args()
    if a.command=='freeze':
        c=freeze_config();preflight(c);write(ROOT/a.config,c);print(json.dumps(dict(dataset_hash=c['dataset_hash'],n=len(c['cases']))));return
    c=read(ROOT/a.config)
    if a.command=='preflight': print(json.dumps(preflight(c),ensure_ascii=False,indent=2));return
    if not a.out:p.error('run requires a new --out directory')
    print(json.dumps(loop(c,ROOT/a.out),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
