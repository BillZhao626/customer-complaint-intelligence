"""Scoped runtime review on top of the existing product guard, opt-in for R2.

Does not approve drafts, repair model fields, or waive failed analysis contracts.
"""
from src.application.product_quality import inspect as original
from src.evaluation.p5b5r2_judge import diagnose
from src.domain.contracts import digest
import re

VERSION='p5b5r2-receipt-review-1'

def supported_record(reply,quote,email,events):
    from src.evaluation.p5b5r2_judge import SCOPES
    for clause in re.split(r'[。！？;；\n.!?]',reply):
        if quote not in clause:continue
        domains=[kinds for _,(pattern,kinds) in SCOPES.items() if re.search(pattern,clause,re.I)]
        valid=[e for e in events if e.get('event_id') and e.get('input_hash')==email.input_hash and e.get('status') in ('created','handoff_pending')]
        if domains and all(any(e.get('kind') in kinds for e in valid) for kinds in domains):return True
    return False

def matching_stop(email,reply):
    source=email.subject+'\n'+email.body
    if re.search(r'锁扣|车架|bicycle|bike|latch|riding',source,re.I):
        return bool(re.search(r'(?:暂停|停止|不要|避免|请勿|不要继续).{0,4}(?:骑行|试骑|骑车)|(?:do not|stop|avoid|pause).{0,12}(?:ride|riding|cycling)',reply,re.I))
    if re.search(r'抽屉|柜|drawer|cabinet',source,re.I):
        return bool(re.search(r'(?:停止|不要|避免|暂停).{0,8}(?:使用|靠近).{0,8}(?:柜|抽屉)|(?:stop|avoid|do not).{0,12}(?:use|using).{0,12}(?:drawer|cabinet)',reply,re.I))
    if re.search(r'灯|电|浸水|受潮|lamp|electric|wet|spark|smoke',source,re.I):
        return bool(re.search(r'(?:不要|请勿|切勿|避免).{0,8}(?:通电|使用)|保持断电|keep.{0,12}unplugged|do not.{0,10}(?:power|use)',reply,re.I))
    return False

def inspect(email,data,reply=None,*,accepted=True,events=()):
    data=data if isinstance(data,dict) else {}
    reply=data.get('suggested_reply','') if reply is None else reply
    base=original(email,data,reply,accepted=accepted)
    diagnostic=diagnose(reply,events=events,expected_input_hash=email.input_hash,customer_context=[dict(role='customer',text=email.body)])
    findings=[]
    for f in base['findings']:
        # A narrow, existing local creation claim may be supported by a matching
        # current-input receipt. External completion and future promises stay blocked.
        if f['code']=='executed_action' and not diagnostic['hard_findings']:
            if re.search(r'记录|登记|提交|创建|opened|recorded|logged',f['quote'],re.I) and supported_record(reply,f['quote'],email,events):
                f=dict(f,severity='review',reason='Matching current-input local receipt; internal pending work only')
        if f['code']=='missing_stop_use_advice' and matching_stop(email,reply):continue
        findings.append(f)
    for f in diagnostic['hard_findings']:
        findings.append(dict(code=f['code'],severity='block',scope='reply',quote=f['quote'],reason=f['reason']))
    for f in diagnostic['review_findings']:
        findings.append(dict(code=f['code'],severity='review',scope='reply',quote=f['quote'],reason=f['reason']))
    for f in findings:f['finding_id']=digest(f)
    return dict(base,version=VERSION,findings=findings,status='blocked' if any(f['severity']=='block' for f in findings) else 'review_required',
        receipts=[e for e in events if e.get('input_hash')==email.input_hash],human_approved=False,semantic_status='SEMANTIC_PROVISIONAL')
