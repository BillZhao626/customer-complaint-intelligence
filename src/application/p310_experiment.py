"""Independent fixed-plan research runner; quality failures preserve denominators."""
from hashlib import sha256
import json
from pathlib import Path

from src.application import p310_prompt
from src.application import p310_correction
from src.application.p39_v2 import messages as champion_messages,system as champion_system
from src.application.p39_experiment import P39Analyzer,dependencies,wire_bytes
from src.application.analysis_service import AnalysisService
from src.application.p39_v2 import ContextOfflineService
from src.domain.contracts import EmailInput,RunConfigV31,digest
from src.domain.analysis_v31 import POLICY,PROJECTION
from src.domain.analysis_v31_context import stored_context_analysis
from src.application.reply_review import VERSION as GATE
from src.infrastructure.repository import Repository
from src.infrastructure.p39_live_context import ContextLiveRepository
from src.infrastructure.dashboard_sources import ReadOnlyRepository

ROOT=Path(__file__).resolve().parents[2]
VERSION='p310-controlled-quality-recovery-v1'
CHAMPION_SHA='a4ecfaa52c37103a5dcd1544240f55c566be0adaa433132848a9c12a90c7027a'


def messages_for(email,arm,context=None):
    if arm=='champion':
        if sha256(champion_system('B').encode()).hexdigest()!=CHAMPION_SHA:raise ValueError('Frozen Champion B drift')
        return champion_messages(email,'B')
    if arm=='challenger':return p310_prompt.messages(email)
    if arm=='correction':return p310_correction.messages(email,context)
    raise ValueError('Unknown P3.10 arm')


def source_identity():
    paths=('src/application/p310_experiment.py','src/application/p310_prompt.py','src/application/p310_prompt2.py','src/application/p310_correction.py','src/infrastructure/p310_budget.py',
           'src/application/live_execution.py','src/application/p39_experiment.py','src/application/p39_v2.py',
           'src/application/urgency_context_v1.py','src/domain/analysis_v31_context.py','src/domain/analysis_v31.py',
           'src/domain/analysis_v3.py','src/domain/contracts.py','src/application/research_policy_v2.py','src/application/analysis_service.py',
           'src/evaluation/p310_audit.py','src/application/reply_review.py','src/infrastructure/deepseek.py',
           'src/infrastructure/repository.py','src/infrastructure/context_repository.py','src/infrastructure/p39_live_context.py')
    from src.application.p39_v2 import source_hash as historical_chain_hash
    return dict(files={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},dependencies=dependencies(),frozen_champion_chain_hash=historical_chain_hash())


class ByteCounter:
    def measure(self,messages):
        payload=wire_bytes(messages)
        return dict(payload_bytes=len(payload),input_token_reserve=len(payload)+1024,
                    token_count_source='conservative serialized UTF8 bytes +1024 framing margin',exact_api_token_proof=False)


