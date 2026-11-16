"""Serve only the independent R2 product. Seed reads saved synthetic runs once."""
import os,sys,argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',action='store_true');a=p.parse_args()
    db=ROOT/'.local/p4/p5b5r2-20261030/product.sqlite3'
    if a.seed:
        if db.exists():raise ValueError('Seed refuses existing workspace')
        from src.application.product_workflow import ProductStore
        from src.domain.contracts import AnalysisRun
        store=ProductStore(db)
        paths=list((ROOT/'.local/p5b5-live-20261030-v1/B2').glob('*/run.json'))
        paths+=list((ROOT/'.local/p5b5-live-20261030-v1/E4').glob('*/run.json'))
        for path in paths:
            run=AnalysisRun.model_validate_json(path.read_text(encoding='utf-8'))
            store.create(run,'R2 read-only historical '+run.config.parameters.get('arm','B2'))
    from src.app.p5b5r2_api import create
    import uvicorn
    uvicorn.run(create(db,web_directory=ROOT/'.local/p5b5r2/web-dist'),host='127.0.0.1',port=8770)

if __name__=='__main__':main()
