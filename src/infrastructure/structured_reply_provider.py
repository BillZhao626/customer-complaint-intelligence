"""Small opt-in LangChain strict-tool adapter. A schema tool is output only, never executed.

Reuses serial Dispatcher reservation and raw-storage contracts. Old JSON mode unchanged.
"""
import asyncio,json,hashlib,os
from src.application.p5b8r1_experiment import write_first
from src.infrastructure.p5b8r3_execution import LangChainProvider

TOOL=dict(type='function',function=dict(name='compose_reply',description='Return the complete customer email only. This function performs no business action.',strict=True,parameters=dict(type='object',properties=dict(reply=dict(type='string')),required=['reply'],additionalProperties=False)))

class StructuredReplyProvider:
 def __init__(self,transport=None):self.transport=transport
 def __call__(self,messages,folder,payload):
  contract=payload.get('strict_output_contract')
  if contract:
   if set(contract)!={'name','schema'} or contract['name'] not in ('plan_service','assess_service'):
    raise ValueError('Unknown structured output contract')
   tool=dict(type='function',function=dict(name=contract['name'],description='Return structured data only. This function performs no business action.',strict=True,parameters=contract['schema']))
   return asyncio.run(self.request(messages,folder,tool))
  if not payload.get('strict_reply_contract'):return LangChainProvider()(messages,folder,payload)
  return asyncio.run(self.request(messages,folder))
 async def request(self,messages,folder,tool=None):
  tool=tool or TOOL
  import httpx
  from langchain_openai import ChatOpenAI
  from langsmith import tracing_context
  from src.infrastructure.deepseek import LiveSettings
  os.environ.update(COMPLAINT_ENABLE_LIVE='true',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
  settings=LiveSettings.from_env();settings.validate();observed={}
  async def audit(request):
   body=await request.aread();wire=json.loads(body)
   if str(request.url)!='https://api.deepseek.com/beta/chat/completions' or wire.get('tools')!=[tool] or wire.get('max_tokens')!=4000 or 'response_format' in wire:raise ValueError('Structured wire drift')
   write_first(folder/'wire-request.json',wire)
   from src.application.p5b5_pipeline import now
   observed.update(payload_sha256=hashlib.sha256(body).hexdigest(),dispatch_at=now())
  async def capture(response):
   body=await response.aread();write_first(folder/'provider-response.txt',body.decode());write_first(folder/'provider-http.json',dict(status=response.status_code,body_sha256=hashlib.sha256(body).hexdigest()))
  http=httpx.AsyncClient(timeout=45,follow_redirects=False,trust_env=False,transport=self.transport,event_hooks=dict(request=[audit],response=[capture]))
  class Client(ChatOpenAI):
   def _get_request_payload(self,input_,*,stop=None,**kwargs):
    p=super()._get_request_payload(input_,stop=stop,**kwargs);p['max_tokens']=p.pop('max_completion_tokens');return p
  client=Client(model='deepseek-flash',api_key=settings.api_key,base_url='https://api.deepseek.com/beta',temperature=0,max_tokens=4000,max_retries=0,timeout=45,http_async_client=http,http_socket_options=(),cache=False,streaming=False,extra_body={'thinking':{'type':'disabled'}})
  try:
   with tracing_context(enabled=False):r=await asyncio.wait_for(client.bind(tools=[tool],tool_choice={'type':'function','function':{'name':tool['function']['name']}}).ainvoke(messages,config={'callbacks':[]}),timeout=90)
   write_first(folder/'langchain-response.json',r.model_dump(mode='json'));meta=r.response_metadata;usage=r.usage_metadata
   # Preserve the literal provider arguments before strict parsing; no JSON repair or field removal.
   from pathlib import Path
   original=json.loads(json.loads((Path(folder)/'provider-response.txt').read_text('utf-8')))['choices'][0]['message'].get('tool_calls',[])
   raw=original[0]['function']['arguments'] if len(original)==1 and original[0]['function']['name']==tool['function']['name'] else ''
   return raw,dict(resolved_model=meta.get('model_name'),model_snapshot='unavailable',provider_response_id=meta.get('id'),finish_reason=meta.get('finish_reason'),input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),total_tokens=usage.get('total_tokens'),usage=usage,contract='STRICT_TOOL_ARGUMENTS_NOT_CONTENT_JSON',**observed)
  finally:await http.aclose()
