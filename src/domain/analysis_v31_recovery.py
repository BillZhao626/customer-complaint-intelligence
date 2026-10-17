"""New explicit validation profile with the same wire, not a historical replacement."""
import re
from src.domain.analysis_v3 import AnalysisV3
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.application.urgency_context_recovery import signals,evidence_context
from src.application.urgency_context_v1 import bare_help
from src.application.research_policy_v2 import requested_language,language


class RecoveryAnalysisV31(ContextAnalysisV31):
    def validate_input(self,email):
        AnalysisV3.validate_input(self,email)
        for issue in self.issues:
            for ev in issue.risk_evidence+issue.urgency_evidence:
                if not 0<=ev.start<ev.end<=len(getattr(email,ev.field)) or getattr(email,ev.field)[ev.start:ev.end]!=ev.quote:
                    raise ValueError('Risk/urgency evidence does not match input')
            facts=signals(evidence_context(email,issue.urgency_evidence),already_visible=True)
            basis=issue.urgency_basis;u=issue.urgency;risk=issue.risk_level
            if basis=='general_help':
                if not bare_help(email.body) or not facts['bare_help']:raise ValueError('general_help requires undifferentiated source help evidence')
                if risk!='severe' and u!='medium':raise ValueError('Bare help default requires medium')
            if basis=='explicit_urgent' and not facts['urgent']:raise ValueError('Explicit urgent basis lacks active source evidence')
            if basis=='explicit_relaxed' and not facts['relaxed']:raise ValueError('Relaxed basis lacks active source evidence')
            if basis=='repeated_failure' and not facts['repeated_failure']:raise ValueError('Repeated failure basis lacks evidenced service failure')
            if basis=='safety' and (risk not in ('minor','severe') or not issue.risk_evidence):raise ValueError('Safety basis requires assessed risk and evidence')
            if basis=='unknown' and u!='unknown':raise ValueError('Unknown basis cannot certify known urgency')
            if risk!='severe' and not facts['ambiguous']:
                if basis=='explicit_urgent' and u!='high':raise ValueError('Active urgent request contradicts urgency')
                if basis=='explicit_relaxed' and u!='low' and not (facts['urgent'] or facts['deadline']):raise ValueError('Relaxed request contradicts urgency')
                if basis=='repeated_failure' and u!='medium' and not (facts['urgent'] or facts['deadline'] or facts['relaxed']):raise ValueError('Repeated failure override needs context evidence')
            if issue.customer_importance=='equal' and not any(re.search(r'equal|equally|same importance|同等重要|一样重要|同样重要',e.quote,re.I) for e in issue.importance_evidence):
                raise ValueError('Together does not establish equal importance')
        global_signals=signals(email.subject+'\n'+email.body)
        if global_signals['severe'] and not any(i.risk_level=='severe' and i.urgency=='high' and signals(evidence_context(email,i.risk_evidence),already_visible=True)['severe'] for i in self.issues):
            raise ValueError('Explicit severe safety anchor omitted or downgraded')
        want=requested_language(email.body);actual=language(self.suggested_reply)
        if want in ('en','zh') and actual in ('en','zh') and want!=actual:raise ValueError('Wrong customer reply language')
        if self.reply_language in ('en','zh') and actual in ('en','zh') and self.reply_language!=actual:raise ValueError('Declared reply language contradicts text')
        return self
