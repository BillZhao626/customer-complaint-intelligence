"""Audit exact staged or committed blobs, never print secret values.

Usage: python scripts/audit_git_payload.py --ref INDEX --output LOCAL.json
Outputs paths/hashes only. Local dotenv is inspected for accidental inclusion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

DENIED_PREFIXES = ('data/', 'outputs/', '.local/', 'docs/dissertation/', 'configs/dissertation/',
                   'docs/p1/evidence/', 'docs/p2/evidence/', 'docs/audit/evidence/', 'docs/p25/local-evidence/')
DENIED_SUFFIXES = ('.sqlite', '.sqlite3', '.db', '.docx', '.pdf', '.png', '.jpg', '.zip')
SECRET_PATTERN = re.compile(rb'(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')

def git(*args):
    return subprocess.check_output(['git', *args])

def audit(ref='INDEX', root=Path('.')):
    names = git('ls-files', '-z') if ref == 'INDEX' else git('ls-tree', '-r', '--name-only', '-z', ref)
    secrets = []
    env = root / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line: continue
            key, value = line.split('=', 1)
            value = value.strip().strip('"\'')
            if any(word in key.upper() for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')) and len(value) >= 8:
                secrets.append(value.encode())
    files, issues = [], []
    for raw in names.split(b'\0'):
        if not raw: continue
        name = raw.decode('utf-8')
        blob = git('show', ':' + name if ref == 'INDEX' else ref + ':' + name)
        forbidden = (name.startswith(DENIED_PREFIXES) or name.lower().endswith(DENIED_SUFFIXES)
                     or (Path(name).name.startswith('.env') and name != '.env.example'))
        if forbidden: issues.append({'path': name, 'reason': 'excluded asset class'})
        if SECRET_PATTERN.search(blob) or any(value in blob for value in secrets):
            issues.append({'path': name, 'reason': 'possible credential; value suppressed'})
        files.append({'path': name, 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
                      'class': 'engineering_source' if name.endswith('.py') else 'synthetic_fixture' if name.startswith('tests/fixtures/') else 'engineering_configuration_or_documentation'})
    return {'ref': ref, 'file_count': len(files), 'files': files, 'issues': issues,
            'status': 'PASS' if not issues else 'FAIL',
            'limitations': 'Pattern and known-local-secret scan plus reviewed allowlist; not a universal secret or ownership proof.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ref', default='INDEX')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.ref)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'status': report['status'], 'file_count': report['file_count'], 'issues': report['issues']}))
    raise SystemExit(bool(report['issues']))
