"""Exploratory authored-data leakage screen; no independence certification."""
from difflib import SequenceMatcher
import re
from src.domain.contracts import EmailInput,digest


def normalized(text):return re.sub(r'\W+','',text.casefold())


def screen(rows,old_inputs,freeze):
    if not freeze.get('candidate_frozen_before_new_data'):raise ValueError('Freeze before authoring evaluation data')
    old=[EmailInput.model_validate(x['email']) for x in old_inputs]
    new=[EmailInput.model_validate(x['email']) for x in rows]
    if len(new)!=40 or len({e.input_hash for e in new})!=40:raise ValueError('Expected40 unique inputs')
    comparisons=[]
    for row,e in zip(rows,new):
        scores=sorted(((SequenceMatcher(None,normalized(e.body),normalized(o.body),autojunk=False).ratio(),o.email_id) for o in old),reverse=True)
        comparisons.append(dict(sample_id=e.email_id,input_hash=e.input_hash,body_hash=digest(e.body),
            exact_old_text=any(e.body==o.body for o in old),max_character_similarity=scores[0][0],nearest_old=scores[0][1],
            near_duplicate_candidate=scores[0][0]>=.75,source=row['source'],semantic_family=row.get('semantic_family'),
            template_group=row.get('template_group'),translation_source=row.get('translation_source'),
            developer_authored=True,independent_human_holdout=False,manual_source_review='pending'))
    within=[]
    for n,e in enumerate(new):
        for other in new[n+1:]:
            ratio=SequenceMatcher(None,normalized(e.body),normalized(other.body),autojunk=False).ratio()
            if ratio>=.75:within.append(dict(left=e.email_id,right=other.email_id,similarity=ratio))
    return dict(version='p310-authored40-leakage-screen-v1',candidate_freeze_hash=digest(freeze),new_count=40,old_count=len(old),
        exact_old_duplicates=sum(r['exact_old_text'] for r in comparisons),near_old_candidates=sum(r['near_duplicate_candidate'] for r in comparisons),
        within_new_near_candidates=within,records=comparisons,translation_note='Explicit authored lineage only; no automatic cross-language equivalence proof',
        semantic_family_note='Shared failure mechanisms/subjects are intended coverage, not proof of common source. Reviewer must assess family overlap.',
        independence_claim=False)
