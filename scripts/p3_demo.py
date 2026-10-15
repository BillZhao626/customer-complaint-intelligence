"""Create a new isolated synthetic demo database. No API or historical writes."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
from src.evaluation.p3_fixture import seed
from src.infrastructure.repository import Repository
from src.application.attribution_service import AttributionService
from src.evaluation.e2e import evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    out=Path(args.out).resolve()
    if any(out.is_relative_to(ROOT/p) for p in ('data','outputs','docs','.local/p2-pilot-v1','.local/p25')):
        raise ValueError('Protected destination')
    out.mkdir(parents=True,exist_ok=False)
    samples,runs=seed(Repository(out/'runs.sqlite3'))
    service=AttributionService(runs,'p3_demo',samples)
    for name,value in [('dataset',[s.model_dump() for s in samples]),('runs',[r.model_dump() for r in runs]),
        ('statistics',service.snapshot(runs[0].cohort_id)),('evaluation',evaluate(samples,runs))]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Synthetic demo ready; 10 cases, no provider calls. Configure COMPLAINT_DB_PATH and COMPLAINT_DATASET_MANIFEST in this directory.')


if __name__=='__main__':main()
