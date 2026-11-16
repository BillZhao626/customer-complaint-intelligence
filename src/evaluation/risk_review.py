"""Four-state review projection over a deterministic audit and a parsed Judge answer."""

VERSION = 'r11-layered-review-v1'

# The archived validator retains these diagnostics. The decision conflicts also
# contain semantic checks, which are evaluated independently below.
SCORE_DIAGNOSTICS = frozenset({
    'ATTITUDE_APPLICABILITY_CONFLICT', 'ACTION_APPLICABILITY_CONFLICT',
    'PASS_DECISION_CONFLICT', 'PARTIAL_DECISION_CONFLICT', 'MAJOR_SERVICE_DECISION_CONFLICT',
    'HARD_DECISION_CONFLICT', 'HARD_ERROR_RELIABILITY_MUST_BE_ZERO',
})
SOURCE_CONFLICTS = frozenset({'SOURCE_PAGE_RANGE_CONFLICT', 'SOURCE_TARIFF_ALLOCATION_UNVERIFIED'})


def consistent_service_decision(verdict, severity, categories, coverage):
    if verdict == 'UNKNOWN':
        return severity == 'UNKNOWN'
    if 'UNKNOWN' in categories or not coverage:
        return False
    if severity == 'HARD':
        return verdict == 'FAIL' and 'HARD_ERROR' in categories
    if 'HARD_ERROR' in categories:
        return False
    if severity == 'MAJOR_NON_HARD':
        return verdict == 'FAIL' and 'MAJOR_SERVICE_GAP' in categories
    if 'MAJOR_SERVICE_GAP' in categories:
        return False
    if severity == 'PARTIAL_SERVICE':
        return verdict == 'PARTIAL' and any(check['status'] != 'COVERED' for check in coverage)
    return (severity in ('NONE', 'SOFT') and verdict == 'PASS'
            and all(check['status'] == 'COVERED' for check in coverage))


def assess(audit, answer=None, *, first_reply='VALID', protocol_error=None, material_dispute=False):
    """Project review decisions without rewriting a model grade or a frozen label.

    Use a current deterministic audit even when the Judge protocol is unavailable.
    An answer must come from the strict parser. An unresolved hard suspicion holds
    the draft for review even when the deterministic recognizer finds no conflict.
    """
    findings = audit.get('findings', [])
    blocks = [finding['code'] for finding in findings if finding['severity'] == 'block']
    source_conflicts = [finding['code'] for finding in findings if finding['code'] in SOURCE_CONFLICTS]
    answer = answer or {}
    validation = answer.get('fact_validation')
    errors = set((validation or {}).get('errors', []))
    evidence_errors = sorted(errors - SCORE_DIAGNOSTICS)
    verdict = answer.get('verdict')
    severity = answer.get('severity')
    coverage = answer.get('required_coverage', [])
    categories = {finding['category'] for finding in answer.get('findings', [])}
    unresolved_hard = severity == 'HARD' or 'HARD_ERROR' in categories
    semantic_consistent = consistent_service_decision(verdict, severity, categories, coverage) if verdict else None

    result, reason = 'UNKNOWN', 'JUDGE_UNAVAILABLE'
    route = 'HUMAN_REVIEW'
    if blocks:
        result, reason, route = 'FAIL', 'DETERMINISTIC_BLOCK', 'BLOCK_DRAFT'
    elif first_reply == 'INVALID':
        result, reason, route = 'FAIL', 'FIRST_STRUCTURE_OR_PLAN', 'BLOCK_DRAFT'
    elif first_reply == 'MISSING':
        reason = 'FIRST_REPLY_UNAVAILABLE'
    elif unresolved_hard:
        reason, route = 'UNRESOLVED_HARD_FINDING', 'BLOCK_DRAFT'
    elif source_conflicts or evidence_errors or material_dispute:
        reason = 'FACT_OR_EVIDENCE_REVIEW'
    elif protocol_error:
        reason = 'JUDGE_PROTOCOL_ERROR'
    elif verdict and validation is not None:
        if semantic_consistent:
            result, reason = verdict, 'SEMANTIC_ADVISORY'
        else:
            reason = 'SEMANTIC_DECISION_CONFLICT'

    return dict(
        version=VERSION,
        deterministic=dict(block_codes=sorted(set(blocks)), source_conflicts=sorted(set(source_conflicts)),
                           evidence_errors=evidence_errors, assessments=audit.get('assessments', [])),
        semantic=dict(verdict=verdict, severity=severity, coverage=coverage, findings=answer.get('findings', []),
                      protocol_error=protocol_error, consistent=semantic_consistent),
        numeric=dict(scores=answer.get('scores'), applicability=answer.get('applicability'),
                     diagnostics=sorted(errors & SCORE_DIAGNOSTICS)),
        review=dict(verdict=result, reason=reason, route=route),
    )
