"""Fixed local historical source discovery. SQLite is always query-only."""
import sqlite3
from pathlib import Path
from src.infrastructure.dashboard_sources import ReadOnlyRepository
from src.infrastructure.context_repository import ReadOnlyContextRepository


def sources(root):
    root = Path(root)
    paths = list((root / '.local/p310').glob('runtime-*/runs.sqlite3'))
    paths += [root / '.local/p39/v2/r3-runtime/runs.sqlite3',
              root / '.local/p39/v2/live-delivery-v1/runtime/runs.sqlite3']
    return [p for p in paths if p.exists()]


def read_run(path, run_id):
    # Inspect the exact config, never initialize a repository for an old path.
    import json
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        row = c.execute('SELECT config_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
    if not row:
        raise ValueError('Historical run not found')
    params = json.loads(row[0]).get('parameters') or {}
    reader = ReadOnlyContextRepository if params.get('urgency_validation_profile') else ReadOnlyRepository
    return reader(path).get(run_id)


def catalog(root):
    import json
    items = []
    seen = set()
    for path in sources(root):
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as c:
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA query_only=ON')
            rows = c.execute('SELECT r.run_id,r.status,r.config_json,e.email_id FROM runs r JOIN emails e USING(input_id) ORDER BY r.created_at').fetchall()
        for r in rows:
            config = json.loads(r['config_json'])
            if config['backend'] != 'deepseek_live' or r['run_id'] in seen:
                continue
            seen.add(r['run_id'])
            items.append(dict(run_id=r['run_id'], path=str(path), email_id=r['email_id'], status=r['status'],
                              prompt=config['prompt_version'], arm=(config.get('parameters') or {}).get('arm', 'unknown')))
    return items
