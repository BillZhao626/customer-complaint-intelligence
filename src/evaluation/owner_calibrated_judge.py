"""R8 Owner calibration, with raw five-dimensional scores retained."""
from src.application.service_response import audit_reply
from src.domain.contracts import EmailInput, digest
from src.evaluation import p5b8r4_judge as prior

VERSION = 'r11-evidence-certification-v1'
DIMENSIONS = prior.DIMENSIONS
bind = prior.previous.bind
SYSTEM = prior.SYSTEM + '''
Evaluate each slot independently using the unchanged five dimensions and thresholds.
Identify the primary customer goal before scoring helpfulness. Secondary detail, praise and
an unnatural source email are not evidence of a reply defect. Evaluate email quality separately
from the reply. The Owner's developmental ratings are not numeric Gold.
Review separately whether an execution claim is supported, a proposed future action is grounded,
the customer was told about each relevant action, and the response helps with the primary goal.
A created local receipt establishes pending work only. A reply can omit or conflate independent
checks even when both tasks exist. Mark that as a service gap, not as fabricated completion.
A promise to relay unsolicited praise without a matching task is a workflow gap, not a claim
of completed delivery. Preserve helpful conditional options with explicit prerequisites.
If a merchant promotion cutoff or eligible payment timestamp is unknown, advising that buying
by an unverified clock protects the discount is a material error even after a disclaimer.
Checking the actual terms or asking billing to confirm is useful. General policies from other
merchants are not evidence. A one-cycle skip inquiry does not authorize cancellation.
Consider aftersales options when the customer stopped using an uncomfortable item. Check usable
order or catalog facts before penalizing a request for missing information. Generic fit knowledge
without a verified product or stock can still help. A dimension-fit omission, ordinary redundant
order details, or awkward phrasing alone is a service/quality gap, not a hard error. Distinguish
that from explicit materially unsafe, unauthorized or false advice. Ordinary optional details do
not disqualify an otherwise useful inquiry that avoids unauthorized booking or data collection.
'''


SYSTEM += '''
For a fitted sheet, changing width/length when only pocket depth is insufficient is a
MAJOR_SERVICE_GAP. Treat it as a hard error only when a separate hard-error condition is shown.
For a time-sensitive correction, assess whether the reply checks timing and provides a practical
route or interim option when one is feasible. Do not require the reply to guarantee a deadline.
Distinguish tasks from constraints, such as keeping a code private. Read an internal product
inquiry created by the sender as a local task, not successful outside contact.
For each created claim, cite the shortest complete assertion including the task noun. Use the
matching slot event ID from deterministic_fact_audit.assessments when it matches the exact claim.
Do not cite a pending receipt for a hypothesis, reported history, a future possibility or a larger
sentence containing several claims. Separate those clauses. If a specific mandatory action has
no matching evidence, preserve the finding or uncertainty. Do not substitute an unrelated ID.
Before returning JSON, check that every quote is a contiguous substring from its own original
text. Copy a supplied quote_inventory span verbatim if unsure. For missing coverage, use status
MISSING and reply_quote "". For partial coverage quote the existing part, not a paraphrase.
For score_evidence, prefer the ref field from the current slot's quote_inventory. These
references resolve to exact Unicode text. A ref from the other slot is invalid.
“You said you have not taken a photo” is negative source context. “Verify what was
dispatched” is an open question. Neither claims completed work. Acknowledging that
an instruction was noted requires no external execution and is not a created business
task. Do not turn RECORD_REVIEW into HARD_ERROR without a separate factual assertion.
'''


def identity():
    return dict(version=VERSION, system_hash=digest(SYSTEM))


def audit_slot(slot, email):
    prior.previous.validate_slot(slot, email)
    audit = prior.audit_slot(slot, email)
    runtime = dict(events=slot['events'], facts=slot.get('facts', {}),
                   identity={key: slot[key] for key in ('run_id', 'arm')})
    extension = audit_reply(email, slot['reply'], runtime)
    audit['findings'].extend(extension['findings'])
    audit['service_review'] = extension
    return audit


