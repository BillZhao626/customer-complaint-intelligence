"""Q&A orchestration: context isolation, durable claims, strict outputs, no product writes."""
import asyncio
import json
from uuid import uuid4
import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from src.application.copilot_questions import context_for, offline_answer, VERSION
from src.application.live_execution import strict_json
from src.infrastructure.copilot_repository import CopilotRepository
from src.infrastructure.deepseek import classify
from src.domain.contracts import digest


class ProviderAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    answer: StrictStr = Field(min_length=1, max_length=12000)
    citations: list[StrictStr] = Field(min_length=1, max_length=40)
    uncertainty: list[StrictStr] = Field(max_length=20)
    actions: list[StrictStr] = Field(max_length=20)


class CopilotService:
    def __init__(self, store):
        self.store = store
        self.repository = CopilotRepository(store.path)

    def ask(self, case_id, question, *, operation_id=None, provider=None, budget_id=None, max_requests=1):
        question = question.strip()
        if not 1 <= len(question) <= 1000: raise ValueError('请输入1–1000字的问题')
        context = context_for(self.store, case_id)
        mode = 'offline_evidence'
        identity = dict(model='deterministic_rules', prompt=VERSION)
        budget = None
        if provider is not None:
            # Deliberately closed live gate. A label alone cannot authorize network.
            if not isinstance(provider.mock_http_transport, httpx.MockTransport) or provider.provider is not None:
                raise ValueError('实时AI追问待独立授权及Provider验证；当前只允许SDK Mock HTTP')
            if len(json.dumps(context,ensure_ascii=False)) > 60000:
                raise ValueError('当前线程超出受控问答上下文上限，请人工缩小资料范围后独立验证')
            mode = 'offline_mock_http'; identity = provider.identity
            budget = (budget_id or '', max_requests)
        record, fresh = self.repository.claim(context, question, operation_id or str(uuid4()), mode, digest(identity), budget)
        if not fresh: return record
        try:
            if provider is None:
                result = offline_answer(context, question)
            else:
                # Only this case's persisted context is available to the provider.
                raw, usage = asyncio.run(provider.request(dict(context=context, question=question), False, provider.settings.deadline))
                result = ProviderAnswer.model_validate(strict_json(raw)).model_dump()
                allowed = {r['id'] for r in context['references']}
                if not set(result['citations']) <= allowed: raise ValueError('invalid_citation')
                if usage.get('finish_reason') != 'stop' or usage.get('resolved_model') != provider.settings.model:
                    raise ValueError('invalid_provider_identity')
                if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens','output_tokens','total_tokens')):
                    raise ValueError('invalid_usage')
                if usage['input_tokens'] == 0 or usage['output_tokens'] == 0 or usage['total_tokens'] != usage['input_tokens']+usage['output_tokens']:
                    raise ValueError('invalid_usage')
                result.update(identity, usage=usage)
                result['uncertainty'].append('SDK Mock HTTP输出；未通过真实Provider语义验证，不是Gold。')
                if context['quality']['status'] == 'blocked' or not context['accepted']:
                    result['answer'] = '【需人工介入】问答不能解除当前分析阻断。\n'+result['answer']
            result['references'] = [r for r in context['references'] if r['id'] in result['citations']]
            return self.repository.finish(record['run_id'], result)
        except Exception as exc:
            # Never persist provider errors containing mail, raw payloads or credentials.
            kind = 'invalid_response' if isinstance(exc, ValueError) else classify(exc)
            return self.repository.finish(record['run_id'], dict(error=kind, usage=None, message='问答未完成；未修改草稿或审核。不会自动重试。', **identity), 'failed')
