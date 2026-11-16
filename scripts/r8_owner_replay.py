"""Read frozen traces; run the production chain with supplied offline drafts."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REVIEW = ROOT / 'docs/r8-owner-cal-20261109-v1'
R8 = ROOT / 'docs/r8-quality-20261109-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def checked_read(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'Historical evidence changed: {path}')
    return json.loads(raw)


def write(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def replay(out, tmp):
    from src.application.r6u0_workflow import generate, product_run
    from src.application import service_response as service
    from src.application.p5b8_product import stored
    from src.domain.contracts import EmailInput, digest
    from src.evaluation import owner_calibrated_judge as judge
    from tests.test_owner_calibration import control_audits

    owner = read(REVIEW / 'owner-overlay.json')
    drafts = read(REVIEW / 'offline-drafts.json')
    published = {
        row['case_id']: row
        for file in ('dev-results.json', 'holdout-results.json') for row in read(R8 / file)['cases']
    }
    rows = []
    for verdict in owner['cases']:
        cid = verdict['case_id']
        first = checked_read(ROOT / verdict['trace_path'], verdict['trace_sha256'])
        saved = checked_read(ROOT / verdict['judge_path'], verdict['judge_sha256'])
        email = EmailInput.model_validate(first['email'])
        assert email.input_hash == verdict['input_hash']
        assert digest(first['slot']['reply']) == verdict['reply_hash']
        historical = next(s for s in saved['payload']['answers'] if s['reply'] == first['slot']['reply'])
        parsed = saved['parsed']
        rescanned = judge.validate_judgment(parsed, saved['payload']) if parsed else None
        old_score = next(a for a in parsed['answers'] if a['slot'] == historical['slot']) if parsed else None
        new_check = next(a for a in rescanned['answers'] if a['slot'] == historical['slot']) if rescanned else None

        calls = []

        def fake(stage, messages, payload):
            calls.append(stage)
            value = first['analysis'] if stage == 'ANALYSIS' else dict(reply=drafts[cid])
            return dict(raw=json.dumps(value, ensure_ascii=False), run_id=f'offline-{cid}-{stage}', elapsed_ms=0,
                        metadata=dict(dispatch_at='2026-11-09T00:00:00+08:00',
                                      finish_reason='stop' if stage == 'ANALYSIS' else 'tool_calls'))

        candidate = generate(first['email'], fake, tmp / cid, arms=('GUIDED',),
                             revision='r8-owner-offline-v1')['GUIDED']
        assert calls == ['ANALYSIS', 'GUIDED-REPLY']
        assert candidate['analysis_parse']['semantic_eligible'] and candidate['parse']['semantic_eligible']
        assert candidate['runtime']['external_actions'] == 0
        product = product_run(candidate)
        product_quality = service.quality(product, stored(product), drafts[cid], True)
        for guard in (candidate['guard'], product_quality):
            if any(f['severity'] == 'block' for f in guard['findings']):
                raise ValueError(f"Offline draft blocked in {cid}: {guard['findings']}")

        earlier_path = ROOT / '.local/r7-20261106-v1/traces' / f'HOLDOUT-{cid}' / 'GUIDED-reply.json'
        earlier = read(earlier_path) if earlier_path.is_file() else None
        rows.append(dict(
            owner=verdict, original_email=first['email'],
            r7=dict(path=earlier_path.relative_to(ROOT).as_posix(), record=earlier) if earlier else None,
            r8=dict(reply=first['slot']['reply'], analysis=first['analysis'], plan=first['plan'],
                    runtime=first['runtime'], service_brief=first['service_brief'], guard=first['guard'],
                    historical_judge_answer=old_score, historical_judge_validation=parsed.get('validation') if parsed else None,
                    published_ai_review={key: published[cid][key] for key in ('new_verdict', 'reason')}),
            calibrated_historical_audit=new_check,
            offline_candidate=dict(origin='HANDWRITTEN_FIXTURE_REPLAY_NOT_PROVIDER', reply=drafts[cid],
                                   run_id=candidate['slot']['run_id'], reply_hash=digest(drafts[cid]),
                                   composer=service.identity(), plan=candidate['plan'], runtime=candidate['runtime'],
                                   service_brief=candidate['service_brief'], guard=candidate['guard'],
                                   product_quality=product_quality, provider_judge=None),
        ))
    controls = control_audits()
    confusion = Counter()
    for row in controls:
        expected, actual = row['expected'][0], bool(row['AB']['A'])
        confusion['TP' if actual and expected else 'FN' if expected else 'FP' if actual else 'TN'] += 1
    write(out / 'replay.json', dict(provider_requests=0, judge=judge.identity(), cases=rows))
    write(out / 'controls.json', dict(
        scope='DETERMINISTIC_SCREEN_AND_BLIND_PAYLOAD_ONLY', families=len(controls),
        family_first_sentinel={k: confusion[k] for k in ('TP', 'FN', 'TN', 'FP')},
        swap_agreement=sum(r['AB'] == r['BA'] for r in controls),
        repeat_agreement=sum(r['AB'] == r['REPEAT'] for r in controls), controls=controls,
        provider_score_agreement=None, human_agreement=None, cohen_kappa=None,
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=False)
    os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false',
                      LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false')
    blocked = RuntimeError('Network disabled for the Owner replay')
    with (TemporaryDirectory(prefix='r8_owner_replay_') as tmp,
          patch.object(socket.socket, 'connect', side_effect=blocked),
          patch.object(socket.socket, 'connect_ex', side_effect=blocked)):
        replay(out, Path(tmp))
    print(f'Offline evidence saved to {out.resolve()}')


if __name__ == '__main__':
    main()
