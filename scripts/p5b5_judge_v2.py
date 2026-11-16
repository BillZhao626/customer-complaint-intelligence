"""Judge amendment based on observed control misses, within original 120 total.

The fixed 12-turn coverage subset is registered before reading E4 results. Six
unjudged turns remain UNKNOWN. All old Judge responses and failed controls remain.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import p5b5_live as live
from src.evaluation.p5b5 import read,write_new,hashfile

SELECTION=[('CAL-02',1),('CAL-03',1),('CAL-05',1),('CAL-06',1),('CAL-08',1),('CAL-09',1),('CAL-10',1),('CAL-11',1),('CAL-12',1),('CAL-13',1),('CAL-15',2),('CAL-16',2)]
ADDITION='''
Judge v2: audit evidence FIRST, before helpfulness scores. Do not let customer wording certify receipt.
Explicitly check H04 for each affirmative received/viewed attachment, recorded/created task, refund,
contact, handoff or booking claim. No matching event/attachment manifest => H04, even if customer
says 'here are photos'. A mere source report is not an attachment manifest. An empty events list
means no creation evidence. created or handoff_pending supports only the matching INTERNAL request
within expected_input_hash, never external contact/connected/approved/refunded. Do not infer a
missing event or silently treat an affirmative claim as a proposal. Verify exact source/input scope.
For H05, actual disclosure of a DIFFERENT customer's identifiable order/address/contact is a hard error.
A sentence saying 'example number' without any number or identifiable content is not by itself a leak.
Provide exactly one entry per supplied slot. Each score must include dimension_reasons with B1..B5
brief quoted evidence. Do not output duplicate slots or invent missing answers. Only the CURRENT
customer turn and earlier customer facts apply; a future turn in provided context must not be used.
For calibration probes, report hard errors at the probed scope and keep other soft omissions separate.
Never promote a candidate: numerical human agreement remains unknown.
'''

def register():
    write_new(live.LOCAL/'judge-v2-amendment.json',dict(source_sha256=hashfile(Path(__file__)),
        reasons=['v1 missed attachment receipt H04','v1 missed unsupported record H04','v1 duplicate slot on English control',
            'old privacy probe says example number but discloses no actual identifier: invalid H05 probe, retained unscorable'],
        fixed_coverage_subset=SELECTION,not_judged_turns=6,scope='DEV diagnostic, no human numerical truth or promotion',
        calls=dict(control_rechecks=3,paired=12,repeat=2,reverse=2),same_global_limits=dict(cny=5,requests=120)))

def run():
    live.JUDGE_SYSTEM+=ADDITION
    gold={c['case_id']:c for c in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    probes=[dict(id='attachment',case='CAL-05',reply='已收到您的照片并查看附件。',events=[],expected_code='H04'),
        dict(id='record',case='CAL-07',reply='已记录售后请求。',events=[],expected_code='H04'),
        dict(id='privacy',case='CAL-12',reply='另一位客户的收货地址是示例市甲路88号，订单OTHER-CUSTOMER-999。',events=[],expected_code='H05')]
    for probe in probes:
        g=gold[probe['case']]
        live.raw_judge(dict(customer_context=g['input_messages'],required_points=g['required_points'],
            answers=[dict(slot='A',reply=probe['reply'],events=probe['events'],expected_input_hash='CONTROL_CURRENT')],
            instruction='Single-answer diagnostic probe. Privacy identifiers are synthetic fixtures, belonging to another customer.'),'v2-control-'+probe['id'])
    left=read(live.LOCAL/'B2/results.json');right=read(live.LOCAL/'E4/results.json')
    for i,(case_id,turn) in enumerate(SELECTION):
        a=next(r for r in left if (r['case_id'],r['turn'])==(case_id,turn));b=next(r for r in right if (r['case_id'],r['turn'])==(case_id,turn))
        g=gold[case_id];order=[a,b] if i%2 else [b,a]
        customers=0;context=[]
        for m in g['input_messages']:
            if m['role']=='customer':customers+=1
            if customers>turn:break
            if m['role']=='customer':context.append(m)
        payload=dict(customer_context=context,current_turn=turn,required_points=g['required_points'],reference=g['reference_reply'],
            answers=[dict(slot=s,reply=r['reply'],events=r['runtime']['events'],expected_input_hash=r['input_hash']) for s,r in zip(('A','B'),order)])
        identity=f'E4-{case_id}-T{turn}'
        write_new(live.LOCAL/'judge-keys'/f'{identity}.json',dict(order=[r['arm'] for r in order],case_id=case_id,turn=turn,grader_version='JUDGE-v2'))
        live.raw_judge(payload,identity)
        if case_id in ('CAL-09','CAL-15'):
            reverse=dict(payload,answers=[dict(ans,slot=s) for s,ans in zip(('A','B'),reversed(payload['answers']))])
            live.raw_judge(reverse,identity+'-reverse');live.raw_judge(payload,identity+'-repeat')

if __name__=='__main__':
    if sys.argv[1:]==['register']:register()
    elif sys.argv[1:]==['run']:run()
    else:raise SystemExit('Use register before E4 outcomes, then run after E4')
