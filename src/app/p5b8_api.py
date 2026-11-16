"""Reuse the existing inbox/review store, plus read-only B8 evidence views."""
from pathlib import Path
import json
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.app.p5b5r2_api import create as base
from src.application.p5b8_research import cases,summary
from src.application.p5b8_product import make_run,quality
ROOT=Path(__file__).resolve().parents[2]
class Import(BaseModel):identity:str
def create(db,web,*,port=8773,quality_override=None,planner_override=None,live_driver=None):
    class Closed:
        @staticmethod
        def status_ui():return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='已保存真实实验；新增付费仅受控命令行，需独立预算')
        @staticmethod
        def generate_ui(*a,**kw):raise PermissionError('CLI only')
        generate_followup_ui=generate_ui
    app=base(db,live_driver=live_driver or Closed(),local_origin_port=port,b8_planner=planner_override);store=app.state.store;old_quality=store.quality_inspector
    inspect=quality_override or quality
    store.quality_inspector=lambda r,d,t,a:inspect(r,d,t,a) if r.config.schema_version=='p5b8-calibration-1' else old_quality(r,d,t,a)
    @app.get('/api/b8/results')
    def results():return summary()
    @app.get('/api/b8/baseline')
    def baseline():
        p=ROOT/'docs/p5b8/BASELINE.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    @app.get('/api/research/classification')
    def classification():
        from src.evaluation.classification_research import build_report
        from src.application.p5b7_research import B7Insights
        return build_report(ROOT,B7Insights(ROOT))
    @app.get('/api/b8/cases')
    def list_cases():return dict(cases=[dict(case_id=r['case_id'],subject=r['email']['subject'],language=r['language'],family=r['family'],dataset_role=r['dataset_role'],analysis=(r['analysis'] or {}).get('data'),variants=list(r['replies']),findings=r['findings']) for r in cases()])
    @app.get('/api/b8/cases/{eid}')
    def case(eid:str):
        r=next((r for r in cases() if r['case_id']==eid),None)
        if not r:raise HTTPException(404,'Case not found')
        c=next((c for c in store.list_cases() if c['run'].email.email_id==eid and c['run'].config.schema_version=='p5b8-calibration-1'),None)
        return dict(r,product_case_id=c['case_id'] if c else None)
    @app.post('/api/b8/import')
    def import_saved(body:Import):
        if body.identity!='P5B8_SAVED_REAL_CHAIN':raise HTTPException(422,'Saved evidence identity required')
        imported=[]
        from src.application.p5b5r2_pipeline import ActionStore
        actions=ActionStore(store.path.with_name('p5b5r2-actions.sqlite3'))
        for r in cases():
            if 'A_GUIDED' not in r['replies']:continue
            run=make_run(r);c=store.create(run,'本轮真实分析与回执增强回复 · 合成研究 · 未人工认证',origin='new_analysis');imported.append(c['case_id'])
            with actions.connect() as conn:
                for e in run.metadata['runtime']['events']:
                    conn.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?,?,?)',(e['event_id'],e['input_hash'],e['conversation_id'],e['operation_id'],e['kind'],e['status'],json.dumps(e['payload'],ensure_ascii=False),e['created_at']))
        return dict(imported=len(imported),case_ids=imported,paid_calls=0)
    app.mount('/',StaticFiles(directory=web,html=True),name='p5b8-product')
    return app
