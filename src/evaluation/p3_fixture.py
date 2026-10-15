"""Explicit synthetic acceptance cases, never model-generated Gold."""
import json
from src.domain.contracts import EmailInput, RunConfig
from src.application.analyzers import OfflineFake
from src.application.analysis_service import AnalysisService
from src.evaluation.e2e_schema import Sample
from src.evaluation.core import FIELDS

# sid, body, prediction overrides, expected overrides, terminal marker.
CASES = [
    ('defect','[store:A] [negative] Synthetic: headphones broke.',{}, {},None),
    ('praise','[store:A] [positive] Synthetic: thank you.',{}, {},None),
    ('service','[store:B] [negative] Synthetic: fitting appointment cancelled twice.',
     {'product_category':'Service/Other','complaint_reason':'customer service','source_attribution':'store service issue'}, {},None),
    ('ambiguous','[negative] Synthetic: neither courier nor shop can locate my parcel.',
     {'product_category':'unknown','complaint_reason':'delivery delay','source_attribution':'unclear'}, {},None),
    ('unknown','[negative] Synthetic: I need help; details unavailable.',
     {'product_category':'unknown','complaint_reason':'unknown','source_attribution':'unknown','sentiment':'unknown'}, {},None),
    ('inquiry','[store:B] [neutral] Synthetic: what are your opening hours?',
     {'product_category':'Service/Other'}, {},None),
    ('wrong-attribution','[store:A] [negative] Synthetic: the courier delivered my shoes three weeks late.',
     {'product_category':'Clothing','complaint_reason':'delivery delay','source_attribution':'product issue'},
     {'source_attribution':'delivery/logistics issue'},None),
    ('failed','[fail] Synthetic injected provider failure.',{}, {},'failed'),
    ('fallback','[store:A] [negative] Synthetic fallback fixture.',{}, {},'fallback'),
    ('uncertain','[fail] Synthetic interrupted request fixture.',{}, {},'interrupted_or_unknown'),
]


class FixtureAnalyzer(OfflineFake):
    model_id = 'p3-explicit-fixture-v1'

    def analyze(self,email):
        result = json.loads(super().analyze(email))
        case = next(c for c in CASES if 'p3-'+c[0] == email.email_id)
        result.update(case[2])
        return json.dumps(result)


def seed(repository):
    config = RunConfig(model_id=FixtureAnalyzer.model_id,prompt_version='p3-fixture-v1')
    service = AnalysisService(repository,FixtureAnalyzer(),config)
    samples=[];runs=[]
    for sid,body,prediction,expected,marker in CASES:
        email = EmailInput(email_id='p3-'+sid,subject='P3 synthetic acceptance: '+sid,body=body)
        # Reference remains explicit even for injected failures; not a provider prediction.
        labels = dict(store_location='unknown',product_category='Electronics',sentiment='neutral',urgency='low',
            is_complaint=False,complaint_reason='none',source_attribution='none')
        if '[store:A]' in body:labels['store_location']='A'
        if '[store:B]' in body:labels['store_location']='B'
        if '[negative]' in body:labels.update(sentiment='negative',urgency='medium',is_complaint=True,complaint_reason='product quality',source_attribution='product issue')
        if '[positive]' in body:labels['sentiment']='positive'
        labels.update({k:v for k,v in prediction.items() if k in FIELDS});labels.update(expected)
        samples.append(Sample.model_validate(dict(dataset_id='p3-synthetic-acceptance-v1',sample_id=email.email_id,
            split='development',provenance=dict(kind='developer_synthetic',source='P3 explicit acceptance table; not NLP quality evidence'),
            template_group=sid,semantic_group=sid,subject=email.subject,email_body=email.body,input_hash=email.input_hash,
            input_schema_version='email-input-v1',taxonomy_version='research-products-v2',annotation_version='p3-reference-v1',
            expected=labels,reference_status='developer_reference',summary_reference={},reply_reference={},attribution_reference={},
            applicable_checks=['seven_fields','summary','reply','aggregate','traceability'])))
        run=service.analyze(email)
        if marker=='fallback':
            # Explicitly injected fixture, never automatic product fallback.
            with repository.connect() as conn:
                conn.execute('UPDATE runs SET metadata_json=? WHERE run_id=?',
                    (json.dumps({'fallback':True,'fixture':True}),run.run_id))
            run=repository.get(run.run_id)
        elif marker=='interrupted_or_unknown':
            repository.finish_live(run.run_id,marker,None,{'fixture':True})
            run=repository.get(run.run_id)
        runs.append(run)
    return samples,runs
