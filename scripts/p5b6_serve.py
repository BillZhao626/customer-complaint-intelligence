"""Offline-only research product, copying existing R2 workspace once, never seeding it."""
import os
import sys
import sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')


def prepare():
    directory=ROOT/'.local/p4/p5b6-20261030';directory.mkdir(parents=True,exist_ok=True)
    source=ROOT/'.local/p4/p5b5r2-20261030'
    for name in ('product.sqlite3','p5b5r2-actions.sqlite3'):
        dest=directory/name;original=source/name
        if dest.exists():continue
        if not original.exists():raise FileNotFoundError(original)
        with sqlite3.connect(original.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(dest) as dst:src.backup(dst)
    marker=directory/'research-import-v1.json'
    if not marker.exists():
        import json
        from src.application.product_workflow import ProductStore
        from src.domain.contracts import AnalysisRun
        store=ProductStore(directory/'product.sqlite3');receipts=[]
        for arm in ('R3','FINAL'):
            for path in sorted((ROOT/'.local/p5b5r2'/arm).glob('*/run.json')):
                run=AnalysisRun.model_validate_json(path.read_text(encoding='utf-8'))
                case=store.create(run,'P5-B6 saved synthetic research '+arm)
                receipts.append(dict(source=str(path.relative_to(ROOT)),run_id=run.run_id,case_id=case['case_id']))
        with marker.open('x',encoding='utf-8') as f:json.dump(dict(identity='DERIVED_REVIEW_WORKSPACE_NOT_NEW_MODEL_OUTPUT',receipts=receipts),f,indent=2)
    return directory/'product.sqlite3'


if __name__=='__main__':
    import uvicorn
    from src.app.p5b6_api import create
    uvicorn.run(create(prepare(),web_directory=ROOT/'.local/p5b6/web-dist'),host='127.0.0.1',port=8771)
