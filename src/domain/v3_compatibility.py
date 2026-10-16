"""Opt-in safe lossy views. Process routing is never verified responsibility."""
from src.domain.analysis_v3 import to_v2

POLICIES=('customer-primary-v2-safe','owner-operational-v2-safe')


def selected_issue(value, operational=False):
    primary=[i for i in value.issues if i.customer_importance=='primary']
    if len(primary)==1:return primary[0]
    if len(value.issues)==1:return value.issues[0]
    if operational:
        ranked=[i for i in value.issues if i.handling_priority is not None]
        first=min((i.handling_priority for i in ranked),default=None)
        winners=[i for i in ranked if i.handling_priority==first]
        if len(winners)==1:return winners[0]
    return None


def project(value, policy):
    if policy not in POLICIES:raise ValueError('Unknown safe compatibility policy')
    old='owner-operational-v1' if policy=='owner-operational-v2-safe' else 'customer-primary-v1'
    result,diagnostics=to_v2(value,old)
    diagnostics=[*diagnostics,'safe projection version: '+policy,
                 'Business source is a reported process classification, never verified cause or liability']
    if value.compatibility_origin is not None:
        return result,diagnostics+['Legacy v2 has no recorded certainty; original restored without fabricating it']
    changes={}
    if value.store_verification in ('uncertain_mention','unknown','unavailable'):
        changes['store_location']='unknown'
        diagnostics.append('Uncertain/unavailable store mention masked in v2; verbatim mention remains in v3')
    issue=selected_issue(value,policy=='owner-operational-v2-safe')
    if result.is_complaint and issue:
        if issue.attribution_certainty in ('unclear','inferred'):
            changes['source_attribution']='unclear'
            diagnostics.append('Unclear/inferred attribution masked; suggested routing does not establish source responsibility')
        elif issue.attribution_certainty=='unknown':
            changes['source_attribution']='unknown'
            diagnostics.append('Unknown attribution stays unknown, independently of routing team')
        else:
            active=[i for i in value.issues if i.issue_kind=='complaint' and i.resolution=='unresolved']
            if (len(active)>1 and not any(i.customer_importance=='primary' for i in active)
                    and any(i.customer_importance=='unspecified' for i in active)
                    and len({i.business_process for i in active})>1):
                changes['source_attribution']='unclear'
                diagnostics.append('Multiple unresolved process domains without a customer primary; operational selection does not establish one email-level source')
    # Validate the new view; no bypass of v2's strict fields.
    return type(result).model_validate(dict(result.model_dump(),**changes)),diagnostics
