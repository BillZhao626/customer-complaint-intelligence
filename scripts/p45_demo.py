"""Create a new exclusive P4.5 offline demo; never open historical ledgers."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false', LANGSMITH_TRACING='false',
                  LANGCHAIN_TRACING='false', LANGCHAIN_TRACING_V2='false')

from src.application.copilot_demo import SCENARIOS, example, CopilotFake
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.infrastructure.repository import Repository


def main(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    store = ProductStore(out / 'product.sqlite3')
    repo = Repository(out / 'product-analysis.sqlite3')
    rows = []
    for scenario in SCENARIOS:
        email, _ = example(scenario)
        case = ProductAnalysis(AnalysisService(repo, CopilotFake(email, scenario)), store).submit(email)
        rows.append(dict(scenario=scenario, case_id=case['case_id'], input_hash=email.input_hash,
                         source=case['source_kind'], state=case['state'], quality=case['quality']['status']))
    (out / 'demo-manifest.json').write_text(json.dumps(dict(version='p45-authored-v1', model_calls=0,
        source='Explicit authored fixtures / unknown, not model inference', cases=rows), ensure_ascii=False, indent=2), encoding='utf-8')
    print('Created 9 offline cases; all drafts unreviewed. Model calls: 0. Product DB: ' + str(store.path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
