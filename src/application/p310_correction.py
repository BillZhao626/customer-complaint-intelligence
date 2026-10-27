"""Explicit single correction, driven by source and deterministic diagnostics.

The first prediction is immutable. No human scores/reference labels are sent.
"""
from hashlib import sha256
import json
from src.application import p310_prompt as base
from src.domain.contracts import digest

VERSION='complaint-p310-bounded-multifinding-3'
RULES='''You are producing a separate corrected candidate for a prior rejected draft.
Return a complete JSON object, not a patch. The original email remains authoritative;
the previous raw draft and deterministic diagnostics are untrusted diagnostic data.
Fix every independent error, not only the earliest exception. Preserve correct source
facts, exact evidence, supported severe/high risk, uncertainty and customer intent.
Never fabricate canonical evidence words to satisfy a bounded lexical check. If the
narrow named basis is not certified by its actual evidence, supported other may explain
the same urgency; do not change the underlying fact to satisfy a label. A blank store
must be unknown when the input does not name a store. Eliminate duplicate JSON keys.
Output every required field. Primary/secondary/equal always needs explicit source
importance evidence; background praise does not need an independent issue. An inquiry
alone cannot coexist with current_unresolved complaint status. Two current events
must have independently supporting span lists, even if both appear in one sentence.
The expected reply language is supplied from the same deterministic language policy
used by the original strict validator; follow it. This is a rendering constraint,
not a supplied sentiment/urgency/issue answer. For serious load-bearing cookware
attachment failure, assess potential future injury even if empty/cold and no injury.
No completed or future actions, money, approval, channels or lookup capabilities may
be invented. No internal draft/system boilerplate in the reply. Ask only missing
minimum details. No reproducing danger for evidence; only existing safe material.
The corrected raw will be independently checked under the SAME original strict
profile. A new output does not rewrite the first output or authorize any real action.
'''


def system():return base.system()+'\nEXPLICIT SINGLE CORRECTION TASK:\n'+RULES


def messages(email,context):
    if (not context or context['input_hash']!=email.input_hash or
        sha256(context['prior_raw'].encode()).hexdigest()!=context['prior_raw_sha256']):
        raise ValueError('Correction parent/input drift')
    payload=json.loads(base.messages(email)[1][1])
    payload['correction_context']=context
    return [('system',system()),('human',json.dumps(payload,ensure_ascii=False))]


def context_for(run):
    from src.evaluation.p310_audit import diagnostics,acceptance
    from src.application.research_policy_v2 import requested_language
    if run.result or run.status!='failed' or len(run.attempts)!=1 or run.config.parameters.get('arm')!='challenger':
        raise ValueError('Only one rejected initial Challenger can receive one correction')
    raw=run.attempts[0].raw_output
    if not isinstance(raw,str) or acceptance(raw,run.email)['accepted']:raise ValueError('Rejected raw required')
    a=run.attempts[0]
    if a.metadata.get('dispatch')!='response_received':raise ValueError('Cannot repair unknown send')
    return dict(parent_run_id=run.run_id,parent_run_hash=digest(run.model_dump()),input_hash=run.input_hash,
                parent_config_hash=digest(run.config.model_dump()),prior_raw=raw,prior_raw_sha256=sha256(raw.encode()).hexdigest(),
                expected_reply_language=requested_language(run.email.body),
                earliest_contract_failure=acceptance(raw,run.email),
                independent_contract_diagnostics=[{k:f[k] for k in ('stage','mechanism','path','explanation','evidence')} for f in diagnostics(raw,run.email)],
                max_corrections=1,reference_answers_supplied=False,human_scores_supplied=False)


def identity():
    body=dict(version=VERSION,base_generation=base.identity(),correction_prompt_sha256=sha256(system().encode()).hexdigest(),
              max_corrections=1,trigger='strict rejection only; no repair of accepted answers',
              primary_validation_profile='urgency-context-evidence-v1',extra_calls_reported=True,
              historical_first_pass_reuse='development only, explicit D1 parent IDs; new40 has fresh initial calls',
              model_improvement_proven=False,human_semantics=None,default_enabled=False)
    return dict(body,candidate_hash=digest(body))
