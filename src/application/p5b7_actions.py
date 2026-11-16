"""Scoped B7 tasks from accepted native issues, using existing event storage.

Regex context is retained for historical workflows. This adapter fixes the new
batch's Chinese/English coverage gap without changing original model receipts.
"""
from uuid import uuid4
import json
from src.application.product_workflow import analysis_data,timestamp
from src.domain.contracts import digest

VERSION='p5b7-native-issue-local-tasks-1'
PROCESS={
 'product issue':('aftersales_request','aftersales'),
 'delivery/logistics issue':('logistics_followup','logistics'),
 'refund/exchange process issue':('aftersales_request','aftersales'),
 'customer service response issue':('support_followup','customer_support'),
 'store service issue':('store_service_request','store_operations'),
 'billing/invoice issue':('billing_request','billing')}

def execute(actions,run,state):
    if run.status!='succeeded':raise ValueError('Failed analysis cannot advance native issue tasks')
    data=analysis_data(run);ctx=state.extract();planned=[]
    for issue in data['issues']:
        if issue['issue_kind']=='praise' or issue['resolution'] in ('resolved','not_applicable'):continue
        kind,owner=PROCESS.get(issue['business_process'],('clarification_request','customer_support'))
        if issue['issue_kind']=='inquiry':kind,owner='human_input_request','product_support'
        a=dict(kind=kind,owner=owner,issue_ids=[issue['issue_id']],customer_goal='；'.join(issue['customer_requests']),order_identifiers=ctx['identifiers'],
            question='核实'+issue['object_name']+'：'+'；'.join(issue['customer_requests'])+'。仅内部待处理请求，事实及处理结果尚待确认。',
            priority='high' if issue['risk_level']=='severe' or issue['urgency']=='high' else 'normal',
            source_business_process=issue['business_process'],source_evidence=issue['evidence'])
        planned.append(a)
        if issue['risk_level']=='severe':planned.append(dict(a,kind='handoff_request',owner='customer_support',question='安全风险人工协调；尚未接入或执行外部动作'))
    with actions.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        for a in planned:
            op=digest(dict(version=VERSION,input_hash=run.input_hash,action=a))
            if c.execute('SELECT 1 FROM events WHERE operation_id=?',(op,)).fetchone():continue
            payload=dict(action=a,context=ctx,source_run_id=run.run_id,version=VERSION,local_only=True,external_execution=False,fact_status='UNKNOWN_UNLESS_SEPARATELY_VERIFIED')
            for status in ('requested','handoff_pending' if a['kind']=='handoff_request' else 'created'):
                c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),run.input_hash,state.conversation_id,op,a['kind'],status,json.dumps(payload,ensure_ascii=False),timestamp()))
    return dict(context=ctx,events=actions.list(run.input_hash),version=VERSION,identity='POST_ANALYSIS_LOCAL_PENDING_TASKS_NOT_ORIGINAL_MODEL_RECEIPTS')
