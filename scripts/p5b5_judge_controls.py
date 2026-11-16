"""Paid Judge controls under the same authorized ledger; no numerical human labels."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import p5b5_live as live
from src.evaluation.p5b5 import read,write_new,hashfile

def main():
    cal=read(ROOT/'.local/p5b5/evidence-v1/calibration.json');gold=read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')
    mapping=dict(natural_equivalent=8,conditional_en=9,attachments=4,refund=8,fee_guarantee=13,danger=7,privacy=11,
        unsupported_record=6,supported_record=6,negated_danger=7,negated_refund=8)
    write_new(live.LOCAL/'judge-control-manifest.json',dict(source_sha256=hashfile(Path(__file__)),
        identity='OWNER_POLICY_DERIVED_DEVELOPER_CONTROLS_NOT_NUMERIC_HUMAN_LABELS',controls=cal['controls']))
    for r in cal['controls']:
        g=gold[mapping[r['id']]]
        payload=dict(customer_context=g['input_messages'],required_points=g['required_points'],reference=g['reference_reply'],
            answers=[dict(slot='A',reply=r['reply'],events=r['events'])],instruction='Only one answer A. Evaluate A; preference UNKNOWN. Judge hard errors separately from soft omissions.')
        live.raw_judge(payload,'control-'+r['id'])

if __name__=='__main__':main()
