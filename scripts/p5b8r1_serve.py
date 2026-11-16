"""R1 local copy of the saved product; no live API or external business action."""
import os,sys,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
def snapshot(source,dest):
    if dest.exists():return
    dest.parent.mkdir(parents=True,exist_ok=True)
    if source.exists():
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as old,sqlite3.connect(dest) as new:old.backup(new)
if __name__=='__main__':
    import uvicorn
    from src.app.p5b8r1_api import create
    folder=ROOT/'.local/p4/p5b8r1-20261031';old=ROOT/'.local/p4/p5b8-20261031-v2'
    for n in ('product.sqlite3','p5b5r2-actions.sqlite3'):snapshot(old/n,folder/n)
    uvicorn.run(create(folder/'product.sqlite3',ROOT/'.local/p5b8r1/web-dist'),host='127.0.0.1',port=8774)
