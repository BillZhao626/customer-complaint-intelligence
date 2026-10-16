"""Research owner policy v2 native contract; old v3 validation stays frozen."""
from typing import Literal
from pydantic import Field, model_validator
from src.domain.analysis_v3 import AnalysisV3, Issue, Evidence, Reason, Process
from src.domain.contracts import AnalysisResult, digest

SCHEMA = 'analysis-v3.1'
TAXONOMY = 'complaint-issues-v3.1'
POLICY = 'research-owner-policy-v2'
PROJECTION = 'customer-primary-v31-safe-1'


class IssueV31(Issue):
    reason: Literal[Reason, 'billing/invoice issue']
    business_process: Literal[Process, 'billing/invoice issue']
    risk_level: Literal['severe', 'minor', 'none', 'unknown']
    risk_evidence: list[Evidence]
    risk_rationale: str = Field(min_length=1)
    urgency_basis: Literal['general_help', 'explicit_urgent', 'explicit_relaxed', 'repeated_failure', 'safety', 'other', 'unknown']
    urgency_evidence: list[Evidence] = Field(min_length=1)

    @model_validator(mode='after')
    def consistency(self):
        # Override only the old safety=high invariant; retain the other constraints.
        if self.extraction_basis != 'native' or not self.evidence:
            raise ValueError('v3.1 requires native source evidence')
        if self.issue_kind == 'complaint' and self.reason == 'none':
            raise ValueError('Complaint reason cannot be none')
        if self.customer_importance != 'unspecified' and not self.importance_evidence:
            raise ValueError('Customer importance requires source evidence')
        if (self.handling_priority is None) != (self.priority_rationale is None):
            raise ValueError('Priority and rationale must be supplied together')
        if self.priority_rationale is not None and not self.priority_rationale.strip():
            raise ValueError('Priority rationale cannot be blank')
        if self.business_process in ('unclear', 'unknown') and not self.missing_evidence:
            raise ValueError('Uncertain attribution requires missing evidence')
        if not self.risk_rationale.strip():
            raise ValueError('Risk rationale cannot be blank')
        if self.risk_level in ('severe', 'minor') and not self.risk_evidence:
            raise ValueError('Risk needs original evidence')
        if self.reason == 'health or safety issue' and self.risk_level not in ('severe', 'minor'):
            raise ValueError('Safety reason requires assessed risk')
        if self.risk_level == 'severe' and self.urgency != 'high':
            raise ValueError('Severe potential injury requires high urgency even without actual harm')
        expected = {'general_help': 'medium', 'explicit_urgent': 'high', 'explicit_relaxed': 'low', 'repeated_failure': 'medium'}
        if self.urgency_basis in expected and self.risk_level != 'severe' and self.urgency != expected[self.urgency_basis]:
            raise ValueError('Urgency contradicts declared policy basis')
        if self.reason == 'billing/invoice issue' or self.business_process == 'billing/invoice issue':
            if self.reason != 'billing/invoice issue' or self.business_process != 'billing/invoice issue' or self.routing_team != 'customer_support':
                raise ValueError('Invoice coordination requires billing type and customer_support route')
        return self


class AnalysisV31(AnalysisV3):
    schema_version: Literal['analysis-v3.1'] = SCHEMA
    taxonomy_version: Literal['complaint-issues-v3.1'] = TAXONOMY
    policy_version: Literal['research-owner-policy-v2']
    issues: list[IssueV31] = Field(min_length=1, max_length=30)
    reply_language: Literal['en', 'zh', 'bilingual', 'unknown']
    compatibility_origin: None = None

    @model_validator(mode='after')
    def distinct_events(self):
        signatures = [tuple(sorted((e.field,e.start,e.end,e.quote) for e in i.evidence)) for i in self.issues]
        if len(set(signatures)) != len(signatures):
            raise ValueError('Independent events need independently supporting evidence; duplicated spans require review')
        return self

    def validate_input(self, email):
        super().validate_input(email)
        for issue in self.issues:
            for ev in issue.risk_evidence + issue.urgency_evidence:
                if getattr(email, ev.field)[ev.start:ev.end] != ev.quote:
                    raise ValueError('Risk/urgency evidence does not match input')
        from src.application.research_policy_v2 import validate_policy
        validate_policy(self, email)
        return self


