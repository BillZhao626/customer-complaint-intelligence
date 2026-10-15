"""Read-only asset verification, new timestamped P2 ledger; no historical writes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'HANDOFF.md','docs/plans/PHASED_ROADMAP.md','src/domain/contracts.py',
         'src/application/analysis_service.py','src/infrastructure/repository.py','src/app/offline_slice.py','tests/run_offline.py'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    baseline=json.loads((ROOT/'docs/p2/evidence/baseline-start.json').read_text(encoding='utf-8'))
    protected=json.loads((ROOT/'docs/p1/evidence/baseline.json').read_text(encoding='utf-8'))['protected']
    bad=[p for p,m in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=m['sha256']]
    changes=[]
    for path,before in baseline['original_files'].items():
        after=sha(ROOT/path) if (ROOT/path).is_file() else None
        if before!=after:changes.append(dict(path=path,before_sha256=before,after_sha256=after))
    unauthorized=[r['path'] for r in changes if r['path'] not in ALLOWED]
    new=[]
    for folder in ('src','scripts','tests','docs/p2'):
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:continue
            rel=path.relative_to(ROOT).as_posix()
            if rel not in baseline['original_files'] and not path.name.startswith('change-ledger-'):
                new.append(dict(path=rel,sha256=sha(path)))
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),status='PASS' if not bad and not unauthorized else 'FAIL',
        protected_count=len(protected),protected_mismatches=bad,unauthorized_original_changes=unauthorized,
        modified_original_files=changes,new_files=new,
        modified_env_template=dict(path='.env.example',before_sha256=None,after_sha256=sha(ROOT/'.env.example'),
            note=baseline['env_template_note']),snapshot=baseline['snapshot'],
        self_exclusion='All change-ledger-*.json excluded from recursive digest; local private run DBs are separately frozen in the pilot evidence manifest.')
    path=ROOT/'docs/p2/evidence'/('change-ledger-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','protected_count','protected_mismatches','unauthorized_original_changes')}))
    print(path)
    if bad or unauthorized:raise SystemExit(1)

if __name__=='__main__':main()
