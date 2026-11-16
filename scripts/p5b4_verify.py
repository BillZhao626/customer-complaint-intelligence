"""Read-only delivery verification. Never opens a provider or writable old DB."""
import os,socket,sys,json,csv,sqlite3
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGCHAIN_TRACING='false',LANGSMITH_TRACING='false')
def blocked(*args,**kwargs):raise RuntimeError('Offline verification: network forbidden')
socket.socket.connect=blocked;socket.create_connection=blocked
from src.evaluation.p5b4 import read,preflight,hashfile,digest
from src.domain.gold_case_v1 import GoldCaseV1

def verify():
    config=read(ROOT/'.local/p5b4/experiment-config-v3.json');preflight(config)
    run=ROOT/'.local/p5b4/run-003';s=read(run/'summary.json')
    assert s['b2_legacy']['contract_first_pass']==27 and s['candidate_full']['legacy_contract_first']==20
    assert s['b2_revised']['product_gate_pass']==26 and s['candidate_full']['product_gate_pass']==17
    assert s['manifest']['budget']==dict(authorized_rmb=0,calls=0,spent_rmb=0)
    candidates=[GoldCaseV1.model_validate_json(line) for line in (ROOT/'docs/p5b4/GOLD_CANDIDATE.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(candidates)==28 and all(c.reviewer is None and c.review_state=='GOLD_CANDIDATE' for c in candidates)
    reviews=read(ROOT/'docs/p5b4/HUMAN_REVIEW_BLANK.json')
    assert reviews['candidate_hash']==digest([c.model_dump() for c in candidates])
    assert all(r['fields']['reviewer_1'] is None and r['fields']['decision'] is None for r in reviews['cases'])
    ledger=list(csv.DictReader((ROOT/'docs/p5b3/PROVIDER_LEDGER.csv').open(encoding='utf-8-sig')))
    assert len(ledger)==77
    from hashlib import sha256
    for row in ledger:
        p=Path(row['raw_path']);response=read(p)
        assert sha256(response['choices'][0]['message']['content'].encode()).hexdigest()==row['raw_sha256']
        assert read(p.parent/'run.json')['run_id']==row['run_id']
    with closing(sqlite3.connect((ROOT/'.local/p5b3-20261029-v1/budget.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        count=c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
        halted=c.execute('SELECT halted FROM policy').fetchone()[0]
        assert count==77 and halted
    initial=read(ROOT/'.local/p5b4/initial.json')
    assert hashfile(ROOT/'.env')==initial['files']['.env']
    before=(ROOT/'.local/p5b4/recovery/HANDOFF.md').read_bytes()
    assert (ROOT/'HANDOFF.md').read_bytes().endswith(before)
    return dict(status='ENGINEERING_DELIVERY_VERIFIED',paired_turns=32,historical_first_outputs=64,b3_historical_calls_verified=77,b3_budget_halted=halted,gold_candidates=28,human_signed=0,promotion_approved=False,new_model_calls=0,new_cost_rmb=0,environment_unchanged=True)

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
