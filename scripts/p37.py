"""P3.7 is offline only: no prepare/live/reset/paid mode exists."""
import argparse
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def guard():
    os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',
                      LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
    def blocked(*a,**k):raise RuntimeError('P3.7 has zero model/network budget')
    socket.socket.connect=socket.socket.connect_ex=socket.create_connection=blocked
    # Python audit also denies SQLite writes to research databases (C-level I/O
    # does not trigger open events), and protects all preexisting phase assets.
    protected=[ROOT/p for p in ('data','outputs','.local/p36','.local/p35','.local/p3','.local/p2-pilot-v1')]
    def deny_path(raw):
        if isinstance(raw,(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(raw)).resolve()
            if any(p.is_relative_to(x.resolve()) for x in protected):raise PermissionError('Historical research asset is read-only')
    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            if (mode and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):deny_path(path)
        elif event in ('os.remove','os.rmdir','os.rename','os.replace'):
            for p in args[:2]:deny_path(p)
        elif event=='os.mkdir':deny_path(args[0])
        elif event=='sqlite3.connect':
            from urllib.parse import urlsplit,parse_qs
            db=str(args[0])
            if db.startswith('file:') and parse_qs(urlsplit(db).query).get('mode')==['ro']:return
            raise PermissionError('P3.7 allows SQLite mode=ro only')
    sys.addaudithook(audit)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['replay'])
    parser.add_argument('--source',type=Path,default=ROOT/'.local/p36');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();guard()
    from src.evaluation.p37_replay import export_replay
    import json
    print(json.dumps(export_replay(args.source,args.out)))


if __name__=='__main__':main()
