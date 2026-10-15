"""Explicit synthetic fixture and replay protocol, never a language analyzer."""
import json
from src.domain.contracts import EmailInput, RunConfig, digest
from src.domain.analysis_v3 import AnalysisV3, Issue, Evidence, Relation

DEMO_EMAIL=EmailInput(email_id='v3-equal-demo',subject='Synthetic: two equally important problems',
    body='My jacket tore and the fitting appointment was cancelled. Both matter equally to me.')


def span(email,quote):
    start=email.body.index(quote)
    return Evidence(field='body',start=start,end=start+len(quote),quote=quote)


def demo_result(email=DEMO_EMAIL):
    equal=span(email,'Both matter equally to me.')
    items=[]
    for id,obj,cat,quote,reason,process,team,priority in [
        ('jacket','jacket','Clothing','My jacket tore','product quality','product issue','product_support',1),
        ('appointment','fitting appointment','Service/Other','the fitting appointment was cancelled','customer service','store service issue','store_operations',2)]:
        items.append(Issue(issue_id=id,object_type='product' if id=='jacket' else 'service',object_name=obj,category=cat,
            issue_kind='complaint',reason=reason,sentiment='negative',urgency='low',resolution='unresolved',evidence=[span(email,quote)],
            business_process=process,routing_team=team,attribution_certainty='inferred',missing_evidence=['Internal handling records'],
            customer_requests=[],customer_importance='equal',importance_evidence=[equal],handling_priority=priority,
            priority_rationale='Business suggestion: inspect jacket damage first, then reschedule; no dependency asserted.'))
    return AnalysisV3(sentiment='negative',urgency='low',request_types=['investigation'],complaint_status='current_unresolved',
        mentioned_store='unknown',store_verification='unknown',contact_channel='unknown',purchase_channel='unknown',
        summary='The jacket tore and the fitting appointment was cancelled; the customer says both matter equally.',
        suggested_reply='I understand that both issues matter equally. Please share the jacket damage and appointment details so we can investigate both.',
        issues=items,relations=[Relation(from_issue='jacket',to_issue='appointment',kind='equal_importance',evidence=[equal])])


def placeholder(email):
    """Pipeline probe with deliberately unknown semantics; never an expected label."""
    return AnalysisV3(sentiment='unknown',urgency='unknown',request_types=['unknown'],complaint_status='unknown',
        mentioned_store='unknown',store_verification='unknown',contact_channel='unknown',purchase_channel='unknown',
        summary='Offline pipeline probe; semantic analysis unavailable.',suggested_reply='Unreviewed offline placeholder; please review the original email.',
        issues=[Issue(issue_id='unclassified',object_type='unknown',object_name='unknown',category='unknown',issue_kind='unknown',
            reason='unknown',sentiment='unknown',urgency='unknown',resolution='unknown',evidence=[span(email,email.body)],
            business_process='unknown',routing_team='unassigned',attribution_certainty='unknown',missing_evidence=['Human review and model analysis pending'],
            customer_requests=[],customer_importance='unspecified',importance_evidence=[])])


class ReplayV3:
    backend='offline_fake'
    model_id='explicit-v3-replay-fixture'
    def __init__(self,outputs,dataset_id='public-demo',dataset_hash=None):
        self.outputs=outputs
        self.config=RunConfig(backend=self.backend,model_id=self.model_id,prompt_version='v3-fixture-replay-1',
            schema_version='analysis-v3',taxonomy_version='complaint-issues-v3',prompt_hash=digest('explicit fixture lookup, not NLP'),
            parameters={'dataset_id':dataset_id,'dataset_hash':dataset_hash,'fixture_hash':digest(outputs)})
    def analyze(self,email):
        if email.input_hash not in self.outputs: raise ValueError('Input outside explicit replay fixture')
        result=self.outputs[email.input_hash]
        return result if isinstance(result,str) else json.dumps(result,ensure_ascii=False)
