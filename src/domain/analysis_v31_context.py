"""Opt-in offline comparison candidate. Same wire fields, different validation profile.

This acceptance change requires researcher confirmation before paid dispatch.
Historical AnalysisV31 behavior is never patched or silently substituted.
"""
import re
from pydantic import Field,model_validator
from src.domain.analysis_v3 import AnalysisV3
from src.domain.analysis_v31 import AnalysisV31,IssueV31,to_v2,POLICY,PROJECTION
from src.domain.contracts import digest,idempotency_key
from src.application.urgency_context_v1 import PROFILE,signals,visible,bare_help
from src.application.research_policy_v2 import requested_language,language


class ContextIssueV31(IssueV31):
    @model_validator(mode='after')
    def consistency(self):
        # All non-urgency guards mirror the immutable IssueV31 contract.
        if self.extraction_basis!='native' or not self.evidence:raise ValueError('v3.1 requires native source evidence')
        if self.issue_kind=='complaint' and self.reason=='none':raise ValueError('Complaint reason cannot be none')
        if self.customer_importance!='unspecified' and not self.importance_evidence:raise ValueError('Customer importance requires source evidence')
        if (self.handling_priority is None)!=(self.priority_rationale is None):raise ValueError('Priority and rationale must be supplied together')
        if self.priority_rationale is not None and not self.priority_rationale.strip():raise ValueError('Priority rationale cannot be blank')
        if self.business_process in ('unclear','unknown') and not self.missing_evidence:raise ValueError('Uncertain attribution requires missing evidence')
        if not self.risk_rationale.strip():raise ValueError('Risk rationale cannot be blank')
        if self.risk_level in ('severe','minor') and not self.risk_evidence:raise ValueError('Risk needs original evidence')
        if self.reason=='health or safety issue' and self.risk_level not in ('severe','minor'):raise ValueError('Safety reason requires assessed risk')
        if self.risk_level=='severe' and self.urgency!='high':raise ValueError('Severe potential injury requires high urgency even without actual harm')
        if self.reason=='billing/invoice issue' or self.business_process=='billing/invoice issue':
            if self.reason!='billing/invoice issue' or self.business_process!='billing/invoice issue' or self.routing_team!='customer_support':
                raise ValueError('Invoice coordination requires billing type and customer_support route')
        return self


class ContextAnalysisV31(AnalysisV31):
    issues:list[ContextIssueV31]=Field(min_length=1,max_length=30)

    def validate_input(self,email):
        AnalysisV3.validate_input(self,email)
        global_signals=signals(email.subject+'\n'+email.body)
        for issue in self.issues:
            for ev in issue.risk_evidence+issue.urgency_evidence:
                if getattr(email,ev.field)[ev.start:ev.end]!=ev.quote:raise ValueError('Risk/urgency evidence does not match input')
            # Mask quotations in the ORIGINAL field, then take the evidence span.
            # A model cannot turn a quoted ASAP into a current request by quoting only its word.
            joined='\n'.join(visible(getattr(email,ev.field))[ev.start:ev.end] for ev in issue.urgency_evidence)
            facts=signals(joined,already_visible=True)
            basis=issue.urgency_basis;u=issue.urgency;risk=issue.risk_level
            if basis=='general_help':
                if not bare_help(email.body) or not facts['bare_help']:raise ValueError('general_help requires undifferentiated source help evidence')
                if risk!='severe' and u!='medium':raise ValueError('Bare help default requires medium, not arbitrary label mapping')
            if basis=='explicit_urgent' and not facts['urgent']:raise ValueError('Explicit urgent basis lacks active, nonquoted urgency evidence')
            if basis=='explicit_relaxed' and not facts['relaxed']:raise ValueError('Relaxed basis lacks active source evidence')
            if basis=='repeated_failure' and not facts['repeated_failure']:raise ValueError('Repeated failure basis lacks an evidenced repeated failure')
            if basis=='safety' and (risk not in ('minor','severe') or not issue.risk_evidence):raise ValueError('Safety basis requires assessed risk and evidence')
            if basis=='unknown' and u!='unknown':raise ValueError('Unknown basis cannot certify a known urgency; use supported other evidence')
            if risk!='severe' and not facts['ambiguous']:
                if basis=='explicit_urgent' and u!='high':raise ValueError('Unqualified active urgent request contradicts declared urgency')
                if basis=='explicit_relaxed' and u!='low' and not (facts['urgent'] or facts['deadline']):raise ValueError('Unqualified relaxed request contradicts declared urgency')
                if basis=='repeated_failure' and u!='medium' and not (facts['urgent'] or facts['deadline'] or facts['relaxed']):raise ValueError('Repeated failure override needs independent context evidence')
            if issue.customer_importance=='equal' and not any(re.search(r'equal|equally|same importance|同等重要|一样重要|同样重要',e.quote,re.I) for e in issue.importance_evidence):
                raise ValueError('Together does not establish equal importance')
        if global_signals['severe'] and not any(i.risk_level=='severe' and i.urgency=='high' and signals('\n'.join(e.quote for e in i.risk_evidence))['severe'] for i in self.issues):
            raise ValueError('Explicit severe safety anchor omitted or downgraded')
        # Global defaults are observations; they do not overwrite a supported issue-level decision.
        want=requested_language(email.body);actual=language(self.suggested_reply)
        if want in ('en','zh') and actual in ('en','zh') and want!=actual:raise ValueError('Wrong customer reply language')
        if self.reply_language in ('en','zh') and actual in ('en','zh') and self.reply_language!=actual:raise ValueError('Declared reply language contradicts text')
        return self


def wire_schema():return AnalysisV31.model_json_schema()


def stored_context_analysis(run):
    params=run.config.parameters
    if (run.config.schema_version!='analysis-v3.1' or run.config.taxonomy_version!='complaint-issues-v3.1'
        or params.get('urgency_validation_profile')!=PROFILE or params.get('policy_version')!=POLICY
        or params.get('projection_policy')!=PROJECTION or run.metadata.get('urgency_validation_profile')!=PROFILE):
        raise ValueError('Explicit context validation profile and v3.1 policy/config required')
    value=ContextAnalysisV31.model_validate(run.metadata['analysis_v31']).validate_input(run.email)
    if (run.input_hash!=run.email.input_hash or run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config)
        or digest(value.model_dump())!=run.metadata.get('analysis_v31_hash') or run.metadata.get('prediction_kind')!='raw_provider_prediction'
        or to_v2(value,PROJECTION)[0]!=run.result or digest(run.result.model_dump())!=run.metadata.get('projection_hash')):
        raise ValueError('Context run/prediction/projection identity drift')
    from src.application.live_execution import strict_json
    if ContextAnalysisV31.model_validate(strict_json(run.attempts[-1].raw_output))!=value:raise ValueError('Context prediction differs from raw')
    return value
