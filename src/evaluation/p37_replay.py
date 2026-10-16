"""Read-only P3.6 audit and versioned deterministic derivation. No provider calls."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from src.domain.contracts import digest,idempotency_key
from src.domain.analysis_v3 import AnalysisV3,stored_analysis,to_v2
from src.application.live_execution import strict_json
from src.application.v3_remediation import derive,verify_derived,HANDLING_POLICY
from src.evaluation.p36_report import development_comparison
from src.infrastructure.dashboard_sources import ReadOnlyRepository


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def budget_snapshot(path):
    path=Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        manifest,allowed,halted=conn.execute('SELECT manifest,allowed,halted FROM policy WHERE id=1').fetchone()
        reservations=conn.execute('SELECT run_id,attempt_no,input_hash,reserved_cny,completed FROM reservations ORDER BY id').fetchall()
        return dict(manifest=json.loads(manifest),allowed=json.loads(allowed),halted=halted,
                    reservations=reservations,count=len(reservations),reserved_cny=sum(r[3] for r in reservations),
                    active_leases=conn.execute('SELECT COUNT(*) FROM lease').fetchone()[0],
                    configurations=conn.execute('SELECT config,experiment_hash FROM configurations ORDER BY cohort').fetchall())


def audit_p36(source):
    source=Path(source);inputs=load(source/'inputs-v1.json');allowed={x['email']['email_id']:x for x in inputs['inputs']}
    ledger=budget_snapshot(source/'budget.sqlite3')
    if set(ledger['allowed'])!={x['input_hash'] for x in allowed.values()} or ledger['manifest'].get('inputs_hash')!=digest(inputs):
        raise ValueError('Budget input whitelist/freeze mismatch')
    if ledger['manifest'].get('limits')!={'requests':40,'cny':15} or ledger['count']>40 or ledger['reserved_cny']>15:
        raise ValueError('Historical authorization limits mismatch')
    if any(r[4]!=1 for r in ledger['reservations']):raise ValueError('Unsettled historical request')
    records=[];groups={};registry={digest(json.loads(c)):h for c,h in ledger['configurations']}
    for name in ('baseline-v1','catalog-v2','draft-v3'):
        root=source/name;manifest=load(root/'manifest.json')
        if digest(inputs)!=manifest['inputs_hash'] or digest(AnalysisV3.model_json_schema())!=manifest['schema_hash']:
            raise ValueError('Frozen input/schema mismatch')
        # Windows text snapshots use CRLF; the actual sent Python system string
        # uses LF. Verify logical sent text and separately retain raw file bytes.
        if sha256((root/'prompt.txt').read_text(encoding='utf8').encode('utf8')).hexdigest()!=manifest['prompt_hash']:
            raise ValueError('Frozen prompt mismatch')
        if registry.get(digest(manifest['config']))!=digest(manifest):raise ValueError('Budget experiment identity mismatch')
        runs=ReadOnlyRepository(root/'runs.sqlite3').list_runs();groups[name]=runs
        json_ids={p.stem.removeprefix('run-') for p in root.glob('run-*.json')}
        if json_ids!={r.run_id for r in runs}:raise ValueError('Run JSON/SQLite coverage mismatch')
        for run in runs:
            if run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config):
                raise ValueError('Run/cohort/idempotency identity mismatch')
            if run.model_dump()!=load(root/f'run-{run.run_id}.json'):raise ValueError('JSON/SQLite run mismatch')
            item=allowed[run.email.email_id]
            if run.email.model_dump()!=item['email'] or run.input_hash!=item['input_hash'] or run.config.model_dump()!=manifest['config']:
                raise ValueError('Original input/config mismatch')
            if run.result:stored_analysis(run)
            for attempt in run.attempts:
                if attempt.metadata.get('actual_system_prompt_sha256')!=manifest['prompt_hash']:raise ValueError('Actual prompt mismatch')
                if strict_json(attempt.raw_output)!=attempt.parsed_output:raise ValueError('Raw/parsed return mismatch')
                reservation=(run.run_id,attempt.attempt_no,run.input_hash,attempt.metadata['reserved_upper_cny'],1)
                if reservation not in [tuple(r) for r in ledger['reservations']]:raise ValueError('Unaccounted request')
            records.append(dict(experiment=name,sample_id=run.email.email_id,run_id=run.run_id,status=run.status,
                input_hash=run.input_hash,config_hash=digest(run.config.model_dump()),cohort_id=run.cohort_id,
                prompt_hash=run.config.prompt_hash,schema_hash=manifest['schema_hash'],
                prompt_snapshot_file_sha256=sha256((root/'prompt.txt').read_bytes()).hexdigest(),
                output_hash=run.metadata.get('analysis_v3_hash'),raw_hashes=[digest(a.raw_output) for a in run.attempts],
                provider_models=[a.metadata.get('resolved_model') for a in run.attempts],
                provider_response_ids=[a.metadata.get('provider_response_id') for a in run.attempts]))
    actual=development_comparison(inputs['inputs'],groups['draft-v3'])
    frozen=load(source/'draft-v3/comparison24-v1.json')
    if actual!=frozen:raise ValueError('Frozen development comparison changed')
    if ledger['count']!=sum(len(r.attempts) for rr in groups.values() for r in rr):raise ValueError('Budget/run count mismatch')
    if ledger['halted']!='authorization_limit' or ledger['active_leases']:raise ValueError('P3.6 budget must stay locked')
    return dict(kind='READ_ONLY_HISTORICAL_REPLAY',records=records,runs=len(records),budget_requests=ledger['count'],
        budget_halted=ledger['halted'],budget_reserved_cny=ledger['reserved_cny'],new_model_requests=0,new_cost_cny=0,
        frozen_all24=actual['all24'],frozen_final_succeeded=sum(r.status=='succeeded' for r in groups['draft-v3']),
        frozen_final_attempted=len(groups['draft-v3']),provider_reinvoked=False),groups


def export_replay(source,out):
    out=Path(out);source=Path(source).resolve()
    target=out.resolve()
    if target.is_relative_to(source) or source.is_relative_to(target):raise ValueError('Replay output must be disjoint from historical source')
    # Audit first; invalid/tampered evidence leaves no apparently valid export.
    audit,groups=audit_p36(source)
    out.mkdir(parents=True,exist_ok=False)
    def write(name,data):
        with (out/name).open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    write('historical-audit.json',audit)
    derived=[];differences=[];missing=[]
    for run in groups['draft-v3']:
        if not run.result:
            missing.append(dict(sample_id=run.email.email_id,run_id=run.run_id,status=run.status,reason='No accepted source prediction; no derived replacement'))
            continue
        for projection,handling in [('customer-primary-v2-safe',None),('owner-operational-v2-safe',None),('owner-operational-v2-safe',HANDLING_POLICY)]:
            packet=derive(run,projection,handling);verify_derived(run,packet);derived.append(packet)
            old=run.result.model_dump();new=packet['projection']
            paired_policy='customer-primary-v1' if projection=='customer-primary-v2-safe' else 'owner-operational-v1'
            paired=to_v2(stored_analysis(run),paired_policy)[0].model_dump()
            differences.append(dict(sample_id=run.email.email_id,run_id=run.run_id,derived_id=packet['derived_id'],
                projection=projection,handling=handling,paired_baseline_policy=paired_policy,
                changes={k:dict(old=paired[k],new=new[k]) for k in paired if paired[k]!=new[k]},
                historical_projection_changes={k:dict(old=old[k],new=new[k]) for k in old if old[k]!=new[k]},
                v3_changes=packet['changes'],quality_improvement_claim=False))
    write('derived-views.json',derived);write('policy-differences.json',differences);write('missing-predictions.json',missing)
    return dict(source_runs=audit['runs'],derived_views=len(derived),missing_final_predictions=len(missing),new_requests=0)
