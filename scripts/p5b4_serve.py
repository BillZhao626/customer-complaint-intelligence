"""Loopback only. Independent product DB; all model endpoints disabled."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')

def create():
    from src.app.p5_api import create_app
    from fastapi.responses import JSONResponse
    app=create_app(ROOT/'.local/p4/p5b4-20261030/product.sqlite3',serve_web=False,live_generate=False,local_origin_port=8768)
    @app.get('/p5b4/data.json')
    def data():
        import json
        return JSONResponse(json.loads((ROOT/'.local/p5b4/view-data.json').read_text(encoding='utf-8')))
    from fastapi.staticfiles import StaticFiles
    app.mount('/',StaticFiles(directory=ROOT/'.local/p5b4/web-dist',html=True),name='p5b4-preview')
    return app

if __name__=='__main__':
    import uvicorn
    uvicorn.run(create(),host='127.0.0.1',port=8768)
