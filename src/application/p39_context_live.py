"""Engineering wiring for the approved immutable context candidate. Smoke only."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from src.application.analysis_service import AnalysisService
from src.application.p39_v2 import ContextOfflineService, source_hash, system, messages, require_comparison_approval
from src.application.p39_experiment import P39Analyzer, dependencies
from src.domain.contracts import EmailInput, digest
from src.domain.analysis_v31_context import stored_context_analysis, wire_schema

ROOT = Path(__file__).resolve().parents[2]
APPROVED = '9a0e63fb494b7e926ac890438155ada2fb730953ba82b26c74a5a06eaf8b499b'
PACKET = 'a91170746805075dddc4dcd56022cdeb2ec2c5985fe6a1478a722c1acf1135fa'
PROMPTS = {'A':'872162575df43d0a81edef6c40882b7d7112e49604ee035750f2321707c2ac44',
           'B':'a4ecfaa52c37103a5dcd1544240f55c566be0adaa433132848a9c12a90c7027a'}


def execution_hash():
    paths = ('src/application/p39_context_live.py','src/infrastructure/p39_live_context.py','scripts/p39_context_live.py')
    return digest(dict(approved_candidate_chain=source_hash(),dependencies=dependencies(),
                       files={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}))


def verify_candidate(m, fixture=False):
    body = dict(m); claim = body.pop('manifest_hash')
    if digest(body) != claim or (not fixture and claim != APPROVED) or m['processing_chain_hash'] != source_hash():
        raise ValueError('Approved candidate/source drift')
    if m['schema_hash'] != digest(wire_schema()) or m['urgency_validation_profile'] != 'urgency-context-evidence-v1':
        raise ValueError('Schema/profile drift')
    if m['inputs_hash'] != digest(m['inputs']) or len(m['inputs']) != 32 or len(m['schedule']) != 64:
        raise ValueError('Input schedule drift')
    for arm in ('A','B'):
        if m['configs'][arm]['prompt_hash'] != PROMPTS[arm] or sha256(system(arm).encode()).hexdigest() != PROMPTS[arm]:
            raise ValueError('Approved Prompt drift')
    # The only group differences are the approved arm and Prompt identity.
    configs=[]
    for arm in ('A','B'):
        c=json.loads(json.dumps(m['configs'][arm]));c.pop('prompt_hash');c.pop('prompt_version');c['parameters'].pop('arm');configs.append(c)
    if configs[0] != configs[1]:
        raise ValueError('A/B common configuration drift')
    for r in m['inputs']:
        if EmailInput.model_validate(r['email']).input_hash != r['input_hash']:
            raise ValueError('Input identity drift')


def build_runtime(m, approval, price, out, counter, fixture=False):
    verify_candidate(m,fixture);require_comparison_approval(m,approval)
    if not fixture and approval.get('decision_packet_hash') != PACKET:
        raise PermissionError('Wrong approved difference packet')
    if sha256(approval['user_approval_evidence'].encode()).hexdigest() != approval['user_approval_evidence_sha256']:
        raise PermissionError('Approval evidence drift')
    bounds=[counter.measure(messages(EmailInput.model_validate(m['inputs'][s['input_index']]['email']),s['arm'])) for s in m['schedule']]
    p=price['prices'];costs=[(b['input_token_reserve']*p['input_cny_per_million']+4000*p['output_cny_per_million'])/1e6 for b in bounds]
    if max(b['payload_bytes'] for b in bounds)>50000 or sum(costs)+.041494>10:
        raise PermissionError('Plan exceeds byte/currency caps')
    body=dict(version='p39-v2-approved-live-wiring-1',candidate=m,comparison_approval=approval,price_receipt=price,
              execution_chain_hash=execution_hash(),runtime_directory=str(Path(out).resolve()),offline_test_fixture=fixture,
              unchanged_candidate_config=True,paid_phase='smoke_only_8',payload_bounds=bounds,new64_reserve_upper_cny=sum(costs),
              smoke8_reserve_upper_cny=sum(costs[:8]),human_smoke_content_approval=None)
    body['runtime_hash']=digest(body);verify_runtime(body);return body


def verify_runtime(runtime):
    body=dict(runtime);claim=body.pop('runtime_hash')
    if digest(body)!=claim or runtime['execution_chain_hash']!=execution_hash():
        raise ValueError('Live execution identity drift')
    verify_candidate(runtime['candidate'],runtime['offline_test_fixture'])
    require_comparison_approval(runtime['candidate'],runtime['comparison_approval'])
    p=runtime['price_receipt']
    if (p['model']!='deepseek-flash' or p['prices']!={'input_cny_per_million':2,'output_cny_per_million':8}
        or not p['model_availability_verified'] or p['price_source']!='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'):
        raise ValueError('Official model/price drift: review required')
    if not runtime['offline_test_fixture']:
        checked=datetime.fromisoformat(p['checked_at'])
        if checked.tzinfo is None or not 0<=(datetime.now(timezone.utc)-checked).total_seconds()<=86400:
            raise ValueError('Price/model receipt expired')
        canonical=ROOT/'.local/p39/v2/live-delivery-v1/runtime'
        if Path(runtime['runtime_directory'])!=canonical.resolve():
            raise PermissionError('One production runtime only')


class ContextLiveAnalyzer(P39Analyzer):
    def __init__(self,settings,manifest,arm,counter,provider=None):
        super().__init__(settings,manifest,arm,counter,provider)
        self.messages=lambda email,repair=False: messages(email,arm)


class ContextLiveService(AnalysisService):
    def validate_result(self,data,email):
        result,metadata=ContextOfflineService.validate_result(self,data,email)
        runtime=self.budget.runtime()
        metadata.update(execution_chain_hash=runtime['execution_chain_hash'],runtime_hash=runtime['runtime_hash'],approved_candidate_manifest_hash=runtime['candidate']['manifest_hash'])
        return result,metadata


def write_new(path,value):
    with Path(path).open('x',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)


def run_smoke(runtime,budget,settings,provider=None):
    verify_runtime(runtime)
    from src.infrastructure.p39_live_context import ContextLiveRepository
    from src.infrastructure.context_repository import ReadOnlyContextRepository
    from dataclasses import replace
    settings=replace(settings,max_tokens=4000,max_attempts=1);settings.validate()
    out=Path(runtime['runtime_directory']);m=runtime['candidate']
    if not out.exists():out.mkdir(parents=True,exist_ok=False)
    budget.install(runtime)
    if budget.runtime()!=runtime:raise ValueError('Runtime binding mismatch')
    repo=ContextLiveRepository(out/'runs.sqlite3')
    analyzers={a:ContextLiveAnalyzer(settings,m,a,budget.counter,provider) for a in ('A','B')}
    runs=[]
    for step in m['schedule'][:8]:
        state=budget.summary()
        if state['halted'] or state['active_lease'] or state['active_wire_claim']:break
        e=EmailInput.model_validate(m['inputs'][step['input_index']]['email'])
        try:
            run=ContextLiveService(repo,analyzers[step['arm']],budget=budget).analyze(e)
            saved=ReadOnlyContextRepository(out/'runs.sqlite3').get(run.run_id)
            if saved.model_dump()!=run.model_dump():raise ValueError('SQLite reload drift')
            if saved.result:stored_context_analysis(saved)
            path=out/('run-'+run.run_id+'.json')
            if path.exists():
                if json.loads(path.read_text(encoding='utf8'))!=saved.model_dump():raise ValueError('Export drift')
            else:write_new(path,saved.model_dump())
            runs.append(saved)
            attempt=saved.attempts[-1] if saved.attempts else None
            meta=attempt.metadata if attempt else {};values=[meta.get(k) for k in ('input_tokens','output_tokens','total_tokens')]
            if saved.status!='succeeded':budget.halt('failure_requires_review');break
            if meta.get('resolved_model')!=m['configs'][step['arm']]['model_id']:
                budget.halt('resolved_model_identity_drift');break
            bound=budget.counter.measure(messages(e,step['arm']))
            hits,misses=meta.get('cache_hit_tokens'),meta.get('cache_miss_tokens')
            if (any(type(v) is not int or v<0 for v in values) or values[2]!=values[0]+values[1]
                or values[0]>bound['input_token_reserve'] or values[1]>4000 or saved.metadata.get('cost_cny') is None
                or saved.metadata['cost_cny']>meta.get('reserved_upper_cny',0)
                or type(hits) is not int or type(misses) is not int or min(hits,misses)<0 or hits+misses!=values[0]
                or meta.get('finish_reason')!='stop' or not meta.get('actual_payload_sha256') or meta.get('actual_payload_bytes',50001)>50000):
                budget.halt('usage_or_payload_anomaly');break
            print(json.dumps(dict(pair=step['pair'],arm=step['arm'],run_id=run.run_id,status=run.status,tokens=values[2],elapsed_ms=run.metadata['elapsed_ms']),ensure_ascii=False),flush=True)
        except BaseException:
            budget.halt('execution_or_storage_exception')
            raise
    state=budget.summary()
    receipt=None
    if len(runs)==8 and state['new_reserved_requests']==8 and all(r.status=='succeeded' for r in runs) and not state['halted']:
        bindings=[]
        for r in runs:
            a=r.attempts[-1];value=stored_context_analysis(r)
            bindings.append(dict(run_id=r.run_id,input_hash=r.input_hash,arm=r.config.parameters['arm'],config_hash=digest(r.config.model_dump()),
                                 output_hash=digest(value.model_dump()),raw_sha256=sha256(a.raw_output.encode()).hexdigest(),attempt_hash=digest(a.model_dump())))
        receipt=dict(version='p39-v2-smoke-receipt-1',candidate_manifest_hash=m['manifest_hash'],runtime_hash=runtime['runtime_hash'],
                     execution_chain_hash=runtime['execution_chain_hash'],comparison_approval_hash=digest(runtime['comparison_approval']),
                     price_receipt_hash=digest(runtime['price_receipt']),passed_pairs=4,new_actual_requests=8,cumulative_actual_requests=9,
                     gate='engineering_only_researcher_content_approval_required',run_bindings=bindings,budget=state,human_content_approval=None)
        receipt['receipt_hash']=digest(receipt)
        target=out/'smoke-receipt.json'
        if not target.exists():write_new(target,receipt)
        elif json.loads(target.read_text(encoding='utf8'))!=receipt:raise ValueError('Smoke receipt drift')
    result=dict(returned_runs=len(runs),budget=state,smoke_receipt_hash=receipt['receipt_hash'] if receipt else None,remaining_dispatch_allowed=False,reply_status='unreviewed_unsent')
    if not (out/'execution-result.json').exists():write_new(out/'execution-result.json',result)
    return result
