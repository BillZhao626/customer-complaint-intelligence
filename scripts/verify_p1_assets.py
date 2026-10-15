"""Read hashes and produce a P1 change ledger. Never reads secret contents into logs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/p1/evidence'
AUTHORIZED_OLD_FILES={
    '.gitignore','app.py','HANDOFF.md',
    'docs/audit/2026-10-14-legacy-audit.md','docs/architecture/2026-10-14-architecture-options.md','docs/plans/PHASED_ROADMAP.md',
    'src/chains/langchain_complaint_chain.py','src/evaluation/evaluate_results.py',
    'src/evaluation/run_i4e2_reviewed_80_eval_v1.py','src/evaluation/run_i4g_full_pool_deepseek_batch_v1.py',
    'src/evaluation/run_smoke_test_v1.py',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline=json.loads((EVIDENCE/'baseline.json').read_text(encoding='utf-8'))
    audit=json.loads((ROOT/'docs/audit/evidence/2026-10-14/baseline-manifest.json').read_text(encoding='utf-8'))
    protected=baseline['protected']
    mismatches=[p for p,meta in protected.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=meta['sha256']]
    changes=[]
    for path,before in baseline['original_files'].items():
        after=digest(ROOT/path) if (ROOT/path).exists() else None
        if before!=after:
            changes.append(dict(path=path,before_sha256=before,after_sha256=after))
    allowed=AUTHORIZED_OLD_FILES
    unauthorized=[p for p,meta in audit.items() if p not in allowed and (not (ROOT/p).is_file() or digest(ROOT/p)!=meta['sha256'])]
    unauthorized+=sorted({c['path'] for c in changes}-allowed-set(unauthorized))
    new=[]
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in ('.git','.venv','__pycache__','.local') for part in path.relative_to(ROOT).parts):
            continue
        rel=path.relative_to(ROOT).as_posix()
        if rel in baseline['existing_paths'] or path.name=='.env' or rel=='docs/p1/evidence/change-ledger.json':
            continue
        new.append(dict(path=rel,sha256=digest(path)))
    result=dict(protected_count=len(protected),protected_mismatches=mismatches,other_original_asset_changes=unauthorized,
                snapshot=baseline['snapshot'],modified_old_files=changes,new_files=sorted(new,key=lambda r:r['path']),
                self_exclusion='change-ledger.json excluded from its own digest',status='PASS' if not mismatches and not unauthorized else 'FAIL')
    (EVIDENCE/'change-ledger.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','protected_count','protected_mismatches','other_original_asset_changes')},indent=2))
    if mismatches or unauthorized:
        raise SystemExit(1)


if __name__=='__main__':
    main()
