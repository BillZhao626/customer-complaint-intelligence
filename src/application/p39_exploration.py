"""At most six separately identified Challenger calls after fixed A/B completion."""
from datetime import datetime,timezone
from hashlib import sha256
import copy
import json
import math
from pathlib import Path

from src.application import p39r3_challenger as prompt
from src.application.p39_continuity import verify_runtime as verify_fixed,reconcile,engineering_check,diagnose
from src.application.p39_context_live import ContextLiveAnalyzer,ContextLiveService,write_new
from src.domain.contracts import RunConfigV31,EmailInput,digest
from src.infrastructure.p39_continuity_budget import ContinuityBudget
from src.infrastructure.p39_live_context import ContextLiveRepository
from src.infrastructure.context_repository import ReadOnlyContextRepository

ROOT=Path(__file__).resolve().parents[2]


def source_hash():
    paths=('src/application/p39_exploration.py','src/application/p39r3_challenger.py')
    return digest({p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})


def build_plan(fixed,budget,sample_ids,out):
    verify_fixed(fixed)
    runs=reconcile(fixed,budget)
    if len(runs)!=64:
        raise PermissionError('Fixed A/B must be complete before exploration')
    if not 1<=len(sample_ids)<=6 or len(set(sample_ids))!=len(sample_ids):
        raise ValueError('One to six distinct representative inputs required')
    rows={r['email']['email_id']:r for r in fixed['candidate']['inputs']}
    if any(s not in rows for s in sample_ids):
        raise PermissionError('Only approved fictional development inputs')
    config=copy.deepcopy(fixed['candidate']['configs']['B'])
    config.update(prompt_version=prompt.VERSION,prompt_hash=prompt.prompt_hash())
    config['parameters'].update(arm='C',exploratory=True,dataset_id='p39-r3-challenger-fact-ownership-1',challenger_candidate_hash=prompt.candidate_identity()['candidate_hash'])
    config=RunConfigV31.model_validate(config).model_dump()
    champion_by_id={r.email.email_id:r.run_id for r in runs if r.config.parameters['arm']=='B'}
    body=dict(version='p39-r3-exploration-1',fixed_runtime=fixed,candidate=prompt.candidate_identity(),config=config,
              inputs=[rows[s] for s in sample_ids],champion_runs=[champion_by_id[s] for s in sample_ids],
              runtime_directory=str(Path(out).resolve()),execution_chain_hash=source_hash(),
              authorization_sha256=fixed['authorization_sha256'],max_new_requests=6,combined_auto_ceiling=71,hard_requests=72,hard_cny=10,
              reply_status='unreviewed_unsent',human_content_approval=None)
    body['plan_hash']=digest(body);verify_plan(body);return body


def verify_plan(plan):
    body=dict(plan);claim=body.pop('plan_hash')
    if digest(body)!=claim or plan['execution_chain_hash']!=source_hash() or plan['candidate']!=prompt.candidate_identity():
        raise ValueError('Challenger identity drift')
    verify_fixed(plan['fixed_runtime'])
    if (plan['authorization_sha256']!=plan['fixed_runtime']['authorization_sha256']
        or (plan['max_new_requests'],plan['combined_auto_ceiling'],plan['hard_requests'],plan['hard_cny'])!=(6,71,72,10)
        or not 1<=len(plan['inputs'])<=6 or len({r['input_hash'] for r in plan['inputs']})!=len(plan['inputs'])
        or len(plan['champion_runs'])!=len(plan['inputs']) or len(set(plan['champion_runs']))!=len(plan['inputs'])
        or plan['reply_status']!='unreviewed_unsent' or plan['human_content_approval'] is not None):
        raise ValueError('Challenger scope drift')
    fixed=plan['fixed_runtime']
    if any(r not in fixed['candidate']['inputs'] for r in plan['inputs']):
        raise ValueError('Challenger input drift')
    c=plan['config'];base=copy.deepcopy(fixed['candidate']['configs']['B'])
    expected=copy.deepcopy(base);expected.update(prompt_version=prompt.VERSION,prompt_hash=prompt.prompt_hash())
    expected['parameters'].update(arm='C',exploratory=True,dataset_id='p39-r3-challenger-fact-ownership-1',challenger_candidate_hash=prompt.candidate_identity()['candidate_hash'])
    if c!=RunConfigV31.model_validate(expected).model_dump():
        raise ValueError('Challenger configuration drift')
    if not fixed['offline_test_fixture'] and Path(plan['runtime_directory'])!=(ROOT/'.local/p39/v2/r3-challenger-runtime').resolve():
        raise PermissionError('One Challenger runtime only')


