"""Offline smoke only. Future paid dispatch requires a new authorized driver."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset.research_generation import plan,collect_responses


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--offline-smoke',action='store_true',required=True);a=p.parse_args()
    data=plan()
    responses=[dict(job_id=j['id'],messages_hash=j['messages_hash'],model='offline-fixture-no-inference',request_id=None,usage=None,
        raw=json.dumps(dict(subject='Offline generation transport fixture '+j['id'],body='This is a transport fixture for '+j['id']+'. It is not a model-generated customer email.'))) for j in data['jobs']]
    manifest=collect_responses(data,responses,a.out,identity='OFFLINE_TRANSPORT_FIXTURE')
    print(json.dumps({k:manifest[k] for k in ('identity','n_received','live_generated_count','missing_jobs')}))


if __name__=='__main__':main()
