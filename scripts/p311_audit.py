"""Read-only policy/source verification. No model clients, budgets or writers."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.application.product_quality import inspect, POLICY, POLICY_HASH
from src.application.product_sources import catalog, read_run
from src.application.product_workflow import raw_hash, analysis_data
from src.domain.contracts import EmailInput, digest


def build(root, attachment):
    manifest = json.loads((attachment / 'SHA256_MANIFEST.json').read_text(encoding='utf8'))
    for name, item in manifest.items():
        raw = (attachment / name).read_bytes()
        if sha256(raw).hexdigest() != item['sha256'] or len(raw) != item['bytes']:
            raise ValueError('Attachment manifest mismatch')
    path = next(attachment.glob('*v1.0.json'))
    decisions = json.loads(path.read_text(encoding='utf8'))
    packet_path = root / '.local/p310/FINAL_REVIEW_V2/content-review.json'
    packet_hash = sha256(packet_path.read_bytes()).hexdigest()
    if packet_hash != 'c57d8d42a27d42446aa2576410913718155b86ed04ac4b292206da7e0c1376e5':
        raise ValueError('Original review packet hash mismatch')
    packet = json.loads(packet_path.read_text(encoding='utf8'))
    by_id = {r['run_id']: r for r in packet['records']}
    source_items = catalog(root)
    source_map = {r['run_id']: r for r in source_items}
    records = []
    missing = []
    for decision in decisions['owner_decisions']:
        original = EmailInput.model_validate(decision['original_email'])
        for output in decision['outputs']:
            if not output.get('run_id'):
                if output['original_status'] != 'NOT_ATTEMPTED':
                    raise ValueError('Missing actual run identity')
                missing.append(dict(sample_id=decision['sample_id'], stage=output['stage'], status='NOT_ATTEMPTED'))
                continue
            record = by_id[output['run_id']]
            run = read_run(source_map[record['run_id']]['path'], record['run_id'])
            if run.email != original or run.input_hash != output['input_hash'] or raw_hash(run) != output['raw_sha256'] or (run.status == 'succeeded') != output['original_acceptance']:
                raise ValueError('Owner/run/input/raw/status identity mismatch')
            if record['raw_sha256'] != raw_hash(run) or record['formal_accepted'] != output['original_acceptance']:
                raise ValueError('Review packet identity mismatch')
            data = analysis_data(run)
            quality = inspect(run.email, data, accepted=True)
            fields = []
            risk = decision['risk_decision']
            if risk.get('state') == 'OWNER_CONFIRMED':
                fields.append(dict(field='risk/urgency', compliant=all(i.get('risk_level') == risk['risk_level'] and i.get('urgency') == risk['urgency'] for i in data['issues'])))
            expected = decision['issue_level_decision']
            for key in ('reason', 'business_process'):
                if key in expected:
                    fields.append(dict(field=key, compliant=all(i.get(key) == expected[key] for i in data['issues'])))
            if decision['customer_importance_decision'].get('state') == 'OWNER_CONFIRMED':
                ordered = sorted(data['issues'], key=lambda i: i.get('handling_priority') or 999)
                fields.append(dict(field='importance/order', compliant=[i.get('customer_importance') for i in ordered] == ['primary', 'secondary'] and [i.get('handling_priority') for i in ordered] == [1, 2]))
            conflict = any(not f['compliant'] for f in fields) or any(f['severity'] == 'block' for f in quality['findings'])
            records.append(dict(sample_id=decision['sample_id'], run_id=run.run_id, input_hash=run.input_hash,
                                raw_sha256=raw_hash(run), source_snapshot_hash=digest(run.model_dump()),
                                historical_contract_status=output['original_status'], formal_accepted=output['original_acceptance'],
                                owner_policy_checks=fields, owner_policy_observation=output['owner_policy_observation'],
                                owner_policy_compliance='core_conflict_or_blocking_candidate' if conflict else 'core_fields_match_full_reply_pending',
                                formal_accepted_but_owner_policy_violation=bool(output['original_acceptance'] and conflict),
                                original_quality_flag=decision['data_quality']['status'],
                                original_unnatural_scope_note=expected.get('target_scope'),
                                diagnostic=quality, human_score=None, full_reply_approved=False))
    # Same raw, old formal acceptance versus separate new diagnostics. No re-evaluation as a new prediction.
    differential = []
    for item in source_items:
        run = read_run(item['path'], item['run_id'])
        data = analysis_data(run)
        q = inspect(run.email, data, accepted=True)
        differential.append(dict(run_id=run.run_id, sample_id=run.email.email_id, input_hash=run.input_hash,
                                 raw_sha256=raw_hash(run), historical_status=run.status,
                                 historical_accepted=bool(run.result), new_diagnostic=q,
                                 false_positive_human_confirmed=None, complete_reply_human_score=None))
    natural = next(d for d in decisions['owner_decisions'] if d['data_quality'].get('replacement_development_variant'))
    e = EmailInput(email_id='N03-natural-v1', subject=natural['original_email']['subject'], body=natural['data_quality']['replacement_development_variant'])
    variant = dict(email=e.model_dump(), input_hash=e.input_hash, parent_input_hash=natural['data_quality']['original_immutable_input_hash'],
                   family=natural['sample_id'], split='exposed_development', independent_holdout=False,
                   prediction=None, gold_status='owner_approved_core_only', parent_quality='owner_flagged_unnatural_contrast')
    return dict(version='p311-owner-policy-audit-v1', policy=POLICY, policy_hash=POLICY_HASH,
                attachment_manifest=manifest, attachment_json_hash=sha256(path.read_bytes()).hexdigest(),
                source_packet_hash=packet_hash, owner_record=decisions, records=records, not_attempted=missing,
                natural_variant=variant, same_raw_differential=differential,
                new_paid_calls=0, old_statuses_modified=0, human_gold=None)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attachment', type=Path, default=ROOT / '.local/p311/adjudication')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    report = build(ROOT, args.attachment)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (args.out / 'N03-natural-v1.json').write_text(json.dumps(report['natural_variant'], ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(dict(verified=len(report['records']), not_attempted=report['not_attempted'],
                         historical_real_runs=len(report['same_raw_differential']),
                         accepted_policy_flags=sum(r['formal_accepted_but_owner_policy_violation'] for r in report['records']),
                         new_paid_calls=0)))
