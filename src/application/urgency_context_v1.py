"""Versioned bounded context evidence checks, not a universal semantic classifier.

Quoted/reported urgency is not a current instruction. Candidates never replace raw
predictions. The historical policy-v2 module is intentionally unchanged.
"""
import re
from src.domain.contracts import digest

PROFILE = 'urgency-context-evidence-v1'
POLICY = 'research-owner-policy-v2-context-review-v1'
QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|「[^」\n]*」|(?<!\w)\x27[^\x27\n]*\x27(?!\w)')
SPLIT = re.compile(r'[.!?。！？;；\n]|\b(?:but|however|nevertheless)\b|但是|不过|然而|但',re.I)
REPORTED = re.compile(r'\b(?:forwarded|quoted|quotation|example|manual|hypothetical|if|they said|he said|she said)\b|转发|引用|引文|例句|说明书|假设|如果',re.I)
NEGATED = re.compile(r"\b(?:no|not|never|without|isn't|wasn't|hasn't|didn't|don't|cannot)\s+(?:\w+\s+){0,4}$|(?:没有|并无|不是|并不|未|不)[^，,]{0,6}$",re.I)
URGENT = r'\bASAP\b|as soon as possible|\burgent(?:ly)?\b|请立即处理|尽快处理|立即处理'
RELAXED = r'\bno rush\b|not urgent|not in a hurry|when convenient|不着急|不急|方便时'
HELP = r'I need help|please contact me|need assistance|请联系我|需要帮助'


def visible(text):
    """Preserve original character positions while excluding quoted material."""
    return QUOTED.sub(lambda m:' '*len(m.group()),text)


def active_clauses(text):
    result=[];start=0
    for m in list(SPLIT.finditer(text))+[None]:
        end=m.start() if m else len(text);part=text[start:end]
        if part.strip() and not REPORTED.search(part):result.append(part)
        if m:start=m.end()
    return result


def positive(part,pattern):
    return any(not NEGATED.search(part[:m.start()]) for m in re.finditer(pattern,part,re.I))


def bare_help(text):
    masked=visible(text)
    if not any(positive(c,HELP) for c in active_clauses(masked)):return False
    rest=re.sub(HELP+r'|\b(?:hello|hi|thanks|thank you)\b|您好|你好|谢谢|我','',masked,flags=re.I)
    return not re.search(r'[A-Za-z0-9\u4e00-\u9fff]',rest)


def signals(text, *, already_visible=False):
    masked=text if already_visible else visible(text)
    active=active_clauses(masked);urgent=[];relaxed=[];repeat=[];deadline=[];severe=[]
    for c in active:
        if positive(c,URGENT):urgent.append(c.strip())
        if positive(c,RELAXED):relaxed.append(c.strip())
        repeats=re.search(r'\btwice\b|\b(?:two|three|several)\s+(?:times|promis\w*|callbacks|replies)|多次|两次|三次',c,re.I)
        failures=re.search(r'missed|cancelled|unanswered|unfulfilled|no reply|none (?:arrived|received)|never (?:arrived|received)|未回复|未兑现|取消|未回电|没有回|一次也没有',c,re.I)
        if repeats and failures and not re.search(r'now resolved|now fixed|已解决|已修好',c,re.I):repeat.append(c.strip())
        # Compound current time constraint + necessity; a date mention alone is not urgent.
        timed=re.search(r'\b(?:by|before).{0,70}(?:today|tonight|tomorrow|\d{1,2}\s*(?:am|pm))\b|今天.{0,12}之前|今日.{0,12}前|今晚之前',c,re.I)
        necessary=re.search(r'\b(?:must|essential|required|need|necessary)\b|必须|务必|需要',c,re.I)
        if timed and necessary and not NEGATED.search(c[:necessary.start()]):deadline.append(c.strip())
        danger=(re.search(r'saucepan|pan handle|锅',c,re.I) and positive(c,r'handle\s+(?:has\s+)?(?:detached|came\s+(?:away|off)|fell\s+off)|锅柄(?:脱落|掉落)'))
        danger= danger or (re.search(r'socket|插座',c,re.I) and positive(c,r'sparks?|冒火花'))
        danger= danger or (re.search(r'battery|电池',c,re.I) and positive(c,r'swollen|smoking|caught fire|膨胀|冒烟|起火'))
        danger= danger or (re.search(r'live wire|电线',c,re.I) and positive(c,r'exposed|裸露'))
        if danger:severe.append(c.strip())
    # Contrast can separate a promise from its non-performance, especially in Chinese.
    joined=' '.join(active)
    if (not repeat and re.search(r'\btwice\b|\b(?:two|three|several)\s+(?:times|promis\w*|callbacks|replies)|多次|两次|三次',joined,re.I)
        and re.search(r'missed|cancelled|unanswered|unfulfilled|no reply|none (?:arrived|received)|未回复|未兑现|取消|未回电',joined,re.I)
        and not re.search(r'now resolved|now fixed|已解决|已修好',joined,re.I)):
        repeat.append(joined)
    ambiguous=bool(urgent and relaxed)
    default='high' if severe else None if ambiguous else 'high' if urgent or deadline else 'low' if relaxed else 'medium' if repeat or bare_help(text) else None
    return dict(profile=PROFILE,urgent=urgent,relaxed=relaxed,repeated_failure=repeat,deadline=deadline,severe=severe,
                bare_help=bare_help(text),ambiguous=ambiguous,urgency_candidate=default,
                semantic_proof=False,caveat='Bounded candidate/context guards; no signal does not prove absence of risk or semantic correctness')


def policy_snapshot():
    data=dict(version=POLICY,validation_profile=PROFILE,source='Current researcher instructions; proposed acceptance change pending explicit comparison approval',
        principle='Evidence and context first; urgency second; basis explains the conclusion, never rewrites raw urgency',
        defaults='bare help medium; routine specific inquiry may low; repeated failure usually medium; evidence may override; unclear unknown',
        safety='severe potential harm always high; source evidence mandatory',
        legacy='research-owner-policy-v2 and historical analysis-v3.1 validators unchanged',gold=False)
    return dict(data,policy_hash=digest(data))