def make_plan(inputs,phase='development'):
    if phase not in ('development','new40','correction'):raise ValueError('Unknown phase')
    rows=[dict(email=EmailInput.model_validate(r['email']).model_dump(),input_hash=EmailInput.model_validate(r['email']).input_hash,
               source=r.get('source','historical exposed fictional development email')) for r in inputs]
    if phase=='correction':
        for row,original in zip(rows,inputs):row['repair_context']=original['repair_context']
    source=source_identity();dataset=digest(rows);candidate=p310_correction.identity()
    params=dict(temperature=0,thinking='disabled',response_format='json_object',max_tokens=4000,sdk_max_retries=0,
                http_timeout=45.0,deadline=90.0,max_attempts=1,endpoint='https://api.deepseek.com/chat/completions',
                policy_version=POLICY,projection_policy=PROJECTION,reply_gate_version=GATE,
                urgency_validation_profile='urgency-context-evidence-v1',dataset_id='p310-'+phase+'-'+dataset,
                processing_chain_hash=digest(source),service_capabilities_hash=digest(p310_prompt.CAPABILITIES))
    configs={}
    for arm in (('challenger',) if phase=='development' else ('correction',) if phase=='correction' else ('champion','challenger')):
        prompt=p310_prompt.system() if arm=='challenger' else p310_correction.system() if arm=='correction' else champion_system('B')
        configs[arm]=RunConfigV31(backend='deepseek_live',model_id='deepseek-flash',
            prompt_version=p310_prompt.VERSION if arm=='challenger' else p310_correction.VERSION if arm=='correction' else 'complaint-p39-v2-B-context-1',
            prompt_hash=sha256(prompt.encode()).hexdigest(),parameters=dict(params,arm=arm)).model_dump()
    schedule=[]
    for index in range(len(rows)):
        arms=('challenger',) if phase=='development' else ('correction',) if phase=='correction' else (('champion','challenger') if index%2==0 else ('challenger','champion'))
        schedule.extend(dict(input_index=index,arm=arm,pair=index+1) for arm in arms)
    body=dict(version=VERSION,phase=phase,inputs=rows,inputs_hash=dataset,source_identity=source,
              candidate_identity=candidate,configs=configs,schedule=schedule,
              primary_validation_profile='urgency-context-evidence-v1',same_strict_gate=True,
              comparison_champion='frozen original B;17/32, retained severe safety handling; not failed R3 candidate',
              target_development=dict(accepted=24,denominator=32),target_new40=dict(accepted=28,denominator=40,paired_gain=4),
              human_semantics=None,new40_independence='developer-authored exploratory; not independent human holdout',
              model_improvement_proven=False,reply_status='unreviewed_unsent')
    body['plan_hash']=digest(body);verify_plan(body);return body


def verify_plan(plan):
    body=dict(plan);claim=body.pop('plan_hash')
    if digest(body)!=claim or plan['source_identity']!=source_identity() or plan['candidate_identity']!=p310_correction.identity():raise ValueError('Plan/source/candidate drift')
    if plan['version']!=VERSION or plan['inputs_hash']!=digest(plan['inputs']) or plan['primary_validation_profile']!='urgency-context-evidence-v1':raise ValueError('Plan identity mismatch')
    count=len(plan['inputs']);phase=plan['phase']
    if phase=='development' and not 1<=count<=32 or phase=='new40' and count!=40 or phase=='correction' and not 1<=count<=40 or phase not in ('development','new40','correction'):raise ValueError('Wrong sample count/phase')
    hashes=set();ids=set();expected=[]
    for index,r in enumerate(plan['inputs']):
        e=EmailInput.model_validate(r['email'])
        if e.input_hash!=r['input_hash'] or e.input_hash in hashes or e.email_id in ids:raise ValueError('Input duplicate/drift')
        hashes.add(e.input_hash);ids.add(e.email_id)
        arms=('challenger',) if phase=='development' else ('correction',) if phase=='correction' else (('champion','challenger') if index%2==0 else ('challenger','champion'))
        if phase=='correction':
            context=r['repair_context']
            if context['input_hash']!=e.input_hash or context['max_corrections']!=1 or context['earliest_contract_failure']['accepted']:
                raise ValueError('Only source-bound failed initial draft can be corrected once')
            messages_for(e,'correction',context)
        expected.extend(dict(input_index=index,arm=a,pair=index+1) for a in arms)
    if plan['schedule']!=expected or set(plan['configs'])!=set(s['arm'] for s in expected):raise ValueError('Schedule drift')
    for arm,config in plan['configs'].items():
        value=RunConfigV31.model_validate(config);p=value.parameters
        if (value.backend!='deepseek_live' or value.model_id!='deepseek-flash' or value.prompt_hash!=sha256(messages_for(EmailInput.model_validate(plan['inputs'][0]['email']),arm,plan['inputs'][0].get('repair_context'))[0][1].encode()).hexdigest()
            or p['max_tokens']!=4000 or p['max_attempts']!=1 or p['arm']!=arm or p['urgency_validation_profile']!='urgency-context-evidence-v1'
            or p['processing_chain_hash']!=digest(plan['source_identity']) or p['policy_version']!=POLICY or p['projection_policy']!=PROJECTION or p['reply_gate_version']!=GATE):
            raise ValueError('Configuration drift')


