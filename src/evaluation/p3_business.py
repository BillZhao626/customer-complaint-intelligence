"""Compare the actual P3 product aggregates with bound, explicitly typed references."""
from collections import Counter
from src.application.attribution_service import AttributionService


def verify_business(samples,runs):
    service=AttributionService(runs,'evaluation_bound_dataset',samples)
    snapshot=service.snapshot(runs[0].cohort_id)
    reference={s.sample_id:s for s in samples}
    successful=[service.get(rid) for rid in snapshot['states']['succeeded']['member_run_ids']]
    comparisons={}
    for dimension in ('store_location','product_category','complaint_reason','source_attribution'):
        eligible=[r for r in successful if getattr(reference[r.email.email_id].expected,dimension) is not None]
        # Compare full successful set for grouping semantics; failed/missing excluded explicitly.
        expected=Counter(str(getattr(reference[r.email.email_id].expected,dimension)) for r in eligible)
        actual=Counter(str(getattr(r.result,dimension)) for r in eligible)
        comparisons[dimension]=dict(reference_coverage=len(eligible),predicted=dict(actual),expected=dict(expected),
            delta={k:actual[k]-expected[k] for k in sorted(actual.keys()|expected.keys())})
    metrics=list(snapshot['metrics'].values())+list(snapshot['states'].values())+list(snapshot['unknown'].values())
    for groups in snapshot['groups'].values():
        for g in groups:metrics.extend(g[k] for k in ('count','negative','complaints'))
    verified=all(m['numerator']==len(m['member_run_ids']) and m['denominator']==len(m['denominator_run_ids'])
        and set(m['member_run_ids'])<=set(m['denominator_run_ids'])
        and all(service.get(rid).email.input_hash==snapshot['members'][rid]['input_hash'] for rid in m['denominator_run_ids']) for m in metrics)
    return dict(status='VERIFIED' if verified else 'FAILED',snapshot=snapshot,reference_comparison=comparisons,
        reference_statuses=sorted({s.reference_status for s in samples}),
        meaning='Arithmetic and traceability only. Unapproved references are not Human Gold; deltas expose semantic disagreement.')
