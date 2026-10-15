"""Evaluation-only contract; preserves the product's frozen analysis-v2 contract."""
from typing import Literal
from pydantic import Field, create_model, model_validator
from src.domain.contracts import StrictModel, AnalysisResult, EmailInput, digest
from src.evaluation.core import FIELDS

ExpectedSeven = create_model('ExpectedSeven', __base__=StrictModel,
    **{name:(AnalysisResult.model_fields[name].annotation | None, ...) for name in FIELDS})


class Provenance(StrictModel):
    kind: Literal['template_synthetic','developer_synthetic','human_authored','real_consumer']
    source: str = Field(min_length=1)
    independent: bool = False
    source_hash: str | None = None
    exposure: str = 'development_exposed'


class ContentReference(StrictModel):
    status: Literal['pending','approved'] = 'pending'
    facts: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    reviewer: str | None = None

    @model_validator(mode='after')
    def approval(self):
        if self.status == 'approved' and (not self.reviewer or not self.facts or not self.constraints):
            raise ValueError('Approved content reference requires reviewer, facts and constraints')
        return self


class Sample(StrictModel):
    dataset_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    split: Literal['development','holdout_candidate','holdout']
    provenance: Provenance
    template_group: str = Field(min_length=1)
    semantic_group: str = Field(min_length=1)
    subject: str
    email_body: str
    input_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    input_schema_version: Literal['email-input-v1']
    taxonomy_version: Literal['research-products-v2']
    annotation_version: str = Field(min_length=1)
    expected: ExpectedSeven
    reference_status: Literal['template_reference','developer_reference','human_pending','human_gold']
    summary_reference: ContentReference
    reply_reference: ContentReference
    attribution_reference: ContentReference
    applicable_checks: list[Literal['seven_fields','summary','reply','aggregate','traceability']]
    exclusions: dict[str,str] = Field(default_factory=dict)
    reviewer: list[str] = Field(default_factory=list)
    adjudication: Literal['pending','accepted'] = 'pending'
    freeze_id: str | None = None
    scenarios: list[str] = Field(default_factory=list)

    def email(self):
        return EmailInput(email_id=self.sample_id,subject=self.subject,body=self.email_body)

    @model_validator(mode='after')
    def integrity(self):
        if self.email().input_hash != self.input_hash:
            raise ValueError('Input hash differs; no cleaning or concatenation permitted')
        if len(self.applicable_checks)!=len(set(self.applicable_checks)):
            raise ValueError('Duplicate applicable checks')
        if any(isinstance(v,str) and not v.strip() for v in self.expected.model_dump().values()):
            raise ValueError('Empty expected strings are not pending or unknown')
        if self.reference_status in ('template_reference','developer_reference') and any(v is None for v in self.expected.model_dump().values()):
            raise ValueError('Reference status requires complete seven fields')
        if self.reference_status=='human_gold':
            if len(set(self.reviewer))<2 or self.adjudication!='accepted' or not self.freeze_id:
                raise ValueError('Gold requires two independent reviewer declarations, adjudication and freeze')
            if any(v is None for v in self.expected.model_dump().values()):
                raise ValueError('Gold cannot have pending structured fields')
        if self.split=='holdout' and (not self.provenance.independent or self.provenance.exposure!='sealed'):
            raise ValueError('Previously exposed data cannot be independent holdout')
        return self


def validate_dataset(samples):
    samples=[Sample.model_validate(s.model_dump() if isinstance(s,Sample) else s) for s in samples]
    if not samples:raise ValueError('Empty evaluation dataset')
    if len({s.sample_id for s in samples})!=len(samples):raise ValueError('Duplicate sample_id')
    for key in ('dataset_id','input_schema_version','taxonomy_version','annotation_version'):
        if len({getattr(s,key) for s in samples})!=1:raise ValueError(f'Mixed {key}')
    # Same source kind is required; candidate queues can be stored separately by provenance.
    if len({s.provenance.kind for s in samples})!=1:raise ValueError('Mixed provenance kinds require separate reports')
    if len({s.provenance.source for s in samples})!=1:raise ValueError('Mixed source cohorts require separate reports')
    for key in ('template_group','semantic_group','input_hash'):
        seen={}
        for sample in samples:
            value=getattr(sample,key)
            if value in seen and seen[value]!=sample.split:raise ValueError(f'Split leakage: {key}')
            seen[value]=sample.split
    return samples


def dataset_hash(samples):
    return digest([s.model_dump() for s in sorted(samples,key=lambda s:s.sample_id)])
