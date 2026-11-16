"""One-off offline recovery of a RECEIVED but malformed Judge reply.

Never performs a provider request or unlocks a missing/UNKNOWN response.
"""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b5r2_live import LOCAL,Budget,now
from src.evaluation.p5b5 import read,write_new,hashfile

def main():
    ev=LOCAL/'judge/control-wrong_action_receipt'
    frozen=read(ev/'frozen-input.json');response=read(ev/'langchain-response.json');http=read(ev/'provider-http.json')
    assert http['status']==200 and http['body_sha256']==hashfile(ev/'provider-response.txt')
    raw_http=json.loads((ev/'provider-response.txt').read_text(encoding='utf-8'))
    assert raw_http['choices'][0]['message']['content']==response['content']
    run_id=frozen['run_id'];b=Budget(LOCAL/'budget.sqlite3')
    with b.connection() as c:
        assert c.execute('SELECT run_id FROM lease').fetchone()==(run_id,)
        cost=c.execute('SELECT cost FROM settlements WHERE run_id=?',(run_id,)).fetchone()[0]
        bound=c.execute('SELECT reserved_cny FROM reservations WHERE run_id=?',(run_id,)).fetchone()[0]
        assert cost>0 and cost<=bound
    usage=response['usage_metadata'];meta=dict(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens'],total_tokens=usage['total_tokens'],usage=usage,token_usage=response['response_metadata']['token_usage'],resolved_model=response['response_metadata']['model_name'])
    write_new(ev/'judgment.json',dict(run_id=run_id,raw=response['content'],parsed=None,parse_error='review_findings item is string, expected structured finding',metadata=meta,cost_upper=cost,reserved=bound,elapsed_ms=None,identity='LLM_JUDGE_PROVISIONAL_NOT_HUMAN',reconciled_offline=True))
    receipt=dict(at=now(),run_id=run_id,provider_received=True,provider_body_sha256=http['body_sha256'],billing_settled_upper=cost,request_repeated=False,original_halt='UNKNOWN_JUDGE_OR_STORAGE',actual_failure='known received response malformed in scoring parser',proof='HTTP200 body+LangChain content exact match, existing settlement and exclusive lease')
    write_new(LOCAL/'known-response-reconciliation.json',receipt)
    with b.connection() as c:
        c.execute('UPDATE reservations SET completed=1 WHERE run_id=?',(run_id,))
        c.execute('DELETE FROM lease WHERE run_id=?',(run_id,))
        assert c.execute('SELECT halted FROM policy').fetchone()[0]=='UNKNOWN_JUDGE_OR_STORAGE'
        c.execute('UPDATE policy SET halted=NULL')
    print(json.dumps(receipt))
if __name__=='__main__':main()
