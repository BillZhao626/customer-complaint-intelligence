"""R1 Judge intake; old numerical judgments are never rewritten."""
from src.evaluation.p5b5r2_judge import JUDGE_SYSTEM_V31,parse_judgment
VERSION='p5b8r1-judge-1-slot-bound'
SYSTEM=JUDGE_SYSTEM_V31+'''
R1 amendment: Grade each slot using ONLY that slot's event list, expected_input_hash,
facts and attachment manifest. Another answer's task receipt is never evidence.
Distinguish proposal, internal-created, pending execution and externally completed.
"Will pass on" is future intent, not H04 completed execution. An unexecutable
material promise may instead be H03; ambiguous relay intention is review, not H04.
A persisted source-input record may support "recorded feedback", never "forwarded".
Score ordinary neutral fault reports without forcing emotional apology. Mixed
feedback should acknowledge praise and concerns. Brevity is not incomplete coverage;
length earns no points. Assess source-supported facts, all goals, action progress,
naturalness and emotion_fit independently. Parse failure is STRUCTURE_NOT_ASSESSABLE,
not a zero emotional-quality score. No human certification may be inferred.
Each answer must also contain action_evidence: [{"quote":"exact reply substring",
"state":"PROPOSAL/INTERNAL_CREATED/PENDING_EXECUTION/EXTERNAL_COMPLETED",
"event_ids":[],"missing_evidence":"explain if unsupported"}]. Every cited event_id
must belong to that slot AND its current input_hash. With no assertion use [].
'''

def parse(raw,payload):
    result=parse_judgment(raw,payload)
    answers={a['slot']:a for a in payload['answers']}
    for answer in result['answers']:
        evidence=answer.get('action_evidence')
        if not isinstance(evidence,list):raise ValueError('R1 action_evidence array required')
        src=answers[answer['slot']]
        events={e['event_id']:e for e in src.get('events',[]) if e.get('input_hash')==src['expected_input_hash'] and e.get('event_id')};ids=set(events)
        for claim in evidence:
            if not isinstance(claim,dict) or not claim.get('quote') or claim['quote'] not in src['reply']:raise ValueError('Action quote is not exact slot text')
            if claim.get('state') not in ('PROPOSAL','INTERNAL_CREATED','PENDING_EXECUTION','EXTERNAL_COMPLETED'):raise ValueError('Unknown action state')
            if not isinstance(claim.get('event_ids'),list) or not set(claim['event_ids'])<=ids:raise ValueError('Foreign-slot or stale receipt reference')
            cited=[events[eid] for eid in claim['event_ids']]
            if claim['state']=='INTERNAL_CREATED' and any(e.get('status') not in ('created','handoff_pending') or e.get('kind')=='knowledge_lookup' for e in cited):raise ValueError('Claimed created state has no created-task receipt')
            if claim['state']=='EXTERNAL_COMPLETED' and any(e.get('status') not in ('completed','executed') or not e.get('payload',{}).get('external_execution') or e.get('payload',{}).get('result',{}).get('status')!='SUCCEEDED' for e in cited):raise ValueError('Claimed external completion lacks successful external receipt')
            if not claim['event_ids'] and not claim.get('missing_evidence') and claim['state']!='PROPOSAL':raise ValueError('Unsupported state needs missing-evidence explanation')
    return result
