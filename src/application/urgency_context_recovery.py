"""Opt-in bounded corrections; the frozen context-v1 implementation is unchanged."""
import re
from src.application import urgency_context_v1 as old

PROFILE = 'urgency-context-evidence-p310-v2'
RELAXED = old.RELAXED+r'|\bno hurry\b|\bnot in any hurry\b|\bcan wait\b|\b(?:a bit |a little )?later is fine\b|晚(?:一)?点(?:儿)?(?:补|处理|回复|再说)?(?:也)?(?:可以|没关系)|迟一点(?:也)?(?:可以|没关系)'
COUNT = r'\btwice\b|\b(?:two|three|several)\s+(?:times|promis\w*|callbacks|replies|support messages|messages)|多次|两次|三次'
SERVICE = r'\b(?:appointment|visits?|replies|reply|callbacks?|support|advisers?|collection|delivery|messages?)\b|预约|回电|回收|客服|回复|送货|上门|消息'
FAILURE = r'missed|cancelled|unanswered|unfulfilled|no reply|zero answers|none (?:arrived|received)|never (?:arrived|received)|未回复|未兑现|取消|未回电|没有回|一次也没有'
RESOLVED = r'now resolved|now fixed|已解决|已修好'


def signals(text, *, already_visible=False):
    masked=text if already_visible else old.visible(text)
    result=old.signals(masked,already_visible=True)
    active=old.active_clauses(masked)
    relaxed=[c.strip() for c in active if old.positive(c,RELAXED)]
    # Require service occasions + non-performance together. Repeated product
    # symptoms/attempts alone do not establish repeated service failure.
    joined=' '.join(active)
    repeated=[]
    def supported(part):
        counts=[m for m in re.finditer(COUNT,part,re.I) if not re.search(
            r"\b(?:not|never|didn't|did not|no)\s+(?:(?:send|receive|have|make)\s+)?$|(?:并非|不是|没有)(?:发过|发送|接到)?$",part[:m.start()],re.I)]
        negated_failure=re.search(r'\b(?:not|never)\s+(?:missed|cancelled|unanswered|unfulfilled)\b|\bno\s+(?:appointments?|visits?)\b|并未(?:取消|失约)|没有失约',part,re.I)
        return bool(counts and re.search(SERVICE,part,re.I) and re.search(FAILURE,part,re.I) and not negated_failure)
    same_clause=any(supported(c) for c in active)
    service_count=re.search(r'\b(?:two|three|several)\s+(?:promised\s+)?(?:replies|callbacks|support messages|messages)\b|(?:多次|两次|三次)(?:承诺)?(?:回电|回复|预约)',joined,re.I)
    linked_clauses=bool(service_count and supported(joined))
    if ((same_clause or linked_clauses) and not re.search(RESOLVED,joined,re.I)):
        repeated=[joined.strip()]
    result.update(profile=PROFILE,relaxed=relaxed,repeated_failure=repeated,
                  ambiguous=bool(result['urgent'] and relaxed))
    result['urgency_candidate']=('high' if result['severe'] else None if result['ambiguous'] else
        'high' if result['urgent'] or result['deadline'] else 'low' if relaxed else
        'medium' if repeated or result['bare_help'] else None)
    return result


def evidence_context(email,evidence):
    """Retain left scope from the original clause, never a detached trigger word.

    The returned fragment ends at the cited span; later uncited facts cannot
    justify this evidence. Quotes are masked in the complete original field.
    """
    pieces=[]
    for ev in evidence:
        source=getattr(email,ev.field)
        if not 0<=ev.start<ev.end<=len(source) or source[ev.start:ev.end]!=ev.quote:
            raise ValueError('Evidence does not match original input')
        masked=old.visible(source)
        boundary=0
        for m in old.SPLIT.finditer(masked[:ev.start]):
            boundary=m.end()
        prefix=masked[boundary:ev.start]
        selected=masked[ev.start:ev.end]
        # A left reporting or negation predicate governs a selected subspan.
        if old.REPORTED.search(prefix) or old.NEGATED.search(prefix):
            selected=' '*len(selected)
        pieces.append(selected)
    return '\n'.join(pieces)
