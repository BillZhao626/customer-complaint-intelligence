"""Opt-in R1 quality calibration; existing inbox, local actions and statistics."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from src.app.p5b8_api import create as base
from src.application.p5b8_research import read,cases
from src.application.p5b8_product import make_run,stored
from src.application.p5b8r1_guard import quality
from src.application.p5b8r1_actions import guided_actions
ROOT=Path(__file__).resolve().parents[2]

def create(db,web,*,port=8774):
    app=base(db,web,port=port,quality_override=quality,planner_override=guided_actions);static=app.router.routes.pop()
    @app.get('/api/b8r1/status')
    def status():
        p=ROOT/'docs/p5b8r1/ABLATION_READINESS.json'
        if not p.exists():raise HTTPException(503,'Run free R1 preparation first')
        r=read(p);return dict(r,historical_A=dict(dispatched=90,judged=27,unjudged=63),historical_ledger='CLOSED_398_REQUESTS',new_paid_authorization=False)
    @app.get('/api/b8r1/cases/{eid}')
    def case(eid:str):
        row=next((r for r in cases() if r['case_id']==eid),None)
        if not row:raise HTTPException(404,'Case not found')
        run=make_run(row);gate=quality(run,stored(run) if run.status=='succeeded' else None,row['replies']['A_GUIDED']['reply'],run.status=='succeeded')
        found=next((c['case_id'] for c in app.state.store.list_cases() if c['run'].email.email_id==eid and c['run'].config.schema_version=='p5b8-calibration-1'),None)
        return dict(row,product_case_id=found,r1_gate=gate,r1_ablation_status='AUTHORIZATION_BLOCKED',new_judge_scores=None)
    @app.get('/api/b8r1/package')
    def package():
        p=ROOT/'docs/p5b8r1/P5-B8-R1_COMPLETE_REVIEW.zip'
        if not p.exists():raise HTTPException(503,'Evidence export not complete')
        return FileResponse(p,filename=p.name,media_type='application/zip')
    app.router.routes.append(static);return app
