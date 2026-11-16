"""Run existing React workspace on an isolated R5 SQLite copy."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
if __name__=='__main__':
    import uvicorn
    from scripts.p5b8r1_serve import snapshot
    from src.app.p5b8r5_api import create
    folder=ROOT/'.local/p4/p5b8r5-20261102'
    for n in ('product.sqlite3','p5b5r2-actions.sqlite3'):snapshot(ROOT/'.local/p4/p5b8r2-20261101'/n,folder/n)
    uvicorn.run(create(folder/'product.sqlite3',ROOT/'.local/p5b8r5/web-dist'),host='127.0.0.1',port=8776)
