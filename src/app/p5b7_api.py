"""Reuse the R2 product and B6 statistics; import only persisted B7 real runs."""
import json
from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.app.p5b5r2_api import create as r2_app
from src.application.p5b7_research import B7Insights
from src.evaluation.classification_research import build_report
from src.domain.contracts import AnalysisRun

ROOT=Path(__file__).resolve().parents[2]
class Import(BaseModel):
    identity: str

def create(db_path,web_directory):
    class ClosedDriver:
        @staticmethod
        def status_ui():return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='本轮实验使用独立受控命令行；网页仅导入真实结果与本地审核')
        @staticmethod
        def generate_ui(*a,**k):raise PermissionError('Controlled CLI only')
        generate_followup_ui=generate_ui
    app=r2_app(db_path,live_driver=ClosedDriver(),local_origin_port=8772)
    def catalog():return B7Insights(ROOT)

    @app.get('/api/research/sources')
    def sources():return dict(sources=catalog().catalog(),live_enabled=False,generation='LLM_SYNTHETIC_REAL_RESULTS')
    @app.get('/api/research/insights')
    def insights(source:str='b7-B2',store:str|None=None,product:str|None=None,sentiment:str|None=None,status:str|None=None,start:str|None=None,end:str|None=None):
        try:return catalog().snapshot(source,store=store,product=product,sentiment=sentiment,status=status,start=start,end=end)
        except (ValueError,KeyError) as e:raise HTTPException(422,str(e)) from e
    @app.get('/api/research/member')
    def member(source:str,member_id:str):
        c=catalog()
        try:r=c.member(source,member_id)
        except (KeyError,StopIteration):raise HTTPException(404,'Member unavailable')
        case=next((x for x in app.state.store.list_cases() if x['run'].run_id==r['run_id']),None)
        return dict(r,source=c.sources[source],product_case_id=case['case_id'] if case else None)
    @app.get('/api/research/classification')
    def classification():return build_report(ROOT,catalog())
    @app.get('/api/b7/results')
    def results():
        p=ROOT/'docs/p5b7/RESULTS.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else dict(status='真实批量实验进行中，尚未汇总',arms={},pairs=[])
    @app.get('/api/b7/import')
    def import_status():
        paths=sorted((ROOT/'.local/p5b7/B2').glob('B7-*/run.json'))
        existing={x['run'].run_id for x in app.state.store.list_cases()}
        rows=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
        return dict(available=len(rows),imported=sum(r['run_id'] in existing for r in rows),identity='P5B7_SAVED_REAL_B2',dispatch=False)
    @app.post('/api/b7/import')
    def import_saved(body:Import):
        if body.identity!='P5B7_SAVED_REAL_B2':raise HTTPException(422,'Explicit saved experiment identity required')
        cases=[]
        for p in sorted((ROOT/'.local/p5b7/B2').glob('B7-*/run.json')):
            run=AnalysisRun.model_validate_json(p.read_text(encoding='utf-8'))
            c=app.state.store.create(run,'本轮 LLM 合成邮件 · 真实 LangChain 分析',origin='new_analysis');cases.append(c['case_id'])
        return dict(import_status(),case_ids=cases)
    app.mount('/',StaticFiles(directory=web_directory,html=True),name='p5b7-product')
    return app