class ResearchRepository(ContextLiveRepository):
    def __init__(self,path):
        path=Path(path).resolve()
        if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT/'.local/p310'):raise PermissionError('Only new P3.10 storage')
        Repository.__init__(self,path)


class ReadOnlyResearchRepository(ResearchRepository):
    def __init__(self,path):ReadOnlyRepository.__init__(self,path)
    def connect(self):return ReadOnlyRepository.connect(self)
    def save(self,*args,**kwargs):raise PermissionError('Read-only')
    def claim_live(self,*args,**kwargs):raise PermissionError('Read-only')
    def finish_live(self,*args,**kwargs):raise PermissionError('Read-only')


class ResearchAnalyzer(P39Analyzer):
    def __init__(self,settings,plan,arm,provider=None):
        super().__init__(settings,dict(configs={'B':plan['configs'][arm]}),'B',ByteCounter(),provider)
        contexts={r['input_hash']:r.get('repair_context') for r in plan['inputs']}
        self.correction_contexts=contexts
        self.messages=lambda email,repair=False:messages_for(email,arm,contexts[email.input_hash]) if not repair else (_ for _ in ()).throw(ValueError('No hidden repair'))


class ResearchService(AnalysisService):
    def validate_result(self,data,email):
        result,metadata=ContextOfflineService.validate_result(self,data,email)
        metadata.update(service_capabilities_hash=digest(p310_prompt.CAPABILITIES),application_actions_executed=[])
        context=self.analyzer.correction_contexts.get(email.input_hash)
        if context:
            metadata.update(correction_parent_run_id=context['parent_run_id'],correction_parent_raw_sha256=context['prior_raw_sha256'],
                            workflow_kind='explicit_single_correction',first_prediction_preserved=True)
        return result,metadata


def engineering_receipt(run,plan,step):
    """Quality failures continue only after exact economic/identity reconciliation."""
    import math
    from src.evaluation.p310_audit import acceptance
    config=plan['configs'][step['arm']];email=EmailInput.model_validate(plan['inputs'][step['input_index']]['email'])
    if run.config.model_dump()!=config or run.email!=email or len(run.attempts)!=1 or run.input_hash!=email.input_hash:raise ValueError('Run identity drift')
    a=run.attempts[0];m=a.metadata
    vals=[m.get(k) for k in ('input_tokens','output_tokens','total_tokens','cache_hit_tokens','cache_miss_tokens')]
    if (m.get('dispatch')!='response_received' or m.get('resolved_model')!='deepseek-flash'
        or any(type(v) is not int or v<0 for v in vals) or vals[0]+vals[1]!=vals[2] or vals[3]+vals[4]!=vals[0]
        or vals[0]>ByteCounter().measure(messages_for(email,step['arm'],plan['inputs'][step['input_index']].get('repair_context')))['input_token_reserve'] or vals[1]>4000
        or m.get('actual_system_prompt_sha256')!=config['prompt_hash'] or m.get('finish_reason') not in ('stop','length','content_filter')
        or not re_full_hash(m.get('actual_payload_sha256')) or type(m.get('actual_payload_bytes')) is not int or not 0<m['actual_payload_bytes']<=50000):
        raise ValueError('Dispatch/usage/model/payload anomaly')
    cost=(vals[0]*2+vals[1]*8)/1e6
    if (type(m.get('cost_cny')) not in (int,float) or not math.isfinite(m['cost_cny'])
        or abs(m['cost_cny']-cost)>1e-10 or run.metadata.get('cost_cny')!=m['cost_cny']
        or type(m.get('reserved_upper_cny')) not in (int,float) or not math.isfinite(m['reserved_upper_cny']) or cost>m['reserved_upper_cny']):raise ValueError('Cost anomaly')
    if any(run.metadata.get(k)!=0 for k in ('sdk_retries','application_retries','json_repair_retries')) or run.metadata.get('fallback') is not False:raise ValueError('Hidden retry/fallback')
    if (run.status=='succeeded')!=(run.result is not None) or run.status not in ('succeeded','failed'):raise ValueError('Unknown run state')
    if run.result:stored_context_analysis(run)
    elif not a.error or a.error.error_type not in ('empty_response','invalid_json','raw_schema_invalid'):raise ValueError('Non-quality failure')
    replay=acceptance(a.raw_output,email)
    if replay['accepted']!=(run.result is not None):raise ValueError('Acceptance identity drift')
    return dict(run_id=run.run_id,run_hash=digest(run.model_dump()),input_hash=email.input_hash,config_hash=digest(config),
                raw_sha256=sha256((a.raw_output or '').encode()).hexdigest(),accepted=bool(run.result),cost_upper_cny=cost,tokens=vals[2])


