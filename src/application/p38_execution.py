"""Future controlled dispatch; requires a fresh explicit authorization artifact."""
import json
from pathlib import Path
from src.domain.contracts import EmailInput,digest
from src.evaluation.p38_ab import preflight


def run_live(manifest,authorization,out,phase='smoke',smoke_review=None):
    if authorization is None:raise PermissionError('P3.8 current authorization is 0 requests / 0 CNY')
    preflight(manifest,authorization)
    if phase not in ('smoke','remaining'):raise ValueError('Choose smoke or remaining')
    from src.infrastructure.p38_budget import P38Budget
    from src.infrastructure.repository import Repository
    from src.infrastructure.deepseek import DeepSeekAnalyzer
    from src.infrastructure.v3_live_settings import V3PilotSettings
    from src.application.analysis_service import AnalysisService
    from src.domain.contracts import RunConfigV31
    out=Path(out).resolve()
    # Budget creation protects all historical locations and is exclusive.
    if phase=='smoke':
        if out.exists():raise FileExistsError('Use a new P3.8 runtime directory')
        budget=P38Budget.create(out/'budget.sqlite3',manifest,authorization)
    else:
        if not out.is_dir():raise ValueError('Missing smoke runtime')
        budget=P38Budget(out/'budget.sqlite3')
        with budget.connection() as conn:saved=json.loads(conn.execute('SELECT manifest FROM policy').fetchone()[0])
        if saved!={'experiment':manifest,'authorization':authorization}:raise ValueError('Runtime authorization drift')
        if not (out/'smoke-pass.json').is_file():raise ValueError('Four-pair smoke gate has not passed')
        receipt=json.loads((out/'smoke-pass.json').read_text(encoding='utf8'))
        if receipt.get('manifest_hash')!=manifest['manifest_hash'] or receipt.get('passed_pairs')!=4:raise ValueError('Invalid smoke receipt')
        if not smoke_review or smoke_review.get('status')!='researcher_approved' or not smoke_review.get('reviewer') or smoke_review.get('smoke_receipt_hash')!=digest(receipt):
            raise ValueError('Researcher smoke content/safety review required before remaining dispatch')
    # Reading environment/client configuration happens after authorization checks.
    settings=V3PilotSettings.from_env()
    from dataclasses import replace
    settings=replace(settings,max_tokens=4000,max_attempts=1)
    analyzers={a:DeepSeekAnalyzer(settings,prompt_profile='multi-issue-v31-'+a) for a in ('A','B')}
    for a in analyzers:analyzers[a].config=RunConfigV31.model_validate(manifest['configs'][a])
    repo=Repository(out/'runs.sqlite3');runs=[]
    if phase=='remaining':
        smoke=repo.list_runs()
        expected={(manifest['inputs'][s['input_index']]['email']['email_id'],s['arm']) for s in manifest['schedule'] if s['phase']=='smoke'}
        good={(r.email.email_id,r.config.parameters['arm']) for r in smoke if r.status=='succeeded' and r.config.model_dump()==manifest['configs'].get(r.config.parameters['arm'])}
        if not expected.issubset(good):raise ValueError('Persisted smoke results no longer satisfy gate')
        bindings=[dict(run_id=r.run_id,input_hash=r.input_hash,output_hash=r.metadata['analysis_v31_hash']) for r in smoke if (r.email.email_id,r.config.parameters['arm']) in expected]
        if sorted(bindings,key=lambda r:r['run_id'])!=sorted(receipt['run_bindings'],key=lambda r:r['run_id']):raise ValueError('Smoke receipt/output binding mismatch')
    for step in manifest['schedule']:
        if step['phase']!=phase:continue
        state=budget.summary()
        if state['halted'] or state['pending_dispatches'] or state['active_lease']:break
        email=EmailInput.model_validate(manifest['inputs'][step['input_index']]['email'])
        run=AnalysisService(repo,analyzers[step['arm']],budget=budget).analyze(email);runs.append(run)
        with (out/f'run-{run.run_id}.json').open('x',encoding='utf8') as f:f.write(run.model_dump_json(indent=2))
        if run.metadata.get('cost_cny') is None or any(a.metadata.get('cost_cny') is not None and a.metadata['cost_cny']>a.metadata.get('reserved_upper_cny',0) for a in run.attempts):
            budget.halt('usage_or_cost_anomaly');break
        if run.metadata.get('resolved_model')!=manifest['configs'][step['arm']]['model_id']:
            budget.halt('resolved_model_identity_drift');break
        if run.status!='succeeded':
            budget.halt('failure_requires_review');break
    if phase=='smoke' and len(runs)==8 and all(r.status=='succeeded' for r in runs) and not budget.summary()['halted']:
        with (out/'smoke-pass.json').open('x',encoding='utf8') as f:json.dump(dict(manifest_hash=manifest['manifest_hash'],passed_pairs=4,
            gate='engineering_only_content_approval_required',run_bindings=[dict(run_id=r.run_id,input_hash=r.input_hash,output_hash=r.metadata['analysis_v31_hash']) for r in runs]),f)
    return dict(phase=phase,returned_runs=len(runs),budget=budget.summary(),reply_status='unreviewed_unsent')
