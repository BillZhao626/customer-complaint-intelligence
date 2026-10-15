"""Deterministic, single-source/version business statistics; never calls a provider."""
from collections import defaultdict
from datetime import datetime

from src.domain.contracts import AnalysisRun, digest, idempotency_key
from src.evaluation.e2e_schema import validate_dataset, dataset_hash

CONCRETE_SOURCES = frozenset(('product issue', 'store service issue', 'delivery/logistics issue',
    'customer service response issue', 'refund/exchange process issue'))
DIMENSIONS = ('store_location', 'product_category', 'complaint_reason', 'source_attribution')


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Time must include timezone')
    return parsed


def state(run):
    return 'fallback' if run.metadata.get('fallback') else run.status


def metric(members, denominator, name):
    ids = sorted(r.run_id for r in members)
    den = sorted(r.run_id for r in denominator)
    if len(ids) != len(set(ids)) or not set(ids) <= set(den):
        raise ValueError('Invalid statistic membership')
    return dict(numerator=len(ids), denominator=len(den), denominator_name=name,
        rate=len(ids)/len(den) if den else None, member_run_ids=ids, denominator_run_ids=den)


class AttributionService:
    def __init__(self, runs, source_id, samples=None):
        if not source_id:
            raise ValueError('Explicit source required')
        self.runs = [AnalysisRun.model_validate(r.model_dump() if isinstance(r, AnalysisRun) else r) for r in runs]
        self.source_id = source_id
        self.samples = validate_dataset(samples) if samples is not None else None
        if len({r.run_id for r in self.runs}) != len(self.runs):
            raise ValueError('Duplicate run ID')
        sample_index = {s.sample_id:s for s in self.samples} if self.samples else None
        for run in self.runs:
            if (run.input_hash != run.email.input_hash or run.cohort_id != run.config.cohort_id
                or run.idempotency_key != idempotency_key(run.email, run.config)):
                raise ValueError('Broken run/input/version binding')
            if (run.status == 'succeeded') != (run.result is not None):
                raise ValueError('Run outcome mismatch')
            if run.result and (not run.attempts or run.attempts[-1].contract_status != 'passed' or run.attempts[-1].error):
                raise ValueError('Result lacks accepted attempt')
            timestamp(run.created_at)
            if sample_index is not None:
                sample = sample_index.get(run.email.email_id)
                if not sample or sample.email() != run.email or sample.taxonomy_version != run.config.taxonomy_version:
                    raise ValueError('Run outside bound dataset')

    @property
    def cohorts(self):
        return {r.cohort_id:r.config.model_dump() for r in self.runs}

    def get(self, run_id):
        return next((r for r in self.runs if r.run_id == run_id), None)

    def snapshot(self, cohort_id, *, store=None, product=None, sentiment=None, status=None, start=None, end=None):
        if not cohort_id or cohort_id not in self.cohorts:
            raise ValueError('Select exactly one known cohort')
        if start and end and timestamp(start) > timestamp(end):
            raise ValueError('Start must precede end')
        if status not in (None, 'succeeded', 'failed', 'running', 'interrupted_or_unknown', 'fallback'):
            raise ValueError('Unknown status')
        eligible = [r for r in self.runs if r.cohort_id == cohort_id
            and (not start or timestamp(r.created_at) >= timestamp(start))
            and (not end or timestamp(r.created_at) <= timestamp(end))]
        latest = {}
        for run in sorted(eligible, key=lambda r:(timestamp(r.created_at), r.run_id)):
            latest[(run.email.email_id, run.input_hash)] = run
        base = list(latest.values())
        selected = [r for r in base if (not status or state(r) == status)
            and all(value is None or (r.result is not None and getattr(r.result, field) == value)
                for field, value in [('store_location',store), ('product_category',product), ('sentiment',sentiment)])]
        success = [r for r in selected if state(r) == 'succeeded']
        complaints = [r for r in success if r.result.is_complaint]
        negative = [r for r in success if r.result.sentiment == 'negative']
        valid = [r for r in complaints if r.result.source_attribution in CONCRETE_SOURCES
                 and r.config.backend != 'legacy_mock']
        metrics = dict(
            emails=metric(selected,selected,'all_selected_email_revisions'),
            successful=metric(success,selected,'all_selected_email_revisions'),
            complaints_all=metric(complaints,selected,'all_selected_email_revisions'),
            complaints_success=metric(complaints,success,'successful_nonfallback'),
            negative_all=metric(negative,selected,'all_selected_email_revisions'),
            negative_success=metric(negative,success,'successful_nonfallback'),
            valid_attribution=metric(valid,complaints,'complaint_emails'))
        groups = {}
        def distribution(name, runs, fields, denominator_name):
            buckets = defaultdict(list)
            for r in runs:
                values = tuple('unavailable' if f == 'source_attribution' and r.config.backend == 'legacy_mock'
                    else getattr(r.result, f) for f in fields)
                buckets[values].append(r)
            rows = []
            for values, members in sorted(buckets.items()):
                key = digest(dict(distribution=name, values=values))[:16]
                count = metric(members,runs,denominator_name)
                neg = metric([r for r in members if r.result.sentiment == 'negative'],members,'group_successful_nonfallback')
                comp = metric([r for r in members if r.result.is_complaint],members,'group_successful_nonfallback')
                rows.append(dict(group_id=key,values=dict(zip(fields,values)),count=count,negative=neg,complaints=comp))
            groups[name] = rows
        for dimension in DIMENSIONS:
            denominator = complaints if dimension in ('complaint_reason','source_attribution') else success
            distribution(dimension,denominator,[dimension], 'complaint_emails' if denominator is complaints else 'successful_nonfallback')
        distribution('store_product',success,['store_location','product_category'],'successful_nonfallback')
        distribution('attribution_valid',valid,['source_attribution'],'valid_attribution')
        distribution('attribution_states',success,['source_attribution'],'successful_nonfallback')
        states = {s:metric([r for r in selected if state(r)==s],selected,'all_selected_email_revisions')
            for s in ('succeeded','failed','fallback','running','interrupted_or_unknown')}
        unknown = {d:metric([r for r in success if getattr(r.result,d)=='unknown' and not
            (d=='source_attribution' and r.config.backend=='legacy_mock')],success,'successful_nonfallback')
            for d in (*DIMENSIONS,'sentiment')}
        unavailable = metric([r for r in selected if not r.result or r.config.backend=='legacy_mock'],selected,'all_selected_email_revisions')
        reference_hashes = {s.sample_id:digest(s.model_dump()) for s in self.samples} if self.samples else {}
        members = {r.run_id:dict(sample_id=r.email.email_id,input_hash=r.input_hash,run_id=r.run_id,
            reference_hash=reference_hashes.get(r.email.email_id),
            output_hash=digest(r.result.model_dump()) if r.result else None,cohort_id=r.cohort_id,
            status=state(r),created_at=r.created_at) for r in selected}
        observed = {r.email.email_id for r in eligible}
        return dict(statistics_version='p3-attribution-v1',source_id=self.source_id,
            dataset_id=self.samples[0].dataset_id if self.samples else 'unregistered',
            dataset_hash=dataset_hash(self.samples) if self.samples else None,
            provenance=self.samples[0].provenance.model_dump() if self.samples else {'kind':'unavailable'},
            cohort_id=cohort_id,versions=self.cohorts[cohort_id],unit='latest run per email_id + input_hash (email revision)',
            filters=dict(store=store,product=product,sentiment=sentiment,status=status,start=start,end=end),
            prefilter_count=len(base),prefilter_states={s:sum(state(r)==s for r in base) for s in states},
            filtered_out=len(base)-len(selected),superseded_run_ids=sorted(r.run_id for r in eligible if r.run_id not in {x.run_id for x in base}),
            missing_sample_ids=sorted(s.sample_id for s in self.samples if s.sample_id not in observed) if self.samples else [],
            missing_scope='manifest samples without run in selected cohort/time; outside run denominators',
            metrics=metrics,groups=groups,states=states,unknown=unknown,attribution_unavailable=unavailable,
            channel='unavailable (not recorded in analysis-v2)',members=members)
