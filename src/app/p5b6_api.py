"""Add read-only research views to the current R2 application."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from src.app.p5b5r2_api import create as r2_app
from src.application.research_insights import ResearchInsights
from src.evaluation.classification_research import build_report


def create(db_path, *, root=None, web_directory=None):
    root=Path(root or Path(__file__).resolve().parents[2])
    class ClosedDriver:
        @staticmethod
        def status_ui():return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='P5B6_NO_PAID_AUTHORIZATION')
        @staticmethod
        def generate_ui(*args,**kwargs):raise PermissionError('No new authorization')
        generate_followup_ui=generate_ui
    package=root/'docs/p5b6/HUMAN_REVIEW_FINAL.json'
    app=r2_app(db_path,live_driver=ClosedDriver(),local_origin_port=8771,
               review_package=package if package.exists() else None)
    catalog=ResearchInsights(root)
    report=build_report(root,catalog)

    @app.get('/api/research/sources')
    def sources():
        return dict(sources=catalog.catalog(),live_enabled=False,generation='LIVE_GENERATION_PENDING')

    @app.get('/api/research/insights')
    def insights(source:str='template400',store:str|None=None,product:str|None=None,sentiment:str|None=None,status:str|None=None,start:str|None=None,end:str|None=None):
        try:return catalog.snapshot(source,store=store,product=product,sentiment=sentiment,status=status,start=start,end=end)
        except (ValueError,KeyError) as e:raise HTTPException(422,str(e)) from e

    @app.get('/api/research/member')
    def member(source:str,member_id:str):
        try:
            r=catalog.member(source,member_id)
            # Linking does not create or import a historical case.
            cases=app.state.store.list_cases()
            case=next((c for c in cases if c['run'].run_id==r['run_id']),None)
            return dict(r,source=catalog.sources[source],product_case_id=case['case_id'] if case else None)
        except (KeyError,StopIteration) as e:raise HTTPException(404,'Member unavailable') from e

    @app.get('/api/research/classification')
    def classification():return report

    if web_directory:app.mount('/',StaticFiles(directory=web_directory,html=True),name='p5b6-product')
    return app
