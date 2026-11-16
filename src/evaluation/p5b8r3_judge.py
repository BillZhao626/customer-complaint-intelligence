"""Strict R3 intake around the unchanged five-dimensional rubric."""
import copy,re
from src.domain.contracts import digest
from src.evaluation import p5b8r2_judge as prior
VERSION='p5b8r3-evidence-4-dimension-anchors-r4-fact-veto'
DIMENSIONS=prior.DIMENSIONS
SYSTEM=prior.SYSTEM+'''
R3: Return JSON only. findings and action_evidence are required arrays (empty allowed). Quote exact answer substrings.
Use N/A only with an explicit applicability explanation; never treat N/A as maximum score.
Assess all independently asserted actions. A task noun containing relay is not completed relay.
Hard errors stay separate from five-dimensional scores. Do not equate a local task with problem resolution.
state describes the action ASSERTED in the answer, not a certification that it happened.
For unsupported claims, use event_ids:[] and explain the missing evidence; report any material hard error separately.
Do not cite knowledge_lookup or requested events as proof of INTERNAL_CREATED/PENDING_EXECUTION/EXTERNAL_COMPLETED.
For actual task creation cite only matching created/handoff_pending events. A completed lookup is not a created task.
Dimension anchors (apply to each answer independently before comparing them):
attitude: for current material damage/inconvenience, 2 requires an ACTUAL proportionate apology in the reply;
acknowledgment alone without apology is 1. For praise, use actual warm thanks. Quote the supporting phrase
in the reason; if missing, explicitly say missing. Do not infer an apology from professional structure.
helpfulness: an explicit dangerous next step contradicting the needed safety precaution makes the guidance
materially harmful: 0. Otherwise assess coverage/next steps, not relative length or which answer came first.
action_accuracy: an invented execution, firm unsupported delivery guarantee or explicitly dangerous proposed action is 0.
If action is applicable/available but no task was created and the reply only proposes support review, use 1.
Use 2 for correct scoped progress or a concrete sufficient proposal when no executable task is applicable.
reliability: any material invented fact/policy/unsupported guarantee or dangerous instruction is 0; never
average it away because the rest is correct. Different hard-error categories remain separate findings.
information_density: evaluate wording/structure only. Do not deduct again here merely because a task was
not created, an apology was missing or safety was wrong; those belong in their specified dimensions.
Explain the exact predicate/evidence for each deduction. Do not award a point in BA that the same evidence
would lose in AB. Assess both replies independently, then determine preference without revising scores.
'''
def validate_slot(slot,email=None):
    for k in ('case_id','run_id','arm','input_hash'):
        if not isinstance(slot.get(k),str) or not slot[k].strip():raise ValueError('Missing slot identity: '+k)
    if not re.fullmatch('[0-9a-f]{64}',slot['input_hash']):raise ValueError('Invalid input hash')
    if email and (slot['case_id']!=email.email_id or slot['input_hash']!=email.input_hash):raise ValueError('Foreign case/input, including empty-event slot')
    if type(slot.get('parse_ok'))is not bool or not isinstance(slot.get('reply'),str):raise ValueError('Invalid reply status')
    if not isinstance(slot.get('events'),list):raise ValueError('Explicit events required')
    for e in slot['events']:
        for k,expected in (('case_id',slot['case_id']),('conversation_id',slot['case_id']),('run_id',slot['run_id']),('arm',slot['arm'])):
            if k in e and e[k]!=expected:raise ValueError('Intrinsic event identity conflicts with slot')
        if not isinstance(e.get('event_id'),str) or not e['event_id'].strip() or not isinstance(e.get('kind'),str) or not e['kind'] or not e.get('status'):raise ValueError('Empty event identity/kind/state')
    return prior.validate_events(slot)
