"""Read-only R3 fixed-run report. No provider initialization or paid path."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--assistant-review');args=parser.parse_args()
    from src.infrastructure.p39_continuity_budget import ContinuityBudget
    from src.evaluation.p39_continuity_report import export
    budget=ContinuityBudget(ROOT/'.local/p39/v2/shared-envelope.sqlite3',None)
    refs=json.loads((ROOT/'.local/p38/prepared-final-v4/old-reference-v1.1.json').read_text(encoding='utf8'))
    report=export(budget.runtime(),budget,Path(args.out),refs,args.assistant_review)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
