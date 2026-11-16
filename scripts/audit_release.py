"""Inspect the exact candidate Git tree and its ancestry without printing secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SECRET = re.compile(rb'(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')
MACHINE = re.compile(rb'(?:[CD]:[/\\](?:Users|Projects)[/\\])')
DENIED = ('.local/', 'data/', 'outputs/', 'output/', 'docs/dissertation/', 'configs/dissertation/', '.venv/', 'node_modules/')


def git(*args):
    return subprocess.check_output(['git', *args])


def read_objects(objects):
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], input=b'\n'.join(objects)+b'\n')
    offset, result = 0, {}
    for oid in objects:
        eol = raw.index(b'\n', offset)
        header = raw[offset:eol].split()
        size = int(header[2])
        result[oid] = raw[eol+1:eol+1+size]
        offset = eol+size+2
    return result


def audit(ref='HEAD', private_env=None, history=False):
    secrets = []
    if private_env:
        for line in Path(private_env).read_text('utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            value = value.strip().strip('"\'')
            if sep and any(t in key.upper() for t in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')) and len(value) >= 12:
                secrets.append(value.encode())
    resolved = git('write-tree').strip().decode() if ref == 'INDEX' else git('rev-parse', '--verify', ref).strip().decode()
    entries = []
    for row in git('ls-tree', '-r', '-z', resolved).split(b'\0'):
        if row:
            metadata, name = row.split(b'\t', 1)
            entries.append((name.decode('utf-8'), metadata.split()[2]))
    bodies = read_objects(list(dict.fromkeys(oid for _, oid in entries)))
    files, findings = [], []
    for name, oid in entries:
        body = bodies[oid]
        p = Path(name)
        if (name.startswith(DENIED) or any(x in p.parts for x in ('node_modules', '.venv', '__pycache__'))
                or p.suffix.lower() in ('.db', '.sqlite', '.sqlite3', '.pdf', '.docx', '.zip', '.pem', '.pfx')
                or (p.name.startswith('.env') and name != '.env.example')):
            findings.append(dict(path=name, category='private_or_generated_asset'))
        if SECRET.search(body) or any(s in body for s in secrets):
            findings.append(dict(path=name, category='credential_candidate_value_suppressed'))
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg') and MACHINE.search(body):
            findings.append(dict(path=name, category='machine_specific_path'))
        if p.suffix.lower() in ('.png', '.jpg', '.jpeg') and not name.startswith('docs/media/'):
            findings.append(dict(path=name, category='unreviewed_media_location'))
        files.append(dict(path=name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
    history_report = None
    if history:
        if ref == 'INDEX':
            raise ValueError('Commit before auditing its exact ancestry')
        objects = [x.split(b' ', 1)[0] for x in git('rev-list', '--objects', resolved).splitlines()]
        history_bodies = read_objects(objects)
        historical = []
        for oid in objects:
            body = history_bodies[oid]
            if SECRET.search(body) or any(s in body for s in secrets):
                historical.append(dict(object=oid.decode(), category='credential_candidate_value_suppressed'))
        findings.extend(historical)
        history_report = dict(commits=len(git('rev-list', resolved).splitlines()), objects=len(objects), credential_candidates=historical)
    return dict(ref=ref, resolved_object=resolved, status='PASS' if not findings else 'FAIL', files=files,
                findings=findings, history=history_report,
                scope='Exact current tree plus selected commit ancestry when requested. Pattern and optional known-secret matching; human review is required for privacy, provenance and redistribution rights.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ref', default='HEAD')
    p.add_argument('--private-env')
    p.add_argument('--history', action='store_true')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    result = audit(args.ref, args.private_env, args.history)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], files=len(result['files']), findings=result['findings'], history=result['history'])))
    raise SystemExit(result['status'] != 'PASS')
