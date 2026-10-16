"""Versioned multi-issue contract. Evidence validation is not semantic verification."""
from typing import Literal
from pydantic import Field, model_validator
from src.domain.contracts import StrictModel, EmailInput, AnalysisResult, RunConfig, digest

SCHEMA = 'analysis-v3'
TAXONOMY = 'complaint-issues-v3'
Sentiment = Literal['positive','neutral','negative','mixed','unknown']
Urgency = Literal['low','medium','high','unknown']
Reason = Literal['product quality','delivery delay','customer service','wrong item','after-sales service',
                 'health or safety issue','refund request','size/fit issue','none','other','unknown']
Process = Literal['product issue','store service issue','delivery/logistics issue',
                  'customer service response issue','refund/exchange process issue','unclear','none','unknown']


class Evidence(StrictModel):
    field: Literal['subject','body']
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start:
            raise ValueError('Evidence must have positive length')
        return self


class Issue(StrictModel):
    issue_id: str = Field(min_length=1)
    object_type: Literal['product','service','unknown']
    object_name: str = Field(min_length=1)
    category: AnalysisResult.model_fields['product_category'].annotation
    issue_kind: Literal['complaint','inquiry','praise','other','unknown']
    reason: Reason
    sentiment: Sentiment
    urgency: Urgency
    resolution: Literal['unresolved','resolved','not_applicable','unknown']
    evidence: list[Evidence]
    business_process: Process
    routing_team: Literal['product_support','store_operations','customer_support','logistics','refunds','unassigned','none']
    attribution_certainty: Literal['reported','inferred','unclear','unknown','not_applicable']
    missing_evidence: list[str]
    responsibility: Literal['unverified'] = 'unverified'
    customer_requests: list[str]
    customer_importance: Literal['primary','secondary','equal','unspecified']
    importance_evidence: list[Evidence]
    handling_priority: int | None = Field(default=None,ge=1)
    priority_rationale: str | None = None
    extraction_basis: Literal['native','v2_projection'] = 'native'

    @model_validator(mode='after')
    def consistency(self):
        if self.extraction_basis == 'native' and not self.evidence:
            raise ValueError('Native issue requires source evidence')
        if self.extraction_basis=='native' and self.issue_kind=='complaint':
            if self.reason=='none': raise ValueError('Complaint reason cannot be none')
            if self.reason=='health or safety issue' and self.urgency!='high':
                raise ValueError('Explicit safety complaint requires high urgency')
        if self.customer_importance != 'unspecified' and not self.importance_evidence:
            raise ValueError('Customer importance requires source evidence')
        if (self.handling_priority is None) != (self.priority_rationale is None):
            raise ValueError('Priority and rationale must be supplied together')
        if self.priority_rationale is not None and not self.priority_rationale.strip():
            raise ValueError('Priority rationale cannot be blank')
        if self.business_process in ('unclear','unknown') and not self.missing_evidence:
            raise ValueError('Uncertain attribution requires missing evidence')
        return self


class Relation(StrictModel):
    from_issue: str
    to_issue: str
    kind: Literal['equal_importance','reported_dependency']
    evidence: list[Evidence] = Field(min_length=1)


class AnalysisV3(StrictModel):
    schema_version: Literal['analysis-v3'] = SCHEMA
    taxonomy_version: Literal['complaint-issues-v3'] = TAXONOMY
    sentiment: Sentiment
    urgency: Urgency
    request_types: list[Literal['information','repair','replacement','refund','investigation','acknowledgement','other','unknown']] = Field(min_length=1)
    complaint_status: Literal['current_unresolved','resolved','no_complaint','unknown']
    mentioned_store: str = Field(min_length=1)
    store_verification: Literal['mentioned_only','uncertain_mention','unknown','unavailable']
    contact_channel: Literal['email','phone','chat','in_person','other','unknown','unavailable']
    purchase_channel: Literal['online','physical_store','phone','other','unknown','unavailable']
    summary: str = Field(min_length=1)
    suggested_reply: str = Field(min_length=1)
    issues: list[Issue] = Field(min_length=1,max_length=30)
    relations: list[Relation] = Field(default_factory=list)
    compatibility_origin: AnalysisResult | None = None

    @model_validator(mode='after')
    def consistency(self):
        ids=[i.issue_id for i in self.issues]
        if len(set(ids)) != len(ids): raise ValueError('Duplicate issue ID')
        for rel in self.relations:
            if rel.from_issue not in ids or rel.to_issue not in ids or rel.from_issue==rel.to_issue:
                raise ValueError('Invalid issue relation')
            if rel.kind=='equal_importance' and any(i.customer_importance!='equal' for i in self.issues if i.issue_id in (rel.from_issue,rel.to_issue)):
                raise ValueError('Equal relation conflicts with customer importance')
        if self.compatibility_origin is None and any(i.extraction_basis!='native' for i in self.issues):
            raise ValueError('Projection needs its original v2 result')
        if self.compatibility_origin is not None and any(i.extraction_basis!='v2_projection' for i in self.issues):
            raise ValueError('Native output cannot supply compatibility origin')
        unresolved=any(i.issue_kind=='complaint' and i.resolution=='unresolved' for i in self.issues)
        if unresolved and self.complaint_status in ('resolved','no_complaint'):
            raise ValueError('Unresolved complaint conflicts with email status')
        if self.complaint_status=='current_unresolved' and not unresolved and self.compatibility_origin is None:
            raise ValueError('Current complaint needs an unresolved issue')
        if any(i.urgency=='high' for i in self.issues) and self.urgency!='high':
            raise ValueError('Email urgency cannot hide a high urgency issue')
        for s in (self.summary,self.suggested_reply,self.mentioned_store):
            if not s.strip(): raise ValueError('Blank text')
        return self

    def validate_input(self,email: EmailInput):
        for ev in [e for i in self.issues for e in i.evidence+i.importance_evidence]+[e for r in self.relations for e in r.evidence]:
            if getattr(email,ev.field)[ev.start:ev.end] != ev.quote:
                raise ValueError('Evidence does not match original input')
        return self


