"""Sequential, once-only first generations; split/arm directories never overwritten."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.p5b3_runtime import generate,LOCAL,Budget
from src.application.product_workflow import ProductStore
from src.domain.contracts import EmailInput,digest
from src.application.mail_threads import assemble_context
from src.application.live_execution import strict_json
from src.evaluation.p5b_pilot import read,write_new,now

def main():
    stage=sys.argv[1]
    if stage not in ('dev','dev-confirm','validation','test','paired-b2','regression'):raise ValueError('Unknown stage')
    if stage not in ('dev','dev-confirm'):
        freeze=read(ROOT/'docs/p5b3/candidate-freeze.json')
        from hashlib import sha256
        for p,h in freeze['source_hashes'].items():
            if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('Frozen generation source drift: '+p)
    if stage=='regression':
        cases=read(ROOT/'docs/p5b_dev_pilot/pilot_manifest_16.json')['cases']
        cases=[dict(case_id=c['calibration_id'],subject=c['turns'][0]['subject'],turns=c['turns'],scoped_facts=[]) for c in cases]
    else:cases=[c for c in read(ROOT/'docs/p5b3/dataset-manifest.json')['cases'] if c['split']==('test' if stage=='paired-b2' else 'dev' if stage=='dev-confirm' else stage)]
    if stage=='dev-confirm':cases=[c for c in cases if c['case_id'] in ('B3-DEV-01','B3-DEV-02','B3-DEV-07','B3-DEV-09','B3-DEV-10')]
    store=ProductStore(ROOT/'.local/p4/p5b3-20261029-v1/experiment-product.sqlite3')
    rows=[]
    for case in cases:
        history=[]
        for n,t in enumerate(case['turns'],1):
            email=EmailInput(email_id=f'{case["case_id"]}-T{n}',subject=t['subject'],body=t['body'] if not history else assemble_context(history,t['subject'],t['body']))
            product=generate(email,stage=stage,candidate=stage!='paired-b2',store=store,
                extra_runtime=dict(scoped_facts=case['scoped_facts']),context_hash=digest(history) if history else None)
            run=product['run'];a=run.attempts[-1] if run.attempts else None
            try:reply=strict_json(a.raw_output).get('suggested_reply','')
            except (ValueError,AttributeError):reply=''
            history.extend([dict(role='customer',at=f'turn-{n}',source='synthetic_customer',subject=t['subject'],body=t['body']),dict(role='assistant',at=f'turn-{n}',source=stage,subject='Draft, not sent',body=reply)])
            rows.append(dict(case_id=case['case_id'],turn=n,stage=stage,run_id=run.run_id,input_hash=email.input_hash,case_product_id=product['case_id'],status=run.status,parse=a.parse_status if a else 'not_run',contract=a.contract_status if a else 'not_run',reply=reply,meta=a.metadata if a else {},human_scores=None))
            print(json.dumps(dict(stage=stage,case=case['case_id'],turn=n,status=run.status,calls=Budget(LOCAL/'budget.sqlite3').summary()['reserved_attempts']),ensure_ascii=False),flush=True)
            if not a or a.metadata.get('dispatch')!='response_received' or a.metadata.get('cost_cny') is None:
                Budget(LOCAL/'budget.sqlite3').halt('UNKNOWN_EXECUTION_OR_USAGE');write_new(LOCAL/stage/'results.json',rows);return
    write_new(LOCAL/stage/'results.json',rows)
    print(json.dumps(Budget(LOCAL/'budget.sqlite3').summary()))

if __name__=='__main__':main()
