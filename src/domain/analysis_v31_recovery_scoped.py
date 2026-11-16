"""Independent v3 diagnostic guard; frozen model experiments use context-v1.

V2 is kept unchanged, including its known cross-event false-positive fixture.
This profile tightens only service-occurrence linkage; no paid prediction uses it.
"""
import re
from src.domain.analysis_v31_recovery import RecoveryAnalysisV31
from src.application.urgency_context_recovery import COUNT,SERVICE,FAILURE,RESOLVED,evidence_context
from src.application.urgency_context_v1 import active_clauses,visible

PROFILE='urgency-context-evidence-p310-v3-scoped-service'


def scoped_repetition(text,already_visible=False):
    active=active_clauses(text if already_visible else visible(text))
    parts=[p for c in active for p in re.split(r'[,，]|\b(?:then|although|whereas)\b',c,flags=re.I) if p.strip()]
    if re.search(RESOLVED,' '.join(parts),re.I):return False
    for n,part in enumerate(parts):
        count=any(not re.search(r"\b(?:not|never|didn't|did not|no)\s+(?:(?:send|receive|have|make)\s+)?$|(?:并非|不是|没有)(?:发过|发送|接到)?$",part[:m.start()],re.I) for m in re.finditer(COUNT,part,re.I))
        if not count or not re.search(SERVICE,part,re.I):continue
        denial=re.search(r'\b(?:not|never)\s+(?:missed|cancelled|unanswered|unfulfilled)|\bno\s+(?:appointments?|visits?)|并未(?:取消|失约)|没有失约',part,re.I)
        if denial:continue
        if re.search(FAILURE,part,re.I):return True
        # Cross-clause ellipsis is allowed only after an unfulfilled service
        # promise, and only if the following fragment has no different service
        # subject. Answered messages cannot borrow one appointment cancellation.
        if (n+1<len(parts) and re.search(r'promis|承诺',part,re.I)
            and not re.search(r'\b(?:answered|received|arrived)\b|已(?:回电|回复)|已经兑现',part,re.I)
            and re.search(FAILURE,parts[n+1],re.I) and not re.search(SERVICE,parts[n+1],re.I)):
            return True
    return False


class ScopedRecoveryAnalysisV31(RecoveryAnalysisV31):
    def validate_input(self,email):
        super().validate_input(email)
        spans=[e for i in self.issues for e in i.evidence+i.importance_evidence]+[e for r in self.relations for e in r.evidence]
        for e in spans:
            if not 0<=e.start<e.end<=len(getattr(email,e.field)):
                raise ValueError('Evidence bounds exceed the original source field')
        for i in self.issues:
            if i.urgency_basis=='repeated_failure' and not scoped_repetition(evidence_context(email,i.urgency_evidence),already_visible=True):
                raise ValueError('Repeated failure count belongs to a different service event or lacks non-performance')
        return self