def check_run(run,plan,counter):
    from src.domain.analysis_v31_context import stored_context_analysis
    if run.config.model_dump()!=plan['config']:
        raise ValueError('Challenger run config drift')
    if run.status not in ('succeeded','failed') or len(run.attempts)!=1 or run.input_hash!=run.email.input_hash:
        raise ValueError('Challenger uncertain send or input drift')
    a=run.attempts[0];m=a.metadata;bound=counter.measure(prompt.messages(run.email))
    values=[m.get(k) for k in ('input_tokens','output_tokens','total_tokens','cache_hit_tokens','cache_miss_tokens')]
    cost=run.metadata.get('cost_cny');reserve=m.get('reserved_upper_cny');payload=m.get('actual_payload_sha256');size=m.get('actual_payload_bytes')
    if (m.get('dispatch')!='response_received' or m.get('resolved_model')!=plan['config']['model_id']
        or m.get('actual_system_prompt_sha256')!=plan['config']['prompt_hash']
        or any(type(v) is not int or v<0 for v in values) or values[2]!=values[0]+values[1] or values[3]+values[4]!=values[0]
        or values[0]>bound['input_token_reserve'] or values[1]>4000 or m.get('finish_reason') not in ('stop','length','content_filter')
        or type(cost) not in (int,float) or not math.isfinite(cost) or cost<0 or m.get('cost_cny')!=cost
        or type(reserve) not in (int,float) or not math.isfinite(reserve) or cost>reserve
        or not isinstance(payload,str) or len(payload)!=64 or any(c not in '0123456789abcdef' for c in payload)
        or type(size) is not int or not 0<size<=50000):raise ValueError('Challenger usage/model/payload anomaly')
    p=plan['fixed_runtime']['price_receipt']['prices']
    if abs(cost-(values[0]*p['input_cny_per_million']+values[1]*p['output_cny_per_million'])/1e6)>1e-10:
        raise ValueError('Challenger price drift')
    if any(run.metadata.get(k)!=0 for k in ('sdk_retries','application_retries','json_repair_retries')) or run.metadata.get('fallback') is not False:
        raise ValueError('Challenger retry/fallback drift')
    if (run.status=='succeeded')!=(run.result is not None):raise ValueError('Challenger terminal state drift')
    if run.result:
        if a.error or a.contract_status!='passed':raise ValueError('Challenger accepted attempt drift')
        stored_context_analysis(run);return 'accepted'
    if not a.error or a.error.error_type not in ('empty_response','invalid_json','raw_schema_invalid'):
        raise ValueError('Challenger non-quality failure')
    if a.error.error_type=='raw_schema_invalid' and diagnose(run)['stage'] not in ('schema','semantic_validation','safety_gate'):
        raise ValueError('Challenger unexplained service rejection')
    return 'model_quality_failure'


