"""Explicit actions only; no import-time model dispatch."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','serve']);a=p.parse_args()
    from src.application.p5b3_runtime import LOCAL,Budget
    from src.evaluation.p5b_pilot import now,write_new
    if a.command=='init':
        auth=dict(experiment='p5b3-20261029-v1',authorized_by='User P5-B3 section 7',limits=dict(provider_calls=120,cny=5,concurrency=1,retries=0),pricing=dict(price_source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',prices_verified_at=now(),prices=dict(input_cache_miss_cny_per_million=2,output_cny_per_million=8,input_cache_hit_cny_per_million=.04)))
        write_new(LOCAL/'authorization.json',auth)
        b=Budget.create(LOCAL/'budget.sqlite3',[],auth)
        with b.connection() as c:
            c.execute('CREATE TABLE stage_reservations(run_id TEXT PRIMARY KEY,stage TEXT NOT NULL)')
            c.execute('CREATE TABLE settlements(run_id TEXT PRIMARY KEY,cost REAL NOT NULL)')
        print(json.dumps(b.summary()));return
    from src.app.p5_api import create_app
    import uvicorn
    app=create_app(ROOT/'.local/p4/p5b3-20261029-v1/product.sqlite3',live_generate=True)
    uvicorn.run(app,host='127.0.0.1',port=8767)

if __name__=='__main__':main()
