"""Offline v3 pipeline and read-only replay. No live-model mode or budget access."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['offline','replay','audit','verify-calibration'])
    parser.add_argument('--dataset',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--runs',type=Path)
    parser.add_argument('--reviews',type=Path)
    parser.add_argument('--fixture-outputs',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    from src.evaluation.calibration import verify_snapshot,exclusive_json
    if args.mode=='verify-calibration':
        p=verify_snapshot(args.snapshot,args.source);print(p['version'],len(p['records']),p['payload_hash']);return
    if not args.dataset or not args.out: parser.error('--dataset and --out required')
    out=args.out.resolve()
    if any(out.is_relative_to(ROOT/p) for p in ('data','outputs','docs','.local/p2-pilot-v1','.local/p25','.local/p3')): raise ValueError('Use a new local or temporary evidence directory')
    from src.evaluation.e2e_v3 import validate_candidates,dataset_hash,evaluate
    rows=validate_candidates(json.loads(args.dataset.read_text(encoding='utf-8-sig')))
    out.mkdir(parents=True,exist_ok=False)
    if args.mode=='audit':
        from src.evaluation.dataset_audit_v3 import audit
        exclusive_json(out/'audit.json',audit(rows));return
    from src.domain.contracts import AnalysisRun
    if args.mode=='replay':
        if not args.runs: parser.error('--runs required for replay')
        runs=[AnalysisRun.model_validate(r) for r in json.loads(args.runs.read_text(encoding='utf-8'))]
    else:
        os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false')
        import socket
        def blocked(*args,**kwargs): raise RuntimeError('Offline v3 command forbids network')
        socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
        from src.application.v3_demo import ReplayV3,placeholder
        from src.application.analysis_service import AnalysisService
        from src.infrastructure.repository import Repository
        outputs=json.loads(args.fixture_outputs.read_text(encoding='utf-8')) if args.fixture_outputs else {r.input_hash:placeholder(r.email()).model_dump() for r in rows if not r.exclusion_reason}
        analyzer=ReplayV3(outputs,rows[0].dataset_id,dataset_hash(rows))
        with tempfile.TemporaryDirectory(prefix='p35-offline-') as temp:
            service=AnalysisService(Repository(Path(temp)/'runs.sqlite3'),analyzer)
            runs=[service.analyze(r.email()) for r in rows if not r.exclusion_reason]
            for r in runs:
                if service.repository.get(r.run_id)!=r: raise AssertionError('Saved run differs from receipt')
        exclusive_json(out/'runs.json',[r.model_dump() for r in runs])
    reviews=json.loads(args.reviews.read_text(encoding='utf-8')) if args.reviews else []
    report=evaluate(rows,runs,reviews)
    exclusive_json(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('eligible','attempted','succeeded','failed','pending','excluded','reference_pending')},ensure_ascii=False))


if __name__=='__main__':main()