class ExplorationBudget(ContinuityBudget):
    def install_plan(self,plan):
        verify_plan(plan)
        fixed_runs=reconcile(plan['fixed_runtime'],self)
        if len(fixed_runs)!=64:
            raise PermissionError('Fixed experiment incomplete')
        champions={r.email.email_id:r.run_id for r in fixed_runs if r.config.parameters['arm']=='B'}
        if plan['champion_runs']!=[champions[r['email']['email_id']] for r in plan['inputs']]:
            raise PermissionError('Champion run binding drift')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE');self._check(c)
            c.execute('CREATE TABLE IF NOT EXISTS r3_challenger_plan(id INTEGER PRIMARY KEY CHECK(id=1),plan TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS r3_challenger_receipts(run_id TEXT PRIMARY KEY,receipt TEXT)')
            row=c.execute('SELECT plan FROM r3_challenger_plan').fetchone()
            if row:
                if json.loads(row[0])!=plan:raise PermissionError('Exploration plan cannot be replaced')
            else:c.execute('INSERT INTO r3_challenger_plan VALUES(1,?)',(json.dumps(plan),))

    def plan(self):
        with self.connection() as c:return json.loads(c.execute('SELECT plan FROM r3_challenger_plan').fetchone()[0])

    def verify_config(self,config):
        plan=self.plan();verify_plan(plan)
        if config.model_dump()!=plan['config']:raise PermissionError('Wrong Challenger config')
        self._config=config

    def acquire(self,run_id,input_hash):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE');self._check(c)
            plan=json.loads(c.execute('SELECT plan FROM r3_challenger_plan').fetchone()[0]);verify_plan(plan)
            if c.execute('SELECT 1 FROM lease').fetchone() or c.execute('SELECT 1 FROM wire_claim').fetchone():raise PermissionError('Unsettled dispatch')
            fixed=c.execute("SELECT COUNT(*) FROM events WHERE kind='v2_reserved'").fetchone()[0]
            n=c.execute("SELECT COUNT(*) FROM events WHERE kind='challenger_reserved'").fetchone()[0]
            if fixed!=64 or n>=len(plan['inputs']) or n>=6:raise PermissionError('Exploration allowance exhausted or fixed incomplete')
            if c.execute('SELECT COUNT(*) FROM r3_challenger_receipts').fetchone()[0]!=n:raise PermissionError('Unreconciled exploration')
            if self._config is None or self._config.model_dump()!=plan['config'] or input_hash!=plan['inputs'][n]['input_hash']:
                raise PermissionError('Exploration schedule drift')
            c.execute('INSERT INTO wire_claim VALUES(1,?,?,?,?)',(run_id,input_hash,'C',digest(plan['config'])))

    def reserve(self,run_id,attempt_no,input_hash,msgs,max_tokens):
        if attempt_no!=1 or max_tokens!=4000:raise PermissionError('No Challenger retries')
        bound=self.counter.measure(msgs)
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE');fixed=self._check(c)
            plan=json.loads(c.execute('SELECT plan FROM r3_challenger_plan').fetchone()[0]);verify_plan(plan)
            if c.execute('SELECT run_id,input_hash,arm,config_hash FROM wire_claim').fetchone()!=(run_id,input_hash,'C',digest(plan['config'])):
                raise PermissionError('Wrong request owner')
            n=c.execute("SELECT COUNT(*) FROM events WHERE kind='challenger_reserved'").fetchone()[0]
            if n>=len(plan['inputs']) or plan['inputs'][n]['input_hash']!=input_hash or msgs!=prompt.messages(EmailInput.model_validate(plan['inputs'][n]['email'])):
                raise PermissionError('Challenger payload drift')
            p=fixed['price_receipt']['prices'];cost=(bound['input_token_reserve']*p['input_cny_per_million']+4000*p['output_cny_per_million'])/1e6
            total_count,total_cost=c.execute("SELECT COUNT(*),COALESCE(SUM(upper_cny),0) FROM events WHERE kind!='settled'").fetchone()
            if (type(bound['input_token_reserve']) is not int or bound['input_token_reserve']<=0 or bound['payload_bytes']>50000
                or not math.isfinite(cost) or not 0<cost<10 or total_count>=71 or total_count>=72 or total_cost+cost>10
                or c.execute('SELECT 1 FROM lease').fetchone()):raise PermissionError('Shared exploration hard cap or lease blocked')
            c.execute('INSERT INTO events(kind,run_id,upper_cny,created_at) VALUES(?,?,?,?)',('challenger_reserved',run_id,cost,datetime.now(timezone.utc).isoformat()))
            c.execute('INSERT INTO lease VALUES(1,?)',(run_id,))
            c.execute('INSERT INTO wire_payloads(run_id,bounds) VALUES(?,?)',(run_id,json.dumps(bound)))
        return cost

    def record_exploration(self,receipt):
        with self.connection() as c:
            old=c.execute('SELECT receipt FROM r3_challenger_receipts WHERE run_id=?',(receipt['run_id'],)).fetchone()
            if old:
                if json.loads(old[0])!=receipt:raise ValueError('Challenger receipt drift')
            else:c.execute('INSERT INTO r3_challenger_receipts VALUES(?,?)',(receipt['run_id'],json.dumps(receipt)))


