"""One observable ChatOpenAI invocation, no SDK retry, cache, tracing or fallback."""
import asyncio
import os
from dataclasses import dataclass, field
from src.application.live_prompt import PROMPT_HASH, PROMPT_VERSION, messages
from src.domain.contracts import RunConfig

class LiveError(Exception):
    def __init__(self,kind):
        self.kind=kind
        super().__init__(kind)

@dataclass(frozen=True)
class LiveSettings:
    api_key: str = field(repr=False)
    enabled: bool = False
    model: str = 'deepseek-flash'
    endpoint: str = 'https://api.deepseek.com'
    max_tokens: int = 1800
    http_timeout: float = 45.0
    deadline: float = 90.0
    max_attempts: int = 2

    def validate(self):
        if not self.enabled or not self.api_key or self.model!='deepseek-flash' or self.endpoint!='https://api.deepseek.com':
            raise LiveError('configuration_error')
        if not (1<=self.max_tokens<=2000 and 0<self.http_timeout<=45 and 0<self.deadline<=90 and 1<=self.max_attempts<=2):
            raise LiveError('configuration_error')
        if any(os.getenv(k,'').lower() in ('true','1','yes') for k in ('LANGSMITH_TRACING','LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2')):
            raise LiveError('configuration_error')

    @classmethod
    def from_env(cls):
        from src.config.llm_config import _load_dotenv_if_present
        _load_dotenv_if_present()
        return cls(api_key=os.getenv('LLM_API_KEY',''),enabled=os.getenv('COMPLAINT_ENABLE_LIVE','false').lower()=='true')

class DeepSeekAnalyzer:
    backend='deepseek_live'
    model_id='deepseek-flash'
    def __init__(self,settings,provider=None,prompt_profile='p2-frozen'):
        settings.validate()
        self.settings=settings
        self.provider=provider
        if prompt_profile=='p2-frozen':
            self.messages=messages;version=PROMPT_VERSION;prompt_hash=PROMPT_HASH
        elif prompt_profile=='service-boundary-v1':
            from src.application import service_boundary_prompt as candidate
            self.messages=candidate.messages;version=candidate.PROMPT_VERSION;prompt_hash=candidate.PROMPT_HASH
        else:
            raise LiveError('configuration_error')
        self.config=RunConfig(backend=self.backend,model_id=self.model_id,prompt_version=version,prompt_hash=prompt_hash,
            parameters=dict(temperature=0,thinking='disabled',response_format='json_object',max_tokens=settings.max_tokens,
                            sdk_max_retries=0,http_timeout=settings.http_timeout,deadline=settings.deadline,max_attempts=settings.max_attempts,
                            endpoint=settings.endpoint+'/chat/completions'))

    def make_client(self,timeout):
        import httpx
        from langchain_openai import ChatOpenAI
        class DeepSeekChatOpenAI(ChatOpenAI):
            def _get_request_payload(self,input_,*,stop=None,**kwargs):
                payload=super()._get_request_payload(input_,stop=stop,**kwargs)
                # langchain-openai 1.2.1 renames this for OpenAI. DeepSeek documents max_tokens.
                payload['max_tokens']=payload.pop('max_completion_tokens')
                return payload
        # No environment proxy or redirects to a third-party endpoint; no hidden retries.
        transport=httpx.AsyncClient(timeout=timeout,follow_redirects=False,trust_env=False)
        client=DeepSeekChatOpenAI(model=self.model_id,api_key=self.settings.api_key,base_url=self.settings.endpoint,
            temperature=0,max_tokens=self.settings.max_tokens,max_retries=0,timeout=timeout,
            model_kwargs={'response_format':{'type':'json_object'}},extra_body={'thinking':{'type':'disabled'}},
            http_async_client=transport,http_socket_options=(),include_response_headers=True,cache=False,streaming=False)
        return client,transport

    async def request(self,email,repair,remaining):
        self.settings.validate()
        payload=self.messages(email,repair)
        if self.provider is not None:
            return await asyncio.wait_for(self.provider(payload,min(self.settings.http_timeout,remaining)),timeout=remaining)
        from langsmith import tracing_context
        client,transport=self.make_client(min(self.settings.http_timeout,remaining))
        try:
            with tracing_context(enabled=False):
                response=await asyncio.wait_for(client.ainvoke(payload,config={'callbacks':[]}),timeout=remaining)
            meta=response.response_metadata or {}
            usage=response.usage_metadata or {}
            tokens=meta.get('token_usage') or {}
            headers=meta.get('headers') or {}
            data=dict(resolved_model=meta.get('model_name'),model_snapshot='unavailable',
                request_id=headers.get('x-request-id') or headers.get('x-ds-request-id'),response_id=response.id,
                response_id_kind='langchain_message_id',provider_response_id=meta.get('id'),
                finish_reason=meta.get('finish_reason'),input_tokens=usage.get('input_tokens',tokens.get('prompt_tokens')),
                output_tokens=usage.get('output_tokens',tokens.get('completion_tokens')),
                total_tokens=usage.get('total_tokens',tokens.get('total_tokens')))
            return response.content,data
        finally:
            await transport.aclose()

    def analyze(self,email):
        raise LiveError('configuration_error')  # Must use durable service path.

def classify(exc):
    if isinstance(exc,LiveError): return exc.kind
    import openai
    if isinstance(exc,openai.AuthenticationError) or getattr(exc,'status_code',None) in (401,403): return 'authentication_error'
    if getattr(exc,'status_code',None)==429: return 'rate_limited'
    if getattr(exc,'status_code',0) and getattr(exc,'status_code',0)>=500: return 'provider_5xx'
    if isinstance(exc,(TimeoutError,openai.APITimeoutError)): return 'timeout'
    if isinstance(exc,(ConnectionError,openai.APIConnectionError)): return 'network_error'
    return 'configuration_error'
