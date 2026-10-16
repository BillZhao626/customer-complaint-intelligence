"""Offline v2 candidate preparation, explicitly gated on acceptance-scope approval."""
from hashlib import sha256
import json
from pathlib import Path
from src.domain.contracts import digest,RunConfigV31
from src.application.p39_experiment import SIX_RULES
from src.application.v31_prompt import BASE,OPTIMIZED,messages as old_messages
from src.application.urgency_context_v1 import PROFILE,policy_snapshot
from src.domain.analysis_v31_context import wire_schema
from src.application.analysis_service import AnalysisService

COMMON = '''
Shared context-first urgency reasoning for BOTH arms:
Read the original email including current risk, time requests, service failures, quoted/reported text,
negation, contrast, resolution and uncertainty. First identify real source facts, then choose urgency,
then explain it with a schema-valid urgency_basis and exact original urgency_evidence.
Only an undifferentiated request for help with no concrete matter usually defaults to medium.
Specific routine product-function or opening-hours questions may be low absent urgent or risk facts.
Ordinary malfunction does not itself establish severe danger or urgent handling. Active urgency usually
supports high; quoted, reported, hypothetical or negated urgency is not a current urgency instruction.
An explicit relaxed request can support low unless stronger risk or time facts override it. Repeated
service failure usually supports medium; independent current deadlines, urgency, relaxation or danger
can change this. Severe potential harm requires high regardless of calm tone or absence of injury.
Unknown is allowed when reliable classification is not possible; never fabricate missing evidence.
general_help is a narrow default basis, not a synonym for every question, please or help sentence.
Use other for supported context not described by a named basis, including ordinary specific inquiries;
use unknown only for an unknown conclusion. Named bases must have supporting, active source evidence.
If a repeated-failure default is overridden, quote BOTH the failure and overriding context.
Do not change a substantively supported urgency merely to satisfy a basis label. Do not repair the
answer after validation; return a consistent raw prediction. Preserve severe-risk and evidence checks.
'''


def system(arm):
    if arm not in ('A','B'):raise ValueError('Unknown arm')
    common=BASE+COMMON
    return common+(OPTIMIZED+SIX_RULES if arm=='B' else '')


def messages(email,arm):return [('system',system(arm)),old_messages(email,arm)[1]]


def source_hash():
    root=Path(__file__).resolve().parents[2]
    paths=('src/application/p39_v2.py','src/application/urgency_context_v1.py','src/domain/analysis_v31_context.py','src/infrastructure/p39_envelope.py','src/infrastructure/context_repository.py','scripts/p39_v2.py')
    from src.application.p39_experiment import chain_hash
    return digest(dict(parent=chain_hash(),candidate={p:sha256((root/p).read_bytes()).hexdigest() for p in paths}))


def manifest(parent,request_hash):
    body=dict(version='p39-v2-context-candidate-1',status='COMPARISON_APPROVAL_REQUIRED',parent_v1_manifest_hash=parent['manifest_hash'],
        schema_version='analysis-v3.1',schema_hash=digest(wire_schema()),urgency_validation_profile=PROFILE,policy=policy_snapshot(),
        acceptance_semantics_changed=True,paid_dispatch_allowed=False,request_evidence_hash=request_hash,
        inputs=parent['inputs'],inputs_hash=parent['inputs_hash'],schedule=parent['schedule'],processing_chain_hash=source_hash(),
        source_references_sent=False,prior_requests=1,new_planned_requests=64,combined_planned_requests=65,unused_retests=7)
    configs={}
    for arm in ('A','B'):
        c=json.loads(json.dumps(parent['configs'][arm]));c.update(prompt_version='complaint-p39-v2-'+arm+'-context-1',prompt_hash=sha256(system(arm).encode('utf8')).hexdigest())
        c['parameters'].update(dataset_id='p39-v2-context-candidate-1',processing_chain_hash=body['processing_chain_hash'],urgency_validation_profile=PROFILE)
        configs[arm]=RunConfigV31.model_validate(c).model_dump()
    body['configs']=configs;body['manifest_hash']=digest(body);return body


def require_comparison_approval(manifest,review):
    if (not review or review.get('status')!='researcher_approved_comparison_change' or not review.get('reviewer')
        or review.get('manifest_hash')!=manifest['manifest_hash'] or not review.get('user_approval_evidence')):
        raise PermissionError('Researcher approval of changed acceptance semantics required before paid initialization')


class ContextOfflineService(AnalysisService):
    """Only explicit offline fixtures are supported until acceptance-profile confirmation."""
    def __init__(self,repository,analyzer):
        if analyzer.backend!='offline_fake':raise PermissionError('Context candidate is offline only, awaiting comparison approval')
        super().__init__(repository,analyzer)

    def validate_result(self,data,email):
        from src.domain.analysis_v31_context import ContextAnalysisV31
        from src.domain.analysis_v31 import to_v2,PROJECTION
        from src.application.reply_review import check
        if self.config.parameters.get('urgency_validation_profile')!=PROFILE:raise ValueError('Missing context profile')
        value=ContextAnalysisV31.model_validate(data).validate_input(email);check(value)
        result,diagnostics=to_v2(value,PROJECTION)
        return result,dict(analysis_v31=value.model_dump(),analysis_v31_hash=digest(value.model_dump()),prediction_kind='raw_provider_prediction',
            projection_hash=digest(result.model_dump()),projection_kind='deterministic_lossy_projection',compatibility_diagnostics=diagnostics,
            urgency_validation_profile=PROFILE,reply_status='unreviewed_unsent')