def to_v2(value, policy=PROJECTION):
    if policy != PROJECTION:
        raise ValueError('v3.1 needs its own explicit projection policy')
    from src.domain.v3_compatibility import selected_issue
    issue = selected_issue(value)
    complaint = value.complaint_status == 'current_unresolved'
    billing = issue and issue.reason == 'billing/invoice issue'
    reason = issue.reason if issue else 'other'
    if reason in ('billing/invoice issue', 'size/fit issue'): reason = 'other'
    source = issue.business_process if issue else 'unclear'
    if billing or source == 'billing/invoice issue' or (issue and issue.attribution_certainty in ('unclear','inferred')): source = 'unclear'
    elif issue and issue.attribution_certainty == 'unknown': source = 'unknown'
    diagnostics = [PROJECTION, 'Risk, evidence, routing, customer importance and business order cannot be represented in v2',
                   'Source classification is not verified cause or liability', 'v2 confidence unavailable; sentinel 0.0']
    if billing: diagnostics.append('billing/invoice issue has no v2 equivalent: other/unclear; customer_support is coordination, not fault or refunds')
    if value.complaint_status == 'unknown': diagnostics.append('Unknown complaint status projects to false; preserve v3.1 status')
    if issue is None: diagnostics.append('No unique customer primary; handling order cannot select customer importance')
    if any(i.risk_level == 'minor' and i.reason == 'health or safety issue' for i in value.issues):
        diagnostics.append('Minor safety risk retains medium/low urgency; never reinterpret through old v3 safety invariant')
    return AnalysisResult(store_location=value.mentioned_store if value.store_verification=='mentioned_only' else 'unknown',
        product_name=issue.object_name if issue else 'unknown',product_category=issue.category if issue else 'unknown',
        sentiment='unknown' if value.sentiment=='mixed' else value.sentiment,urgency=value.urgency,is_complaint=complaint,
        complaint_reason=reason if complaint else 'none',source_attribution=source if complaint else 'none',
        key_information=[e.quote for i in value.issues for e in i.evidence],summary=value.summary,
        suggested_reply=value.suggested_reply,confidence=0.0), diagnostics


def stored_analysis(run):
    if (run.config.schema_version,run.config.taxonomy_version) != (SCHEMA,TAXONOMY):
        raise ValueError('Not a v3.1 run')
    value = AnalysisV31.model_validate(run.metadata['analysis_v31']).validate_input(run.email)
    params = run.config.parameters or {}
    if params.get('policy_version') != POLICY or params.get('projection_policy') != PROJECTION:
        raise ValueError('v3.1 policy/config binding mismatch')
    if run.input_hash != run.email.input_hash or digest(value.model_dump()) != run.metadata.get('analysis_v31_hash'):
        raise ValueError('v3.1 input/output binding mismatch')
    if to_v2(value,params['projection_policy'])[0] != run.result:
        raise ValueError('Stored v3.1 projection mismatch')
    if run.metadata.get('prediction_kind') != 'raw_provider_prediction':
        raise ValueError('Prediction identity missing')
    from src.domain.contracts import idempotency_key
    from src.application.live_execution import strict_json
    if run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config):
        raise ValueError('Stored v3.1 run identity mismatch')
    if not run.attempts or AnalysisV31.model_validate(strict_json(run.attempts[-1].raw_output))!=value:
        raise ValueError('Stored prediction differs from raw provider output')
    if run.metadata.get('projection_hash')!=digest(run.result.model_dump()):
        raise ValueError('Projection hash mismatch')
    return value
