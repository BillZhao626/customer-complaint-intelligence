"""Create an exclusive P4.7 offline service inbox; never overwrite old assets."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false', LANGSMITH_TRACING='false',
                  LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')

from src.application.service_scenarios import SCENARIOS, CUSTOM_SCENARIO, VERSION, POLICY_VERSION, POLICY_HASH, example, ServiceCopilotFake
from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, example as v2_example, ServiceCopilotFake as V2Fake, VERSION as V2_VERSION, DEMO_AFTERSALES_POLICY_VERSION, DEMO_AFTERSALES_POLICY_HASH
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.infrastructure.repository import Repository
from src.domain.contracts import digest


def main(out, *, include_engineering=False):
    out = Path(out).resolve()
    # ProductStore enforces this boundary too; fail before creating a directory.
    if out.is_relative_to(ROOT) and not out.is_relative_to(ROOT / '.local/p4'):
        raise ValueError('仓库内演示目录须位于 .local/p4 下；请使用一个新的 p47-* 目录。')
    out.mkdir(parents=True, exist_ok=False)
    store = ProductStore(out / 'product.sqlite3')
    repo = Repository(out / 'product-analysis.sqlite3')
    rows = []
    if include_engineering:
        from src.application.copilot_demo import SCENARIOS as OLD, CopilotFake, example as old_example
        for scenario in (OLD[4], OLD[5], OLD[8]):
            email, data = old_example(scenario)
            case = ProductAnalysis(AnalysisService(repo, CopilotFake(email, scenario)), store).submit(email)
            rows.append(dict(scenario=scenario, case_id=case['case_id'], input_hash=email.input_hash, source=case['source_kind'],
                             state=case['state'], quality=case['quality']['status'], engineering_example=True))
    # Inbox sorts newest first: seed engineering first and consultation last so
    # a new demonstration opens with the ordinary customer-service path.
    recommended=(SCENARIOS[0],V2_SCENARIOS[3])+SCENARIOS[2:4]+V2_SCENARIOS[:3]+SCENARIOS[5:9]
    for scenario in reversed(recommended):
        if scenario == CUSTOM_SCENARIO:
            continue
        email, data = v2_example(scenario) if scenario in V2_SCENARIOS else example(scenario)
        analyzer = V2Fake(email,scenario) if scenario in V2_SCENARIOS else ServiceCopilotFake(email, scenario)
        case = ProductAnalysis(AnalysisService(repo, analyzer), store).submit(email)
        rows.append(dict(scenario=scenario, case_id=case['case_id'], input_hash=email.input_hash, output_hash=digest(data),
                         scenario_hash=analyzer.config.parameters['scenario_hash'], fixture_hash=analyzer.config.parameters['fixture_hash'],
                         source=case['source_kind'], state=case['state'], quality=case['quality']['status']))
    (out / 'demo-manifest.json').write_text(json.dumps(dict(version=VERSION, policy_version=POLICY_VERSION,
        policy_hash=POLICY_HASH, supplemental_version=V2_VERSION, demo_aftersales_policy_version=DEMO_AFTERSALES_POLICY_VERSION,
        demo_aftersales_policy_hash=DEMO_AFTERSALES_POLICY_HASH, model_calls=0, real_sends=0,
        source='Developer-authored synthetic development examples, not model inference, Human Gold or holdout', cases=rows),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Created {len(rows)} offline cases; all drafts unreviewed. Model calls: 0. Product DB: {store.path}')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--include-engineering', action='store_true', help='Also retain original failure and unsafe-analysis demonstrations')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8547)
    args = parser.parse_args()
    main(args.out, include_engineering=args.include_engineering)
    if args.serve:
        env = dict(os.environ, COMPLAINT_PRODUCT_DB=str(args.out.resolve() / 'product.sqlite3'),
                   COMPLAINT_DB_PATH=str(args.out.resolve() / 'legacy.sqlite3'))
        subprocess.run([sys.executable, '-B', '-m', 'streamlit', 'run', str(ROOT / 'app.py'), '--server.address', '127.0.0.1',
                        '--server.port', str(args.port), '--server.fileWatcherType', 'none', '--browser.gatherUsageStats', 'false',
                        '--theme.base', 'light', '--theme.primaryColor', '#5264d9'], cwd=ROOT, env=env, check=True)
