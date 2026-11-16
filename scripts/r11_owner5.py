"""Append-only Owner calibration evidence. Every operation is provider-free."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAME = 'r11-owner5-20261110-v1'
LOCAL = ROOT / '.local' / NAME
DOCS = ROOT / 'docs' / NAME
PRIOR = ROOT / '.local/r11-followthrough-h1043z-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))


def save(path, value):
    path = Path(path)
    if path.exists():
        assert read(path) == value, f'Immutable evidence differs: {path}'
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def files(directory):
    for base, dirs, names in os.walk(directory, followlinks=False):
        dirs[:] = [name for name in dirs if name not in ('__pycache__', 'node_modules', '.git', '.venv')
                   and not (Path(base) / name).is_symlink() and not (Path(base) / name).is_junction()]
        for name in names:
            path = Path(base) / name
            if path.suffix != '.pyc' and not path.is_symlink():
                yield path


def prepare():
    LOCAL.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    if (LOCAL / 'baseline.json').exists():
        print('Baseline already preserved')
        return
    baseline = read(PRIOR / 'baseline.json')
    protected = dict(baseline['protected'])
    for folder in (PRIOR, ROOT / 'docs/r11-followthrough-h1043z-v1'):
        for path in files(folder):
            protected[path.relative_to(ROOT).as_posix()] = sha(path)
    sources = {}
    for folder in ('src', 'scripts', 'tests', 'web-client/src'):
        for path in files(ROOT / folder):
            relative = path.relative_to(ROOT)
            sources[relative.as_posix()] = sha(path)
            target = LOCAL / 'baseline-source' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    shutil.copy2(ROOT / 'HANDOFF.md', LOCAL / 'HANDOFF.original.md')
    save(LOCAL / 'baseline.json', dict(
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        protected=protected, sources=sources, environment_sha256=sha(ROOT / '.env'),
        ledger_sha256=sha(PRIOR / 'live/budget.sqlite3'),
        call_map_sha256=sha(PRIOR / 'call-map.sqlite3'),
    ))
    print('Protected', len(protected), 'files; preserved', len(sources), 'source files')


def verify():
    original = read(LOCAL / 'baseline.json')
    changed = [name for name, expected in original['protected'].items()
               if not (ROOT / name).is_file() or sha(ROOT / name) != expected]
    print(json.dumps(dict(checked=len(original['protected']), changed=changed), ensure_ascii=False))
    assert not changed


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'verify'))
    args = parser.parse_args()
    {'prepare': prepare, 'verify': verify}[args.command]()
