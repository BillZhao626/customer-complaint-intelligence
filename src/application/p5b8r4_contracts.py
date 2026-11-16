"""Strict FIRST status, separately measured non-paid syntax recovery."""
import json
from src.application.p5b8r1_contracts import parse_outcome
from src.domain.contracts import digest

def parse_reply(raw,metadata=None):
    first=parse_outcome(raw,metadata=metadata)
    result=dict(raw_hash=digest(raw),first=first,recovery=None,metric='FIRST_CONTRACT_UNCHANGED')
    # Only a missing final OBJECT brace with a fully closed string can recover.
    # Never drop extra fields, trailing data, empty strings or truncated content.
    if first['status']=='rejected' and isinstance(raw,str) and (metadata or {}).get('finish_reason') not in ('length','max_tokens'):
        text=raw.rstrip()
        if text.startswith('{') and not text.endswith('}'):
            try:
                value=json.loads(text+'}')
                if set(value)=={'reply'}:
                    restored=parse_outcome(text+'}',metadata=metadata)
                    if restored['status']=='accepted':result['recovery']=dict(status='LOCAL_SYNTAX_RECOVERY_ONLY',value=restored['value'],operation='append_one_object_brace',recovered_hash=digest(text+'}'),semantic_certified=False)
            except (ValueError,TypeError):pass
    return result
