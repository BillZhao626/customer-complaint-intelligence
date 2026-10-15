"""Offline reviewer comparison and human-approved freeze. No autofill of labels."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.e2e_schema import validate_dataset
from src.evaluation.gold import compare,freeze,verify_freeze

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['compare','freeze','verify'])
    parser.add_argument('--dataset');parser.add_argument('--reviewer-a');parser.add_argument('--reviewer-b')
    parser.add_argument('--adjudication');parser.add_argument('--output');parser.add_argument('--manifest')
    args=parser.parse_args()
    if args.command=='verify':
        samples=verify_freeze(read(args.manifest));print('Validated frozen samples:',len(samples));return
    samples=validate_dataset(read(args.dataset));a=read(args.reviewer_a);b=read(args.reviewer_b)
    if args.command=='freeze':freeze(samples,a,b,read(args.adjudication),args.output)
    else:
        report=compare(samples,a,b)
        with Path(args.output).open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
