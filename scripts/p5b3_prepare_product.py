"""Copy immutable real run/task evidence to this round's separate UI workspace."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.product_workflow import ProductStore
from src.application.p5b3_actions import journal
from src.domain.contracts import AnalysisRun
from src.evaluation.p5b_pilot import read,write_new
store=ProductStore(ROOT/'.local/p4/p5b3-20261029-v1/product.sqlite3')
source=ProductStore(ROOT/'.local/p4/p5b3-20261029-v1/experiment-product.sqlite3')
selected={'B3-DEV-01-T1','B3-DEV-07-T1','B3-TEST-05-T1','B3-TEST-06-T1'}
rows=[]
for stage in ('dev-confirm','test'):
    for p in (ROOT/'.local/p5b3-20261029-v1'/stage).glob('*/run.json'):
        r=AnalysisRun.model_validate(read(p))
        if r.email.email_id not in selected:continue
        # Preserve exact task IDs/events returned to this original generation.
        sj,dj=journal(source),journal(store)
        with sj.connect() as sc,dj.connect() as dc:
            for t in sc.execute('SELECT * FROM tasks WHERE input_hash=?',(r.input_hash,)):
                dc.execute('INSERT OR IGNORE INTO tasks VALUES(?,?,?)',tuple(t))
                for e in sc.execute('SELECT * FROM events WHERE task_id=?',(t['task_id'],)):
                    dc.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?)',tuple(e))
        c=store.create(r,'P5-B3 saved run '+stage)
        rows.append(dict(email_id=r.email.email_id,case_id=c['case_id'],run_id=r.run_id,source_kind=c['source_kind']))
write_new(ROOT/'docs/p5b3/PRODUCT_REPLAYS.json',rows)
print(json.dumps(rows,ensure_ascii=False))
