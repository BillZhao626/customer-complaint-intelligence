"""R1 output protocol; old first responses remain rejected and immutable."""
import json,copy
from pydantic import Field
from src.domain.contracts import StrictModel
from src.application.p5b8_pipeline import Calibration,validate_analysis,DEFINITION,POLICY
from src.application.live_execution import strict_json
VERSION='p5b8r1-contract-1'
class Reply(StrictModel):
    reply:str=Field(min_length=1,max_length=16000)

def analysis_system():
    schema=Calibration.model_json_schema();ordered=['version','uncertainty']+[k for k in schema['properties'] if k not in ('version','uncertainty')]
    schema['properties']={k:schema['properties'][k] for k in ordered}
    # Complete shape example is explicitly a format fixture, never a semantic label.
    example=dict(version='p5b8-calibration-1',uncertainty=[],expressed_sentiment='neutral',expressed_evidence=[],experience_polarity='unknown',complaint_intent='uncertain',complaint_evidence=[],urgency='unknown',urgency_evidence=[],mentioned_store=None,issues=[dict(issue_id='I1',object_type='unknown',object_name='unspecified request',category='unknown',sentiment='neutral',experience_polarity='unknown',issue_kind='inquiry',business_process='unclear',customer_requests=['clarify the request'],evidence=['help'],risk='unknown',urgency='unknown',resolution='unknown')])
    return ('Return one complete JSON object. Required keys: '+', '.join(ordered)+'.\nAlways include uncertainty; [] is an explicit model decision, never omitted. Check every required key and the closing object brace before returning. Never copy fixture labels or quote help unless present in the actual email.\n'+DEFINITION+'\nFORMAT FIXTURE ONLY:\n'+json.dumps(example,ensure_ascii=False)+'\nJSON SCHEMA:\n'+json.dumps(schema,ensure_ascii=False))

REPLY_SYSTEM=POLICY+'''\nR1 formatting contract: The response is exactly one object with one nonblank string key reply.
Example of JSON syntax only: {"reply":"Complete customer-facing response."}
Encode internal quotes/newlines with JSON escaping and include the final closing object brace.
No comments, markdown fences or trailing text. Check structure before finishing. Do not fill missing facts.
Classify action wording internally: proposal / internal-created / pending / external-completed.
Only source-bound receipts authorize completed claims. Future intent is not completed execution;
promised callbacks need an actual executor, owner and deadline, not just a created pending request.'''

def parse_reply(raw,metadata=None):
    d=strict_json(raw);r=Reply.model_validate(d)
    if not r.reply.strip():raise ValueError('Blank reply')
    if (metadata or {}).get('finish_reason') in ('length','max_tokens'):raise ValueError('Provider output incomplete: length finish')
    return r.model_dump()
def parse_analysis(raw,email,metadata=None):
    if (metadata or {}).get('finish_reason') in ('length','max_tokens'):raise ValueError('Provider output incomplete: length finish')
    return validate_analysis(raw,email)
def parse_outcome(raw,*,email=None,metadata=None):
    try:
        value=parse_analysis(raw,email,metadata) if email else parse_reply(raw,metadata)
        return dict(status='accepted',value=value,error=None,semantic_eligible=True)
    except (ValueError,TypeError,KeyError) as exc:
        return dict(status='rejected',value=None,error=str(exc),semantic_eligible=False)

EMOTION_KEYS={'expressed_sentiment','expressed_evidence','experience_polarity','sentiment'}
def without_emotion(value):
    if isinstance(value,dict):return {k:without_emotion(v) for k,v in value.items() if k not in EMOTION_KEYS}
    if isinstance(value,list):return [without_emotion(v) for v in value]
    return copy.deepcopy(value)
def emotion_layer(analysis):
    return dict(expressed_sentiment=analysis['expressed_sentiment'],expressed_evidence=analysis['expressed_evidence'],experience_polarity=analysis['experience_polarity'],issues=[dict(issue_id=i['issue_id'],sentiment=i['sentiment'],experience_polarity=i['experience_polarity']) for i in analysis['issues']],scope='Model-provisional explicit labels grounded in source; original email overrides labels. No extra facts or actions.')
def paired_messages(email,analysis,runtime):
    issues=without_emotion(analysis)
    # Free-form annotation notes sometimes restate sentiment. Neither arm gets
    # these notes; preserve them in the raw analysis, not as hidden treatment.
    issues.pop('uncertainty',None)
    common=dict(customer=email.model_dump(),structured_issues=issues,verified_facts=runtime['facts'],action_receipts=runtime['events'],attachment_manifest=[],policies='No verified merchant eligibility, stock or ETA. Local pending requests only.')
    return {v:[('system',REPLY_SYSTEM),('human',json.dumps(dict(common,**({'explicit_emotion':emotion_layer(analysis)} if v=='ISSUES_WITH_SENTIMENT' else {})),ensure_ascii=False))] for v in ('ISSUES_NO_SENTIMENT','ISSUES_WITH_SENTIMENT')}

def build_judge_pair(email,answers):
    """Never score empty parsed strings as evidence of emotional improvement."""
    if any(not a.get('parse_ok') or not a.get('reply','').strip() for a in answers):
        return dict(status='NOT_ASSESSABLE_STRUCTURE',payload=None,emotion_delta=None)
    return dict(status='READY_FOR_AUTHORIZED_JUDGE',payload=dict(customer_context=[dict(role='customer',text=email.subject+'\n'+email.body)],reference_requirements=None,answers=answers),emotion_delta=None)
