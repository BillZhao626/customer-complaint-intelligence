"""Existing product with an opt-in audited cohort, no paid provider."""
from pathlib import Path
from fastapi import HTTPException
from src.app.p5b8_api import create as base
from src.application.p5b8r2_guard import quality
from src.application.p5b8r4_actions import guided_actions
from src.application.p5b8r5_insights import R5Insights,SOURCE
ROOT=Path(__file__).resolve().parents[2]
def create(db,web,port=8776,*,policy_overlays=None,planner=None,trace_cases=None,live_driver=None):
    def inspect(run,data,reply,accepted):
        if run.config.parameters.get('experiment')=='p5b8r6':
            from src.application.service_response import quality as current_quality
            return current_quality(run,data,reply,accepted)
        return quality(run,data,reply,accepted)
    app=base(db,web,port=port,quality_override=inspect,planner_override=planner or guided_actions,live_driver=live_driver);static=app.router.routes.pop()
    app.router.routes=[r for r in app.router.routes if getattr(r,'path','') not in ('/api/research/sources','/api/research/insights','/api/research/member')]
    catalog=R5Insights(ROOT,policy_overlays=policy_overlays)
    @app.get('/api/research/sources')
    def sources():return dict(sources=catalog.catalog(),live_enabled=False)
    @app.get('/api/research/insights')
    def insights(source:str=SOURCE,store:str|None=None,product:str|None=None,sentiment:str|None=None,status:str|None=None,start:str|None=None,end:str|None=None):
        try:return catalog.snapshot(source,store=store,product=product,sentiment=sentiment,status=status,start=start,end=end)
        except (KeyError,ValueError) as e:raise HTTPException(422,str(e))
    @app.get('/api/research/member')
    def member(source:str,member_id:str):
        try:
            r=catalog.member(source,member_id);current=(trace_cases or {}).get(r['email']['email_id'],{}) if source=='b8-r6-policy' else {}
            return dict(r,source=catalog.sources[source],product_case_id=current.get('case_id'),reply=current.get('reply',r.get('reply')),current_reply_identity=current.get('identity'))
        except (KeyError,StopIteration):raise HTTPException(404,'Member unavailable')
    app.router.routes.append(static);return app
