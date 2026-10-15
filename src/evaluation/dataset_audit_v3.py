"""Deterministic lexical leakage signals; semantic independence needs human review."""
from collections import Counter
from difflib import SequenceMatcher
import re
import unicodedata
from src.domain.contracts import digest
from src.evaluation.e2e_v3 import validate_candidates,dataset_hash


def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    text=re.sub(r'\d+','<number>',text)
    return re.sub(r'\s+',' ',text).strip()


def audit(candidates,historical=None):
    rows=validate_candidates(candidates);historical=historical or []
    texts=[normalize(r.body) for r in rows];exact=[];near=[];maximum=(0.0,None,None)
    for i in range(len(rows)):
        for j in range(i):
            if texts[i]==texts[j]:exact.append([rows[j].sample_id,rows[i].sample_id])
            ratio=SequenceMatcher(None,texts[i],texts[j],autojunk=False).ratio()
            if ratio>maximum[0]:maximum=(ratio,rows[j].sample_id,rows[i].sample_id)
            if ratio>=0.86:near.append(dict(ids=[rows[j].sample_id,rows[i].sample_id],similarity=ratio))
    history_matches=[]
    for row,text in zip(rows,texts):
        for h in historical:
            old=normalize(h['body'])
            # quick_ratio safely avoids expensive exact scoring for impossible matches.
            matcher=SequenceMatcher(None,text,old,autojunk=False)
            if matcher.quick_ratio()<0.86: continue
            ratio=matcher.ratio()
            if ratio>=0.86:history_matches.append(dict(sample_id=row.sample_id,historical_id=h['sample_id'],similarity=ratio,source_hash=h.get('source_hash')))
    return dict(protocol='candidate-audit-v3-1',dataset_id=rows[0].dataset_id,dataset_hash=dataset_hash(rows),count=len(rows),
        input_hashes={r.sample_id:r.input_hash for r in rows},languages=dict(Counter(r.language for r in rows)),
        coverage=dict(Counter(s for r in rows for s in r.scenarios)),semantic_families=dict(Counter(r.semantic_family for r in rows)),
        template_families=len({r.template_family for r in rows}),splits=dict(Counter(r.split for r in rows)),
        review_states=dict(Counter(r.review_status for r in rows)),exact_normalized_body_duplicates=exact,near_duplicates=near,
        max_pair_similarity=dict(value=maximum[0],ids=list(maximum[1:])),historical_checked=len(historical),historical_near_matches=history_matches,
        quarantine=[r.sample_id for r in rows if r.exclusion_reason],human_gold='PENDING',independent_holdout='PENDING',
        caveat='Lexical threshold .86 is a review signal, not proof of semantic independence; all candidates exposed to Codex. No model-generated expected labels.')
