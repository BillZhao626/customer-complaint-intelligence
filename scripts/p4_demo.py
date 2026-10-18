"""Create an exclusive reproducible product demo and a vertical acceptance receipt.

Only explicit offline LangChain fixtures and read-only saved real runs. No SMTP,
CRM or paid provider. All approvals here are demo_test, never human evaluation.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(COMPLAINT_ENABLE_LIVE='false', LLM_ENABLE_API='false', LANGSMITH_TRACING='false',
                  LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')

from src.application.product_demo import SCENARIOS, ProductFake, example
from src.application.product_workflow import ProductStore, Conflict
from src.application.analysis_service import AnalysisService
from src.infrastructure.repository import Repository
from src.domain.contracts import digest

CHECKS = dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True)


def main(out, real_replay=False):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    db = ProductStore(out / 'product.sqlite3')
    repo = Repository(out / 'analysis.sqlite3')
    results = []
    def act(c, action, **kwargs):
        return db.act(c['case_id'], action, expected_revision=c['revision'], actor='engineering_demo_operator',
                      actor_type='demo_test', reason='Automated vertical demonstration; no human semantic approval or Gold',
                      checks=CHECKS, operation_id=str(uuid4()), **kwargs)
    for n, scenario in enumerate(SCENARIOS[:-1]):
        e, _ = example(scenario)
        run = AnalysisService(repo, ProductFake(e, scenario)).analyze(e)
        c = db.create(run, 'LangChain offline runnable / explicit engineering fixture')
        if n in (4, 5):
            assert c['state'] == 'analysis_failed' and not c['draft']
            try:
                act(c, 'simulate_send')
                raise AssertionError('Invalid analysis was sendable')
            except Conflict:
                pass
        else:
            try:
                act(c, 'simulate_send')
                raise AssertionError('Unreviewed draft was sendable')
            except Conflict:
                pass
            if n == 3:
                c = act(c, 'request_changes')
                c = act(c, 'save_edit', body='Thank you for describing the lamp fault. Please share its model and existing purchase information so available support options can be verified.')
            c = act(c, 'approve')
            c = act(c, 'simulate_send')
            assert c['receipt']['body_hash'] == c['draft']['body_hash']
        fresh = ProductStore(db.path).get(c['case_id'])
        assert fresh['run'].input_hash == run.email.input_hash
        assert fresh['state'] == c['state']
        assert fresh['drafts'] == c['drafts']
        results.append(dict(scenario=scenario, case_id=c['case_id'], source=fresh['source_kind'], status=fresh['state'],
                            input_hash=run.input_hash, source_snapshot_hash=c['snapshot_hash'], versions=len(c['drafts']),
                            events=len(c['events']), sqlite_reloaded=True, receipt=c['receipt']))
    # Separate rejection scenario, retaining an unsent immutable analysis.
    e, _ = example(SCENARIOS[0]); e = e.model_copy(update={'email_id': 'p4-rejected-fixture'})
    run = AnalysisService(repo, ProductFake(e, SCENARIOS[0])).analyze(e)
    c = act(db.create(run), 'reject')
    results.append(dict(scenario='Explicit rejection', case_id=c['case_id'], source=c['source_kind'], status=c['state'], sqlite_reloaded=ProductStore(db.path).get(c['case_id'])['state'] == 'rejected'))
    if real_replay:
        from src.application.product_sources import catalog, read_run
        items = catalog(ROOT)
        for run_id in ('69937d52-da7a-42f8-a275-5ec753f1c3f1', '86d85387-9dcc-49be-80a1-0ac55019af65', '017538b6-5770-4607-9cd8-e82805f39f5d'):
            item = next(i for i in items if i['run_id'] == run_id)
            run = read_run(item['path'], run_id)
            before = digest(run.model_dump())
            c = db.create(run, item['path'])
            if c['accepted'] and c['quality']['status'] != 'blocked':
                c = act(c, 'approve'); c = act(c, 'simulate_send')
            elif c['draft']:
                c = act(c, 'reject')
            else:
                assert c['state'] == 'analysis_failed'
            assert digest(read_run(item['path'], run_id).model_dump()) == before
            fresh = ProductStore(db.path).get(c['case_id'])
            results.append(dict(scenario='Historical real replay', run_id=run_id, case_id=c['case_id'],
                                source=c['source_kind'], original_status=run.status, status=c['state'],
                                quality=fresh['quality'], sqlite_reloaded=True, original_snapshot_unchanged=True))
    with db.connect() as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        foreign_keys = [tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
    report = dict(version='p4-vertical-acceptance-v1', scenarios=results, dashboard=db.dashboard(),
                  sqlite_integrity=integrity, foreign_key_errors=foreign_keys, new_paid_calls=0, real_emails_sent=0,
                  review_actor_type='demo_test', human_semantic_quality=None,
                  test_kind='service/SQLite vertical demonstration; browser and AppTest evidence recorded separately')
    (out / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (out / 'START.md').write_text('# Local P4 demo\n\n```powershell\n$env:COMPLAINT_PRODUCT_DB = \'' + str(db.path) + '\'\n$env:COMPLAINT_DB_PATH = \'' + str(out / 'legacy.sqlite3') + "'\n.\\.venv\\Scripts\\python.exe -B -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false\n```\n\nAll approvals are demo_test, not Human Gold. Use work history to reopen. Fresh offline input or historical real replay always starts unreviewed.\n", encoding='utf8')
    print(json.dumps(dict(scenarios=len(results), integrity=integrity, foreign_key_errors=foreign_keys, paid_calls=0, real_sends=0, database=str(db.path))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--real-replay', action='store_true')
    args = parser.parse_args()
    main(args.out, args.real_replay)