def re_full_hash(value):
    import re
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def run_plan(plan,budget,settings,out,provider=None):
    verify_plan(plan);budget.verify_root()
    if budget.fixture and provider is None:raise PermissionError('Offline fixture cannot initialize real provider')
    if settings.max_attempts!=1 or settings.max_tokens!=4000 or settings.http_timeout!=45 or settings.deadline!=90:raise PermissionError('Explicit frozen one-call settings required')
    settings.validate();budget.register_plan(plan)
    out=Path(out).resolve()
    if not budget.fixture and out!=(ROOT/'.local/p310'/('runtime-'+plan['plan_hash'])).resolve():raise PermissionError('One runtime per plan')
    out.mkdir(parents=True,exist_ok=True);repo=ResearchRepository(out/'runs.sqlite3')
    with budget.connection() as c:
        claims=c.execute('SELECT run_id,step_index FROM claims WHERE plan_hash=? ORDER BY step_index',(plan['plan_hash'],)).fetchall()
        outcomes={r[0]:json.loads(r[1]) for r in c.execute('SELECT run_id,receipt FROM outcomes')}
    state=budget.summary()
    if state['halted'] or state['active_lease'] or state['pending_dispatches']:raise PermissionError('Stopped or unsettled envelope')
    if len(claims)!=len([r for r in claims if r[0] in outcomes]):raise PermissionError('Missing settlement; manual recovery required')
    for run_id,index in claims:
        saved=ReadOnlyResearchRepository(out/'runs.sqlite3').get(run_id)
        if not saved or engineering_receipt(saved,plan,plan['schedule'][index])!=outcomes[run_id]:raise ValueError('Saved outcome drift')
    analyzers={a:ResearchAnalyzer(settings,plan,a,provider) for a in plan['configs']}
    for step in plan['schedule'][len(claims):]:
        try:
            email=EmailInput.model_validate(plan['inputs'][step['input_index']]['email'])
            run=ResearchService(repo,analyzers[step['arm']],budget=budget).analyze(email)
            saved=ReadOnlyResearchRepository(out/'runs.sqlite3').get(run.run_id)
            if saved.model_dump()!=run.model_dump():raise ValueError('Read-only SQLite reload drift')
            receipt=engineering_receipt(saved,plan,step)
            target=out/('run-'+run.run_id+'.json')
            with target.open('x',encoding='utf8') as f:f.write(saved.model_dump_json(indent=2))
            budget.settle(run.run_id,receipt)
            print(json.dumps(dict(pair=step['pair'],arm=step['arm'],status=run.status,tokens=receipt['tokens'],cost_upper_cny=receipt['cost_upper_cny'])),flush=True)
        except BaseException:
            budget.halt('engineering_or_identity_or_persistence_failure')
            raise
    return dict(plan_hash=plan['plan_hash'],budget=budget.summary(),runs=len(plan['schedule']),reply_status='unreviewed_unsent')