def blind_pair(email, answers, *, reverse=False):
    payload, key = prior.blind_pair(email, answers, reverse=reverse)
    for slot in payload['answers']:
        slot['deterministic_fact_audit'] = audit_slot(slot, email)
    payload['judge_version'] = VERSION
    return payload, key


def validate_judgment(data, payload):
    """Add an inspectable veto without overwriting any Judge score or finding."""
    result = prior.validate_judgment(data, payload)
    email = EmailInput.model_validate(payload['customer'])
    slots = {slot['slot']: slot for slot in payload['answers']}
    validation = result['validation']
    validation['version'] = VERSION
    for answer in result['answers']:
        slot = slots[answer['slot']]
        audit = audit_slot(slot, email)
        service = audit['service_review']
        findings = service['findings']
        scores = answer['scores']
        errors = answer['fact_validation']['errors']
        for finding in findings:
            if finding['severity'] == 'block':
                if scores['reliability'] != 0 or scores['action_accuracy'] != 0:
                    errors.append('HARD_ERROR_RELIABILITY_OR_ACTION_NONZERO')
                if finding['code'] == 'UNVERIFIED_PROMOTION_PURCHASE_TIMING' and scores['helpfulness'] != 0:
                    errors.append('UNSAFE_PURCHASE_ADVICE_FULL_CREDIT')
                if not any(f['category'] == 'HARD_ERROR' and f['quote'] and (f['quote'] in finding['quote'] or finding['quote'] in f['quote'])
                           for f in answer['findings']):
                    errors.append('JUDGE_HARD_ERROR_OMISSION')
            elif finding['code'] == 'PENDING_CHECK_NOT_DISTINCT' and scores['action_accuracy'] in (2, 'N/A'):
                errors.append('CREATED_WORK_DISCLOSURE_GAP')
            elif finding['code'] == 'UNGROUNDED_RELAY_INTENT' and scores['action_accuracy'] == 2:
                errors.append('UNGROUNDED_INTENT_FULL_CREDIT')
        errors[:] = sorted(set(errors))
        answer['fact_validation'].update(audit=audit, certifiable=not errors)
        execution = [check for check in audit['assessments'] if check['state'] == 'EXTERNAL_COMPLETED']
        answer['service_review'] = dict(
            executed_claim_supported=all(check.get('supported', False) for check in execution) if execution else None,
            intended_action_grounded=service['intended_action_grounded'],
            customer_informed_of_actions=service['customer_informed_of_actions'],
            primary_goal_helpfulness=dict(
                judge_reported_goals=answer.get('customer_goals'),
                judge_reported_coverage=answer.get('issue_coverage'),
                judge_reported_helpfulness=scores['helpfulness'],
                evidence_status='UNCERTIFIED' if errors else 'AUTOMATED_PROVISIONAL',
            ),
        )
    validation['errors'] = [
        dict(slot=answer['slot'], code=code) for answer in result['answers']
        for code in answer['fact_validation']['errors']
    ]
    if validation['errors']:
        validation.update(status='UNCERTIFIED', validated_preference='UNKNOWN')
    return result


def parse(raw, payload):
    import copy
    import json
    value = json.loads(raw) if isinstance(raw, str) else copy.deepcopy(raw)
    slots = {s['slot']: s for s in payload['answers']}
    for answer in value.get('answers', []):
        slot = slots.get(answer.get('slot'), {})
        inventory = slot.get('quote_inventory', {})
        refs = {span['ref']: span['quote'] for source in ('reply', 'customer')
                for span in inventory.get(source, []) if 'ref' in span}
        spans = answer.get('score_evidence', {})
        if isinstance(spans, dict):
            for dimension, quote in spans.items():
                if isinstance(quote, str) and quote in refs:
                    spans[dimension] = refs[quote]
    return validate_judgment(prior.parse(value, payload), payload)
