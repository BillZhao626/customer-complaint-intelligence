"""R1 action-state calibration over inherited product gates, no executors."""
import re,copy
from src.domain.contracts import digest
from src.application.p5b8_product import quality as previous_quality
from src.evaluation.p5b5r2_judge import SCOPES
VERSION='p5b8r1-action-states-2-r4-scoped-creation'
SCOPES_R1={**SCOPES,'store':(r'门店|店员|store|staff|thanks|表扬|谢意',{'store_service_request','feedback_request'})}
def valid(events,input_hash,statuses):
    return [e for e in events if e.get('event_id') and e.get('input_hash')==input_hash and e.get('kind') and e.get('status') in statuses]
def creation_supported(text,runtime,h):
    from src.application.p5b8r4_evidence import creation_support
    return creation_support(text,runtime,h)
def completed_supported(runtime,h):
    events=valid(runtime.get('events',[]),h,{'completed','executed'})
    found=[e for e in events if e['kind']=='feedback_relay' and e.get('payload',{}).get('external_execution') is True and e['payload'].get('result',{}).get('status')=='SUCCEEDED' and e['payload']['result'].get('authority') in ('AUTHORIZED_FIXTURE','VERIFIED_CONNECTOR') and e['payload']['result'].get('source_id')]
    return bool(found),[e['event_id'] for e in found]
def future_supported(runtime,h):
    cap=runtime.get('capabilities',{}).get('customer_reply',{})
    events=valid(runtime.get('events',[]),h,{'scheduled'})
    found=[e for e in events if e['kind']=='support_followup' and all(e.get('payload',{}).get('action',{}).get(k) for k in ('owner','deadline','executor')) and e['payload']['action'].get('executor')==cap.get('executor') and e['payload'].get('result',{}).get('status')=='SCHEDULED' and e['payload']['result'].get('authority') in ('AUTHORIZED_FIXTURE','VERIFIED_CONNECTOR')]
    return bool(cap.get('enabled') is True and cap.get('authorized') is True and cap.get('executor') and found),[e['event_id'] for e in found]
def audit_supported(runtime,h):
    return [x for x in runtime.get('audit_records',[]) if x.get('record_id') and x.get('input_hash')==h and len(x.get('artifact_sha256',''))==64 and x.get('phase')=='before_provider']

def assess(reply,runtime,h):
    assessments=[];findings=[]
    def add(state,quote,supported,ids=(),code=None,reason=''):
        a=dict(state=state,quote=quote,supported=supported,event_ids=list(ids),reason=reason);assessments.append(a)
        if code:findings.append(dict(code=code,quote=quote,reason=reason,severity='review' if code.endswith('_REVIEW') else 'block',scope='reply',finding_id=digest(a)))
    for segment in re.split(r'[。！？!?;；\n]|\bbut\b|但是|不过',reply or ''):
        def negated(m):return bool(re.search(r'尚未|没有|并未|不能|无法|如果|假设|\b(?:not|never|if)\b',segment[max(0,m.start()-14):m.start()],re.I))
        tasks=re.finditer(r'(?:已(?:经)?).{0,14}(?:登记|创建|提交).{0,24}(?:请求|任务|工单|待办)|已(?:经)?(?:为您)?建单|(?:请求|任务|工单).{0,8}已(?:经)?(?:登记|创建|提交)|(?:I|we)(?: have|.ve)?\s+(?:also\s+)?(?:opened|logged|created|submitted|filed)[^.]{0,35}(?:request|task|ticket|case)|\b(?:an?|the) [^.]{0,100}?\b(?:request|task|ticket)\b[^.]{0,110}?\b(?:has been|was) (?:created|opened|logged|submitted)\b',segment,re.I)
        for task in tasks:
            if negated(task):continue
            ok,ids=creation_supported(task.group(),runtime,h);add('INTERNAL_CREATED',task.group(),ok,ids,None if ok else 'H04','Current-input created task required; plans and UNKNOWN lookups do not establish creation.')
        # 已有购买记录 denotes existing evidence, not a recording action.
        record=re.search(r'(?:已(?!经?有)(?:经)?(?:(?!提交|创建|转交|转达|联系).){0,14}记录(?:了)?|记录了)(?:(?!并|会|将|转交|转达|联系)[^，,]){0,35}|(?:I|we)(?: have|.ve) (?:logged|recorded)(?:(?!\band\b).){0,65}',segment,re.I)
        if record and not negated(record) and not re.search(r'请求|任务|工单|request|task|ticket|case',record.group(),re.I):
            records=audit_supported(runtime,h);add('INTERNAL_CREATED',record.group(),bool(records),[x['record_id'] for x in records],None if records else 'RECORD_REVIEW','Saved customer-input audit record supports recording only, never routing, task creation or delivery.')
        completed=re.search(r'(?:已经|已)(?:(?!会|尚未|就|查询|核实|确认|是否|能否|咨询|预计).){0,12}(?:转达|转交|转发|送达|联系门店|与门店沟通)|(?:I|we)(?: have|.ve)?\s+(?:relayed|passed(?: your thanks| the message)? (?:on|along)|contacted the store|notified the store)|and (?:have )?(?:relayed|passed (?:it |them )?(?:on|along))|(?:has been|was) (?:relayed|passed on)',segment,re.I)
        if completed and not negated(completed):
            ok,ids=completed_supported(runtime,h);add('EXTERNAL_COMPLETED',completed.group(),ok,ids,None if ok else 'H04','External completion requires a matching successful delivery receipt, not an internal created task.')
        proposal=re.search(r'可以(?:请|协助|申请)|可(?:提出|申请)|(?:I|we) can (?:ask|request)|could (?:ask|request)',segment,re.I)
        if proposal and not negated(proposal):add('PROPOSAL',proposal.group(),True,reason='Conditional assistance is not an assertion of execution.')
        future=re.search(r'(?:将|会)(?:在内部|向门店|给门店)?(?:转交|转达|跟进)|(?:我们|客服|团队|后续|后)(?:有[\u4e00-\u9fff]{0,8})?(?:会|将).{0,16}(?:回复|回访|联系|同步|告知|答复)|(?:I|we|the team|our team|support)(?:[\x27’]ll| will) (?:pass|relay|reply|respond|follow up|contact)|(?:the team|our team|support) will .{0,48}(?:contact|reply|respond)',segment,re.I)
        if future and not negated(future):
            callback=bool(re.search(r'回复|回访|联系|同步|告知|reply|respond|follow up|contact',future.group(),re.I))
            ok,ids=future_supported(runtime,h) if callback else (False,[])
            add('PENDING_EXECUTION',future.group(),ok,ids,None if ok else 'H03' if callback else 'FUTURE_INTENT_REVIEW','Future intent is not completed action. A promised callback needs an executable authorized schedule, owner and deadline; mere relay intention remains semantic review.')
        attachment=re.search(r'已(?:经)?(?:收到|看到|查看|看过).{0,10}(?:照片|附件|图片)|(?:I|we)(?: have|.ve)? (?:received|seen|viewed|reviewed).{0,18}(?:photo|attachment)',segment,re.I)
        if attachment and not negated(attachment):
            want='viewed' if re.search(r'看到|查看|看过|seen|viewed|reviewed',attachment.group(),re.I) else 'received'
            ok=[a for a in runtime.get('attachment_manifest',[]) if a.get('attachment_id') and a.get('input_hash')==h and a.get('status')==want]
            add('EXTERNAL_COMPLETED',attachment.group(),bool(ok),[a['attachment_id'] for a in ok],None if ok else 'H04','Customer-reported photos are not an attachment receipt or viewing event.')
    return dict(version=VERSION,assessments=assessments,findings=findings,external_executors_available=False)