def bind(events,*,case_id,run_id,arm,input_hash):
    identity=dict(case_id=case_id,run_id=run_id,arm=arm,input_hash=input_hash)
    for e in events:
        for k in ('case_id','run_id','arm','input_hash'):
            if k in e and e[k]!=identity[k]:raise ValueError('Cannot relabel a foreign raw event')
        if e.get('conversation_id',case_id)!=case_id:raise ValueError('Foreign event conversation')
    out=prior.bind_events(events,**identity)
    validate_slot(dict(identity,parse_ok=True,reply='validation',events=out));return out
def blind_pair(email,answers,*,reverse=False):
    if len(answers)!=2:raise ValueError('Two answers required')
    for slot in answers:validate_slot(slot,email)
    if len({(s['run_id'],s['arm']) for s in answers})!=2:raise ValueError('Duplicate source slot')
    # Do not neutralize intrinsic fields by silently relabeling them. The trusted
    # unblinding key retains source bindings; model-visible IDs use opaque scope.
    cleaned=copy.deepcopy(answers)
    for s in cleaned:
        for e in s['events']:
            e.pop('_binding')
            # Conversation is already visible in the customer record. Preserve
            # its original value so strict intake does not invent it after blind.
            for k in ('case_id','run_id','arm'):e.pop(k,None)
            e['event_id']=digest(dict(scope={k:s[k] for k in ('case_id','run_id','arm','input_hash')},source_event_id=e['event_id']))
        s['events']=prior.bind_events(s['events'],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')})
    payload,key=prior.blind_pair(email,cleaned,reverse=reverse)
    ordered=list(reversed(answers)) if reverse else answers
    for label,s in zip(('X','Y'),ordered):
        key[label]['event_key']={digest(dict(scope={k:s[k] for k in ('case_id','run_id','arm','input_hash')},source_event_id=e['event_id'])):e['event_id'] for e in s['events']}
    return payload,key
def parse(raw,payload):
    from src.domain.contracts import EmailInput
    email=EmailInput.model_validate(payload['customer'])
    for s in payload['answers']:validate_slot(s,email)
    value=copy.deepcopy(raw) if not isinstance(raw,str) else __import__('json').loads(raw)
    # Keep background citations without authorizing the asserted action. Foreign
    # IDs remain fatal even when the model says evidence is missing.
    by_slot={s['slot']:s for s in payload['answers']}
    for answer in value.get('answers',[]):
        source=by_slot.get(answer.get('slot'))
        if not source:raise ValueError('Foreign slot')
        events={e['event_id']:e for e in source['events']}
        for claim in answer.get('action_evidence',[]):
            ids=claim.get('event_ids',[])
            if not isinstance(ids,list) or any(e not in events for e in ids) or len(ids)!=len(set(ids)):raise ValueError('Foreign/duplicate event citation')
            state=claim.get('state');allowed={'INTERNAL_CREATED':{'created','handoff_pending'},'PENDING_EXECUTION':{'created','handoff_pending','scheduled'},'EXTERNAL_COMPLETED':{'completed','executed'}}.get(state)
            invalid=allowed is not None and any(events[e]['status'] not in allowed or (events[e]['kind'].endswith('_lookup') and state in ('INTERNAL_CREATED','PENDING_EXECUTION')) for e in ids)
            if invalid and claim.get('missing_evidence'):
                claim['context_event_ids']=ids;claim['event_ids']=[];claim['support_status']='UNSUPPORTED_CONTEXT_ONLY'
    data=prior.parse(value,payload)
    for answer in data['answers']:
        if not isinstance(answer.get('findings'),list):raise ValueError('Findings required')
        for c in answer['action_evidence']:
            if len(c['event_ids'])!=len(set(c['event_ids'])):raise ValueError('Duplicate cited event')
            if c['state']=='PENDING_EXECUTION':
                events={e['event_id']:e for e in next(s for s in payload['answers'] if s['slot']==answer['slot'])['events']}
                if any(events[e]['status'] not in ('created','handoff_pending','scheduled') or events[e]['kind'].endswith('_lookup') for e in c['event_ids']):raise ValueError('Query/request is not executable pending work')
    from src.evaluation.p5b8r4_judge import validate_judgment
    return validate_judgment(data,payload)
