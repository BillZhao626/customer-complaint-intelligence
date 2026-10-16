from datetime import datetime, timezone
import json
from uuid import uuid4

from src.application.analyzers import Analyzer
from src.domain.contracts import (AnalysisAttempt,AnalysisResult,AnalysisRun,EmailInput,ErrorDTO,RunConfig,
    business_warnings,idempotency_key,PRODUCT_CATEGORIES)


def now():
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:
    def __init__(self,repository,analyzer: Analyzer,config: RunConfig | None=None,budget=None):
        self.budget=budget
        self.repository=repository
        self.analyzer=analyzer
        self.config=config or getattr(analyzer,'config',None) or RunConfig(backend=analyzer.backend,model_id=analyzer.model_id)
        if (self.config.backend,self.config.model_id)!=(analyzer.backend,analyzer.model_id):
            raise ValueError('Analyzer identity must match requested configuration')
        if analyzer.backend=='deepseek_live' and self.config!=analyzer.config:
            raise ValueError('Live prompt/parameters must match analyzer configuration')
        if (self.config.schema_version,self.config.taxonomy_version) not in (('analysis-v2','research-products-v2'),('analysis-v3','complaint-issues-v3')):
            raise ValueError('Unsupported schema version')

    def validate_result(self,data,email):
        if self.config.schema_version=='analysis-v3':
            from src.domain.analysis_v3 import AnalysisV3,to_v2
            from src.domain.contracts import digest
            from src.application.v3_safety import check_reply
            value=AnalysisV3.model_validate(data).validate_input(email)
            if value.compatibility_origin is not None:
                raise ValueError('Providers must produce native v3 output')
            check_reply(value,(self.config.parameters or {}).get('reply_gate_version'))
            result,diagnostics=to_v2(value,(self.config.parameters or {}).get('projection_policy','customer-primary-v1'))
            return result,dict(analysis_v3=value.model_dump(),analysis_v3_hash=digest(value.model_dump()),compatibility_diagnostics=diagnostics)
        return AnalysisResult.model_validate(data),{}

    def analyze(self,email: EmailInput) -> AnalysisRun:
        email=EmailInput.model_validate(email)
        if self.config.backend=='deepseek_live':
            from src.application.live_execution import execute
            return execute(self,email)
        key=idempotency_key(email,self.config)
        existing=self.repository.successful(key)
        if existing:
            return existing
        started=now();raw=None;result=None;error=None;warnings=[];metadata={}
        parse=contract=normalization=business='not_run'
        try:
            response=self.analyzer.analyze(email)
            if not isinstance(response,str):
                raise TypeError('Analyzer must return raw JSON text')
            raw=response
            parse='failed'
            from src.application.live_execution import strict_json
            data=strict_json(raw)
            parse='passed';contract='failed'
            if self.config.backend=='legacy_mock':
                # Validate original mock shape before adding an explicitly unavailable field.
                from src.schemas.complaint_schema import ComplaintAnalysis
                expected=set(ComplaintAnalysis.model_fields)-{'email_id'}
                if not isinstance(data,dict) or set(data)!=expected:
                    raise ValueError('Incomplete legacy mock structure')
                ComplaintAnalysis.model_validate(dict(data,email_id=email.email_id),strict=True)
                normalized=dict(data,source_attribution='unknown')
                warnings.append('Legacy mock has no source_attribution; adapter marks unavailable as unknown')
                if normalized['product_category'] not in PRODUCT_CATEGORIES:
                    normalized['product_category']='unknown'
                    warnings.append('Legacy mock category incompatible with v2')
                if normalized['complaint_reason'] not in AnalysisResult.model_fields['complaint_reason'].annotation.__args__:
                    normalized['complaint_reason']='unknown'
                    warnings.append('Legacy mock complaint_reason incompatible with v2')
                result=AnalysisResult.model_validate(normalized)
                normalization='incompatible'
            else:
                result,metadata=self.validate_result(data,email)
                normalization='identity'
            contract='passed'
            warnings+=business_warnings(result)
            business='warning' if warnings else 'passed'
        except Exception as exc:
            # Errors never embed raw provider exception text or customer content.
            kind='parse_error' if parse=='failed' else 'contract_error' if contract=='failed' else 'analyzer_error'
            error=ErrorDTO(error_type=kind,message=f'{kind}: {type(exc).__name__}',occurred_at=now())
            result=None
        attempt=AnalysisAttempt(attempt_no=1,started_at=started,finished_at=now(),parse_status=parse,
            contract_status=contract,normalization_status=normalization,business_status=business,warnings=warnings,raw_output=raw,error=error)
        run=AnalysisRun(run_id=str(uuid4()),idempotency_key=key,email=email,input_hash=email.input_hash,config=self.config,
            cohort_id=self.config.cohort_id,status='succeeded' if result else 'failed',created_at=started,result=result,attempts=[attempt],metadata=metadata)
        # Persistence failures propagate: the UI must never display a success receipt.
        return self.repository.save(run)

    def aggregate(self,cohort_id,dimension='store_location',store=None,product=None):
        if not cohort_id:
            raise ValueError('An explicit version/backend cohort is required')
        if dimension not in ('store_location','product_category'):
            raise ValueError('Unsupported aggregation dimension')
        groups={}
        for run in self.repository.list_runs(cohort_id=cohort_id,status='succeeded',store=store,product=product):
            value=getattr(run.result,dimension)
            group=groups.setdefault(value,dict(group=value,numerator=0,denominator=0,member_run_ids=[],negative_member_run_ids=[],cohort_id=cohort_id,source='new_sqlite_runs',unit='successful analysis runs; one email per run'))
            group['denominator']+=1
            group['member_run_ids'].append(run.run_id)
            if run.result.sentiment=='negative':
                group['numerator']+=1;group['negative_member_run_ids'].append(run.run_id)
        for group in groups.values():
            group['negative_rate']=group['numerator']/group['denominator']
        return [groups[k] for k in sorted(groups)]
