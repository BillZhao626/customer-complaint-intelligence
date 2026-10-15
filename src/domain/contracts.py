"""P1 single-email / primary-issue contract. Structure is not semantic accuracy."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProductCategory = Literal['Beauty/Personal Care','Clothing','Electronics','Food/Beverage','Furniture','Home Appliances','Service/Other','Sports/Outdoor','unknown']
PRODUCT_CATEGORIES = get_args(ProductCategory)
TaxonomyVersion = Literal['research-products-v2']
RunStatus = Literal['succeeded','failed','running','interrupted_or_unknown']


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True,extra='forbid',frozen=True,allow_inf_nan=False)


class EmailInput(StrictModel):
    email_id: str = Field(min_length=1,max_length=200)
    subject: str = Field(max_length=2000)
    body: str = Field(min_length=1,max_length=100000)

    @field_validator('email_id','body')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Email ID and body must not be blank')
        return value

    @property
    def input_hash(self):
        return digest(dict(subject=self.subject,body=self.body))


class RunConfig(StrictModel):
    backend: Literal['offline_fake','legacy_mock','deepseek_live'] = 'offline_fake'
    model_id: str = Field(default='fixture-fake-v1',min_length=1)
    prompt_version: str = Field(default='offline-demo-v1',min_length=1)
    schema_version: str = Field(default='analysis-v2',min_length=1)
    taxonomy_version: TaxonomyVersion = 'research-products-v2'

    prompt_hash: str | None = None
    parameters: dict | None = None

    @property
    def cohort_id(self):
        return digest(self.model_dump(exclude_none=True))


def idempotency_key(email: EmailInput, config: RunConfig):
    return digest(dict(email_id=email.email_id,input_hash=email.input_hash,config=config.model_dump(exclude_none=True)))


class AnalysisResult(StrictModel):
    store_location: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    product_category: ProductCategory
    sentiment: Literal['positive','neutral','negative','unknown']
    urgency: Literal['low','medium','high','unknown']
    is_complaint: bool
    complaint_reason: Literal['product quality','delivery delay','customer service','wrong item','after-sales service','health or safety issue','refund request','none','other','unknown']
    source_attribution: Literal['product issue','store service issue','delivery/logistics issue','customer service response issue','refund/exchange process issue','unclear','none','unknown']
    key_information: list[str]
    summary: str = Field(min_length=1)
    suggested_reply: str = Field(min_length=1)
    confidence: float = Field(ge=0,le=1)

    @field_validator('store_location','product_name','summary','suggested_reply')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Blank string is missing, not unknown')
        return value


class ErrorDTO(StrictModel):
    error_type: str
    message: str
    occurred_at: str


class AnalysisAttempt(StrictModel):
    attempt_no: int
    started_at: str
    finished_at: str | None
    parse_status: Literal['passed','failed','not_run']
    contract_status: Literal['passed','failed','not_run']
    normalization_status: Literal['identity','mapped','incompatible','failed','not_run']
    business_status: Literal['passed','warning','not_run']
    warnings: list[str]
    raw_output: str | None
    error: ErrorDTO | None
    elapsed_ms: float | None = None
    parsed_output: dict | list | str | int | float | bool | None = None
    metadata: dict = Field(default_factory=dict)
    stage: str | None = None


class AnalysisRun(StrictModel):
    run_id: str
    idempotency_key: str
    email: EmailInput
    input_hash: str
    config: RunConfig
    cohort_id: str
    status: RunStatus
    created_at: str
    result: AnalysisResult | None
    attempts: list[AnalysisAttempt]
    metadata: dict = Field(default_factory=dict)


class LegacyProviderResult(AnalysisResult):
    """Independent strict structure check BEFORE legacy normalization."""
    product_category: Literal['Electronics','Home Appliances','Clothing','Furniture','Beauty Products','Sportswear','Service','Other']
    sentiment: Literal['positive','neutral','negative']
    urgency: Literal['low','medium','high']


def adapt_legacy(data):
    raw = LegacyProviderResult.model_validate(data).model_dump()
    # Exact shared categories alone have unambiguous meaning across both schemas.
    category = raw['product_category']
    warnings=[]
    if category not in PRODUCT_CATEGORIES:
        raw['product_category']='unknown'
        warnings.append(f'legacy category {category!r} has no approved unambiguous mapping')
    return AnalysisResult.model_validate(raw), warnings


def business_warnings(result):
    warnings=[]
    if not result.is_complaint and (result.complaint_reason not in ('none','unknown') or result.source_attribution not in ('none','unknown')):
        warnings.append('Non-complaint with a complaint reason/source: requires semantic review')
    if result.is_complaint and result.complaint_reason=='none':
        warnings.append('Complaint with reason none: requires semantic review')
    return warnings
