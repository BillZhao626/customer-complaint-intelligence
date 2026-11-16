"""Opt-in lexical false-rejection repairs; original v3.2 profile is unchanged."""
import re
from src.application.urgency_context_v2 import signals as previous
from src.application.urgency_context_v1 import visible, active_clauses
from src.application.reply_review import inspect_reply

PROFILE='p5b7-context-checks-1'
def signals(text,*,already_visible=False):
    d=previous(text,already_visible=already_visible)
    clauses=active_clauses(text if already_visible else visible(text))
    for c in clauses:
        repeated=re.search(r'两次|三次|几次|好几次|多次|反复|\b(?:a couple|two|three|several)\s+(?:of\s+)?times\b',c,re.I)
        failure=re.search(r'没人(?:回|接|处理)|没有(?:人)?回复|无人(?:回|接)|未(?:获|得到).{0,5}回复|无人回应|getting passed around|nobody.{0,18}(?:explained|replied|helped)|no one.{0,18}(?:replied|answered)',c,re.I)
        if repeated and failure and not re.search(r'已解决|now resolved',c,re.I):d['repeated_failure'].append(c.strip())
        if re.search(r'准备(?:在)?这周末.{0,12}(?:穿|用|参加)|\b(?:need|must|have to).{0,50}(?:this weekend|Saturday|Sunday)\b',c,re.I) and not re.search(r'不需要|不是|\bnot\b',c,re.I):d['deadline'].append(c.strip())
    d['profile']=PROFILE
    return d

def reply_review(reply,source):
    result=inspect_reply(reply);kept=[];excluded=[]
    for finding in result['findings']:
        quote=finding['quote'];before=reply[max(0,finding['start']-36):finding['start']]
        # Exact customer-reported listing ETA with an explicit reporting prefix.
        listing=(quote in source and finding['kind'] in ('vague_material_promise','material_commitment') and re.search(r'(?:您|你).{0,12}(?:下单时|页面显示|页面写|看到|提到)',before))
        # 已说明 is a reporting verb, not execution; retain nested action claims.
        report=(finding['kind']=='executed_action' and re.match(r'已(?:说明|提到|表示|告知)',quote) and re.search(r'(?:你|您)$',before) and not re.search(r'已(?:经|为您|给您)?(?:退款|批准|支付|转交|安排)',quote[3:]))
        if listing or report:excluded.append(dict(finding,exclusion='EXACT_REPORTED_LISTING' if listing else 'CUSTOMER_REPORTING_VERB_NOT_EXECUTION'))
        else:kept.append(finding)
    return dict(result,version=PROFILE,findings=kept,source_scoped_exclusions=excluded,status='blocked' if any(f['severity']=='block' for f in kept) else 'review_required' if kept else 'no_lexical_signal')
