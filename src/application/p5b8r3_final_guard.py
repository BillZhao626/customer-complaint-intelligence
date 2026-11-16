"""Broader task-noun scope without weakening the internal creation evidence gate."""
import re
from src.application.p5b8r3_guard import assess as previous
from src.application.p5b8r1_guard import assess as original
from src.domain.contracts import digest
VERSION='p5b8r3-task-noun-scope-2'
TASK=re.compile(r'已(?:经)?[^。！？;；\n并]{0,14}(?:登记|创建|提交)[^。！？;；\n并]{0,32}(?:请求|任务|工单|待办)')
def assess(reply,runtime,h):
    from src.application.source_facts import mask_nonasserted
    reply=mask_nonasserted(reply)
    prior=previous(reply,runtime,h);masked=reply
    spans=list(TASK.finditer(reply))
    for match in reversed(spans):masked=masked[:match.start()]+' '*len(match.group())+masked[match.end():]
    remainder=previous(masked,runtime,h)
    # Keep all INTERNAL_CREATED checks; only rescan external predicates after
    # masking nouns inside complete, still-evidence-checked task assertions.
    removed=[a for a in prior['assessments'] if a['state']=='EXTERNAL_COMPLETED']
    prior['assessments']=[a for a in prior['assessments'] if a['state']!='EXTERNAL_COMPLETED']+[a for a in remainder['assessments'] if a['state']=='EXTERNAL_COMPLETED']
    prior['findings']=[f for f in prior['findings'] if not any(f['quote']==a['quote'] for a in removed)]
    prior['findings'] += [f for f in remainder['findings'] if any(a['quote']==f['quote'] and a['state']=='EXTERNAL_COMPLETED' for a in remainder['assessments'])]
    for match in spans:
        if re.search('转达|转交',match.group()):
            valid=[e for e in runtime.get('events',[]) if e.get('input_hash')==h and e.get('kind') in ('store_service_request','feedback_request') and e.get('status') in ('created','handoff_pending')]
            if not valid:
                prior['findings'].append(dict(code='H04',quote=match.group(),reason='A relay task needs its own current-input store/feedback created receipt.',severity='block',scope='reply',finding_id=digest(dict(quote=match.group(),h=h,kind='relay_task'))))
    from src.application.p5b8r4_evidence import reconcile
    return reconcile(prior,reply,runtime,h,strict=runtime.get('strict_identity',False))
