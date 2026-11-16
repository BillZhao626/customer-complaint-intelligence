"""Fresh local product database; all web paid dispatch disabled."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
if __name__=='__main__':
    import uvicorn
    from src.app.p5b8_api import create
    uvicorn.run(create(ROOT/'.local/p4/p5b8-20261031-v2/product.sqlite3',ROOT/'.local/p5b8/web-dist'),host='127.0.0.1',port=8773)
