"""Append prediction links to the existing Registry by overlay, without relabeling."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation.p5b5 import read, hashfile, text_hash


def build():
    base_path = ROOT/'.local/p5b5/evidence-v1/case-registry.json'
    base = read(base_path)
    source_root = ROOT/'.local/p5b5-live-20261030-v1'
    current = ROOT/'.local/p5b5r2'
    scenario_path = current/'scenario-holdout.json'
    frozen = read(current/'scenario-holdout-manifest.json')
    assert hashfile(scenario_path) == frozen['sha256']
    scenarios = {c['case_id']: c for c in read(scenario_path)['cases']}
    prediction_links = []
    sources = {str(base_path.relative_to(ROOT)): hashfile(base_path),
               str(scenario_path.relative_to(ROOT)): frozen['sha256']}
    added_objects = {}
    seen = set()
    def append(record, path, generation):
        if record['run_id'] in seen:
            return
        seen.add(record['run_id'])
        run_path = Path(record['run_path'])
        run = read(run_path)
        assert run['run_id'] == record['run_id']
        assert run['input_hash'] == record['input_hash']
        assert len(run['attempts']) == 1
        assert run['attempts'][0]['attempt_no'] == 1
        assert record['first_contract'] == (run['status'] == 'succeeded')
        case_id = record['case_id']
        if case_id in base['aliases']:
            object_id = base['aliases'][case_id]
            purposes = ['DEV_REGRESSION', 'CALIBRATION']
        elif case_id in scenarios:
            c = scenarios[case_id]
            customers = [m['text'] for m in c['input_messages'] if m['role'] == 'customer']
            object_id = text_hash(json.dumps(customers, ensure_ascii=False, separators=(',', ':')))
            purposes = ['INDEPENDENT_TEST']
            added_objects.setdefault(object_id, dict(object_id=object_id, aliases=[case_id], customer_messages=customers,
                dataset_role=purposes, gold_status=['SYNTHETIC_UNLABELED_SCENARIO_HOLDOUT'],
                independent_test=True, independent_human_gold=False,
                independence_scope='New one-shot synthetic scenes not used for candidate optimization; no independent human truth and no population claim.',
                source=str(scenario_path.relative_to(ROOT)), source_sha256=frozen['sha256'],
                human_dimension_scores=None, reference_reply=None))
        else:
            # A live UI smoke is an exposed, confirmed synthetic development input.
            customers = [run['email']['body']]
            object_id = text_hash(json.dumps(customers, ensure_ascii=False, separators=(',', ':')))
            purposes = ['DEV_REGRESSION']
            added_objects.setdefault(object_id, dict(object_id=object_id, aliases=[case_id], customer_messages=customers,
                dataset_role=purposes, gold_status=['SYNTHETIC_UI_SMOKE_NO_HUMAN_GOLD'],
                independent_test=False, independent_human_gold=False,
                source=str(run_path.relative_to(ROOT)), source_sha256=hashfile(run_path),
                human_dimension_scores=None, reference_reply=None))
        raw = run['attempts'][0].get('raw_output')
        turn = record.get('turn')
        if turn is None:
            email_id = run['email']['email_id']
            if '-T' in email_id and email_id.rsplit('-T', 1)[-1].isdigit():
                turn = int(email_id.rsplit('-T', 1)[-1])
            else:
                turn = 1
        prediction_links.append(dict(object_id=object_id, case_id=case_id, turn=turn, arm=record['arm'],
            generation=generation, dataset_role=purposes, annotation_kind='MODEL_FIRST_PREDICTION_NOT_GOLD',
            run_id=run['run_id'], input_hash=run['input_hash'],
            prediction_text_sha256=text_hash(record.get('reply', '')), raw_sha256=text_hash(raw) if raw else None,
            run_path=str(run_path.relative_to(ROOT)), run_sha256=hashfile(run_path),
            record_path=str(path.relative_to(ROOT)), record_sha256=hashfile(path),
            status=run['status'], first_contract=record['first_contract'],
            provider_received=record.get('provider_received'), failed=run['status'] != 'succeeded',
            tool_receipt_sha256=text_hash(json.dumps(record.get('runtime', {}).get('events', []), ensure_ascii=False, sort_keys=True)),
            config_hash=text_hash(json.dumps(run['config'], ensure_ascii=False, sort_keys=True)),
            semantic_human_accepted=None))
    for arm in ('B2', 'E1', 'E2', 'E3', 'E4'):
        p = source_root/arm/'results.json'
        records = read(p)
        assert len(records) == 18
        sources[str(p.relative_to(ROOT))] = hashfile(p)
        for record in records:
            append(record, p, 'HISTORICAL_P5B5_NOT_R2_RETEST')
    for p in sorted(current.glob('**/results.json')):
        data = read(p)
        if not isinstance(data, list) or not all(isinstance(x, dict) and 'run_id' in x and 'run_path' in x for x in data):
            continue
        sources[str(p.relative_to(ROOT))] = hashfile(p)
        for record in data:
            append(record, p, 'P5B5_R2_NEW_REAL_FIRST_GENERATION')
    # Retain completed rows even before an arm's summary is written, including UI smoke.
    for p in sorted(current.glob('**/evaluation.json')):
        data = read(p)
        if isinstance(data, dict) and 'run_id' in data and 'run_path' in data:
            sources[str(p.relative_to(ROOT))] = hashfile(p)
            append(data, p, 'P5B5_R2_NEW_REAL_FIRST_GENERATION')
    assert all(set(x['dataset_role']) <= {'DEV_REGRESSION', 'CALIBRATION', 'INDEPENDENT_TEST'} for x in prediction_links)
    from collections import Counter
    return dict(version='p5b5r2-case-registry-prediction-overlay-1',
        base_registry=str(base_path.relative_to(ROOT)), base_registry_sha256=hashfile(base_path),
        base_registry_unchanged=True, base_objects=174, base_gold_identity_unchanged=True,
        source_hashes=sources, added_objects=list(added_objects.values()), prediction_links=prediction_links,
        counts=dict(predictions=len(prediction_links), by_arm=dict(Counter(x['arm'] for x in prediction_links)),
                    by_generation=dict(Counter(x['generation'] for x in prediction_links)),
                    new_objects=len(added_objects), human_numerical_reply_labels=0),
        missing_attachment_truth='A customer mentioning photos does not create an attachment receipt or attachment Gold. No missing policy or tool outcome is automatically labeled correct.',
        note='Only prediction overlays appended by existing object_id. Same conversation across turns is one source object; attempts and arm denominators remain separate. New synthetic holdout status is not independent human Gold.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    p.add_argument('--verify', action='store_true')
    a = p.parse_args()
    report = build()
    path = Path(a.out)
    if a.verify:
        assert read(path) == report
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report['counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
