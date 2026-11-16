"""Read-only reuse/realism audit. New reports only; no provider or old DB opens."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import argparse
import csv
import json
import os
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false',
                  LANGSMITH_TRACING='false', LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')
from src.evaluation.dataset_audit import audit_dataset, normalized_body
from src.evaluation.p5b5 import read, hashfile

VERSION = 'p5b5r2-readonly-data-audit-1'
ROLES = {'DEV_REGRESSION', 'CALIBRATION', 'INDEPENDENT_TEST'}
DIMENSIONS = ['A1_expression', 'A2_consistency', 'A3_information', 'A4_emotion',
              'A5_repetition_leakage', 'A6_multiturn']


def digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


def registry_audit():
    registry_path = ROOT/'.local/p5b5/evidence-v1/case-registry.json'
    gold_path = ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json'
    registry, gold = read(registry_path), read(gold_path)
    objects = registry['objects']
    assert len(objects) == registry['counts']['canonical_objects'] == 174
    assert all(set(o['dataset_role']) <= ROLES for o in objects)
    assert all(not o['independent_test'] for o in objects)
    assert len(gold) == 16
    anchors = read(ROOT/'docs/p5q/owner_accepted_references_v1.json')['anchors']
    preserved = []
    for case in gold:
        assert case['reference_sha256'] == digest(case['reference_reply'])
        if case['case_id'] in {'CAL-01', 'CAL-04', 'CAL-08'}:
            anchor = next(a for a in anchors if a['id'] == case['history_anchor_id'])
            assert case['reference_reply'] == anchor['reply']
            assert case['gold_status'] == 'OWNER_ACCEPTED_VERBATIM'
            preserved.append(dict(case_id=case['case_id'], reference_sha256=case['reference_sha256']))
        else:
            assert case['reference_author'] == 'assistant_from_owner_policy'
            assert case['gold_status'] == 'OWNER_AUTHORIZED_DEV_SEMANTIC_REFERENCE'
            assert not case['user_verbatim_signature']
    assert len(preserved) == 3
    assert registry['counts']['classification_p35'] == 24
    assert registry['counts']['classification_i4'] == 80
    assert len(registry['b4_reconciliation']) == 28
    assert all(c['status'] == 'PENDING_HUMAN' for c in registry['b4_reconciliation'])
    return dict(source=str(registry_path.relative_to(ROOT)), sha256=hashfile(registry_path),
                unchanged_reused=True, counts=registry['counts'], roles=sorted(ROLES),
                observed_roles=sorted({r for o in objects for r in o['dataset_role']}),
                gold_identity_is_separate_from_use=True, verbatim_reference_checks=preserved,
                human_numerical_reply_labels=sum(any(v is not None for v in c['human_dimension_scores'].values()) for c in gold),
                independent_test_cases=0,
                independent_test_note='Existing 174 objects are exposed DEV. New one-shot synthetic tests, if any, are separately registered; none gains independent human Gold identity.',
                historical_prediction_overlays='B2–E4 are predictions, never reference or customer fact',
                review_identity='24 researcher-confirmed AI-assisted classification; 80 historical reviewed labels (70 accepted / 10 corrected); neither supplies reply-dimension human scores')


def realism_audit():
    path = ROOT/'data/synthetic/customer_emails_full_v1.csv'
    rows = list(csv.DictReader(path.open(encoding='utf-8-sig')))
    result = audit_dataset(path)
    old = read(ROOT/'docs/p25/evidence/dataset-statistics.json')
    old_issues = read(ROOT/'docs/p25/evidence/suspect-samples.json')
    assert result['input_sha256'] == old['input_sha256']
    assert result['n'] == old['n'] == 400
    assert result['template_count'] == old['template_count'] == 55
    assert result['leakage_components'] == old['leakage_components'] == 10
    assert len(result['issues']) == len(old_issues) == 146
    assert {i['sample_id']: i['flags'] for i in result['issues']} == {i['sample_id']: i['flags'] for i in old_issues}
    # Additional transparent screen: original generator boilerplate discloses synthetic case IDs.
    marker_ids = [r['email_id'] for r in rows if 'synthetic' in r['email_body'].lower()]
    normalized = Counter(normalized_body(r) for r in rows)
    groups = {}
    for sample in result['samples']:
        groups.setdefault(sample['semantic_group'], []).append(sample['sample_id'])
    by_id = {r['email_id']: r for r in rows}
    flags = {r['sample_id']: r['flags'] for r in result['issues']}
    # Fixed purposefully stratified examples. No sampling from model scores.
    fixed = ['F001', 'F051', 'F121', 'F141', 'F176', 'F241', 'F281', 'F331']
    samples = []
    for sid in fixed:
        r = by_id[sid]
        samples.append(dict(case_id=sid, source=str(path.relative_to(ROOT)), source_sha256=hashfile(path),
                            input_sha256=digest(r['email_body']), source_kind='HISTORICAL_SYNTHETIC_TEMPLATE',
                            dataset_role=['DEV_REGRESSION'], subject=r['subject'], customer=r['email_body'],
                            scenario_family=r['scenario_type'], template=r['generation_template_id'],
                            provisional_flags=flags.get(sid, []), synthetic_marker_in_body='synthetic' in r['email_body'].lower(),
                            human_scores={d: None for d in DIMENSIONS[:-1]} | {'A6_multiturn': 'N/A'},
                            applicability_reason='Independent single email: A6 N/A, not zero.',
                            recommendation='Use as a grouped engineering regression or human realism review candidate; never independent test.'))
    dev = read(ROOT/'resources/p5a/cases_dev.json')
    for sid in ['P5A-F01-M01-1', 'P5A-F08-M01-1', 'P5A-F11-M01-1', 'P5A-F12-M02-1']:
        c = next(c for c in dev if c['case_id'] == sid)
        isolated = '-F11-' in sid
        samples.append(dict(case_id=sid, source='resources/p5a/cases_dev.json',
                            source_sha256=hashfile(ROOT/'resources/p5a/cases_dev.json'),
                            input_sha256=digest(c['body']), source_kind=c['source_kind'], dataset_role=['DEV_REGRESSION'],
                            subject=c['subject'], customer=c['body'], scenario_family=c['scenario_family'],
                            human_scores={d: None for d in DIMENSIONS[:-1]} | {'A6_multiturn': None if isolated else 'N/A'},
                            applicability_reason='Isolated follow-up without full preceding conversation: A6 UNKNOWN.' if isolated else 'Independent single email: A6 N/A.',
                            provisional_flags=['ISOLATED_FOLLOWUP'] if isolated else [],
                            recommendation='Existing exposed synthetic DEV; may calibrate variety but cannot certify population representativeness.'))
    for sid in ['P5A-D4', 'P5A-D6']:
        c = next(c for c in read(ROOT/'resources/p5a/conversations_dev.json') if c['conversation_id'] == sid)
        samples.append(dict(case_id=sid, source='resources/p5a/conversations_dev.json',
                            source_sha256=hashfile(ROOT/'resources/p5a/conversations_dev.json'),
                            input_sha256=digest(json.dumps(c['turns'], ensure_ascii=False, sort_keys=True)),
                            source_kind=c['source_kind'], dataset_role=['DEV_REGRESSION'],
                            customer_messages=[t['body'] for t in c['turns'] if t['role'] == 'customer'],
                            full_context=c['turns'], human_scores={d: None for d in DIMENSIONS},
                            provisional_flags=['DEVELOPER_SCRIPTED_TWO_TURN_SLOT_FILLING'],
                            recommendation='Review continuity with original context; do not count assistant candidate as confirmed fact.'))
    revisions = [
        dict(case_id='F001', proposed_subject='Headphones stopped working',
             proposed_body='Hi, I bought wireless headphones from your Hangzhou West Lake store last week. They stopped working while I was using them normally. What should I do to get them checked?',
             basis='Remove synthetic marker and fix article/number agreement; keep product, store, timing and failure. This is a proposed rewrite, not customer data or a new Gold.'),
        dict(case_id='F121', proposed_subject='Still waiting for help with my headphones',
             proposed_body='Hi, I bought wireless headphones through your app last week from the Hangzhou West Lake store. I have sent support several messages and have not had a reply. Can someone help me follow this up?',
             basis='Restore customer as the subject of support messages; preserve facts and avoid inventing the unspecified underlying problem.'),
        dict(case_id='F141', proposed_subject='Refund request has not moved forward',
             proposed_body='I bought a hair dryer from the Hangzhou West Lake store through your website last week. I asked for a refund, but I have not seen any progress. Could you tell me what is still needed?',
             basis='Replace product-as-requester grammar, remove repeated but and synthetic marker. No refund eligibility or approval is asserted.'),
        dict(case_id='F176', proposed_subject='Help with my membership support request',
             proposed_body=None,
             basis='Do not silently rewrite membership plan into a physical repair. Product/policy truth is missing; researcher must decide whether this is a service benefit or an unsuitable object/scenario pairing.')
    ]
    source_by_id = {s['case_id']: s for s in samples}
    for r in revisions:
        r['original'] = source_by_id[r['case_id']]['customer']
        r['original_input_sha256'] = source_by_id[r['case_id']]['input_sha256']
        r['status'] = 'PROPOSED_SYNTHETIC_REWRITE_NOT_HUMAN_ACCEPTED'
        r['dataset_role'] = ['DEV_REGRESSION']
        r['new_source_kind'] = 'ASSISTANT_PROPOSED_SYNTHETIC_REVISION'
        r['proposed_input_sha256'] = digest(r['proposed_body']) if r['proposed_body'] else None
    markers_before = sum('synthetic' in r['original'].lower() for r in revisions if r['proposed_body'])
    markers_after = sum('synthetic' in r['proposed_body'].lower() for r in revisions if r['proposed_body'])
    return dict(identity='PROVISIONAL_AUTOMATIC_AND_DEVELOPER_DIAGNOSTIC_NOT_HUMAN_REALISM_RATING',
                source_sha256=result['input_sha256'], original_input_unchanged=True,
                recomputed=dict(n=400, templates=55, suspected_leakage_components=10, flagged_samples=146,
                                flag_counts=result['issue_counts'], distributions=result['distributions'],
                                language=result['language'], length_chars=result['length_chars']),
                historical_values_reproduced=True, all_400_bodies_with_synthetic_marker=len(marker_ids),
                unique_slot_masked_bodies=len(normalized), conservative_components=groups,
                semantic_duplicate_status='Lexical/template and scenario-family proxy only; no new human semantic judgment.',
                human_naturalness_labels=0, human_naturalness_pass_rate=None,
                human_representativeness_pass_rate=None,
                rubric='docs/p5q/EVALUATION_PROTOCOL_v0.1.md A1–A6; processable customer goal and population distribution reviewed separately, without invented numerical Gold.',
                samples=samples, revision_candidates=revisions,
                revision_comparison=dict(scope='3 proposed rewrites, not accepted new corpus', denominator=3,
                                         synthetic_markers_before=markers_before, synthetic_markers_after=markers_after,
                                         human_realism_improvement=None, real_model_comparison='NOT_RUN'),
                gaps=['400/400 synthetic English templates; no real customer distribution or prevalence estimates.',
                      '8 product categories have exactly 50 records and 10 stores exactly 40: designed balancing, not measured demand.',
                      'No missing store/product in the original pool, unlike incomplete real customer messages.',
                      'P5A adds 36 Chinese / 12 English messages and six short scripted conversations; still exposed developer data.',
                      'External corpora not imported in R2; no new license/privacy assumptions or external business policy transferred.'])


def review_materials(realism):
    # Material for the ONE root review package, not a separately signed review form.
    result = []
    for sid in ['F001', 'F176', 'P5A-F08-M01-1', 'P5A-F11-M01-1', 'P5A-D6']:
        s = next(s for s in realism['samples'] if s['case_id'] == sid)
        rewrite = next((r for r in realism['revision_candidates'] if r['case_id'] == sid), None)
        result.append(dict(item_id='DATA-'+sid, category='DATA_REALISM', approval_level='SUGGESTED_SPOT_CHECK',
                           case_id=sid, source=s['source'], customer=s.get('customer', s.get('customer_messages')),
                           source_sha256=s['source_sha256'], input_sha256=s['input_sha256'],
                           reference_status='SYNTHETIC_DEV_NOT_REPLY_GOLD', gold_reference=None,
                           required_points=['Keep source identity separate from apparent naturalness.', 'A6 N/A for genuine single turn; UNKNOWN for isolated follow-up.'],
                           b2_reply=None, latest_reply=None, tool_events=[],
                           automatic_evidence=s.get('provisional_flags', []),
                           engineering_diagnosis=rewrite['basis'] if rewrite else s['recommendation'],
                           proposed_revision=rewrite.get('proposed_body') if rewrite else None,
                           recommended_decision='Allow grouped DEV use; keep human realism rating pending. F176 needs object/policy clarification.' if sid == 'F176' else 'Use only for DEV/calibration and review naturalness with the complete sibling/context evidence.',
                           choices=['AGREE', 'MODIFY', 'REJECT', 'UNABLE_TO_JUDGE'], human_choice=None, human_comment=None))
    return result


def report():
    registry = registry_audit()
    realism = realism_audit()
    sources = ['src/evaluation/dataset_audit.py', 'src/evaluation/p5b5.py',
               'data/synthetic/customer_emails_full_v1.csv', 'resources/p5a/cases_dev.json',
               'resources/p5a/conversations_dev.json', 'docs/p5q/EVALUATION_PROTOCOL_v0.1.md',
               'docs/p5q/owner_accepted_references_v1.json', '.local/p5b5/evidence-v1/owner-policy-overlay.json',
               '.local/p5b5/evidence-v1/case-registry.json']
    return dict(version=VERSION, source_hashes={p: hashfile(ROOT/p) for p in sources},
                registry=registry, data_realism=realism, unified_review_materials=review_materials(realism),
                local_business_results='See DATA_ACTIONS_EXECUTION.json produced by explicit temporary-store tests; local requests do not establish external completion.',
                paid_requests=0, external_business_actions=0)


def action_execution():
    """Fresh offline event evidence; original and R2 stores are isolated fixtures."""
    import io
    import tempfile
    import unittest
    from src.application.p5b5_state_v3 import ConversationState as OldState
    from src.application.p5b5_pipeline import ActionStore as OldStore
    from src.application.p5b5r2_pipeline import ConversationState, ConversationStore, ActionStore
    from tests.test_p5b5r2_actions import P5B5R2ActionTests
    stream = io.StringIO()
    test_result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(P5B5R2ActionTests))
    examples = [
        ('unknown_multi', ['抽屉滑出来磕腿，周六取旧床没人来，发票漏项。订单DEMO-PROBE-24。']),
        ('cancel_then_invoice', ['预约安装周一上午。', '我要取消安装，不要再安排师傅了。', '另外帮我核实发票漏项。']),
        ('resolved_then_invoice', ['台灯坏了，想退货。', '售后已解决，不用处理了。', '另外帮我核实发票漏项。']),
        ('correct_order', ['订单DEMO-OLD-24，周一安装。', '号码写错，更正为DEMO-NEW-24。只有周三下午在家。']),
    ]
    evidence = []
    with tempfile.TemporaryDirectory(prefix='p5b5r2-offline-action-probe-') as directory:
        root = Path(directory)
        for name, customer_texts in examples:
            old, new = OldState(name), ConversationState(name)
            persistence = ConversationStore(root/(name+'-conversation.db'))
            for i, text in enumerate(customer_texts):
                old.update('customer', text)
                new = persistence.update(name, 'customer', text, name+'-customer-'+str(i))
            old_runtime = OldStore(root/(name+'-old-actions.db')).execute(old, name+'-input')
            new_runtime = ActionStore(root/(name+'-new-actions.db')).execute(new, name+'-input')
            reopened = ActionStore(root/(name+'-new-actions.db')).execute(ConversationStore(root/(name+'-conversation.db')).load(name), name+'-input')
            assert reopened == new_runtime
            evidence.append(dict(case_id='ENGINEERING-'+name, source_kind='EXPLICIT_OFFLINE_FIXTURE_NOT_LLM_GENERATION',
                customer_messages=customer_texts, input_sha256=digest(json.dumps(customer_texts, ensure_ascii=False)),
                old_runtime=old_runtime, r2_runtime=new_runtime, restarted_and_idempotent_equal=True,
                external_business_completed=False, customer_goal_fully_resolved=None,
                note='Observed task/state differences, not independent semantic human quality scores.'))
    sources = ['scripts/p5b5r2_audit.py', 'tests/test_p5b5r2_actions.py', 'src/application/p5b5r2_pipeline.py',
               'src/application/p5b5_state_v3.py', 'src/application/p5b5_pipeline.py']
    return dict(version='p5b5r2-offline-business-evidence-1',
                source_hashes={p: hashfile(ROOT/p) for p in sources},
                tests=dict(run=test_result.testsRun, failures=len(test_result.failures), errors=len(test_result.errors),
                           skipped=len(test_result.skipped), successful=test_result.wasSuccessful(), log=stream.getvalue()),
                evidence=evidence, paid_requests=0, external_business_completed=0,
                human_semantic_accuracy=None, fake_model_quality_claim=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default=str(ROOT/'docs/p5b5r2/DATA_ACTIONS.json'))
    p.add_argument('--verify', action='store_true')
    p.add_argument('--actions-out')
    a = p.parse_args()
    def blocked(*args, **kwargs):
        raise RuntimeError('Read-only data audit: network disabled')
    socket.socket.connect = blocked
    socket.create_connection = blocked
    if a.actions_out:
        value = action_execution()
        target = Path(a.actions_out)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        print(json.dumps(value['tests'] | dict(log='saved in '+str(target)), ensure_ascii=False))
        if not value['tests']['successful']:
            raise SystemExit(1)
        return
    value = report()
    target = Path(a.out)
    if a.verify:
        assert read(target) == value
        print('PASS: original source hashes, 174 reused Registry objects, 400/55/10/146 and pending human fields reproduced')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        print(json.dumps(dict(out=str(target), registry_objects=174, original_emails=400,
                              templates=55, suspected_components=10, screened=146,
                              human_realism_labels=0, paid_requests=0)))


if __name__ == '__main__':
    main()
