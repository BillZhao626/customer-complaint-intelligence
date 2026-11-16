"""Coordinate saved analysis and review snapshots; never infer paid authorization."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from src.domain.contracts import EmailInput, digest


class SnapshotPending(RuntimeError):
    def __init__(self, run_id):
        self.run_id = run_id
        super().__init__('Analysis saved; recover product snapshot by run_id: ' + run_id)


@dataclass(frozen=True)
class ProductAuthorization:
    authorization_id: str
    config_hash: str
    input_hashes: frozenset[str]
    budget_path: str
    expires_at: str
    mode: str = 'live'

    def verify(self, service, email, *, server_enabled):
        params = service.config.parameters or {}
        mode = params.get('product_transport', 'live')
        import httpx
        transport = getattr(service.analyzer, 'mock_http_transport', None)
        if ((mode == 'offline_mock_http') != isinstance(transport, httpx.MockTransport)
                or getattr(service.analyzer, 'provider', None) is not None
                or service.config != service.analyzer.config):
            raise ValueError('Product transport identity does not match the analyzer')
        expiry = datetime.fromisoformat(self.expires_at)
        if (not self.authorization_id.startswith('product-') or expiry.tzinfo is None
                or expiry <= datetime.now(timezone.utc) or self.mode != mode
                or mode not in ('live', 'offline_mock_http')
                or (mode == 'live' and not server_enabled)
                or self.config_hash != digest(service.config.model_dump())
                or email.input_hash not in self.input_hashes or service.budget is None
                or Path(self.budget_path).resolve() != service.budget.path.resolve()):
            raise ValueError('Product authorization does not match this request')
        # Existing experiment ledgers lack this product-specific identity. No
        # auto-create/reset/clone path, and no acceptance of an old remaining slot.
        with service.budget.connection() as conn:
            row = conn.execute('SELECT manifest,allowed,halted FROM policy WHERE id=1').fetchone()
        manifest = json.loads(row[0])
        if (row[2] or manifest.get('product_authorization_id') != self.authorization_id
                or manifest.get('config') != service.config.model_dump()
                or set(json.loads(row[1])) != set(self.input_hashes)):
            raise ValueError('A new matching product budget is required')
        service.budget.verify_config(service.config)


class ProductAnalysis:
    def __init__(self, service, store, *, authorization=None, server_enabled=False):
        self.service, self.store = service, store
        self.authorization, self.server_enabled = authorization, server_enabled

    def submit(self, email):
        email = EmailInput.model_validate(email)
        if self.service.config.backend == 'deepseek_live':
            if self.authorization is None:
                raise ValueError('Separate product request authorization required')
            self.authorization.verify(self.service, email, server_enabled=self.server_enabled)
        run = self.service.analyze(email)
        return self.recover(run.run_id)

    def recover(self, run_id):
        """Read a persisted run only, including after expiry or exhausted budget."""
        run = self.service.repository.get(run_id)
        if run is None or run.status not in ('succeeded', 'failed'):
            raise ValueError('A persisted terminal analysis is required')
        try:
            return self.store.create(run, 'ProductAnalysis / persisted run', origin='new_analysis')
        except Exception as exc:
            raise SnapshotPending(run.run_id) from exc

    def submit_many(self, emails):
        """Explicit batch API; callers select a backend and retain row outcomes."""
        results = []
        for row_index, email in enumerate(emails):
            try:
                case = self.submit(email)
                results.append(dict(row_index=row_index, case_id=case['case_id'], run_id=case['run'].run_id, state=case['state']))
            except SnapshotPending as exc:
                results.append(dict(row_index=row_index, run_id=exc.run_id, state='snapshot_pending'))
            except ValueError:
                results.append(dict(row_index=row_index, state='input_or_authorization_rejected'))
        return results
