"""Durable live orchestration, called only by AnalysisService."""
import asyncio
import json
import time
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from pydantic import ValidationError
from src.application.analysis_service import now
from src.domain.contracts import AnalysisAttempt,AnalysisResult,ErrorDTO,business_warnings
from src.infrastructure.deepseek import LiveError,classify
from src.infrastructure.pilot_budget import estimate_cost,PRICE_SOURCE,PRICE_DATE

def strict_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def reject(value): raise ValueError('Non-finite JSON number')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=reject)

def execute(service,email):
    return asyncio.run(_execute(service,email))

async def _execute(service,email):
    repo=service.repository;analyzer=service.analyzer;budget=service.budget
    repo.mark_stale_live((datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat())
    run,owned=repo.claim_live(email,service.config)
    if not owned: return run
    start=time.perf_counter();result=None;status='failed';acquired=False;keep_lease=False
    metadata=dict(requested_model=analyzer.model_id,model_snapshot='unavailable',started_at=run.created_at,
                  cost_cny=None,cost_kind='peak_cache_miss_upper_estimate',price_source=PRICE_SOURCE,price_checked_at=PRICE_DATE,
                  sdk_retries=0,application_retries=0,json_repair_retries=0,fallback=False)
    costs=[];repair=False
    try:
        analyzer.settings.validate()
        if budget is None: raise LiveError('configuration_error')
        budget.verify_config(service.config)
        if hasattr(budget,'pricing'):
            pricing=budget.pricing()
            metadata.update(price_source=pricing['price_source'],price_checked_at=pricing['prices_verified_at'],prices=pricing['prices'])
        budget.acquire(run.run_id,email.input_hash);acquired=True
        for number in range(1,analyzer.settings.max_attempts+1):
            remaining=analyzer.settings.deadline-(time.perf_counter()-start)
            if remaining<=0: raise LiveError('timeout')
            attempt=AnalysisAttempt(attempt_no=number,started_at=now(),finished_at=None,parse_status='not_run',
                contract_status='not_run',normalization_status='not_run',business_status='not_run',warnings=[],raw_output=None,
                error=None,stage='prepared',metadata={'dispatch':'not_sent','retry_kind':'json_repair' if repair else 'network' if number>1 else 'initial',
                    'resolved_model':None,'model_snapshot':'unavailable','request_id':None,'finish_reason':None,
                    'input_tokens':None,'output_tokens':None,'total_tokens':None,'cost_cny':None,
                    'actual_system_prompt_sha256':sha256(analyzer.messages(email,repair)[0][1].encode('utf-8')).hexdigest()})
            repo.put_attempt(run.run_id,attempt)
            bound=budget.reserve(run.run_id,number,email.input_hash,analyzer.messages(email,repair),analyzer.settings.max_tokens)
            attempt=attempt.model_copy(update={'stage':'request','metadata':dict(attempt.metadata,dispatch='started_or_unknown',reserved_upper_cny=bound)})
            repo.put_attempt(run.run_id,attempt)
            call_start=time.perf_counter();kind=None
            try:
                raw,provider_meta=await analyzer.request(email,repair,remaining)
                elapsed=(time.perf_counter()-call_start)*1000
                attempt=attempt.model_copy(update={'raw_output':raw if isinstance(raw,str) else None,'elapsed_ms':elapsed,
                    'metadata':dict(attempt.metadata,**provider_meta,dispatch='response_received'),'stage':'parse'})
                cost=budget.estimate_cost(provider_meta) if hasattr(budget,'estimate_cost') else estimate_cost(provider_meta);costs.append(cost)
                attempt=attempt.model_copy(update={'metadata':dict(attempt.metadata,cost_cny=cost,price_source=metadata['price_source'],price_checked_at=metadata['price_checked_at'])})
                if not isinstance(raw,str) or not raw.strip(): raise LiveError('empty_response')
                attempt=attempt.model_copy(update={'parse_status':'failed'})
                try: data=strict_json(raw)
                except (ValueError,TypeError): raise LiveError('invalid_json') from None
                attempt=attempt.model_copy(update={'parse_status':'passed','parsed_output':data,'contract_status':'failed','stage':'raw_schema'})
                try:
                    result,extra=service.validate_result(data,email)
                    metadata.update(extra)
                    if service.config.schema_version in ('analysis-v3','analysis-v3.1'):
                        metadata['resolved_model']=provider_meta.get('resolved_model')
                except (ValueError,TypeError): raise LiveError('raw_schema_invalid') from None
                attempt=attempt.model_copy(update={'contract_status':'passed','normalization_status':'failed','stage':'normalization'})
                try: result=AnalysisResult.model_validate(result.model_dump())
                except Exception: raise LiveError('normalization_failed') from None
                warnings=business_warnings(result)
                attempt=attempt.model_copy(update={'normalization_status':'identity','business_status':'warning' if warnings else 'passed',
                    'warnings':warnings,'stage':'semantic_warning' if warnings else 'accepted'})
                status='succeeded'
            except Exception as exc:
                result=None;kind=classify(exc)
                if len(costs)<number:costs.append(None)
                attempt=attempt.model_copy(update={'elapsed_ms':(time.perf_counter()-call_start)*1000,
                    'error':ErrorDTO(error_type=kind,message=kind,occurred_at=now())})
                if kind in ('timeout','network_error','interrupted_or_unknown'):
                    status='interrupted_or_unknown';keep_lease=True
                if kind=='authentication_error': budget.halt(kind)
            attempt=attempt.model_copy(update={'finished_at':now()})
            repo.put_attempt(run.run_id,attempt)
            budget.completed(run.run_id,number)
            if result or status=='interrupted_or_unknown' or number==analyzer.settings.max_attempts: break
            if kind not in ('rate_limited','provider_5xx','empty_response','invalid_json','raw_schema_invalid'): break
            repair=kind in ('empty_response','invalid_json','raw_schema_invalid')
            metadata['json_repair_retries' if repair else 'application_retries']+=1
            await asyncio.sleep(min(0.5,max(0,analyzer.settings.deadline-(time.perf_counter()-start))))
    except LiveError as exc:
        metadata['error_type']=exc.kind
        if exc.kind in ('timeout','interrupted_or_unknown'):status='interrupted_or_unknown'
    except BaseException as exc:
        # Preserve pre-call records and global lease after storage failure or interrupt.
        # No success receipt and no automatic second request.
        keep_lease=True
        try: repo.finish_live(run.run_id,'interrupted_or_unknown',None,dict(metadata,error_type='storage_error' if isinstance(exc,Exception) else 'interrupted_or_unknown'))
        except Exception: pass
        raise
    metadata.update(finished_at=now(),elapsed_ms=(time.perf_counter()-start)*1000,
                    cost_cny=sum(costs) if costs and all(c is not None for c in costs) else None)
    try:
        saved=repo.finish_live(run.run_id,status,result,metadata)
    except Exception:
        # Existing running/attempt state is authoritative; global lease remains locked.
        raise
    if acquired and not keep_lease: budget.release(run.run_id)
    return saved
