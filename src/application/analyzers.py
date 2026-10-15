"""Explicit local analyzers; this module has no provider/network configuration."""
import json
from typing import Protocol
from src.domain.contracts import EmailInput


class Analyzer(Protocol):
    backend: str
    model_id: str
    def analyze(self, email: EmailInput) -> str: ...


class OfflineFake:
    """Synthetic demo protocol, not an NLP model: [store:A], [positive], etc."""
    backend = 'offline_fake'
    model_id = 'fixture-fake-v1'

    def analyze(self,email):
        body=email.body.lower()
        if '[fail]' in body:
            raise RuntimeError('Injected offline demo failure')
        store='A' if '[store:a]' in body else 'B' if '[store:b]' in body else 'unknown'
        sentiment='negative' if '[negative]' in body else 'positive' if '[positive]' in body else 'neutral'
        complaint=sentiment=='negative'
        return json.dumps(dict(store_location=store,product_name='demo headphones',product_category='Electronics',
            sentiment=sentiment,urgency='medium' if complaint else 'low',is_complaint=complaint,
            complaint_reason='product quality' if complaint else 'none',source_attribution='product issue' if complaint else 'none',
            key_information=['Synthetic Offline Fake / Demo'],summary='Synthetic demonstration result.',
            suggested_reply='Demo draft: thank you for your message.',confidence=1.0))


class LegacyMock:
    backend = 'legacy_mock'
    model_id = 'legacy-rules-v1'

    def analyze(self,email):
        from src.chains.mock_complaint_chain import analyze_email
        raw=analyze_email(email.body,email_id=email.email_id).model_dump()
        raw.pop('email_id')
        # Legacy mock never produced source_attribution. Explicit adapter metadata,
        # not a claim that the original provider returned this required v2 field.
        return json.dumps(raw,ensure_ascii=False)
