"""Create an exclusive offline inbox demo, optionally serve the real app."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.p45_demo import main as seed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True,help='New directory; existing assets are never overwritten')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--port',type=int,default=8546)
    args=parser.parse_args()
    out=args.out.resolve()
    seed(out)  # Original p45-authored-v1 identity, inputs and manifest retained.
    if args.serve:
        env=dict(os.environ,COMPLAINT_PRODUCT_DB=str(out/'product.sqlite3'),COMPLAINT_DB_PATH=str(out/'legacy.sqlite3'),
            LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
        subprocess.run([sys.executable,'-B','-m','streamlit','run',str(ROOT/'app.py'),'--server.address','127.0.0.1',
            '--server.port',str(args.port),'--browser.gatherUsageStats','false','--theme.base','light','--theme.primaryColor','#6556d8'],
            cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
