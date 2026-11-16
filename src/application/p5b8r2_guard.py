"""R2 predicate scoping: routing *request* is not a completed relay.

Only mask the relay noun inside a task assertion while scanning completion.
Keep the original task check, and scan remaining clauses so a second unsupported
completion is never waived. All non-action safety gates remain inherited.
"""
import re
from src.application.p5b8r1_guard import assess as old_assess, calibrate as old_calibrate, quality as old_quality
VERSION='p5b8r2-predicate-scope-1'
TASK = re.compile(r'已(?:经)?(?:为您)?(?:创建|提交|登记)[^。！？;；\n并]{0,24}(?:请求|任务|工单|待办)')

def assess(reply,runtime,h):
    original=old_assess(reply,runtime,h)
    spans=list(TASK.finditer(reply))
    # Check each task intact. Mask only that completed task noun phrase when
    # looking for external predicates, preserving separate conjunctions.
    masked=reply
    for m in reversed(spans):masked=masked[:m.start()]+' '*len(m.group())+masked[m.end():]
    remainder=old_assess(masked,runtime,h)
    original['assessments']=[a for a in original['assessments'] if a['state']!='EXTERNAL_COMPLETED']
    original['findings']=[f for f in original['findings'] if not any(f['quote']==a['quote'] and a['state']=='EXTERNAL_COMPLETED' for a in old_assess(reply,runtime,h)['assessments'])]
    original['assessments'].extend(a for a in remainder['assessments'] if a['state']=='EXTERNAL_COMPLETED')
    original['findings'].extend(f for f in remainder['findings'] if any(a['quote']==f['quote'] and a['state']=='EXTERNAL_COMPLETED' for a in remainder['assessments']))
    original['version']=VERSION
    return original

def quality(run,data,reply,accepted):
    from pathlib import Path
    from src.application.p5b8r1_guard import input_audit
    rt=dict(run.metadata['runtime'],audit_records=input_audit(run,Path(__file__).resolve().parents[2]),attachment_manifest=[],capabilities={})
    out=old_quality(run,data,reply,accepted)
    prior=old_assess(reply or '',rt,run.input_hash);new=assess(reply or '',rt,run.input_hash)
    excluded=[a for a in prior['assessments'] if a['state']=='EXTERNAL_COMPLETED' and a not in new['assessments']]
    # Exact spurious completion finding only; never suppress unrelated gates.
    out['findings']=[f for f in out['findings'] if not (f['code']=='H04' and any(f.get('quote')==a['quote'] for a in excluded))]
    out['findings'].extend(f for f in new['findings'] if f not in out['findings'])
    out.update(version=VERSION,action_states=new['assessments'],status='blocked' if any(f['severity']=='block' for f in out['findings']) else 'review_required')
    return out
