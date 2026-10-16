"""Bounded lexical policy checks. Findings are candidates, never semantic Gold."""
import re
from src.domain.contracts import digest

POLICY = 'research-owner-policy-v2'
RULES = {
 'urgency': 'General help medium; explicit urgency high; relaxed low absent severe danger; repeated failure usually medium; danger overrides tone; unintelligible unknown.',
 'events': 'Missed promised callback and unanswered warranty are two independently evidenced events; paraphrase alone is one.',
 'importance': 'Follow up together is not equal importance. Drawer, collection and invoice retained; business order separate; dependency needs source.',
 'safety': 'Detached cold saucepan handle and sparks near socket during kettle use severe/high; ordinary drawer collision minor/medium; no injury does not remove severe potential harm.',
 'billing': 'billing/invoice issue -> customer_support coordination; neither refund nor proven fault; v2 other/unclear diagnostic.',
 'reply': 'Main customer language or explicit request; check repeated requests, main request, disclaimers, invented actions, material promises, safety/privacy, all issues separately; unsent/unreviewed.',
 'adoption': 'Adopt approved 11 P3.7 rewrites with new hashes and no inherited references; retain old versions and 20 representatives; 128 pending.',
 'adversarial': 'P35-073 remains adversarial development, excluded from natural email quality denominator.'}
LEDGER = dict(version=POLICY,status='POLICY_V2_OWNER_APPROVED',source='Researcher explicit P3.8 task, 2026-10-16 Asia/Shanghai',
              scope='Future v3.1 only; calibration-decision-v1.1 unchanged',rules=RULES,human_gold_approval=False)
POLICY_HASH = digest(LEDGER)


def clauses(text):
    return [s.strip() for s in re.split(r'[.!?。！？;；\n]|\b(?:but|however)\b|但是|不过|但',text,flags=re.I) if s.strip()]


def positive(text, pattern):
    for clause in clauses(text):
        for m in re.finditer(pattern,clause,re.I):
            prefix=clause[:m.start()]
            if not re.search(r"\b(?:no|not|never|without|isn't|wasn't|hasn't|didn't|don't)\s+(?:\w+\s+){0,3}$|(?:没有|并无|不是|并不|未|不)[^，,]{0,5}$",prefix,re.I):
                return clause
    return None


def assess(text):
    # Closed, documented anchors; no blanket safety-keyword=>high rule.
    severe=None
    for c in clauses(text):
        if re.search(r'\b(?:if|manual|instructions|hypothetical|quoted)\b|说明书|假设|如果|如有',c,re.I):continue
        if re.search(r'saucepan|pan handle|锅',c,re.I) and positive(c,r'handle\s+(?:has\s+)?(?:detached|came\s+(?:away|off)|fell\s+off)|锅柄(?:脱落|掉落)'):
            severe=c
        if re.search(r'socket|插座',c,re.I) and positive(c,r'sparks?|冒火花'):
            severe=c
    urgent=positive(text,r'ASAP|as soon as possible|请立即处理|尽快处理')
    relaxed=positive(text,r'no rush|not urgent|not in a hurry|when convenient|不着急|不急|方便时')
    general=positive(text,r'I need help|please contact me|请联系我|需要帮助')
    if general:
        residual=re.sub(r'I need help|please contact me|请联系我|需要帮助|\b(?:hello|hi|thanks|thank you)\b|您好|你好|谢谢|我','',text,flags=re.I)
        if re.search(r'[A-Za-z0-9\u4e00-\u9fff]',residual):general=None
    repeat=positive(text,r'cancelled twice|missed.{0,20}twice|overdue|past the promised|超过约定|多次|两次')
    if positive(text,r'now resolved|now fixed|already resolved|已解决|已修好'):repeat=None
    if severe: return dict(urgency='high',basis='safety',risk='severe',quote=severe,ambiguous=False)
    for c in clauses(text):
        if re.search(r'drawer|抽屉',c,re.I) and positive(c,r'bump|collision|碰撞|磕碰'):
            return dict(urgency='high' if urgent else 'medium',basis='explicit_urgent' if urgent else 'safety',risk='minor',quote=c,ambiguous=False)
    if urgent and relaxed: return dict(urgency=None,basis='other',risk=None,quote=None,ambiguous=True)
    if urgent:return dict(urgency='high',basis='explicit_urgent',risk=None,quote=urgent,ambiguous=False)
    if relaxed:return dict(urgency='low',basis='explicit_relaxed',risk=None,quote=relaxed,ambiguous=False)
    if repeat:return dict(urgency='medium',basis='repeated_failure',risk=None,quote=repeat,ambiguous=False)
    if general:return dict(urgency='medium',basis='general_help',risk=None,quote=general,ambiguous=False)
    return dict(urgency=None,basis='unknown',risk=None,quote=None,ambiguous=True)


def language(text):
    zh=len(re.findall(r'[\u4e00-\u9fff]',text));en=len(re.findall(r'[A-Za-z]+',text))
    if zh and en and 0.5 < zh/max(en,1) < 2:return 'bilingual'
    return 'zh' if zh>en else 'en' if en else 'unknown'


def requested_language(text):
    # Explicit requests override main-language heuristics; contradictory requests remain ambiguous.
    en=bool(re.search(r'请用(?:英文|英语)回复|reply in English',text,re.I))
    zh=bool(re.search(r'请用中文回复|reply in Chinese',text,re.I))
    return 'bilingual' if en and zh else 'en' if en else 'zh' if zh else language(text)


def validate_policy(value,email):
    text=email.body
    finding=assess(text)
    if finding['risk']=='severe' and not any(i.risk_level=='severe' and i.urgency=='high' and assess(' '.join(e.quote for e in i.risk_evidence))['risk']=='severe' for i in value.issues):
        raise ValueError('Explicit severe safety anchor omitted or downgraded')
    if finding['urgency'] and value.urgency != finding['urgency'] and not any(i.risk_level=='severe' for i in value.issues):
        raise ValueError('Email urgency contradicts explicit policy anchor')
    for i in value.issues:
        if i.customer_importance=='equal':
            if not any(re.search(r'equal|equally|same importance|同等重要|一样重要|同样重要',e.quote,re.I) for e in i.importance_evidence):
                raise ValueError('Together does not establish equal importance')
    want=requested_language(text);actual=language(value.suggested_reply)
    if want in ('en','zh') and actual in ('en','zh') and want!=actual:
        raise ValueError('Wrong customer reply language')
    if value.reply_language in ('en','zh') and actual in ('en','zh') and value.reply_language!=actual:
        raise ValueError('Declared reply language contradicts text')
    return value
