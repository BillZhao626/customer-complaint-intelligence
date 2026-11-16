"""Two-stage fact boundary prototype. Offline only; no provider/client construction."""
import json
from pydantic import BaseModel, ConfigDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import BaseCallbackHandler
from src.application.p5b4_guard import receipts
from src.domain.contracts import digest
from src.domain.analysis_v32 import wire_schema
from src.application.live_execution import strict_json

class Claim(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    field: str
    start: int
    end: int
    quote: str

class Extraction(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    customer_claims: list[Claim]
    unresolved_questions: list[str]

class Trace(BaseCallbackHandler):
    def __init__(self): self.events=[]
    def on_chain_start(self,serialized,inputs,*,run_id,**kwargs):
        self.events.append(dict(event='start',run_id=str(run_id),name=kwargs.get('name') or (serialized or {}).get('name'),input_hash=digest(str(inputs))))
    def on_chain_end(self,outputs,*,run_id,**kwargs):
        self.events.append(dict(event='end',run_id=str(run_id),output_hash=digest(str(outputs))))

def offline_extract(email, raw, *, expected_language, journal_path=None):
    if expected_language not in ('zh','en','mixed','unknown'): raise ValueError('Explicit language attribute required')
    first = strict_json(raw)  # JsonOutputParser must not implicitly repair first output.
    prompt=ChatPromptTemplate.from_messages([('system','Extract customer-reported claims as JSON spans only. Never create verified_facts or action receipts. Reply language attribute: {expected_language}. Schema: {schema}'),('human','Subject: {subject}\nBody: {body}')])
    trace=Trace()
    fixture=RunnableLambda(lambda rendered: raw, name='explicit_offline_raw_fixture')
    chain=prompt | fixture | JsonOutputParser()
    parsed=chain.invoke(dict(expected_language=expected_language,schema=json.dumps(Extraction.model_json_schema()),subject=email.subject,body=email.body),config={'callbacks':[trace],'run_name':'p5b4_offline_extraction_prototype'})
    if parsed != first: raise ValueError('Parser may not replace or repair the first JSON output')
    extraction=Extraction.model_validate(parsed)
    for claim in extraction.customer_claims:
        if claim.field not in ('subject','body') or not 0<=claim.start<claim.end<=len(getattr(email,claim.field)) or getattr(email,claim.field)[claim.start:claim.end]!=claim.quote:
            raise ValueError('Claim must cite exact original input span')
    # Verified facts and action receipts are exclusively supplied by trusted runtime.
    context=dict(customer_claims=extraction.model_dump()['customer_claims'],verified_facts=[],unresolved_questions=extraction.unresolved_questions,expected_language=expected_language,action_receipts=receipts(journal_path,email.input_hash),input_hash=email.input_hash)
    return dict(identity='OFFLINE_FIXTURE_LANGCHAIN_EXECUTION_NOT_MODEL_GENERATION',context=context,trace=trace.events)

def strict_audit(schema, path='$'):
    findings=[]
    if isinstance(schema,dict):
        if schema.get('type')=='object' and (set(schema.get('required',[]))!=set(schema.get('properties',{})) or schema.get('additionalProperties') is not False):
            findings.append(path+': strict objects require every property and additionalProperties=false')
        for key,value in schema.items():
            if key in ('minLength','maxLength','minItems','maxItems'): findings.append(path+'/'+key+': documented unsupported strict keyword')
            findings.extend(strict_audit(value,path+'/'+key))
    elif isinstance(schema,list):
        for i,v in enumerate(schema): findings.extend(strict_audit(v,path+'/'+str(i)))
    return findings

def dry_requests():
    schema=wire_schema()
    strict=dict(model='deepseek-flash',messages=[dict(role='user',content='Return analysis using the schema; offline payload only.')],tools=[dict(type='function',function=dict(name='analyze_complaint',strict=True,parameters=schema))],thinking=dict(type='disabled'),temperature=0,max_tokens=4000)
    return dict(mode='NO_DISPATCH_PAYLOAD_COMPARISON',json_mode=dict(endpoint='https://api.deepseek.com/chat/completions',response_format=dict(type='json_object'),business_schema_guarantee=False),strict_mode=dict(endpoint='https://api.deepseek.com/beta/chat/completions',payload=strict,local_incompatibilities=strict_audit(schema),provider_acceptance='NOT_RUN',production_switch=False),two_stage=dict(extraction_schema=Extraction.model_json_schema(),reply_context_fields=['customer_claims','verified_facts','action_receipts','expected_language'],live_generation='NOT_RUN',limited_repair='NOT_RUN_NO_REPLACEMENT_OF_FIRST_RAW'))
