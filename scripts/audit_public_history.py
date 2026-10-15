"""Read all reachable Git objects and every commit tree; suppress credential values."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from audit_git_payload import DENIED_PREFIXES, DENIED_SUFFIXES, SECRET_PATTERN


def git(*args):return subprocess.check_output(['git',*args])


def scan():
    secrets=[]
    env=Path('.env')
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' not in line:continue
            key,value=line.split('=',1);value=value.strip().strip('\"\'')
            if any(k in key.upper() for k in ('KEY','TOKEN','PASSWORD','SECRET')) and len(value)>=8:secrets.append(value.encode())
    refs=git('for-each-ref','--format=%(refname)','refs/heads','refs/tags','refs/remotes').decode().splitlines()
    local_only=git('for-each-ref','--format=%(refname)','refs/codex').decode().splitlines()
    commits=git('rev-list',*refs).decode().splitlines()
    objects={line.split(' ',1)[0]:line.partition(' ')[2] for line in git('rev-list','--objects',*refs).decode().splitlines()}
    raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(objects)+'\n').encode())
    offset=0;issues=[];candidates=[];identities=set();counts={};inventory=[]
    for oid,path in objects.items():
        eol=raw.index(b'\n',offset);header=raw[offset:eol].decode().split();size=int(header[2]);kind=header[1]
        body=raw[eol+1:eol+1+size];offset=eol+size+2
        counts[kind]=counts.get(kind,0)+1
        if SECRET_PATTERN.search(body) or any(s in body for s in secrets):issues.append(dict(object=oid,path=path,reason='credential candidate; value suppressed'))
        if kind in ('commit','tag'):
            for email in re.findall(rb'<([^<>\s]+@[^<>\s]+)>',body):identities.add(email.decode())
        if kind=='blob':
            inventory.append(dict(object=oid,path=path,sha256=hashlib.sha256(body).hexdigest(),bytes=size))
            for name,pattern in [('absolute_path',rb'(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)[^\s\"\x27`<>]+'),
                ('email_address',rb'\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
                ('phone_candidate',rb'(?<![0-9A-Fa-f])1[3-9][0-9]{9}(?![0-9A-Fa-f])'),
                ('ownership_marker',rb'(?i)copyright|licensed under|all rights reserved|copied from')]:
                if re.search(pattern,body):candidates.append(dict(object=oid,path=path,category=name))
    trees={}
    for commit in commits:
        names=git('ls-tree','-r','--name-only',commit).decode().splitlines();trees[commit]=names
        for name in names:
            if name.startswith(DENIED_PREFIXES) or name.lower().endswith(DENIED_SUFFIXES) or (Path(name).name.startswith('.env') and name!='.env.example'):
                issues.append(dict(commit=commit,path=name,reason='excluded asset class'))
    return dict(status='PASS' if not issues else 'FAIL',commits=commits,object_counts=counts,tree_files=trees,
        blobs=inventory,issues=issues,review_candidates=candidates,
        git_identity_domains=sorted({e.rsplit('@',1)[1] for e in identities}),git_identity_count=len(identities),
        identity_values_suppressed=True,scope='All heads/tags/remote refs, every tree, deleted historical blobs, commit/tag metadata',
        scanned_refs=refs,excluded_local_app_refs=local_only,
        limitation='Pattern and exact local-secret scan plus manual candidate review; cannot certify unknown secrets or legal ownership.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    result=scan()
    with Path(args.out).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ('status','object_counts','issues','git_identity_domains')}))