def calibrate(prior,reply,runtime,h,*,action_audit=None):
    out=copy.deepcopy(prior);audit=action_audit if action_audit is not None else assess(reply,runtime,h);kept=[];excluded=[]
    for f in prior['findings']:
        quote=f.get('quote','');matches=[a for a in audit['assessments'] if quote and (quote in a['quote'] or a['quote'] in quote)]
        asserted=[a for a in matches if a['state'] in ('INTERNAL_CREATED','EXTERNAL_COMPLETED')]
        supported=[a for a in asserted if a['supported']]
        future=[a for a in matches if a['state']=='PENDING_EXECUTION']
        if action_audit is not None and f['code']=='executed_action':
            recording=[x for x in audit['findings'] if x['code']=='RECORD_REVIEW' and x['severity']=='review' and quote and (quote in x['quote'] or x['quote'] in quote)]
            conflicting=[x for x in audit['findings'] if x['severity']=='block' and quote and (quote in x['quote'] or x['quote'] in quote)]
            if recording and not conflicting:
                excluded.append(dict(f,reason_r1='Shared recording audit retains review; recording is not external execution or a created business task.',evidence=recording));continue
        if action_audit is not None and f['code'] in ('H03','unavailable_future_action') and future:
            current=[x for x in audit['findings'] if any(x['quote']==a['quote'] for a in future)]
            if current and all(x['severity']=='review' for x in current):
                excluded.append(dict(f,reason_r1='Current Owner policy classifies this nonrigid future intent as review, not completed execution or a firm callback guarantee.',evidence=future));continue
        if f['code'] in ('H04','executed_action') and supported and all(a['supported'] for a in asserted):
            excluded.append(dict(f,reason_r1='Exact predicate has scoped supporting evidence; does not authorize other predicates.',evidence=supported));continue
        if f['code']=='H04' and future and not any(a['state'] in ('INTERNAL_CREATED','EXTERNAL_COMPLETED') for a in matches):
            excluded.append(dict(f,reason_r1='Future-intent predicate cannot be a completed-action H04; concern retained separately.',evidence=future));continue
        if f['code']=='unavailable_future_action' and any(a['supported'] and a['state']=='PENDING_EXECUTION' for a in matches):
            excluded.append(dict(f,reason_r1='Matching authorized schedule, owner, deadline and executor receipt.',evidence=matches));continue
        kept.append(f)
    kept.extend(f for f in audit['findings'] if f not in kept)
    out.update(version=audit['version'] if action_audit is not None else VERSION,findings=kept,exclusions=excluded,action_states=audit['assessments'],status='blocked' if any(f['severity']=='block' for f in kept) else 'review_required',human_approved=False)
    return out

def input_audit(run,root):
    """Read-only, server-owned evidence. Never trust a model-supplied record claim."""
    import json,hashlib
    path=root/'.local/p5b8/calls/A_GUIDED'/run.email.email_id/'frozen-input.json'
    if not path.exists():return []
    f=json.loads(path.read_text(encoding='utf-8'));payload=f.get('payload',{})
    from src.domain.contracts import EmailInput
    try:email=EmailInput.model_validate(payload['email'])
    except (ValueError,KeyError):return []
    if email.input_hash!=run.input_hash or f['run_id']!=run.run_id:return []
    return [dict(record_id=f['run_id']+':input',input_hash=run.input_hash,artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),phase='before_provider',source=str(path.relative_to(root)))]
def quality(run,data,reply,accepted):
    from pathlib import Path
    root=Path(__file__).resolve().parents[2];runtime=dict(run.metadata['runtime'],audit_records=input_audit(run,root),attachment_manifest=[],capabilities={})
    return calibrate(previous_quality(run,data,reply,accepted),reply or '',runtime,run.input_hash)
