"""Independent working copy. No seed, old ledger access or provider dispatch."""
import os
import sqlite3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')

def prepare():
    target=ROOT/'.local/p4/p5b7-20261030';target.mkdir(parents=True,exist_ok=True)
    for name in ('product.sqlite3','p5b5r2-actions.sqlite3'):
        dest=target/name
        if not dest.exists():
            src=ROOT/'.local/p4/p5b6-20261030'/name
            with sqlite3.connect(src.resolve().as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(dest) as b:a.backup(b)
    return target/'product.sqlite3'

if __name__=='__main__':
    import uvicorn
    from src.app.p5b7_api import create
    uvicorn.run(create(prepare(),ROOT/'.local/p5b7/web-dist'),host='127.0.0.1',port=8772)
