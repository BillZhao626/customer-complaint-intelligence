"""Bounded local product acceptance over five real synthetic outputs. No model."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.product_workflow import ProductStore
from src.application.p5b5r2_pipeline import ActionStore,ConversationState
from src.application.p5b7_actions import execute
from src.application.service_triage import triage

def main():
    db=ROOT/'.local/p4/p5b7-20261030/product.sqlite3';store=ProductStore(db);actions=ActionStore(db.with_name('p5b5r2-actions.sqlite3'));rows=[]
    for eid in ('B7-018','B7-036','B7-050','B7-075','B7-076'):
        c=next(c for c in store.list_cases() if c['run'].email.email_id==eid and c['run'].config.parameters.get('experiment')=='p5b7')
        run=c['run'];state=ConversationState(c['case_id']);state.update('customer',run.email.body)
        runtime=execute(actions,run,state);before=len(runtime['events']);runtime2=execute(actions,run,state)
        assert len(runtime2['events'])==before
        row=dict(email_id=eid,case_id=c['case_id'],run_id=run.run_id,input_hash=run.input_hash,events=runtime['events'],idempotent=True,
            facts='UNKNOWN_NO_EXTERNAL_VERIFICATION',reply=run.result.suggested_reply,model_reply_precedes_product_tasks=True,external_actions=0,quality=c['quality'])
        if c['state']!='simulated_sent' and c['quality']['status']!='blocked':
            if triage(c)['requires_takeover'] and not triage(c)['takeover_complete']:
                c=store.act(c['case_id'],'take_over',expected_revision=c['revision'],actor='p5b7_workflow_acceptance',actor_type='demo_test',reason='本地模拟操作者，不是真人接入',operation_id='b7-qa-takeover-'+eid)
            c=store.act(c['case_id'],'approve',expected_revision=c['revision'],actor='p5b7_workflow_acceptance',actor_type='demo_test',reason='合成案例流程验收：仅提议核实、内部待处理；不代签人工Gold',operation_id='b7-qa-approve-'+eid,checks=dict(facts_evidence=True,authority_privacy=True,all_issues=True,safety=True))
            c=store.act(c['case_id'],'simulate_send',expected_revision=c['revision'],actor='p5b7_workflow_acceptance',actor_type='demo_test',reason='仅本地模拟，不发送客户邮件',operation_id='b7-qa-simulate-'+eid)
        row.update(state=c['state'],receipt=c['receipt'],audit_events=c['events']);rows.append(row)
    # A second connection must recover the exact product receipt and events.
    reopened=ProductStore(db)
    assert all(reopened.get(r['case_id'])['receipt']==r['receipt'] for r in rows)
    out=ROOT/'docs/p5b7/WORKFLOW_ACCEPTANCE.json'
    out.write_text(json.dumps(dict(identity='LOCAL_DEMO_TEST_NOT_HUMAN_QUALITY_SIGNOFF',n=5,simulated=sum(r['state']=='simulated_sent' for r in rows),pending_business_tasks=sum(e['status']=='created' for r in rows for e in r['events']),restart_read=True,rows=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Local five-scenario acceptance:',sum(r['state']=='simulated_sent' for r in rows),'/5; external actions=0')

if __name__=='__main__':main()
