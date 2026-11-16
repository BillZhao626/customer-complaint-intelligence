"""Independent product workspace; paid and external actions disabled."""
import os,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',action='store_true');a=p.parse_args()
    db=ROOT/'.local/p4/p5b5-20261030/product.sqlite3'
    if a.seed:
        if db.exists():raise ValueError('Seed refuses existing product workspace')
        import json
        from src.application.product_workflow import ProductStore
        from src.domain.contracts import AnalysisRun
        store=ProductStore(db)
        config=json.loads((ROOT/'.local/p5b4/experiment-config-v3.json').read_text(encoding='utf-8'))
        for c in reversed(config['cases']):
            run=AnalysisRun.model_validate_json((ROOT/c['b2_path']).read_text(encoding='utf-8'))
            store.create(run,'P5B5 historical B2 '+c['case_id'])
    from src.app.p5b5_api import create
    import uvicorn
    uvicorn.run(create(db,web_directory=ROOT/'.local/p5b5/web-dist'),host='127.0.0.1',port=8769)

if __name__=='__main__':main()
