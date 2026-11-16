"""P5-B2 opt-in contract. Runtime provenance is distinct from raw prediction."""
from typing import Literal
import copy
import re
from pydantic import Field, model_validator
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.domain.analysis_v31 import POLICY, PROJECTION, to_v2
from src.domain.analysis_v3 import AnalysisV3
from src.domain.contracts import digest, idempotency_key
from src.application.research_policy_v2 import language, requested_language
from src.application.urgency_context_v2 import signals

SCHEMA = 'analysis-v3.2'
PROFILE = 'p5b2-context-evidence-v2'

class AnalysisV32(ContextAnalysisV31):
    schema_version: Literal['analysis-v3.2'] = SCHEMA
    mentioned_store: str | None

    @model_validator(mode='after')
    def consistency(self):
        # Preserve all parent email invariants; only optional-store semantics differ.
        ids = [i.issue_id for i in self.issues]
        if len(ids) != len(set(ids)): raise ValueError('Duplicate issue ID')
        for rel in self.relations:
            if rel.from_issue not in ids or rel.to_issue not in ids or rel.from_issue == rel.to_issue:
                raise ValueError('Invalid issue relation')
            if rel.kind == 'equal_importance' and any(i.customer_importance != 'equal' for i in self.issues if i.issue_id in (rel.from_issue, rel.to_issue)):
                raise ValueError('Equal relation conflicts with customer importance')
        if self.compatibility_origin is not None or any(i.extraction_basis != 'native' for i in self.issues):
            raise ValueError('Native v3.2 only')
        unresolved = any(i.issue_kind == 'complaint' and i.resolution == 'unresolved' for i in self.issues)
        if unresolved and self.complaint_status in ('resolved', 'no_complaint'):
            raise ValueError('Unresolved complaint conflicts with email status')
        if self.complaint_status == 'current_unresolved' and not unresolved:
            raise ValueError('Current complaint needs an unresolved issue')
        if any(i.urgency == 'high' for i in self.issues) and self.urgency != 'high':
            raise ValueError('Email urgency cannot hide a high urgency issue')
        if not self.summary.strip() or not self.suggested_reply.strip(): raise ValueError('Blank text')
        if self.mentioned_store is None:
            if self.store_verification not in ('unknown', 'unavailable'): raise ValueError('Named store requires source text')
        elif not self.mentioned_store.strip() or self.store_verification in ('unknown', 'unavailable'):
            raise ValueError('Missing store must be null; named store needs explicit verification state')
        return self

    def validate_input(self, email, *, signal_reader=None):
        evidence_signals = signal_reader or signals
        AnalysisV3.validate_input(self, email)
        if self.mentioned_store is not None and self.mentioned_store not in email.subject+'\n'+email.body:
            raise ValueError('Mentioned store lacks original source')
        # Reuse every context guard with the independently versioned signals function.
        from src.application.urgency_context_v1 import visible, bare_help
        from src.application.product_quality import load_failure
        for issue in self.issues:
            for ev in issue.risk_evidence + issue.urgency_evidence:
                if getattr(email, ev.field)[ev.start:ev.end] != ev.quote:
                    raise ValueError('Risk/urgency evidence does not match input')
            joined = '\n'.join(visible(getattr(email,e.field))[e.start:e.end] for e in issue.urgency_evidence)
            facts = evidence_signals(joined, already_visible=True)
            basis, u, risk = issue.urgency_basis, issue.urgency, issue.risk_level
            if basis == 'general_help' and (not bare_help(email.body) or not facts['bare_help'] or (risk != 'severe' and u != 'medium')):
                raise ValueError('general_help requires undifferentiated medium source help')
            if basis == 'explicit_urgent' and not (facts['urgent'] or facts['deadline']):
                raise ValueError('Explicit urgent basis lacks active request or deadline')
            if basis == 'explicit_relaxed' and not facts['relaxed']: raise ValueError('Relaxed basis lacks active source evidence')
            if basis == 'repeated_failure' and not facts['repeated_failure']: raise ValueError('Repeated failure lacks customer-reported evidence')
            if basis == 'safety' and (risk not in ('minor','severe') or not issue.risk_evidence): raise ValueError('Safety basis requires assessed risk and evidence')
            if basis == 'unknown' and u != 'unknown': raise ValueError('Unknown basis cannot certify known urgency')
            if risk != 'severe' and not facts['ambiguous']:
                if basis == 'explicit_urgent' and u != 'high': raise ValueError('Active urgency requires high')
                if basis == 'explicit_relaxed' and u != 'low' and not (facts['urgent'] or facts['deadline']): raise ValueError('Relaxed request requires low absent stronger evidence')
                if basis == 'repeated_failure' and u != 'medium' and not (facts['urgent'] or facts['deadline'] or facts['relaxed']): raise ValueError('Repeated failure override needs independent evidence')
            if issue.customer_importance == 'equal' and not any(re.search(r'equal|equally|same importance|同等重要|一样重要|同样重要',e.quote,re.I) for e in issue.importance_evidence):
                raise ValueError('Together does not establish equal importance')
        text = email.subject+'\n'+email.body
        if evidence_signals(text)['severe'] and not any(i.risk_level=='severe' and i.urgency=='high' and evidence_signals('\n'.join(e.quote for e in i.risk_evidence))['severe'] for i in self.issues):
            raise ValueError('Explicit severe safety anchor omitted or downgraded')
        if load_failure(text) and not any(i.risk_level=='severe' and i.urgency=='high' and load_failure(' '.join(e.quote for e in i.risk_evidence)) for i in self.issues):
            raise ValueError('Load-bearing failure requires severe/high source evidence')
        # Evaluate latest customer message for multi-turn language, never assistant history.
        current = email.body.rsplit('[customer · current message]\n',1)[-1]
        want, actual = requested_language(current), language(self.suggested_reply)
        if want in ('en','zh') and actual != want: raise ValueError('Wrong customer reply language')
        if self.reply_language != actual: raise ValueError('Declared reply language contradicts text')
        return self

