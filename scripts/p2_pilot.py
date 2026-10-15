"""Explicit authorized live pilot. No work on import. Never resets budgets or retries saved runs."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SPACE=ROOT/'.local/p2-pilot-v1'
FIXTURES=ROOT/'tests/fixtures/p2_pilot_v1.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)

def fixtures():
    from src.domain.contracts import EmailInput
    return [(EmailInput.model_validate(r['email']),r) for r in json.loads(FIXTURES.read_text(encoding='utf-8'))['cases']]

def prepare():
    from src.application.live_prompt import PROMPT_HASH,PROMPT_VERSION,SYSTEM_PROMPT
    from src.domain.contracts import AnalysisResult,digest
    from src.infrastructure.pilot_budget import PilotBudget,PRICE_SOURCE,PRICE_DATE
    from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
    cases=fixtures();assert len(cases)<=12 and len({e.input_hash for e,_ in cases})==len(cases)
    manifest=dict(pilot='p2-pilot-v1',source='developer-authored synthetic fixtures; not blind human Gold',
        created_at=datetime.now(timezone.utc).isoformat(),fixture_sha256=sha(FIXTURES),prompt_hash=PROMPT_HASH,
        prompt_version=PROMPT_VERSION,schema_hash=digest(AnalysisResult.model_json_schema()),
        price_source=PRICE_SOURCE,price_checked_date=PRICE_DATE,peak_input_cny_per_million=2,peak_output_cny_per_million=8,
        limits=dict(unique_emails=12,http_reservations=20,cny=20,concurrency=1),
        config=DeepSeekAnalyzer(LiveSettings('offline-configuration-only',True)).config.model_dump(),
        packages={p:importlib.metadata.version(p) for p in ('langchain-openai','openai','httpx','streamlit','pydantic')},
        inputs=[dict(email_id=e.email_id,input_hash=e.input_hash,phase=r['phase']) for e,r in cases])
    write_new(SPACE/'manifest.json',manifest)
    write_new(SPACE/'fixtures.json',json.loads(FIXTURES.read_text(encoding='utf-8')))
    (SPACE/'prompt.txt').write_text(SYSTEM_PROMPT,encoding='utf-8')
    PilotBudget.create(SPACE/'budget.sqlite3',[e.input_hash for e,_ in cases],manifest)
    print(json.dumps({'prepared':str(SPACE),'planned_samples':len(cases),'prompt_hash':PROMPT_HASH}))

def verify_frozen():
    from src.application.live_prompt import PROMPT_HASH
    manifest=json.loads((SPACE/'manifest.json').read_text(encoding='utf-8'))
    if sha(FIXTURES)!=manifest['fixture_sha256'] or PROMPT_HASH!=manifest['prompt_hash']:
        raise RuntimeError('Frozen fixture/prompt mismatch: refuse paid execution')
    return manifest

def run_phase(phase):
    from src.application.analysis_service import AnalysisService
    from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
    from src.infrastructure.repository import Repository
    from src.infrastructure.pilot_budget import PilotBudget
    verify_frozen()
    if os.getenv('COMPLAINT_ENABLE_LIVE')!='true':raise RuntimeError('Explicit COMPLAINT_ENABLE_LIVE=true required')
    budget=PilotBudget(SPACE/'budget.sqlite3');repo=Repository(SPACE/'runs.sqlite3')
    summary=budget.summary()
    if summary['halted'] or summary['active_lease']:
        print(json.dumps({'stopped':summary}));return
    service=AnalysisService(repo,DeepSeekAnalyzer(LiveSettings.from_env()),budget=budget)
    for email,row in fixtures():
        if row['phase']!=phase:continue
        if phase=='ui':
            from streamlit.testing.v1 import AppTest
            os.environ['COMPLAINT_DB_PATH']=str(repo.path)
            app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=115).run()
            assert not app.exception
            app.selectbox(key='offline_backend').set_value('deepseek_live').run()
            app.text_input(key='offline_email_id').set_value(email.email_id)
            app.text_input(key='offline_subject').set_value(email.subject)
            app.text_area(key='offline_body').set_value(email.body)
            before=budget.summary()['reserved_attempts']
            ui_started=time.perf_counter()
            app.button(key='offline_analyze').click().run(timeout=115)
            ui_elapsed_ms=(time.perf_counter()-ui_started)*1000
            assert not app.exception
            run_id=app.session_state['offline_run_id'];run=repo.get(run_id)
            assert run and run.config.backend=='deepseek_live'
            app.run()
            fresh=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
            fresh.text_input(key='offline_lookup').set_value(run_id)
            fresh.button(key='offline_load').click().run()
            assert not fresh.exception
            assert any(email.body in t.value for t in fresh.text)
            assert budget.summary()['reserved_attempts']>=before
            write_new(SPACE/('ui-evidence-'+run_id+'.json'),dict(run_id=run_id,status=run.status,
                path='actual app.py AppTest -> AnalysisService -> ChatOpenAI -> DeepSeek -> SQLite -> new AppTest session reload',
                browser_e2e=False,original_reloaded=True,success_visible=any('DeepSeek Live saved successfully' in s.value for s in fresh.success),
                ui_submit_to_render_elapsed_ms=ui_elapsed_ms,
                attempts_before=before,attempts_after=budget.summary()['reserved_attempts']))
        else:run=service.analyze(email)
        output=SPACE/('run-'+run.run_id+'.json')
        if not output.exists():write_new(output,run.model_dump())
        print(json.dumps(dict(email_id=email.email_id,run_id=run.run_id,status=run.status,attempts=len(run.attempts),budget=budget.summary())),flush=True)
        if budget.summary()['halted'] or budget.summary()['active_lease']:break

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','smoke','semantic','ui','report']);args=parser.parse_args()
    if args.phase=='prepare':prepare()
    elif args.phase=='report':
        from src.evaluation.p2_report import generate
        print(generate(ROOT,SPACE,FIXTURES))
    else:run_phase(args.phase)

if __name__=='__main__':main()