def exploration_runs(plan,budget):
    state=budget.summary()
    if state['halted'] or state['active_lease'] or state['active_wire_claim']:raise PermissionError('Exploration stopped or unsettled')
    path=Path(plan['runtime_directory'])/'runs.sqlite3'
    runs=ReadOnlyContextRepository(path).list_runs() if path.exists() else []
    by={r.run_id:r for r in runs}
    with budget.connection() as c:
        events=c.execute("SELECT run_id,upper_cny FROM events WHERE kind='challenger_reserved' ORDER BY id").fetchall()
        settled={r[0] for r in c.execute("SELECT run_id FROM events WHERE kind='settled'")}
        completed={r[0]:r[1] for r in c.execute('SELECT run_id,completed FROM wire_payloads')}
    if len(by)!=len(runs) or len(events)!=len(runs):raise ValueError('Exploration reservation/run mismatch')
    ordered=[]
    for n,(rid,cost) in enumerate(events):
        run=by[rid]
        if (run.input_hash!=plan['inputs'][n]['input_hash'] or run.email.model_dump()!=plan['inputs'][n]['email']
            or 'settled:'+rid not in settled or completed.get(rid)!=1 or run.attempts[-1].metadata.get('reserved_upper_cny')!=cost):
            raise ValueError('Exploration schedule/settlement drift')
        check_run(run,plan,budget.counter);ordered.append(run)
    return ordered


def run_exploration(plan,budget,settings,provider=None):
    from dataclasses import replace
    verify_plan(plan)
    if budget.plan()!=plan:raise PermissionError('Installed Challenger plan binding drift')
    settings=replace(settings,max_tokens=4000,max_attempts=1);settings.validate()
    out=Path(plan['runtime_directory']);out.mkdir(parents=True,exist_ok=True)
    repo=ContextLiveRepository(out/'runs.sqlite3')
    analyzer=ContextLiveAnalyzer(settings,plan['fixed_runtime']['candidate'],'B',budget.counter,provider)
    analyzer.config=RunConfigV31.model_validate(plan['config'])
    analyzer.messages=lambda email,repair=False:prompt.messages(email)
    class Service(ContextLiveService):
        def validate_result(self,data,email):
            result,meta=super().validate_result(data,email)
            meta.update(challenger_plan_hash=plan['plan_hash'],challenger_execution_hash=plan['execution_chain_hash'],
                        challenger_candidate_hash=plan['candidate']['candidate_hash'],experiment_kind='exploratory_development')
            return result,meta
    try:
        while True:
            if budget.plan()!=plan:raise PermissionError('Challenger plan changed during execution')
            saved=exploration_runs(plan,budget)
            for r in saved:
                budget.record_exploration(dict(run_id=r.run_id,run_hash=digest(r.model_dump()),plan_hash=plan['plan_hash'],
                    classification=check_run(r,plan,budget.counter),diagnosis=diagnose(r),reply_status='unreviewed_unsent'))
            if len(saved)>=len(plan['inputs']):break
            email=EmailInput.model_validate(plan['inputs'][len(saved)]['email'])
            run=Service(repo,analyzer,budget=budget).analyze(email)
            reread=ReadOnlyContextRepository(out/'runs.sqlite3').get(run.run_id)
            if reread.model_dump()!=run.model_dump():raise ValueError('Challenger SQLite reload drift')
            target=out/('run-'+run.run_id+'.json')
            if not target.exists():write_new(target,run.model_dump())
            elif json.loads(target.read_text(encoding='utf8'))!=run.model_dump():raise ValueError('Challenger export drift')
            category=check_run(run,plan,budget.counter)
            print(json.dumps(dict(challenger_request=len(saved)+1,run_id=run.run_id,status=run.status,classification=category,
                                 tokens=run.attempts[0].metadata['total_tokens']),ensure_ascii=False),flush=True)
    except BaseException:
        budget.halt('r3_challenger_engineering_stop');raise
    return dict(attempted=len(saved),accepted=sum(r.result is not None for r in saved),failed=sum(r.result is None for r in saved),
                budget=budget.summary(),formal_ab_results_modified=False,quality_improvement_proven=False,reply_status='unreviewed_unsent')
