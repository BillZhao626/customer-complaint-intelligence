"""R2 evidence review in the existing React UI, an isolated copy, all live calls disabled."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
if __name__=='__main__':
    import uvicorn
    from scripts.p5b8r1_serve import snapshot
    from src.app.p5b8_api import create
    from src.application.p5b8r2_guard import quality
    from src.application.p5b8r1_actions import guided_actions
    folder=ROOT/'.local/p4/p5b8r2-20261101'
    for n in ('product.sqlite3','p5b5r2-actions.sqlite3'):
        snapshot(ROOT/'.local/p4/p5b8r1-20261031'/n,folder/n)
    # Existing R1 endpoints are used by its frozen web build; use that app,
    # with the R2 predicate correction installed on the same product store.
    from src.app.p5b8r1_api import create as r1_create
    app=r1_create(folder/'product.sqlite3',ROOT/'.local/p5b8r1/web-dist',port=8775)
    old=app.state.store.quality_inspector
    app.state.store.quality_inspector=lambda r,d,t,a:quality(r,d,t,a) if r.config.schema_version=='p5b8-calibration-1' else old(r,d,t,a)
    # Keep the existing component and layout; point its evidence links at R2.
    app.router.routes=[r for r in app.router.routes if getattr(r,'path','') not in ('/api/b8r1/status','/api/b8r1/package')]
    static=app.router.routes.pop()
    @app.get('/api/b8r1/status')
    def readiness():
        import json
        m=json.loads((ROOT/'docs/p5b8r2/EXPERIMENT_MANIFEST.json').read_text('utf-8'))
        return dict(m['A'],version=m['version'],new_paid_authorization=False)
    @app.get('/api/b8r1/package')
    def package():
        from fastapi.responses import FileResponse
        return FileResponse(ROOT/'docs/p5b8r2/P5-B8-R2_COMPLETE_REVIEW.zip',filename='P5-B8-R2_COMPLETE_REVIEW.zip')
    app.router.routes.append(static)
    uvicorn.run(app,host='127.0.0.1',port=8775)
