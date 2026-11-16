"""Five dimensions, strict source binding, independently enforced fact veto.

Original numerical judgments are retained even when certification is refused.
"""
import copy
from src.domain.contracts import digest
from src.evaluation import p5b8r3_judge as previous
from src.application.p5b8r4_evidence import claim, support

VERSION='r11-five-dimension-source-fact-veto-6-grounded-reference'
DIMENSIONS=previous.DIMENSIONS
SYSTEM=previous.SYSTEM+'''
R4 executable protocol: First identify the customer's CURRENT objectives, resolved historical
matters, experience and deadlines. Cite short exact customer spans. Then cover each major issue,
useful professional help and remaining gaps. Use the supplied deterministic_fact_audit as a floor:
no numerical score or fluent wording can authorize an unsupported action. For every action cite
only this answer's matching event kind, business goal, state and ID. No event means UNKNOWN
execution, never a verified action. requested/created/assigned/executed/completed differ.
Any HARD_ERROR in your own findings or the deterministic audit requires reliability=0.
Unsupported execution or dangerous proposed action also requires action_accuracy=0.
Check attachment source levels: offer, taken, reported sent, received, viewed are distinct.
Never infer photo history from a request to help. Missing core objectives are a major service gap.
Never invent a human score from an Owner qualitative preference. Do not use answer length as a proxy.
Keep HARD_ERROR, MAJOR_SERVICE_GAP, SOFT_QUALITY_ISSUE and UNKNOWN separate.
Each answer must also contain:
customer_goals:[{"goal":"current objective","quote":"exact customer span"}],
issue_coverage:[{"issue":"...","reply_quote":"exact reply span","status":"COVERED/PARTIAL/MISSING"}],
score_evidence:{each of the five dimension names:"exact nonempty reply span"}.
Give applicability reasons for N/A, and brief verifiable reasons, not hidden reasoning.
Return the existing answers/preference JSON schema plus these three fields. Assess independently
before preferring X/Y/TIE/UNKNOWN. A COMBINE Owner policy is not a winner label.
'''

SYSTEM+='''
OUTPUT COMPLETENESS CHECK: Every answer MUST include customer_goals, issue_coverage,
score_evidence, scores, reasons, findings and action_evidence. Never omit these on a
bad answer or on N/A. For score_evidence values return ONLY an exact source substring;
put explanations in reasons. For N/A choose the literal customer clause (e.g. no action
needed), never write N/A or an explanation as the quoted span. Customer_goals must
still cite the actual concern or praise when no action is requested. Missing core
help remains MAJOR_SERVICE_GAP even if reliability=2. Use the supplied quote inventory
as literal citation candidates; do not change case, Unicode or punctuation.
'''

def quote_inventory(email,slot):
    import re
    source=email.subject+'\n'+email.body
    def spans(text, prefix):
        matches = (m for m in re.finditer(r'[^。！？!?\n]+',text) if m.group().strip())
        return [dict(ref=f'{slot["slot"]}:{prefix}{i}',quote=m.group(),start=m.start(),end=m.end())
                for i,m in enumerate(matches,1)]
    return dict(customer=spans(source,'C'),reply=spans(slot['reply'],'R'),
                coordinate='Original Unicode codepoints; exact substrings only')

# Preserve the scale and veto. Clarify the observed false-positive boundary,
# rather than changing a threshold or converting old scores.
SYSTEM+='''
Calibration boundary: unnecessary ordinary order details are SOFT_QUALITY_ISSUE,
not HARD_ERROR by themselves. Soliciting secret pickup codes/PINs or full ID images
over ordinary email is materially different. A conditional, denied or explicitly
customer-reported event is not a completed application action; inspect its own scope.
A receipt heading does not establish the seller. A shallow pocket is not cured by
increasing sheet width/length. Generic dimensions, missing item/store identity and
invented operator procedures require explicit service-gap review.
'''

def blind_pair(email,answers,*,reverse=False):
    # R4 is an independent-arm execution experiment. A raw task receipt cannot
    # become two executions merely by acquiring two caller-created bindings.
    if len(answers)==2 and ({e.get('event_id') for e in answers[0].get('events',[])} & {e.get('event_id') for e in answers[1].get('events',[])}):
        raise ValueError('Shared receipt across independent arms')
    payload,key=previous.blind_pair(email,answers,reverse=reverse)
    ordered=list(reversed(answers)) if reverse else answers
    for slot,source in zip(payload['answers'],ordered):
        # Executor capability is evidence too; retain its OWN source through BA.
        slot['capabilities']=copy.deepcopy(source.get('capabilities',{}))
        slot['deterministic_fact_audit']=audit_slot(slot,email)
        slot['quote_inventory']=quote_inventory(email,slot)
    payload['judge_version']=VERSION
    return payload,key