class EmailAnalysis(StrictModel):
    """Portable typed envelope; AnalysisRun additionally carries attempts/status."""
    email: EmailInput
    input_hash: str
    config: RunConfig
    analysis: AnalysisV3
    resolved_model: str | None = None

    @model_validator(mode='after')
    def binding(self):
        if self.input_hash!=self.email.input_hash or self.config.schema_version!=SCHEMA or self.config.taxonomy_version!=TAXONOMY:
            raise ValueError('Input/schema/taxonomy binding mismatch')
        self.analysis.validate_input(self.email)
        return self


def to_v2(value: AnalysisV3,policy='customer-primary-v1'):
    if policy in ('customer-primary-v2-safe','owner-operational-v2-safe'):
        from src.domain.v3_compatibility import project
        return project(value,policy)
    if policy not in ('customer-primary-v1','owner-operational-v1'):raise ValueError('Unknown compatibility policy')
    if value.compatibility_origin is not None:
        return value.compatibility_origin,['v2-origin restored; new issue fields unavailable']
    diagnostics=['v3 issue evidence, channels, lifecycle, routing and priority not representable in v2']
    primary=[i for i in value.issues if i.customer_importance=='primary']
    selected=primary[0] if len(primary)==1 else value.issues[0] if len(value.issues)==1 else None
    if selected is None and policy=='owner-operational-v1':
        ranked=[i for i in value.issues if i.handling_priority is not None]
        if ranked:
            first=min(i.handling_priority for i in ranked)
            candidates=[i for i in ranked if i.handling_priority==first]
            if len(candidates)==1:
                selected=candidates[0]
                diagnostics.append('Explicit owner-operational-v1 lossy projection uses handling order, NOT customer primary importance')
    complaint=value.complaint_status=='current_unresolved'
    if value.complaint_status=='unknown':diagnostics.append('Complaint status unknown projects to false; v2 cannot express pending complaint status')
    if selected is None: diagnostics.append('No unique customer primary issue; operational order is not customer importance')
    reason=selected.reason if selected else 'other'
    if reason=='size/fit issue': reason='other';diagnostics.append('size/fit issue projects to other, never wrong item')
    sentiment=value.sentiment
    if sentiment=='mixed': sentiment='unknown';diagnostics.append('mixed sentiment projects to unknown')
    return AnalysisResult(store_location=value.mentioned_store,product_name=selected.object_name if selected else 'unknown',
        product_category=selected.category if selected else 'unknown',sentiment=sentiment,urgency=value.urgency,
        is_complaint=complaint,complaint_reason=reason if complaint else 'none',
        source_attribution=(selected.business_process if selected else 'unclear') if complaint else 'none',
        key_information=[ev.quote for i in value.issues for ev in i.evidence],summary=value.summary,
        suggested_reply=value.suggested_reply,confidence=0.0),diagnostics+['v2 confidence unavailable; compatibility sentinel 0.0']


def from_v2(value: AnalysisResult):
    issue=Issue(issue_id='legacy-primary',object_type='unknown',object_name=value.product_name,category=value.product_category,
        issue_kind='complaint' if value.is_complaint else 'unknown',reason=value.complaint_reason,sentiment=value.sentiment,
        urgency=value.urgency,resolution='unknown',evidence=[],business_process=value.source_attribution,
        routing_team='unassigned',attribution_certainty='unknown',missing_evidence=['v2 did not record issue evidence or verified responsibility'],
        customer_requests=[],customer_importance='unspecified',importance_evidence=[],extraction_basis='v2_projection')
    return AnalysisV3(sentiment=value.sentiment,urgency=value.urgency,request_types=['unknown'],complaint_status='unknown',
        mentioned_store=value.store_location,store_verification='unavailable',contact_channel='unavailable',purchase_channel='unavailable',
        summary=value.summary,suggested_reply=value.suggested_reply,issues=[issue],compatibility_origin=value)


def stored_analysis(run):
    if run.config.schema_version!=SCHEMA: raise ValueError('Not a v3 run')
    value=AnalysisV3.model_validate(run.metadata['analysis_v3'])
    EmailAnalysis(email=run.email,input_hash=run.input_hash,config=run.config,analysis=value,
                  resolved_model=run.metadata.get('resolved_model'))
    if run.metadata.get('analysis_v3_hash')!=digest(value.model_dump()): raise ValueError('Stored v3 output hash mismatch')
    if to_v2(value,(run.config.parameters or {}).get('projection_policy','customer-primary-v1'))[0]!=run.result: raise ValueError('Stored v2 projection mismatch')
    return value
