"""Read-only same-raw causal diagnostics; never creates a prediction or a run.

This module has no provider, database, budget or file-write path. Cross-version
results are explicitly diagnostics, not a reclassification of historical runs.
"""
from hashlib import sha256
import json
from pathlib import Path
import re

from src.application.live_execution import strict_json
from src.application.reply_review import check as gate3
from src.application.v3_safety import check_reply as gate2
from src.domain.analysis_v3 import AnalysisV3
from src.domain.analysis_v31 import AnalysisV31
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.domain.contracts import EmailInput, RunConfig, RunConfigV31, digest, idempotency_key


VERSION = 'p39r3-same-raw-causal-audit-1'
# Exact rule reconstruction from .local/p36/recovery/.../v3_safety.py. Its
# snapshot byte hash is recorded by read_saved; never import/execute snapshots.
GATE1_PATTERNS = (
    r'(?<!not )(?<!not been )\b(?:refund|compensation) (?:has been |is )?approved\b',
    r'\b(?:manager|we|i) (?:has |have )?approved\b',
    r'\b(?:will|guarantee(?:d)?) (?:be )?(?:paid|pay|payment|refund|arrive|deliver)\b',
    r'\b(?:we have|i have) (?:refunded|processed|sent|cancelled)\b',
    r'(?:已批准|保证明天|明日到账|已退款|已经支付|已为您安排)',
)


def gate1(value):
    if any(re.search(p, value.suggested_reply, re.I) for p in GATE1_PATTERNS):
        raise ValueError('Unverified commitment in unsent draft')


def _failure(exc, stage):
    """Keep validator messages/locations, never raw input_value or full text."""
    if hasattr(exc, 'errors'):
        return [dict(location=list(e['loc']), message=e['msg'], kind=e['type'])
                for e in exc.errors(include_input=False, include_url=False, include_context=False)]
    # Only known local validator messages are allowed; parse failures can embed
    # arbitrary text, so they are reduced to the exception class.
    if stage in ('source_and_policy_validation', 'safety_gate') and type(exc) is ValueError:
        # These two local checks emit only static, reviewed policy messages.
        return [dict(kind=type(exc).__name__, message=str(exc))]
    return [dict(kind=type(exc).__name__)]


def replay(raw, email, profile):
    """Replay unchanged raw with one explicit contract/profile/gate identity."""
    profiles = {
        'v3-gate1-historical-reconstruction': (AnalysisV3, gate1),
        'v3-gate2': (AnalysisV3, gate2),
        'v3-gate3': (AnalysisV3, gate3),
        'v31-policy-v2-gate3': (AnalysisV31, gate3),
        'v31-context-v1-gate3': (ContextAnalysisV31, gate3),
    }
    if profile not in profiles:
        raise ValueError('Unknown explicit replay profile')
    email = EmailInput.model_validate(email)
    model, gate = profiles[profile]
    result = dict(version=VERSION, diagnostic_kind='same_raw_replay_not_prediction',
                  profile=profile, input_hash=email.input_hash,
                  raw_text_sha256=sha256(raw.encode('utf8')).hexdigest(),
                  raw_project_digest=digest(raw), accepted=False, failed_stage=None,
                  model_quality_proven=False, human_approved=False,
                  new_provider_calls=0, original_raw_unchanged=True)
    stage = 'parsing'
    try:
        data = strict_json(raw)
        stage = 'schema_and_cross_field_invariants'
        value = model.model_validate(data)
        stage = 'source_and_policy_validation'
        value.validate_input(email)
        stage = 'safety_gate'
        gate(value)
    except (ValueError, TypeError, KeyError) as exc:
        result.update(failed_stage=stage, errors=_failure(exc, stage))
    else:
        result.update(accepted=True, errors=[])
    return result


def read_saved(path):
    """Read a saved export, preserve original status and all relevant identities.

    Returns no email body, reply, summary or raw content. It does not open any
    SQLite database and does not silently convert v3 predictions to v3.1.
    """
    path = Path(path).resolve(strict=True)
    before = path.read_bytes()
    record = json.loads(before.decode('utf-8-sig'))
    email = EmailInput.model_validate(record['email'])
    if record['input_hash'] != email.input_hash:
        raise ValueError('Historical input binding mismatch')
    attempts = record['attempts']
    if not attempts or not isinstance(attempts[-1]['raw_output'], str):
        raise ValueError('Saved raw required; no replacement prediction permitted')
    raw = attempts[-1]['raw_output']
    try:
        parsed = strict_json(raw)
    except (ValueError, TypeError):
        parsed = None
        if attempts[-1].get('parse_status') != 'failed':
            raise ValueError('Unparseable raw without historical parse failure') from None
    if parsed != attempts[-1].get('parsed_output'):
        raise ValueError('Historical raw/parsed binding mismatch')
    schema = record['config']['schema_version']
    config_model = RunConfigV31 if schema == 'analysis-v3.1' else RunConfig
    config = config_model.model_validate(record['config'])
    if record['cohort_id'] != config.cohort_id or record['idempotency_key'] != idempotency_key(email, config):
        raise ValueError('Historical cohort/idempotency binding mismatch')
    profiles = {'analysis-v3': ('v3-gate1-historical-reconstruction', 'v3-gate2', 'v3-gate3'),
                'analysis-v3.1': ('v31-policy-v2-gate3', 'v31-context-v1-gate3')}
    if schema not in profiles:
        raise ValueError('Unsupported historical wire identity; no migration implied')
    results = [replay(raw, email, p) for p in profiles[schema]]
    if path.read_bytes() != before:
        raise ValueError('Historical source changed during read-only replay')
    original_error = attempts[-1].get('error')
    error_identity = None if original_error is None else dict(
        error_type=original_error.get('error_type'), error_hash=digest(original_error))
    return dict(version=VERSION, source=str(path), source_file_sha256=sha256(before).hexdigest(),
                run_id=record['run_id'], sample_id=email.email_id,
                original_status=record['status'], input_hash=email.input_hash,
                config_hash=digest(record['config']), prompt_hash=record['config']['prompt_hash'],
                original_schema=schema,
                original_validation_profile=record['config'].get('parameters', {}).get('urgency_validation_profile'),
                original_attempt_error=error_identity,
                raw_text_sha256=sha256(raw.encode('utf8')).hexdigest(),
                new_provider_calls=0, historical_result_modified=False,
                diagnostic_results=results)


def source_identity(root):
    """Hash concrete validators and historical snapshot, without executing it."""
    root = Path(root)
    names = ('src/evaluation/p39r3_causal.py', 'src/domain/analysis_v3.py',
             'src/domain/analysis_v31.py', 'src/domain/analysis_v31_context.py',
             'src/application/research_policy_v2.py', 'src/application/urgency_context_v1.py',
             'src/application/v3_safety.py', 'src/application/reply_review.py')
    data = {n: sha256((root / n).read_bytes()).hexdigest() for n in names}
    snapshot = '.local/p36/recovery/src/application/v3_safety.py'
    if (root / snapshot).exists():
        data[snapshot] = sha256((root / snapshot).read_bytes()).hexdigest()
    return dict(version=VERSION, files=data, source_identity_hash=digest(data),
                historical_gate1='explicit reconstruction; snapshot is evidence, not executable code')
