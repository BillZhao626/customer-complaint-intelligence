"""Small extension over the saved B8 cases; no live transport or open budget."""
import json,time
from uuid import uuid4
from pathlib import Path
from src.domain.contracts import digest
from src.application.p5b8r1_contracts import parse_outcome
VERSION='p5b8r1-explicit-emotion-1'
ARMS=('ISSUES_NO_SENTIMENT','ISSUES_WITH_SENTIMENT')
MODEL=dict(model_id='deepseek-flash',model_snapshot='unavailable',temperature=0,thinking='disabled',response_format='json_object',max_tokens=4000,sdk_max_retries=0,max_attempts=1,endpoint='https://api.deepseek.com/chat/completions',deadline_seconds=90)

def write_first(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2)

def pair_invariant(messages):
    a,b=(messages[v] for v in ARMS)
    if a[0]!=b[0]:raise ValueError('Different system prompts')
    x,y=json.loads(a[1][1]),json.loads(b[1][1]);emo=y.pop('explicit_emotion',None)
    if x!=y or not emo:raise ValueError('Treatment differs beyond explicit emotion layer')
    for issue in x['structured_issues']['issues']:
        if {'sentiment','experience_polarity'} & issue.keys():raise ValueError('Emotion field leak')
    if {'expressed_sentiment','expressed_evidence','experience_polarity','uncertainty'} & x['structured_issues'].keys():raise ValueError('Global emotion/free-form note leak')
    return dict(equal_common=True,common_hash=digest(x),emotion_hash=digest(emo),facts_hash=digest(x['verified_facts']),receipts_hash=digest(x['action_receipts']),customer_hash=digest(x['customer']))

def run_pair(prepared,invoke,outdir,*,mode='OFFLINE_FIXTURE'):
    # A future explicit user authorization must introduce its own budget adapter.
    # Environment variables or the old closed ledger cannot authorize this entry.
    if mode!='OFFLINE_FIXTURE':raise PermissionError('AUTHORIZATION_BLOCKED: P5-B8-R1 has no new paid authorization; old ledger remains closed')
    pair_invariant(prepared['messages']);outdir=Path(outdir);results={}
    for arm in prepared['order']:
        rid='OFFLINE_FIXTURE-'+str(uuid4());folder=outdir/arm
        write_first(folder/'frozen-input.json',dict(run_id=rid,case_id=prepared['case_id'],mode=mode,messages=prepared['messages'][arm],model=MODEL))
        start=time.perf_counter()
        try:
            raw,metadata=invoke(prepared['messages'][arm],dict(MODEL))
        except BaseException as e:
            write_first(folder/'error.json',dict(run_id=rid,status='UNKNOWN_DO_NOT_RETRY',type=type(e).__name__,mode=mode));raise
        response=dict(run_id=rid,raw=raw,metadata=metadata,elapsed_ms=(time.perf_counter()-start)*1000,cost_cny=0,paid_requests=0,mode=mode)
        write_first(folder/'response.json',response) # Durable first response BEFORE parse.
        outcome=parse_outcome(raw,metadata=metadata);write_first(folder/'parse.json',outcome)
        results[arm]=dict(response=response,parse=outcome)
    return results
