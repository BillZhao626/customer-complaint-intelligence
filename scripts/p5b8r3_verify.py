"""No-fee verification of delivered identities, caps, first responses and assets."""
import json,hashlib,sqlite3,sys,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.domain.contracts import digest
from src.infrastructure.p5b8r3_execution import read
DOC=ROOT/'docs/p5b8r3';LOCAL=ROOT/'.local/p5b8r3'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    total=completed=unknown=0;token_total=0;ids=set();checks=[]
    for root in [LOCAL/f'live-v{i}' for i in (1,2,3,4)]+[LOCAL/'quality-final-v1']:
        c=sqlite3.connect(f'file:{(root/"budget.sqlite3").as_posix()}?mode=ro',uri=True)
        try:
            rows=c.execute('SELECT identity,request_hash,run_id,state,metadata FROM calls').fetchall();assert c.execute('SELECT halted FROM policy').fetchone()[0]
        finally:c.close()
        for identity,h,rid,state,meta in rows:
            assert rid not in ids;ids.add(rid);total+=1;folder=root/'calls'/digest(identity);f=read(folder/'frozen-input.json');assert f['run_id']==rid and f['request_hash']==h
            assert (folder/'wire-request.json').is_file();http=read(folder/'provider-http.json');assert sha(folder/'provider-response.txt')==http['body_sha256']
            if state=='COMPLETED':
                r=read(folder/'response.json');assert r['run_id']==rid and digest(r)==json.loads(meta)['response_hash'];assert http['status']==200
                assert read(folder/'provider-response.txt')['choices'][0]['message']['content']==r['raw']
                completed+=1;token_total+=r['metadata']['total_tokens']
            else:
                assert root.name=='live-v1' and state=='UNKNOWN' and http['status']==400
                assert not (folder/'response.json').exists();unknown+=1
        checks.append(dict(run=root.name,requests=len(rows),closed=True))
    assert total==298 and completed==297 and unknown==1
    budget=read(DOC/'COMPLETE_BUDGET.json');assert budget['actual_requests']==total and total<=310 and budget['reserved_and_settled_upper_cny']<=35
    first=read(DOC/'RESULTS.json');assert first['A']['actual_first_replies']==48 and first['B']['actual_reply_pairs']==12
    final=read(DOC/'FINAL_QUALITY_RESULTS.json');assert final['independent_generation']['generated']==12 and final['independent_generation']['valid_frozen']==12
    assert final['identity']['used_for_tuning']is False
    freeze=read(LOCAL/'quality-final-v1/FINAL_CANDIDATE_AND_JUDGE_FREEZE.json')
    assert all(sha(ROOT/p)==h for p,h in freeze['sources'].items())
    assert len(read(DOC/'A_48_FIRST_REPLY_SLOTS.json'))==48
    with (DOC/'ACCEPTANCE_FINAL_74.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    with (ROOT/'docs/p5b8r2/ACCEPTANCE.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
    assert len(rows)==74 and {r['id'] for r in rows}=={r['id'] for r in old}
    protection=read(DOC/'PROTECTION_FINAL.json');assert not protection['unexpected'] and not protection['missing']
    assert (ROOT/'HANDOFF.md').read_bytes().endswith((LOCAL/'recovery/HANDOFF.md').read_bytes())
    result=dict(status='VERIFIED_ARTIFACTS_NOT_QUALITY_CERTIFICATION',requests=total,completed_provider_responses=completed,archived_HTTP400_with_reserved_unknown=unknown,total_tokens=token_total,caps_respected=True,run_checks=checks,old_assets_checked=protection['checked'],unexpected_old_asset_changes=protection['unexpected'],gold16_unchanged=True,acceptance_rows=74,independent_body_generated_after_freeze=True,post_test_source_hashes_unchanged=True,human_numeric_n=0)
    (DOC/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