def adapt(data, *, legacy=False, policy=POLICY):
    """Explicit normalization; never edits the supplied object or its raw text."""
    d=copy.deepcopy(data); changes=[]
    if policy != POLICY: raise ValueError('Unrecognized runtime policy')
    if legacy:
        if d.get('schema_version','analysis-v3.1') != 'analysis-v3.1': raise ValueError('Not legacy v3.1')
        d['schema_version']=SCHEMA; changes.append('legacy_schema_to_v3.2')
        if d.get('mentioned_store') in ('','unknown') and d.get('store_verification') in ('unknown','unavailable'):
            d['mentioned_store']=None; changes.append('legacy_missing_store_sentinel_to_null')
    if 'policy_version' in d and d['policy_version'] != policy: raise ValueError('Provider policy conflicts with runtime')
    if 'policy_version' not in d: changes.append('runtime_policy_version')
    d['policy_version']=policy
    actual=language(d.get('suggested_reply',''))
    if 'reply_language' in d and d['reply_language'] != actual: raise ValueError('Provider language label conflicts with text')
    if 'reply_language' not in d: changes.append('runtime_observed_reply_language')
    d['reply_language']=actual
    return d, changes

def wire_schema():
    d=AnalysisV32.model_json_schema()
    for k in ('policy_version','reply_language'):
        d['properties'].pop(k); d['required'].remove(k)
    return d

def validate(data, email, *, legacy=False, context_check_profile=None):
    from src.application.reply_review import check
    normalized, changes=adapt(data,legacy=legacy)
    if context_check_profile is None:
        value=AnalysisV32.model_validate(normalized).validate_input(email); check(value)
    else:
        from src.application.p5b7_context_checks import PROFILE as B7_PROFILE,signals as b7_signals,reply_review
        if context_check_profile!=B7_PROFILE:raise ValueError('Unknown context check profile')
        value=AnalysisV32.model_validate(normalized).validate_input(email,signal_reader=b7_signals)
        if reply_review(value.suggested_reply,email.subject+'\n'+email.body)['findings']:
            raise ValueError('Unverified claim or material promise requires review')
    result, diagnostics=to_v2(value,PROJECTION)
    return value,result,changes,diagnostics

def stored_analysis(run):
    from src.application.live_execution import strict_json
    from src.application.reply_review import VERSION as GATE
    if (run.config.schema_version != SCHEMA or run.config.parameters.get('validation_profile') != PROFILE
        or run.config.parameters.get('policy_version') != POLICY or run.config.parameters.get('projection_policy') != PROJECTION
        or run.config.parameters.get('reply_gate_version') != GATE):
        raise ValueError('v3.2 explicit config binding required')
    value,result,changes,_=validate(strict_json(run.attempts[-1].raw_output),run.email,context_check_profile=run.config.parameters.get('context_check_profile'))
    if (value.model_dump()!=run.metadata.get('analysis_v32') or digest(value.model_dump())!=run.metadata.get('analysis_v32_hash')
        or result!=run.result or changes!=run.metadata.get('runtime_normalization') or digest(result.model_dump())!=run.metadata.get('projection_hash')
        or run.input_hash!=run.email.input_hash or run.cohort_id!=run.config.cohort_id or run.idempotency_key!=idempotency_key(run.email,run.config)
        or run.metadata.get('prediction_kind')!='raw_provider_prediction_with_runtime_context'):
        raise ValueError('v3.2 stored raw/result/context binding mismatch')
    return value
