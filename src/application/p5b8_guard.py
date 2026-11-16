"""Supplemental receipt predicates discovered in real B8 failures; opt-in v2.

Keeps original diagnostics and source outputs intact. No case IDs or Gold labels.
"""
import re
from src.application.p5b8_pipeline import check_reply
from src.evaluation.p5b5r2_judge import SCOPES
VERSION='p5b8-receipt-predicates-2'
def inspect(email,reply,runtime):
    out=check_reply(email,reply or '',runtime);hard=list(out['hard_findings']);excluded=[]
    if not reply:
        hard=[f for f in hard if f['code']!='LANGUAGE']
        hard.append(dict(code='UNPARSEABLE_REPLY',quote='',reason='No parsed reply; original raw remains available. Language is unassessable, not a proven language error.'))
        out['language']=dict(out['language'],matches=None)
    trusted=[e for e in runtime['events'] if e.get('event_id') and e.get('input_hash')==email.input_hash and e.get('status') in ('created','handoff_pending')]
    for clause in re.split(r'[。！？!?;；\n]|\bbut\b|但是|不过',reply or ''):
        pattern=r'(?:已经|已).{0,14}(?:提交|登记|创建|建单|记录).{0,30}(?:请求|任务|工单|待办)|(?:已经|已).{0,20}(?:请求|任务|工单|待办).{0,8}(?:提交|登记|创建)|(?:已(?:经)?(?:为您)?建单)|(?:I|we)(?: have|.ve)?\s+(?:opened|logged|created|submitted|filed).{0,45}(?:request|task|ticket|case)'
        for m in re.finditer(pattern,clause,re.I):
            before=clause[:m.start()]
            if re.search(r'(?:尚未|没有|并未|未曾|不曾|不能|无法|未能|如果|假设)[^，,]{0,12}$|(?:not|never|if)\s+(?:\w+\s+){0,3}$',before,re.I):continue
            if re.search(r'(?:您|你|客户).{0,12}(?:说|提到|表示|说明)[^，,]{0,12}$|you (?:said|mentioned)[^,]{0,24}$',before,re.I):continue
            domains=[kinds for _,(p,kinds) in SCOPES.items() if re.search(p,clause,re.I)]
            if re.search(r'查询请求|核实请求|query request|verification request',m.group(),re.I) and not domains:domains=[{'human_input_request','support_followup','clarification_request','aftersales_request'}]
            supported=bool(trusted) and all(any(e['kind'] in kinds for e in trusted) for kinds in domains)
            if not supported:
                f=dict(code='H04',quote=m.group(),reason='Creation/submission predicate lacks matching current-input created/handoff_pending receipt; lookup UNKNOWN is insufficient')
                if f not in hard:hard.append(f)
        m=re.search(r"(?:I|we)(?: have|.ve)? received.{0,18}(?:photos?|attachments?)",clause,re.I)
        if m and not re.search(r'not|never',clause[:m.start()],re.I):hard.append(dict(code='H04',quote=m.group(),reason='No received attachment manifest exists in this pipeline'))
    return dict(out,version=VERSION,hard_findings=hard,reviewable=bool(reply and reply.strip()) and not hard,identity='SUPPLEMENTAL_DETERMINISTIC_DIAGNOSTIC_NOT_GOLD',exclusions=excluded)
