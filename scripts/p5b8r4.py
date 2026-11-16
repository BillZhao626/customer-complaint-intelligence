"""R4 read-only evidence audit and opt-in execution over the existing dispatcher.

Default is offline. All derived material goes to a new R4 version directory.
No historical writer, SMTP client or business connector is called.
"""
import argparse,copy,csv,hashlib,json,os,sqlite3,sys
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.domain.contracts import EmailInput,digest
from src.application.p5b8r3_final_guard import assess
from src.application.p5b8r4_contracts import parse_reply
from src.application import p5b8r4_reply as composer
from src.evaluation import p5b8r4_judge as judge

DOC=ROOT/'docs/p5b8r4';LOCAL=ROOT/'.local/p5b8r4'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def dump(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
def block(value):return '\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n'
def text_hash(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

POLICIES={
 'B7-036':('GUIDED',['受损即道歉，即使情绪中性','少复述损坏细节','安全建议、请求提供已拍照片','有据推进售后物流'],['不得声称已收到或已阅照片']),
 'B7-084':('COMBINE',['感谢混合反馈、保留专业知识','尊重已完成排查','核实到店售后、不着急仍跟进'],['产品咨询回执不能证明表扬转达','无安排不承诺回访']),
 'B7-035':('DIRECT',['Direct结构、周六前期限及加急思路','增强诚恳态度','保留Guided已有high-priority事实'],['不得保证次日补发或售后完成']),
 'B7-009':('DIRECT',['真诚感谢、真实办理表扬转达','历史耳机问题已解决、友善祝福'],['不得虚构考核奖励','不得假设历史故障复发']),
 'B7-010':('DIRECT',['直接自然、记录并真实转达','适当祝使用愉快'],['不得无任务声称已登记','不机械解释内部流程']),
 'B7-085':('GUIDED',['先核查收费依据、票据及是否告知','肯定店员产品正面反馈'],['未请求退款不反复强调未批准','不得无凭据承诺退款']),
}

def history():
    results=[];calls=[];seen=set()
    for run in [ROOT/'.local/p5b8r3'/x for x in ('live-v1','live-v2','live-v3','live-v4','quality-final-v1')]:
        for p in (run/'results').glob('*.json'):
            row=read(p);rid=row.get('call',{}).get('run_id')
            if rid and rid not in seen and row['call'].get('mode')=='LIVE':
                seen.add(rid);results.append((p,row))
        for p in (run/'calls').glob('*/frozen-input.json'):
            row=read(p)
            if row.get('mode')=='LIVE':calls.append((p,row))
    return results,calls

def overlay(calls):
    goldpath=ROOT/'docs/p5b8r3/prepared-v4/GOLD16_READONLY_COPY.json';gold=read(goldpath)
    raw={r['case_id']:r for r in map(json.loads,(ROOT/'docs/p5b8r2/RAW_EVIDENCE.jsonl').read_text('utf-8').splitlines())}
    cal_calls=[(p,c) for p,c in calls if c['identity'].startswith('CAL-')]
    earlier=[]
    for phase in ('p5b5-live-20261030-v1','p5b5r2'):
        for p in (ROOT/'.local'/phase/'judge').glob('*/frozen-input.json'):
            earlier.append((p,read(p)))
    def participation(body):
        return [dict(identity=c['identity'],run_id=c['run_id'],source=rel(p)) for p,c in cal_calls if c.get('payload',{}).get('blind_payload',{}).get('customer',{}).get('body')==body]
    def earlier_participation(g):
        return [dict(source=rel(p),run_id=c.get('run_id'),identity=p.parent.name,kind='REFERENCE_EXPOSED_DEV_SCORING_OR_CONTROL_NOT_HUMAN_AGREEMENT',
                     raw_response_available=(p.parent/'provider-response.txt').exists()) for p,c in earlier
                if c.get('payload',{}).get('reference')==g['reference_reply'] or
                any(m.get('text')==g['display_input'] for m in c.get('payload',{}).get('customer_context',[]) if isinstance(m,dict))]
    rows=[]
    accepted=read(ROOT/'docs/p5q/owner_accepted_references_v1.json')['anchors']
    for g in gold:
        exact=g['reference_status']=='OWNER_PREVIOUSLY_ACCEPTED_VERBATIM'
        if exact:
            a=next(a for a in accepted if a['id']==g['history_anchor_id'])
            if a['reply']!=g['reference_reply']:raise ValueError('Verbatim owner reference drift')
        rows.append(dict(case_id=g['case_id'],task='REPLY_REFERENCE',text_hash=text_hash(g['display_input']),reference_hash=text_hash(g['reference_reply']),
            original_decision_excerpt=g.get('owner_acceptance_of_principles'),source=rel(goldpath)+'#'+g['case_id'],source_sha256=sha(goldpath),
            annotation_owner='OWNER_HISTORICAL_VERBATIM' if exact else 'OWNER_PRINCIPLES_ASSISTANT_DRAFT',
            owner_approved_exact_text=exact,owner_semantic_policy=True,assistant_drafted_reference=not exact,human_numeric_score_available=False,
            required_points=g.get('required_points',[]),forbidden_claims=g['forbidden_claims'],known_good='CONDITIONAL_OWNER_TEXT' if exact else 'OWNER_NOT_SPECIFIED',known_bad='OWNER_NOT_SPECIFIED',
            owner_preference='OWNER_NOT_SPECIFIED',business_action_preconditions=g.get('tool_event_preconditions',g.get('reply_preconditions')),
            dataset_role='EXPOSED_DEV_REPLY_REFERENCE',semantic_family=g['scenario_family'],family_leakage=True,
            historical_calibration_calls=participation(g['display_input']),earlier_dev_judge_uses=earlier_participation(g),r4_live_calibration_n=0,r4_offline_use='RULE_AUDIT_ONLY',
            offline_reference_audit=assess(g['reference_reply'],dict(events=[]),g['input_sha256']),reference_text=g['reference_reply']))
    policypath=ROOT/'docs/p5b8r2/OWNER_POLICY_v2.md'
    for cid,(pref,required,forbidden) in POLICIES.items():
        source=raw[cid]['source'];email=EmailInput.model_validate(source['email'])
        rows.append(dict(case_id=cid,task='REPLY_QUALITATIVE_POLICY',text_hash=text_hash(email.body),input_hash=email.input_hash,
            source=rel(policypath)+'#'+cid,source_sha256=sha(policypath),original_decision_excerpt=next(l for l in policypath.read_text('utf-8').splitlines() if '**'+cid+'**' in l),
            current_authority='.local/p5b8r4/attachment-0.txt §3 (user explicitly requested execution)',annotation_owner='OWNER_QUALITATIVE_POLICY_VIA_AUTHORIZED_ATTACHMENT',
            owner_approved_exact_text=False,owner_semantic_policy=True,assistant_drafted_reference=False,human_numeric_score_available=False,
            required_points=required,forbidden_claims=forbidden,known_good='OWNER_NOT_SPECIFIED',known_bad='UNSUPPORTED_EXECUTION_FORBIDDEN',owner_preference=pref,
            business_action_preconditions='Own case/run/arm/input + event kind/goal/state; external completion requires authority',dataset_role='EXPOSED_DEV_POLICY',family_leakage=True,
            historical_calibration_calls=participation(email.body),r4_live_calibration_n=0,r4_offline_use='POLICY_MIGRATION_AND_CONTEXT_PREPARATION'))
    cls=read(ROOT/'.local/p35/calibration-decision-v1.1/snapshot.json')
    for r in cls['records']:
        rows.append(dict(case_id=r['sample_id'],task='SEVEN_FIELD_CLASSIFICATION',text_hash=r['input_hash'],source='.local/p35/calibration-decision-v1.1/snapshot.json#'+r['sample_id'],
            annotation_owner='RESEARCH_OWNER_REVIEWED_AI_ASSISTED',owner_approved_exact_text=False,owner_semantic_policy=False,assistant_drafted_reference=True,
            human_numeric_score_available=False,owner_preference='NOT_APPLICABLE',dataset_role='EXPOSED_CLASSIFICATION_DEV_NOT_REPLY_GOLD',
            required_points=[],forbidden_claims=[],known_good='NOT_REPLY_GOLD',known_bad='OWNER_NOT_SPECIFIED',business_action_preconditions='NOT_APPLICABLE',family_leakage=True,r4_live_calibration_n=0))
    cp=ROOT/'data/golden/golden_labels_review_sample_v1_reviewed.csv'
    with cp.open(encoding='utf-8-sig') as f:
        classification=list(csv.DictReader(f))
    for index,r in enumerate(classification):
        rows.append(dict(case_id=r.get('email_id',r.get('sample_id',str(index+1))),task='LEGACY_CLASSIFICATION_REFERENCE',text_hash=digest(r),source=rel(cp)+':'+str(index+2),
            annotation_owner='PROJECT_REVIEWED_REFERENCE_NOT_INDEPENDENT_HUMAN',owner_approved_exact_text=False,owner_semantic_policy=False,assistant_drafted_reference=False,
            human_numeric_score_available=False,dataset_role='CLASSIFICATION_ONLY',owner_preference='NOT_APPLICABLE',r4_live_calibration_n=0))
    b4=[json.loads(l) for l in (ROOT/'docs/p5b4/GOLD_CANDIDATE.jsonl').read_text('utf-8').splitlines()]
    for r in b4:
        rows.append(dict(case_id=r['case_id'],task='B4_REPLY_CANDIDATE',text_hash=digest(r['input_email']),source='docs/p5b4/GOLD_CANDIDATE.jsonl#'+r['case_id'],
            annotation_owner=r['author'],owner_approved_exact_text=False,owner_semantic_policy=False,assistant_drafted_reference=True,human_numeric_score_available=False,
            dataset_role=r['review_state'],reviewer=r['reviewer'],owner_preference='OWNER_NOT_SPECIFIED',r4_live_calibration_n=0))
    summary=dict(reply_references=len(gold),exact_owner_text=sum(r['owner_approved_exact_text'] for r in rows),assistant_drafted_reply_reference=13,
                 owner_policy_cases=6,classification_owner_assisted=len(cls['records']),classification_legacy=len(classification),b4_candidates=len(b4),
                 b4_distinct_threads=len({r['thread_id'] for r in b4}),historical_calibration_requests=len(cal_calls),
                 r3_gold16_cases_used=sum(bool(r['historical_calibration_calls']) for r in rows if r['task']=='REPLY_REFERENCE'),
                 earlier_gold16_cases_used=sum(bool(r['earlier_dev_judge_uses']) for r in rows if r['task']=='REPLY_REFERENCE'),
                 historical_owner6_cases_used=sum(bool(r['historical_calibration_calls']) for r in rows if r['task']=='REPLY_QUALITATIVE_POLICY'),
                 r4_new_model_calibration_requests=0,r4_human_numeric_n=0,human_numeric_status='HUMAN_NUMERIC_UNAVAILABLE',kappa=None,
                 near_30_claim='No distinct source-backed set of approximately 30 signed reply judgments identified; 28 B4 candidate turns are not signed replies.',
                 public_benchmarks='NOT_PROJECT_GOLD; no external dataset label imported',source_gold16_file=gold[0].get('source_file'),
                 source_gold16_file_exists=Path(gold[0].get('source_file','nonexistent')).is_file())
    summary['historical_calibration_responses']=sum((p.parent/'response.json').exists() for p,c in cal_calls)
    summary['source_gold16_file_sha256']=sha(Path(summary['source_gold16_file'])) if summary['source_gold16_file_exists'] else None
    public_path=ROOT/'docs/external_dataset_reference_review_v1.md'
    for name in ('Amazon Reviews / Amazon Customer Review Datasets','CFPB Consumer Complaint Database','Bitext Customer Support Dataset','Generic Customer Support Ticket Datasets'):
        rows.append(dict(case_id='PUBLIC_REFERENCE:'+name,task='PUBLIC_RESOURCE_REFERENCE',text_hash=sha(public_path),source=rel(public_path)+'#'+name,
                         annotation_owner='PUBLIC_RESOURCE_NOT_PROJECT_OWNER',owner_approved_exact_text=False,owner_semantic_policy=False,assistant_drafted_reference=False,
                         human_numeric_score_available=False,dataset_role='TAXONOMY_OR_STYLE_REFERENCE_NOT_PROJECT_GOLD',owner_preference='NOT_APPLICABLE',r4_live_calibration_n=0,
                         original_decision_excerpt='Existing project review explicitly says these resources cannot replace this retail-email task Gold.',imported_records=0))
    summary['public_resource_groups_reviewed']=4
    for r in rows:
        for k,v in dict(required_points=[],forbidden_claims=[],known_good='OWNER_NOT_SPECIFIED',known_bad='OWNER_NOT_SPECIFIED',business_action_preconditions='OWNER_NOT_SPECIFIED',family_leakage=True,original_decision_excerpt='OWNER_NOT_SPECIFIED').items():r.setdefault(k,v)
    dump(DOC/'evidence/annotation-overlay.json',dict(summary=summary,records=rows));return summary,rows,raw

def controls():
    """Balanced developer controls; no simulated numerical scores enter quality metrics."""
    from tests.test_p5b8r4 import fixture
    specs=[('relay_good','已创建内部表扬转达请求。','store_service_request','created','转达表扬谢意',False),
           ('relay_product_mismatch','已创建内部表扬转达请求。','human_input_request','created','核实水箱原因',True),
           ('relay_same_kind_wrong_goal','已创建内部表扬转达请求。','store_service_request','created','核实收费依据',True),
           ('product_good','已创建水箱咨询请求。','human_input_request','created','核实水箱渗水原因',False),
           ('billing_good','已创建收费核实请求。','billing_request','created','核实收费依据',False),
           ('logistics_good','已提交物流核实请求。','logistics_followup','created','核实物流进度',False),
           ('relay_completed_fake','已转达您的谢意。','store_service_request','created','转达表扬谢意',True),
           ('refund_fake','已为您退款。','aftersales_request','created','核实退款条件',True),
           ('arrival_fake','包裹已到货。','logistics_followup','executed','查询物流进度',True),
           ('photo_received_fake','我们已收到照片。','human_input_request','created','核实水箱原因',True),
           ('photo_viewed_fake','我们已查看照片。','human_input_request','created','核实水箱原因',True),
           ('condition_good','如果需要，可以请售后核实退款条件。','aftersales_request','requested','核实退款条件',False),
           ('negation_good','尚未退款。','aftersales_request','requested','核实退款条件',False),
           ('english_condition_good','If needed, we can request a refund review.','aftersales_request','requested','refund review',False),
           ('english_refund_fake','We have refunded your payment.','aftersales_request','created','refund review',True),
           ('english_relay_good','We have created a praise relay request.','store_service_request','created','relay praise and thanks',False),
           ('english_relay_fake','We have relayed your thanks.','store_service_request','created','relay thanks',True),
           ('taken_good','请提供已拍好的照片。','human_input_request','created','核实产品问题',False),
           ('sent_good','您说已发送照片，可以先核实接收情况。','human_input_request','created','核实产品问题',False),
           ('long_conditional_good','感谢您的耐心说明。如果需要，可以请售后核实退款条件。现有信息还不足以确认条件，请保留已有票据。','aftersales_request','requested','核实退款条件',False)]
    for state in ('requested','assigned','completed','failed','unknown'):
        specs.append(('relay_state_'+state,'已创建内部表扬转达请求。','store_service_request',state,'转达表扬谢意',state not in ('assigned','completed')))
    results=[]
    for name,reply,kind,state,goal,hard in specs:
        email,s=fixture(kind=kind,status=state,goal=goal,reply=reply)
        out=judge.audit_slot(s);blocked=any(f['severity']=='block' for f in out['findings'])
        results.append(dict(id=name,expected_hard=hard,detected_hard=blocked,correct=hard==blocked,identity='DEVELOPER_FACT_CONTROL_NOT_OWNER_NUMERIC',
                            customer=email.model_dump(),slot=s,audit=out,input_hash=email.input_hash,control_hash=digest(s)))
    matrix=Counter(('TP' if r['detected_hard'] else 'FN') if r['expected_hard'] else ('FP' if r['detected_hard'] else 'TN') for r in results)
    summary=dict(n=len(results),confusion={k:matrix[k] for k in ('TP','FN','FP','TN')},normal_n=sum(not r['expected_hard'] for r in results),
                 hard_n=sum(r['expected_hard'] for r in results),unknown_n=0,not_applicable_n=0,identity='DETERMINISTIC_DEVELOPER_CONTROLS_NOT_LLM_CALIBRATION',
                 new_judge_AB_BA=dict(status='AUTHORIZATION_BLOCKED',n=0),new_judge_repeat=dict(status='AUTHORIZATION_BLOCKED',n=0),owner_direction=dict(status='AUTHORIZATION_BLOCKED',n=0))
    dump(DOC/'evidence/fact-controls.json',dict(summary=summary,rows=results));return summary,results

def structure(results):
    rows=[]
    for p,r in results:
        c=r['call'];parsed=parse_reply(c['raw'],c['metadata']);wire=p.parent.parent/'calls'/digest(c['identity'])/'wire-request.json'
        request=read(wire) if wire.exists() else None
        error=parsed['first']['error'] or ''
        failure='NONE' if parsed['first']['status']=='accepted' else 'SCHEMA_EXTRA_FIELD' if 'extra_forbidden' in error else 'JSON_TRAILING_DATA' if 'Extra data' in error else 'JSON_SYNTAX'
        rows.append(dict(identity=c['identity'],run_id=c['run_id'],source=rel(p),raw_hash=digest(c['raw']),raw=c['raw'],metadata=c['metadata'],parsed=parsed,
                         defect=failure,wire_source=rel(wire) if wire.exists() else None,wire_sha256=sha(wire) if wire.exists() else None,
                         response_format=request.get('response_format') if request else None,max_tokens=request.get('max_tokens') if request else None,
                         system_json_instruction=bool(request and 'json' in request['messages'][0]['content'].lower())))
    summary=dict(attempted=len(rows),first_valid=sum(r['parsed']['first']['status']=='accepted' for r in rows),
                 defects=dict(Counter(r['defect'] for r in rows)),local_recovery=sum(r['parsed']['recovery'] is not None for r in rows),
                 failures_finish_reason=dict(Counter(r['metadata'].get('finish_reason') for r in rows if r['defect']!='NONE')),
                 actual_wire_available=sum(r['wire_source'] is not None for r in rows),r4_new_first_reply_n=0,r4_first_rate=None,
                 official_source='https://api-docs.deepseek.com/guides/json_mode/',official_verified_on='2026-11-02',
                 interpretation='json_object mode, json keyword, example, max_tokens required; JSON mode does not enforce Reply field whitelist. stop alone does not prove complete valid output.')
    dump(DOC/'evidence/structure-audit.json',dict(summary=summary,rows=rows));return summary,rows

def prepare(raw,control_rows):
    targets=[]
    for cid in POLICIES:
        source=raw[cid]['source'];email=EmailInput.model_validate(source['email'])
        # Historical records are comparison baselines only. Live execution below
        # starts each new arm in its own empty ActionStore.
        historical=next((r for _,r in history()[0] if r['customer']['email_id']==cid and r['slot']['arm']=='GUIDED'),None)
        if historical is None:
            historical=next(r for _,r in history()[0] if r['customer']['email_id']==cid)
        targets.append(dict(case_id=cid,email=email.model_dump(),input_hash=email.input_hash,source=source,
                            historical_baseline=historical,new_state_policy='NEW_OWN_ARM_EMPTY_STORE; historical receipts never dispatched as new evidence'))
    # Three order/repetition calls per owner pair, and three per fact-control pair.
    controls_to_run=control_rows[:10]
    ids=[f'{stage}-{t["case_id"]}-{arm}' for t in targets for arm in ('DIRECT','GUIDED') for stage in ('PLAN','REPLY')]+[f'JUDGE-{t["case_id"]}-{order}' for t in targets for order in ('AB','BA','REPEAT')]+[f'CAL-{t["id"]}-{order}' for t in controls_to_run for order in ('AB','BA','REPEAT')]
    plan=dict(version='p5b8r4-frozen-dev-1',authorization_scope='P5-B8-R4-DEV',planned_requests=len(ids),allowed_call_ids=ids,proposed_cny_cap=10,
              pricing=dict(input_cny_per_million=3,output_cny_per_million=12),pricing_status='CONSERVATIVE_CNY_RESERVATION_BOUND_REQUIRES_AUTHORIZATION_ACCEPTANCE',
              official_pricing=dict(url='https://api-docs.deepseek.com/quick_start/pricing/',checked_on='2026-11-02',peak_input_usd_per_million=.3,peak_output_usd_per_million=1.2,
                                    conversion='Reservation assumes at most 10 CNY/USD; not a claim about exchange rate or actual charge'),
              composer=composer.identity(),judge=judge.identity(),targets=targets,controls=controls_to_run,
              independent=dict(status='NOT_RUN',exposure='R3N and old24 are DEV for R4',new_text_created=False,requirement='Separate authorization and frozen semantic-family protocol before new independent collection'),
              permissions=dict(external_business_execution=False,paid_authorization=None,unknown_retry=False,first_attempt_only=True))
    dump(DOC/'evidence/prepared-plan.json',plan)
    sources={rel(p):sha(p) for folder in ('src','tests','scripts') for p in (ROOT/folder).glob('*p5b8r4*.py')}
    sources.update({rel(p):sha(p) for folder in ('src/application','src/evaluation','src/infrastructure') for p in (ROOT/folder).glob('*p5b8r4*.py')})
    for n in ('src/application/p5b8r1_guard.py','src/application/p5b8r3_final_guard.py','src/evaluation/p5b8r3_judge.py','src/infrastructure/p5b8r3_execution.py'):
        sources[n]=sha(ROOT/n)
    dump(DOC/'evidence/freeze.json',dict(at=datetime.now(timezone.utc).isoformat(),plan_hash=digest(plan),sources=sources,new_independent_seen_n=0,stage='DEV_CANDIDATE_NOT_PROMOTED'))
    return plan,targets

def run_plan(plan,dispatcher):
    """Execute only the predeclared requests; never choose a better retry."""
    from src.application.p5b8r3_experiment import save
    from src.application.p5b8r1_contracts import analysis_system,parse_outcome
    from src.application.p5b8r4_actions import guided_actions
    from src.application.p5b8_pipeline import execute,validate_plan
    root=dispatcher.root
    def evaluate(identity,email,slots,reverse=False):
        payload,key=judge.blind_pair(email,slots,reverse=reverse)
        call=dispatcher.call(identity,[('system',judge.SYSTEM),('human',json.dumps(payload,ensure_ascii=False))],dict(blind_payload=payload))
        try:parsed=judge.parse(call['raw'],payload);error=None
        except (ValueError,TypeError,KeyError) as exc:parsed=None;error=str(exc)
        row=dict(call=call,payload=payload,key=key,parsed=parsed,error=error)
        save(root/'judgments'/(identity+'.json'),row)
        return row
    control_checks=[]
    for row in plan['controls']:
        email=EmailInput.model_validate(row['customer']);a=row['slot'];b=copy.deepcopy(a)
        b.update(run_id='control-proposal-'+row['id'],arm='PROPOSAL',reply='如果需要，可以请同事进一步核实。',events=[])
        for order in ('AB','BA','REPEAT'):
            result=evaluate('CAL-'+row['id']+'-'+order,email,[a,b],order=='BA')
            parsed=result['parsed'];source_slot=next((label for label,key in result['key'].items() if key['arm']==a['arm']),None)
            answer=next((x for x in parsed['answers'] if x['slot']==source_slot),None) if parsed else None
            detected=any(f['category']=='HARD_ERROR' for f in answer['findings']) if answer else None
            control_checks.append(dict(id=row['id'],order=order,expected_hard=row['expected_hard'],detected_hard=detected,correct=detected==row['expected_hard'] if answer else False))
    save(root/'control-checks.json',dict(rows=control_checks,mode=dispatcher.mode))
    if dispatcher.mode=='LIVE' and not all(c['correct'] for c in control_checks):
        dispatcher.halt('R4_JUDGE_CALIBRATION_FAILED_NO_DEV_DISPATCH');return
    for target in plan['targets']:
        email=EmailInput.model_validate(target['email']);slots=[]
        for arm in ('DIRECT','GUIDED'):
            planner_id='PLAN-'+email.email_id+'-'+arm
            system=composer.PLANNER_SYSTEM if arm=='DIRECT' else analysis_system()
            planning=dispatcher.call(planner_id,[('system',system),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(stage='PLAN',arm=arm,customer=email.model_dump()))
            analysis=None;planning_error=None
            try:
                if arm=='DIRECT':actions=validate_plan(planning['raw'],email)
                else:
                    outcome=parse_outcome(planning['raw'],email=email,metadata=planning['metadata'])
                    if not outcome['semantic_eligible']:raise ValueError(outcome['error'])
                    analysis=outcome['value'];actions=guided_actions(analysis)
            except (ValueError,TypeError,KeyError,AssertionError) as exc:actions=[];planning_error=str(exc)
            save(root/'plans'/(planner_id+'.json'),dict(call=planning,analysis=analysis,actions=actions,error=planning_error))
            runtime=execute(email,actions,root/'state'/(email.email_id+'-'+arm)/'actions.sqlite3')
            save(root/'runtime'/(planner_id+'.json'),runtime)
            identity='REPLY-'+email.email_id+'-'+arm
            call=dispatcher.call(identity,composer.chain_messages(email,runtime,analysis),dict(customer=email.model_dump(),runtime=runtime,runtime_role='NEW_OWN_ARM_LOCAL_STORE',planner_run=planning['run_id']))
            parsed=parse_reply(call['raw'],call['metadata']);value=parsed['first']['value']
            slot=dict(case_id=email.email_id,run_id=call['run_id'],arm=arm,input_hash=email.input_hash,parse_ok=parsed['first']['semantic_eligible'],reply=value['reply'] if value else '',events=[])
            slot['events']=judge.previous.bind(runtime['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
            save(root/'results'/(identity+'.json'),dict(call=call,parse=parsed,slot=slot,customer=email.model_dump(),runtime=runtime))
            slots.append(slot)
        for order in ('AB','BA','REPEAT'):
            identity='JUDGE-'+email.email_id+'-'+order
            if not all(s['parse_ok'] for s in slots):save(root/'judgments'/(identity+'.json'),dict(status='UNSCORABLE_FIRST_STRUCTURE',planned=True,dispatched=False))
            else:evaluate(identity,email,slots,order=='BA')
    dispatcher.halt('R4_DEV_COMPLETED_NO_REUSE')

def live(authorization):
    plan=read(DOC/'evidence/prepared-plan.json')
    # All denials occur before Provider construction or any ledger side effect.
    if authorization is None:raise PermissionError('AUTHORIZATION_BLOCKED: R4 has no new CNY/request authorization')
    auth=read(authorization)
    if auth.get('scope')!='P5-B8-R4-DEV' or auth.get('plan_hash')!=digest(plan):raise PermissionError('R4 authorization identity mismatch')
    if not auth.get('accepts_reservation_price_bound'):raise PermissionError('CNY reservation price bound must be explicitly accepted for new authorization')
    freeze=read(DOC/'evidence/freeze.json')
    if freeze['plan_hash']!=digest(plan) or any(sha(ROOT/n)!=h for n,h in freeze['sources'].items()):raise PermissionError('Frozen implementation drift')
    from src.infrastructure.p5b8r3_execution import Dispatcher,LangChainProvider
    # Dispatcher checks scope, plan hash, positive CNY, request count, parent caps.
    dispatcher=Dispatcher(LOCAL/'new-authorized-live',plan,authorization=auth,mode='LIVE')
    dispatcher.provider=LangChainProvider()
    run_plan(plan,dispatcher)

def audit():
    DOC.mkdir(parents=True,exist_ok=True)
    results,calls=history();os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false')
    summary,annotations,raw=overlay(calls);cm,control_rows=controls();st,structure_rows=structure(results);plan,targets=prepare(raw,control_rows)
    dump(DOC/'evidence/summary.json',dict(owner=summary,controls=cm,structure=st,real_requests=0,cost_cny=0,semantic_improvement='UNKNOWN',plan_hash=digest(plan)))
    print(json.dumps(dict(owner=summary,controls=cm,structure=st,planned_requests=plan['planned_requests']),ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');ap.add_argument('--authorization',type=Path)
    args=ap.parse_args()
    if args.live:live(args.authorization)
    else:audit()
