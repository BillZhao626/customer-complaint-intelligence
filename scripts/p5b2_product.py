"""Import only this experiment's saved real runs, never regenerate or send externally."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b2 import LOCAL,DOC,read,write_new
from src.domain.contracts import AnalysisRun
from src.application.product_workflow import ProductStore

WORK=ROOT/'.local/p4/p5-b2-20261029-v1'

def seed():
    store=ProductStore(WORK/'product.sqlite3');rows=[]
    for row in read(LOCAL/'formal/results.json'):
        r=AnalysisRun.model_validate(read(LOCAL/'formal/turns'/row['turn_id']/'run.json'))
        case=store.create(r,'P5B2 formal first generation',origin='new_analysis')
        rows.append(dict(turn_id=row['turn_id'],calibration_id=row['calibration_id'],case_id=case['case_id'],
            state=case['state'],quality=case['quality'],run_id=r.run_id))
    write_new(DOC/'PRODUCT_CASES.json',rows);print(json.dumps([{k:r[k] for k in ('calibration_id','turn_id','case_id','state')} for r in rows]))

if __name__=='__main__':
    if sys.argv[1]=='seed':seed()
    elif sys.argv[1]=='serve':
        from src.app.p5_api import create_app
        import uvicorn
        uvicorn.run(create_app(WORK/'product.sqlite3',web_directory=LOCAL/'web-dist'),host='127.0.0.1',port=8766,workers=1,access_log=False)
