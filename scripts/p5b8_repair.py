"""Bounded DEV repair. New identities, never replaces the frozen primary trial."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b8_live import raw_call,LOCAL,load_email
from src.application.p5b8_pipeline import analysis_messages,validate_analysis,reply_messages,execute,guided_actions,check_reply
from src.application.live_execution import strict_json
from src.evaluation.p5b_pilot import read,write_new
GUIDANCE='''P5-B8 R2 general correction: Always return every required JSON key including uncertainty (an array even if empty).
A neutral expression does not cancel a negative experience or a request for correction. A fault needing repair can have complaint intent yes while expressed neutral.
Distinguish current requests from prior completed customer actions: already emailed photos is not a new request to email photos.
Do not create a separate unresolved issue for a completed instruction unless current receipt checking is actually requested.
Do not imply an asynchronous callback/update will occur unless the supplied receipt explicitly authorizes scheduled follow-up.
Internal pending task creation is real, but does not prove colleagues are presently reviewing it or will contact the customer.
Use a concrete review/check path and actual status without guaranteeing future work. Do not add repeated disclaimers.
Complete the JSON object and check all delimiters before returning.'''
def actions_v2(a):
    # Positive inquiry classification must not divert an actual product fault to sales knowledge.
    actions=guided_actions(a)
    issues={i['issue_id']:i for i in a['issues']}
    for action in actions:
        linked=[issues[k] for k in action['issue_ids']]
        if action['kind']=='human_input_request' and any(i['business_process']=='product issue' and i['experience_polarity'] in ('negative','mixed') for i in linked):action['kind']='aftersales_request'
    return actions
def main():
    plan=LOCAL/'repair-plan.json'
    if not plan.exists():
        failures=[p.stem for p in sorted((LOCAL/'analysis').glob('B7-*.json')) if read(p)['error']]
        replyfail=[p.stem for p in sorted((LOCAL/'replies/A_GUIDED').glob('B7-*.json')) if read(p)['error']]
        # Up to three structural DEV failures plus two demonstrated future-promise families.
        ids=list(dict.fromkeys(failures[:3]+replyfail[:1]+['B7-035','B7-074']))
        write_new(plan,dict(version='p5b8-R2-dev-1',ids=ids,analysis_repair_ids=failures[:3],max_calls=15,scope='Exposed DEV only, no changes to primary A/B or independent transfer cases',guidance=GUIDANCE))
    schedule=read(plan);rows=[]
    for eid in schedule['ids']:
        e=load_email(eid);old=read(LOCAL/'analysis'/(eid+'.json'));a=old['data'];ar=None;error=None
        dest=LOCAL/'repairs'/(eid+'.json')
        if dest.exists():rows.append(read(dest));continue
        if eid in schedule['analysis_repair_ids']:
            ar=raw_call('R2-'+eid,analysis_messages(e)+[('system',GUIDANCE)],'ANALYSIS_R2',e.model_dump())
            try:a=validate_analysis(ar['raw'],e)
            except (ValueError,TypeError,KeyError) as ex:a=None;error=str(ex)
        if a:runtime=execute(e,actions_v2(a),LOCAL/'state/R2'/eid/'actions.sqlite3')
        else:runtime=read(LOCAL/'replies/A_GUIDED'/(eid+'.json'))['runtime']
        reply_call=raw_call('R2-'+eid,reply_messages(e,runtime,a or {'status':'ANALYSIS_UNAVAILABLE'})+[('system',GUIDANCE)],'GUIDED_R2',dict(email=e.model_dump(),analysis=a,runtime=runtime))
        try:d=strict_json(reply_call['raw']);assert set(d)=={'reply'} and d['reply'].strip();text=d['reply'];reply_error=None
        except (ValueError,TypeError,KeyError,AssertionError) as ex:text='';reply_error=str(ex)
        row=dict(case_id=eid,version='p5b8-R2-dev-1',analysis=a,analysis_error=error,analysis_call=ar,reply=text,reply_error=reply_error,call=reply_call,runtime=runtime,checks=check_reply(e,text,runtime),identity='NEW_DEV_REPAIR_FIRST_RESPONSE_NOT_PRIMARY_OR_HOLDOUT')
        write_new(dest,row);rows.append(row)
    from src.evaluation.p5b5r2_judge import JUDGE_SYSTEM_V31,parse_judgment
    from scripts.p5b8_live import JUDGE_EXTRA
    for n,row in enumerate(rows):
        eid=row['case_id'];dest=LOCAL/'repair-judgments'/(eid+'.json')
        if dest.exists():continue
        e=load_email(eid);old=read(LOCAL/'replies/A_GUIDED'/(eid+'.json'));order=['ORIGINAL_GUIDED','R2_GUIDED'] if n%2==0 else ['R2_GUIDED','ORIGINAL_GUIDED'];by={'ORIGINAL_GUIDED':old,'R2_GUIDED':row}
        payload=dict(customer_context=[dict(role='customer',text=e.subject+'\n'+e.body)],current_turn=1,reference_requirements=None,reference_identity='NO_HUMAN_GOLD',answers=[dict(slot=slot,reply=by[v]['reply'],events=by[v]['runtime']['events'],expected_input_hash=e.input_hash,attachment_manifest=[]) for slot,v in zip(('A','B'),order,strict=True)])
        call=raw_call('R2-'+eid,[('system',JUDGE_SYSTEM_V31+JUDGE_EXTRA),('human',json.dumps(payload,ensure_ascii=False))],'JUDGE_R2',dict(blind_payload=payload,slot_order=order))
        try:parsed=parse_judgment(call['raw'],payload);err=None
        except (ValueError,TypeError,KeyError) as ex:parsed=None;err=str(ex)
        write_new(dest,dict(case_id=eid,order=order,parsed=parsed,error=err,call=call,payload=payload))
    report=dict(version='p5b8-R2-dev-1',n=len(rows),rows=rows,judgments=[read(p) for p in sorted((LOCAL/'repair-judgments').glob('*.json'))],primary_unchanged=True,independent_certification=False)
    p=ROOT/'docs/p5b8/REPAIR_RESULTS.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Saved R2 DEV repairs',len(rows),flush=True)
if __name__=='__main__':main()
