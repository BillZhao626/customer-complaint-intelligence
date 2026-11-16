"""Current service orchestration shared by controlled Web and research runs.

Reuses the R6 service, local executor, strict output provider and review projection.
No external business executor. Caller supplies a budgeted immutable invoke function.
"""
import json
from pathlib import Path
from src.domain.contracts import EmailInput, digest, idempotency_key
from src.application import service_response as service
from src.application.p5b8r1_contracts import analysis_system, parse_outcome
from src.application.p5b8_pipeline import validate_plan
from src.application.p5b8_product import make_run
from src.evaluation import owner_calibrated_judge as judge

ANALYSIS_POLICY = '''
A purchase store is not a service complaint target without evidence of its service.
Separate customer affect, experience and intent. Do not treat polite thanks as praise.
Keep exact source evidence and all current requests; resolved history is context.
Copy evidence verbatim from the original Unicode text. Preserve simplified/traditional
characters, case, punctuation and width. Never translate or normalize quoted spans.
A fault followed by now working well / so far so good is resolved history unless the customer reports a current recurrence. Do not invent a current repair request from that history.
Do not infer ownership, liability, policy, attachment receipt or authorization.
Category must be exactly one of Beauty/Personal Care, Clothing, Electronics,
Food/Beverage, Furniture, Home Appliances, Service/Other, Sports/Outdoor, unknown.
Household linens and storage containers have no dedicated category in this taxonomy:
use unknown unless an existing category genuinely fits. Never invent a category.
Stored-value card activation, balance and transaction checks belong to billing, not product repair.
Preserve separate current privacy/contact and delivery problems, even when they share a message.
Distinguish the main request from praise and incidental details. A request to verify eligibility,
availability, or policy does not authorize a booking, cancellation, payment or order change.
Treat prohibitions, data-handling preferences and quoted status messages as constraints on the
current request. Give them separate issues only when the customer actually seeks a separate remedy.
'''

