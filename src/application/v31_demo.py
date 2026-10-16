"""Explicit synthetic engineering fixture; no natural-language model claim."""
import json
from src.domain.contracts import EmailInput,RunConfigV31,digest
from src.domain.analysis_v31 import AnalysisV31,POLICY,PROJECTION,SCHEMA,TAXONOMY
from src.application.reply_review import VERSION as GATE

EMAIL=EmailInput(email_id='v31-three-event-fixture',subject='Synthetic fixture: three open problems',
    body='The drawer stays open at night and I might bump my knee. The old bed collection appointment was missed. One item is missing from the invoice. Please follow up on all three.')


def span(email,quote):
    start=email.body.index(quote)
    return dict(field='body',start=start,end=start+len(quote),quote=quote)


def fixture():
    specs=[('drawer','Furniture','health or safety issue','product issue','product_support','minor',1),
           ('old bed collection','Service/Other','after-sales service','store service issue','store_operations','none',2),
           ('invoice','Service/Other','billing/invoice issue','billing/invoice issue','customer_support','none',3)]
    quotes=EMAIL.body.split('. ')[:3];issues=[]
    for (obj,cat,reason,process,team,risk,priority),quote in zip(specs,quotes):
        ev=span(EMAIL,quote)
        issues.append(dict(issue_id=obj,object_type='product' if obj=='drawer' else 'service',object_name=obj,
            category=cat,issue_kind='complaint',reason=reason,sentiment='negative',urgency='medium',resolution='unresolved',
            evidence=[ev],business_process=process,routing_team=team,attribution_certainty='reported',missing_evidence=['Internal records and cause verification'],
            customer_requests=['Please follow up'],customer_importance='unspecified',importance_evidence=[],
            handling_priority=priority,priority_rationale='Risk inspection, service rescheduling, then invoice coordination; no reported dependency.',
            risk_level=risk,risk_evidence=[ev] if risk=='minor' else [],risk_rationale='Ordinary collision potential' if risk=='minor' else 'No specific injury risk stated',
            urgency_basis='other',urgency_evidence=[ev]))
    return AnalysisV31(policy_version=POLICY,reply_language='en',sentiment='negative',urgency='medium',request_types=['investigation'],
        complaint_status='current_unresolved',mentioned_store='unknown',store_verification='unknown',contact_channel='email',purchase_channel='unknown',
        summary='Three unresolved issues: drawer collision risk, missed old-bed collection, and missing invoice line.',
        suggested_reply='Thank you for explaining all three issues. Please keep the walkway clear of the open drawer. The collection booking and invoice line need checking; please share the booking reference and invoice number if available.',issues=issues).validate_input(EMAIL)


class ReplayV31:
    backend='offline_fake'
    model_id='explicit-v31-fixture-replay'
    def __init__(self,outputs,dataset_id='p38-public-fixture',dataset_hash=None,arm=None):
        self.outputs=outputs
        from src.application.v31_prompt import prompt_hash
        self.config=RunConfigV31(backend=self.backend,model_id=self.model_id,prompt_version='v31-explicit-fixture-'+(arm or 'demo'),
            schema_version=SCHEMA,taxonomy_version=TAXONOMY,prompt_hash=prompt_hash(arm) if arm else digest('explicit fixture, not NLP'),
            parameters=dict(dataset_id=dataset_id,dataset_hash=dataset_hash,fixture_hash=digest(outputs),policy_version=POLICY,
                projection_policy=PROJECTION,reply_gate_version=GATE,arm=arm))
    def analyze(self,email):
        if email.input_hash not in self.outputs:raise ValueError('Outside explicit fixture whitelist')
        data=self.outputs[email.input_hash]
        return data if isinstance(data,str) else json.dumps(data,ensure_ascii=False)


def pipeline_probe(email):
    """One unknown placeholder per input, only for import/storage plumbing checks."""
    from src.application.research_policy_v2 import assess,requested_language
    finding=assess(email.body);ev=span(email,email.body);data=fixture().model_dump();issue=data['issues'][0]
    issue.update(issue_id='pipeline-placeholder',object_type='unknown',object_name='unknown',category='unknown',issue_kind='unknown',
        reason='unknown',sentiment='unknown',resolution='unknown',evidence=[ev],business_process='unknown',routing_team='unassigned',
        attribution_certainty='unknown',missing_evidence=['No model analysis; human semantic review pending'],customer_requests=[],
        customer_importance='unspecified',importance_evidence=[],handling_priority=None,priority_rationale=None,
        risk_level=finding['risk'] or 'unknown',risk_evidence=[ev] if finding['risk'] else [],
        risk_rationale='Offline probe: bounded lexical anchor candidate only, no semantic quality claim',
        urgency=finding['urgency'] or 'unknown',urgency_basis=finding['basis'],urgency_evidence=[ev])
    lang=requested_language(email.body)
    reply='离线流程占位回复，尚未进行模型分析，需要人工审核。' if lang=='zh' else 'Offline pipeline placeholder; model analysis and human review pending.'
    if lang=='bilingual':reply+=' 离线占位，人工待审。'
    data.update(issues=[issue],sentiment='unknown',urgency=issue['urgency'],request_types=['unknown'],complaint_status='unknown',
        summary='Offline fake pipeline probe; no model understanding or quality claim.',suggested_reply=reply,reply_language=lang)
    return AnalysisV31.model_validate(data).validate_input(email)
