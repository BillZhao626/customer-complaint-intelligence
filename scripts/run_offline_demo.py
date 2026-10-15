"""Reproducible P1 demo; explicit fake only, no .env/provider imports."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.application.analysis_service import AnalysisService
from src.application.analyzers import OfflineFake
from src.domain.contracts import EmailInput
from src.infrastructure.repository import Repository


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True,help='Dedicated new-run SQLite path; no historical import')
    args=parser.parse_args()
    repo=Repository(args.db)
    service=AnalysisService(repo,OfflineFake())
    fixtures=[('demo-a-negative','[store:A] [negative] Synthetic: broken headphones.'),
              ('demo-a-positive','[store:A] [positive] Synthetic: thank you.'),
              ('demo-b-neutral','[store:B] [neutral] Synthetic: inquiry.'),
              ('demo-unknown','[neutral] Synthetic: store unspecified.'),
              ('demo-failed','[fail] Synthetic failure injection.')]
    runs=[service.analyze(EmailInput(email_id=key,subject='Synthetic Offline Fake / Demo',body=body)) for key,body in fixtures]
    print(json.dumps(dict(backend=service.config.backend,config=service.config.model_dump(),
        runs=[dict(run_id=r.run_id,email_id=r.email.email_id,status=r.status) for r in runs],
        statistics=service.aggregate(service.config.cohort_id)),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