def audit_slot(slot,email=None):
    from src.application.p5b8r3_final_guard import assess
    identity={k:slot[k] for k in ('case_id','run_id','arm','input_hash')}
    identity['conversation_id']=slot['case_id']
    out=assess(slot['reply'],dict(events=slot['events'],facts=slot.get('facts',{}),identity=identity,strict_identity=True,future_intent_policy='owner-nonrigid-v1',
                 attachment_manifest=slot.get('attachment_manifest',[]),capabilities=slot.get('capabilities',{})),slot['input_hash'])
    if email is not None:
        from src.application.source_facts import attachment_claim_audit,reported_delivery_claim
        excluded=[]
        for f in out['findings']:
            evidence=reported_delivery_claim(slot['reply'],f.get('quote',''),email) if f.get('code')=='H04' else None
            if evidence:excluded.append(dict(f,source_report=evidence))
        out['findings']=[f for f in out['findings'] if not any(f=={k:v for k,v in x.items() if k!='source_report'} for x in excluded)]
        out['source_report_exclusions']=excluded
        attachment=attachment_claim_audit(slot['reply'],email,slot.get('attachment_manifest',[]))
        out['findings'].extend(attachment['findings'])
        out['attachment_evidence']=attachment['facts']
        from src.evaluation.p5b5r2_judge import diagnose
        inherited=diagnose(slot['reply'],events=slot['events'],expected_input_hash=slot['input_hash'],customer_context=[dict(role='customer',text=email.body)],attachment_manifest=slot.get('attachment_manifest',[]))
        # Action evidence uses R4; keep every separate safety/privacy/policy gate.
        for f in inherited['hard_findings']:
            if f['code'] not in ('H04',):out['findings'].append(dict(f,severity='block',scope='reply'))
        out['inherited_non_action_reviews']=inherited['review_findings']
    return out

def validate_judgment(data,payload):
    result=copy.deepcopy(data); sources={s['slot']:s for s in payload['answers']}; problems=[]
    for a in result['answers']:
        from src.domain.contracts import EmailInput
        slot=sources[a['slot']]; audit=audit_slot(slot,EmailInput.model_validate(payload['customer'])); contradictions=[]
        blocked=[f for f in audit['findings'] if f['severity']=='block']
        if (blocked or any(f.get('category')=='HARD_ERROR' for f in a['findings'])) and a['scores']['reliability']!=0:
            contradictions.append('HARD_ERROR_RELIABILITY_MUST_BE_ZERO')
        if blocked and any(a['scores'][d] in (2,'N/A') for d in ('action_accuracy','reliability')):
            contradictions.append('JUDGE_INTERNAL_CONTRADICTION')
        for c in a['action_evidence']:
            identity={k:slot[k] for k in ('case_id','run_id','arm','input_hash')};identity['conversation_id']=slot['case_id']
            selected=[e for e in slot['events'] if e['event_id'] in c['event_ids']]
            assertion=claim(c['quote'],c['state'])
            antecedent=next((x for x in audit['assessments'] if x.get('quote')==c['quote'] and x.get('state')==c['state'] and x.get('antecedent_quote') and x.get('supported') is True),None)
            if antecedent:
                assertion.update({k:antecedent[k] for k in ('business_object','object_mentions','target','antecedent_quote','antecedent_event_ids')})
            check=support(assertion,dict(events=selected,identity=identity,receipt_inventory=slot['events']),slot['input_hash'],strict=True)
            wrong_compound_ids = (assertion.get('task_components') is not None
                                  and set(c['event_ids']) != set(check['event_ids']))
            if c['state']!='PROPOSAL' and c['event_ids'] and (not check['supported'] or wrong_compound_ids):
                contradictions.append('JUDGE_EVIDENCE_MISMATCH')
            c['deterministic_support']=check
        for f in blocked:
            if not any(x['category']=='HARD_ERROR' and (f['quote'] in x['quote'] or x['quote'] in f['quote']) for x in a['findings']):
                contradictions.append('JUDGE_HARD_ERROR_OMISSION')
        a['fact_validation']=dict(audit=audit,errors=sorted(set(contradictions)),certifiable=not contradictions)
        problems.extend(dict(slot=a['slot'],code=e) for e in sorted(set(contradictions)))
    result['validation']=dict(version=VERSION,status='UNCERTIFIED' if problems else 'AUTOMATED_PROVISIONAL',errors=problems,
                              validated_preference='UNKNOWN' if problems else result['preference'],human_numeric_status='HUMAN_NUMERIC_UNAVAILABLE')
    return result

def parse(raw,payload):
    # Existing intake still validates every identity even if a slot has no events.
    data=previous.parse(raw,payload)
    customer=payload['customer']['subject']+'\n'+payload['customer']['body']
    for a in data['answers']:
        slot=next(s for s in payload['answers'] if s['slot']==a['slot'])
        goals=a.get('customer_goals');coverage=a.get('issue_coverage');spans=a.get('score_evidence',{})
        if not isinstance(goals,list) or not goals or any(not g.get('goal') or not g.get('quote') or g['quote'] not in customer for g in goals):raise ValueError('Grounded customer goals required')
        if not isinstance(coverage,list) or not coverage or any(not c.get('issue') or c.get('status') not in ('COVERED','PARTIAL','MISSING') or (c.get('status')!='MISSING' and (not c.get('reply_quote') or c['reply_quote'] not in slot['reply'])) for c in coverage):raise ValueError('Issue coverage required')
        if set(spans)!=set(DIMENSIONS) or any(not isinstance(q,str) or not q or (q not in slot['reply'] and not (a['scores'][d]=='N/A' and q in customer)) for d,q in spans.items()):raise ValueError('Five grounded score spans required; N/A may cite customer applicability')
    return data

def identity():return dict(version=VERSION,system_hash=digest(SYSTEM))