def persist(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if json.loads(path.read_text('utf8'))!=value:raise ValueError('Immutable result drift: '+str(path))
    else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    return value

def generate(email,invoke,folder,*,role='DEV',arms=('DIRECT','GUIDED'),revision='v1',authorized_facts=None,semantic_planning=False):
    email=EmailInput.model_validate(email);folder=Path(folder)
    if authorized_facts is not None:
        from src.application.reply_guidance import verified_facts
        if (authorized_facts.get('status') not in ('KNOWN','UNKNOWN')
            or any(f.get('input_hash')!=email.input_hash or f.get('authority')!='AUTHORIZED_FIXTURE'
                   for f in authorized_facts.get('facts',[]))
            or (authorized_facts['status']=='KNOWN' and not verified_facts(email,authorized_facts))):
            raise ValueError('Invalid case-scoped authorized fixture facts')
    base=dict(case_id=email.email_id,input_hash=email.input_hash,dataset_role=role,revision=revision,
              planning_mode='EXPERIMENTAL_SEMANTIC_OPT_IN' if semantic_planning else 'SOURCE_BOUND_DETERMINISTIC')
    a=invoke('ANALYSIS',[('system',analysis_system()+ANALYSIS_POLICY),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(base,stage='analysis'))
    parsed=parse_outcome(a['raw'],email=email,metadata=a['metadata']);analysis=parsed['value']
    persist(folder/'analysis.json',dict(call=a,parse=parsed))
    results={}
    for arm in arms:
        plan_error=None;service_plan=None;service_plan_call=None;plan_scope_exclusions=[]
        if arm=='DIRECT':
            p=invoke('DIRECT-PLAN',[('system',service.PLANNER_SYSTEM),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(base,stage='plan',arm=arm))
            try:actions=validate_plan(p['raw'],email)
            except (ValueError,TypeError,KeyError,AssertionError) as ex:actions=[];plan_error=str(ex)
            persist(folder/'direct-plan.json',dict(call=p,actions=actions,error=plan_error))
            actions=service.reconcile_plan(email,actions)
        else:
            actions=service.plan_actions(analysis,email=email)
            baseline_actions=actions
            if semantic_planning:
                from src.application import service_plan as planning
                service_plan_call=invoke('GUIDED-PLAN',planning.messages(email,analysis,actions,authorized_facts or dict(status='UNKNOWN')),
                    dict(base,stage='service_plan',arm=arm,service_planner=planning.identity(),parent_run_id=a['run_id'],
                         strict_output_contract=dict(name='plan_service',schema=planning.transport_schema(email,analysis))))
                try:
                    service_plan,plan_scope_exclusions=planning.enforce_scope(planning.parse(service_plan_call['raw'],email,analysis),email,analysis)
                    actions=service.reconcile_plan(email,service_plan['actions'])
                except (ValueError,TypeError,KeyError,AssertionError) as ex:
                    plan_error=type(ex).__name__+': '+str(ex)
                    # A failed advisory plan must not erase the established
                    # source-bound workflow. Keep a conservative local plan,
                    # but retain failure/fallback identity and forbid approval.
                    actions=baseline_actions
                persist(folder/'service-plan.json',dict(call=service_plan_call,value=service_plan,error=plan_error,scope_exclusions=plan_scope_exclusions,identity=planning.identity()))
        runtime_path=folder/(arm+'-runtime.json')
        if runtime_path.exists():
            runtime=json.loads(runtime_path.read_text('utf8'))
            if authorized_facts is not None and runtime['facts']!=authorized_facts:
                raise ValueError('Frozen facts drift in saved runtime')
        else:
            runtime=service.execute(email,actions,folder/arm/'actions.sqlite3',execution_scope=dict(case_id=email.email_id,revision=revision,arm=arm))
            if authorized_facts is not None:
                runtime['facts']=authorized_facts
            if service_plan is not None:runtime['service_plan']=service_plan
            if plan_error:
                runtime['service_plan_error']=plan_error
                runtime['planning_fallback']='DETERMINISTIC_SOURCE_BOUND_REVIEW_REQUIRED'
            persist(runtime_path,runtime)
        c=invoke(arm+'-REPLY',service.chain_messages(email,runtime,analysis if arm=='GUIDED' else None),dict(base,stage='reply',arm=arm,parent_run_id=(service_plan_call or a)['run_id'],strict_reply_contract=True,runtime=runtime,composer=service.identity()))
        result=parse_outcome(c['raw'],metadata=c['metadata']);reply=result['value']['reply'] if result['value'] else ''
        slot=dict(case_id=email.email_id,input_hash=email.input_hash,run_id=c['run_id'],arm=arm,parse_ok=result['semantic_eligible'],reply=reply,facts=runtime['facts'],attachment_manifest=[])
        slot['events']=judge.bind(runtime['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
        guard=judge.audit_slot(slot,email) if reply else dict(findings=[],structure_failed=True)
        record=dict(email=email.model_dump(),analysis=analysis,analysis_call=a,analysis_parse=parsed,call=c,parse=result,slot=slot,runtime=runtime,plan=actions,plan_error=plan_error,service_plan_call=service_plan_call,guard=guard,service_brief=service.composition_brief(email,runtime,analysis if arm=='GUIDED' else None),composer=service.identity(),dataset_role=role)
        persist(folder/(arm+'-reply.json'),record);results[arm]=record
    return results

def product_run(record):
    r=record
    case=dict(email=r['email'],analysis=dict(data=r['analysis'],call=r['analysis_call'],error=r['analysis_parse']['error']),replies={'A_GUIDED':dict(reply=r['slot']['reply'],runtime=r['runtime'],call=r['call'],error=r.get('plan_error') or r['parse']['error'])},dataset_role=r['dataset_role'],annotation_status='AI_PROVISIONAL_NOT_HUMAN_GOLD')
    if r.get('plan_error'):
        # Full valid analysis remains in the immutable trace; the product must
        # not offer approval of a chain whose business plan failed validation.
        case['analysis'].update(data=None,error='Service planning failed: '+r['plan_error'])
    run=make_run(case)
    config=run.config.model_copy(update=dict(prompt_version=r['composer']['version'],parameters=dict(run.config.parameters,experiment='p5b8r6',arm=r['slot']['arm'],current_experiment='R6-U0',contract='strict-tool-arguments')))
    return run.model_copy(update=dict(config=config,cohort_id=config.cohort_id,idempotency_key=idempotency_key(run.email,config)))
