"""Read-only historical arithmetic audit; writes only a new requested report.

No provider imports or historical runner execution. Private sources are optional;
missing evidence is unavailable, never a manufactured successful recomputation.
"""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.core import FIELDS, normalize, evaluate


def percentile(values, q):
    values = sorted(values)
    if not values: return None
    x = (len(values) - 1) * q; i = int(x)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (x - i)


def audit(root):
    sources = {}
    def read(path):
        p = root / path
        raw = p.read_bytes(); sources[p.relative_to(root).as_posix()] = sha256(raw).hexdigest()
        return json.loads(raw.decode('utf-8-sig'))
    def rows(path):
        p = root / path
        raw = p.read_bytes(); sources[path] = sha256(raw).hexdigest()
        return list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    def runfiles(pattern):
        paths = sorted(root.glob(pattern))
        if not paths: raise FileNotFoundError(pattern)
        return [read(p.relative_to(root)) for p in paths]
    def costs(runs):
        attempts = [a for r in runs for a in r['attempts']]
        metadata = [a['metadata'] for a in attempts]
        def total(key):
            values = [m.get(key) for m in metadata]
            return sum(values) if values and all(v is not None for v in values) else None
        inp, out = total('input_tokens'), total('output_tokens')
        return dict(requests=len(attempts), received=sum(m.get('dispatch') == 'response_received' for m in metadata),
            accepted=sum(r.get('status', r.get('state', r.get('original_status'))) == 'succeeded' for r in runs),
            failed=sum(r.get('status', r.get('state', r.get('original_status'))) == 'failed' for r in runs),
            input_tokens=inp, output_tokens=out, total_tokens=total('total_tokens'),
            estimated_peak_miss_cny=round((inp * 2 + out * 8) / 1e6, 6) if inp is not None and out is not None else None,
            price_basis='historical 2026-10-15/17 input 2/output 8 CNY per million; not current price or invoice',
            provider_latency_n=sum(a.get('elapsed_ms') is not None for a in attempts),
            provider_p50_ms=percentile([a['elapsed_ms'] for a in attempts if a.get('elapsed_ms') is not None], .5),
            provider_p95_ms=percentile([a['elapsed_ms'] for a in attempts if a.get('elapsed_ms') is not None], .95), actual_invoice=None)
    def compare(pairs):
        checks = [[actual is not None and normalize(expected[f]) == normalize(actual.get(f)) for f in FIELDS] for expected, actual in pairs]
        return dict(fields_correct=sum(sum(c) for c in checks), fields_total=len(checks)*7,
                    emails_all_correct=sum(all(c) for c in checks), emails_total=len(checks))
    report = dict(version='readiness-recalculation-v1', date='2026-10-26', new_paid_calls=0, metrics={}, source_hashes=sources)
    def section(name, function):
        try: report['metrics'][name] = dict(evidence='recomputed_from_machine_records', **function())
        except FileNotFoundError as exc: report['metrics'][name] = dict(evidence='unavailable', missing=str(exc))

    def dataset():
        records = rows('data/synthetic/customer_emails_full_v1.csv')
        # Pure memory generator, no main()/write path.
        from src.dataset.generate_full_dataset_v1 import generate_records
        generated = generate_records()
        same = len(generated) == len(records) and all(all(str(g[k]).lower() == str(r[k]).lower() for k in r) for g, r in zip(generated, records))
        return dict(n=len(records), unique_ids=len({r['email_id'] for r in records}),
            templates=len({r['generation_template_id'] for r in records}),
            scenarios=dict(Counter(r['scenario_type'] for r in records)), generator_matches=same,
            source='deterministic_program_templates_not_LLM', human_gold=False)
    section('historical400', dataset)
    def eighty():
        r = evaluate(rows('outputs/i4e2_reviewed_80_predictions_v1.csv'), rows('data/golden/golden_labels_review_sample_v1_reviewed.csv'))
        return {k: r[k] for k in ('correct_fields', 'total_fields', 'whole_email_correct', 'expected', 'accuracy')}
    section('historical80', eighty)
    def p2():
        runs = runfiles('.local/p2-pilot-v1/run-*.json'); by_id = {r['email']['email_id']: r for r in runs}
        fixtures = read('.local/p2-pilot-v1/fixtures.json')['cases']
        return dict(**compare([(f['expected'], by_id[f['email']['email_id']]['result']) for f in fixtures]), runtime=costs(runs))
    section('p2', p2)
    def p36():
        comparison = read('.local/p36/draft-v3/comparison24-v1.json')['rows']
        runs = runfiles('.local/p36/draft-v3/run-*.json'); by_id = {r['run_id']: r for r in runs}
        pairs = [(m['expected'], by_id[m['run_id']]['result']) for m in comparison]
        all_runs = runfiles('.local/p36/*/run-*.json')
        return dict(**compare(pairs), final_runtime=costs(runs), all_runtime=costs(all_runs))
    section('p36', p36)
    def p39():
        d = read('.local/p39/r3/fixed-report-delivery/paired-evaluation.json')
        result = {}
        for arm in ('A', 'B'):
            members = [m for m in d['members'] if m['arm'] == arm]
            pairs = []
            for m in members:
                comp = m['historical_reference_comparison']
                if comp:
                    pairs.append(({f: comp[f]['expected'] for f in FIELDS}, {f: comp[f]['actual'] for f in FIELDS} if m['state'] == 'succeeded' else None))
            result[arm] = dict(**compare(pairs), runtime=costs(members))
        result['pairs'] = dict(Counter(str(p['A']['state']) + '/' + str(p['B']['state']) for p in d['pairs']))
        return result
    section('p39_fixed', p39)
    def p310():
        all_runs = runfiles('.local/p310/runtime-*/run-*.json')
        by_id = {r['run_id']: r for r in all_runs}
        result = dict(total=costs(list(by_id.values())))
        for phase in ('dev-v1', 'dev-v2', 'new40-initial'):
            d = read('.local/p310/' + phase + '-report/evaluation.json')
            result[phase] = {arm: costs([by_id[m['run_id']] for m in d['members'] if m['arm'] == arm]) for arm in d['arms']}
        for phase, path in [('dev-workflow', '.local/p310/dev-v3-workflow.json'), ('new40-workflow', '.local/p310/new40-workflow-final.json')]:
            d = read(path); result[phase] = {}
            for arm in d['arms']:
                members = [m for m in d['members'] if m['arm'] == arm]
                initial = [by_id[m['first_pass_run_id']] for m in members]
                corrections = [by_id[m['correction_run_id']] for m in members if m['correction_run_id']]
                final = [by_id[m['selected_run_id']] for m in members]
                intervals = [sum(by_id[i]['metadata'].get('elapsed_ms', 0) for i in (m['first_pass_run_id'], m['correction_run_id']) if i) for m in members]
                result[phase][arm] = dict(denominator=len(members), first_accepted=sum(r['status']=='succeeded' for r in initial),
                    final_accepted=sum(r['status']=='succeeded' for r in final), corrections=len(corrections),
                    correction_accepted=sum(r['status']=='succeeded' for r in corrections),
                    uncorrected_failures=sum(not m['first_pass_accepted'] and not m['correction_run_id'] for m in members),
                    workflow_runtime=costs(initial+corrections), service_p50_ms=percentile(intervals,.5), service_p95_ms=percentile(intervals,.95))
        return result
    section('p310', p310)
    report['independent_human_gold'] = 'not established; historical human scores remain null; owner policy/reference decisions are separate'
    report['limitations'] = 'Machine-record arithmetic, not a new model experiment or human semantic audit. All old24/32/new40 are exposed development material.'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = audit(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as f: json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
