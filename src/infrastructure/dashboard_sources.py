"""Read-only source adapters. No import/migration of historical runs."""
import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager

from src.infrastructure.repository import Repository
from src.application.attribution_service import AttributionService


class ReadOnlyRepository(Repository):
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        with self.connect() as conn:
            if conn.execute('PRAGMA user_version').fetchone()[0] != 2:
                raise ValueError('Dashboard requires existing v2 database; no migration permitted')

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        try:
            yield conn
        finally:
            conn.close()


def sqlite_source(path, manifest=None):
    samples = json.loads(Path(manifest).read_text(encoding='utf-8')) if manifest else None
    return AttributionService(ReadOnlyRepository(path).list_runs(), 'configured_sqlite', samples)


def p2_source(root):
    # Existing P2.5 adapter creates the same validated Sample objects as evaluation.
    from src.evaluation.e2e_schema import Sample
    from src.domain.contracts import EmailInput
    fixture = json.loads((root/'tests/fixtures/p2_pilot_v1.json').read_text(encoding='utf-8'))
    samples = [Sample.model_validate(dict(dataset_id='p2-developer-pilot-v1',sample_id=c['email']['email_id'],
        subject=c['email']['subject'],email_body=c['email']['body'],input_hash=EmailInput.model_validate(c['email']).input_hash,
        split='development',provenance=dict(kind='developer_synthetic',source='Frozen P2 developer reference; not Human Gold'),
        template_group=c['email']['email_id'],semantic_group=c['email']['email_id'],input_schema_version='email-input-v1',
        taxonomy_version='research-products-v2',annotation_version='pending-v1',expected=c['expected'],
        reference_status='developer_reference',summary_reference={},reply_reference={},attribution_reference={},
        applicable_checks=['seven_fields','summary','reply','aggregate','traceability'],scenarios=[c['coverage']])) for c in fixture['cases']]
    records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((root/'.local/p2-pilot-v1').glob('run-*.json'))]
    return AttributionService(records,'p2_saved_json_readonly',samples)
