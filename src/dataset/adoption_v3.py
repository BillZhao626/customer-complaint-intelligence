"""Append-only owner-approved adoption; source text and old references stay intact."""
from collections import Counter
from difflib import SequenceMatcher
import re
from src.domain.contracts import EmailInput, digest
from src.evaluation.e2e_v3 import validate_candidates
from src.evaluation.dataset_audit_v3 import normalize
from src.application.research_policy_v2 import POLICY_HASH

VERSION='p38-dataset-adoption-v3'
APPROVED=tuple('P35-'+x for x in ('009','031','045','051','086','122','128','137','147','157','159'))


def build(source, reviews, proposals):
    rows=validate_candidates(source)
    by_id={r.sample_id:r for r in rows}
    rev={r['sample_id']:r for r in reviews}
    prop={r['parent_sample_id']:r for r in proposals}
    if len(rev)!=len(reviews) or len(prop)!=len(proposals) or set(prop)!=set(APPROVED):
        raise ValueError('Duplicate or unexpected revision approval scope')
    if (Counter(r['recommendation'] for r in reviews)!=Counter(retain=20,revise=11,quarantine_recommended=1)
        or not set(rev).issubset(by_id) or set(prop)!={r['sample_id'] for r in reviews if r['recommendation']=='revise'}
        or rev.get('P35-073',{}).get('recommendation')!='quarantine_recommended'):
        raise ValueError('Owner review scope mismatch')
    records=[];receipts=[]
    for row in rows:
        raw=row.model_dump();r=rev.get(row.sample_id)
        if r and (r['input_hash']!=row.input_hash or r['original']!={'subject':row.subject,'body':row.body} or r['source_record_hash']!=digest(raw)):
            raise ValueError('Reviewed original identity mismatch')
        queue='quarantine' if row.exclusion_reason else 'adversarial' if row.sample_id=='P35-073' else 'natural'
        state='superseded' if row.sample_id in prop else 'current'
        record=dict(record_id=row.sample_id,logical_id=row.sample_id,state=state,queue=queue,source_record=raw,
            input_hash=row.input_hash,source_record_hash=digest(raw),supersedes=None,
            quality_status='owner_adopted' if r else 'historical_quarantine' if queue=='quarantine' else 'pending',
            semantic_review_status='pending',reference=None,prediction=None,output_hash=None)
        records.append(record)
        if row.sample_id in prop:
            p=prop[row.sample_id];new=p['candidate']
            if row.input_hash!=p['parent_input_hash'] or p['new_input_hash']!=new['input_hash']:
                raise ValueError('Rewrite parent/hash mismatch')
            candidate=validate_candidates([new])[0]
            if candidate.input_hash==row.input_hash or candidate.reference is not None or candidate.reference_basis is not None:
                raise ValueError('New text must have new hash and no inherited reference')
            records.append(dict(record_id=candidate.sample_id,logical_id=row.sample_id,state='current',queue='natural',
                source_record=candidate.model_dump(),input_hash=candidate.input_hash,source_record_hash=digest(candidate.model_dump()),
                supersedes=dict(record_id=row.sample_id,input_hash=row.input_hash,source_record_hash=digest(raw)),
                quality_status='owner_adopted',semantic_review_status='pending',reference=None,prediction=None,output_hash=None))
        if r:
            latest=records[-1]
            receipts.append(dict(logical_id=row.sample_id,action='replace' if state=='superseded' else 'isolate_adversarial' if queue=='adversarial' else 'retain',
                old_input_hash=row.input_hash,new_input_hash=latest['input_hash'],old_record_hash=digest(raw),new_record_id=latest['record_id'],
                old_text=dict(subject=row.subject,body=row.body),new_text={k:latest['source_record'][k] for k in ('subject','body')},
                semantic_change=r['business_and_evidence'],source_review_hash=digest(r),policy_hash=POLICY_HASH,
                approval_scope='Text quality and adoption only; no independent Gold',semantic_reference='pending'))
    manifest=dict(version=VERSION,policy_hash=POLICY_HASH,source_dataset_hash=digest(source),source_review_hash=digest(reviews),
        source_proposals_hash=digest(proposals),records=records,receipts=receipts,
        exposure='development_exposed',human_gold='PENDING',independent_holdout='PENDING')
    manifest['counts']=counts(manifest)
    manifest['manifest_hash']=digest(manifest)
    return validate(manifest)


def counts(manifest):
    rows=manifest['records'];current=[r for r in rows if r['state']=='current']
    natural=[r for r in current if r['queue']=='natural']
    return dict(history_records=len(rows),current_versions=len(current),natural_candidates=len(natural),
        adversarial_candidates=sum(r['queue']=='adversarial' for r in current),quality_quarantine=sum(r['queue']=='quarantine' for r in current),
        superseded_versions=sum(r['state']=='superseded' for r in rows),
        natural_semantic_review_pending=sum(r['semantic_review_status']=='pending' for r in natural),
        current_semantic_review_pending=sum(r['semantic_review_status']=='pending' for r in current),
        natural_quality_pending=sum(r['quality_status']=='pending' for r in natural))


def validate(manifest):
    copy=dict(manifest);claim=copy.pop('manifest_hash')
    if digest(copy)!=claim or manifest['counts']!=counts(manifest) or manifest['policy_hash']!=POLICY_HASH:
        raise ValueError('Adoption manifest binding mismatch')
    rows=manifest['records'];index={r['record_id']:r for r in rows};logical={}
    if len(index)!=len(rows):raise ValueError('Duplicate record identity')
    for r in rows:
        c=validate_candidates([r['source_record']])[0]
        if c.input_hash!=r['input_hash'] or digest(c.model_dump())!=r['source_record_hash']:
            raise ValueError('Record source binding mismatch')
        if r['state'] not in ('current','superseded') or r['queue'] not in ('natural','adversarial','quarantine'):
            raise ValueError('Unknown dataset state/queue')
        if r['state']=='current':logical.setdefault(r['logical_id'],[]).append(r)
        if r['logical_id']=='P35-073' and r['queue']!='adversarial':raise ValueError('Adversarial must remain isolated')
        if r['supersedes']:
            parent=index.get(r['supersedes']['record_id'])
            if not parent or parent['state']!='superseded' or parent['logical_id']!=r['logical_id'] or parent['input_hash']!=r['supersedes']['input_hash'] or parent['source_record_hash']!=r['supersedes']['source_record_hash']:
                raise ValueError('Broken supersedes lineage')
            if parent['input_hash']==r['input_hash'] or any(r[k] is not None for k in ('reference','prediction','output_hash')):
                raise ValueError('Rewrite cannot inherit reference or prediction')
    if any(len(v)!=1 for v in logical.values()):raise ValueError('Multiple active versions')
    if set(logical)!={r['logical_id'] for r in rows}:raise ValueError('Missing current version')
    return manifest


def current_candidates(manifest,queue='natural'):
    validate(manifest)
    # Explicit import view: source records remain immutable in the history manifest.
    rows=[]
    for r in manifest['records']:
        if r['state']=='current' and r['queue']==queue:
            c=dict(r['source_record'],dataset_id=VERSION,reference=None,reference_basis=None,review_status='pending')
            rows.append(c)
    return [r.model_dump() for r in validate_candidates(rows)]


def leakage_audit(manifest,frozen,frozen_lineage=None):
    validate(manifest);nodes=[]
    lineage=frozen_lineage or {}
    for r in manifest['records']:
        c=r['source_record']
        nodes.append(dict(id=r['record_id'],logical_id=r['logical_id'],body=c['body'],subject=c['subject'],input_hash=r['input_hash'],
            semantic=c['semantic_family'],narrative=re.sub(r'^p37-rewrite-','',c['template_family']),queue=r['queue'],state=r['state'],
            provenance=dict(dataset=c['dataset_id'],method=c['generation_method'],record_hash=r['source_record_hash'])))
    for f in frozen:
        e=EmailInput.model_validate(f['email'])
        if e.input_hash!=f['input_hash']:raise ValueError('Frozen input mismatch')
        original=lineage.get(e.email_id,{}).get('original',{})
        if original and (original['input_hash']!=e.input_hash or original['subject']!=e.subject or original['email_body']!=e.body or digest(original)!=lineage[e.email_id]['source_record_hash']):
            raise ValueError('Frozen lineage/input mismatch')
        nodes.append(dict(id='frozen:'+e.email_id,logical_id=e.email_id,subject=e.subject,body=e.body,input_hash=e.input_hash,
            semantic=original.get('semantic_group'),narrative=original.get('template_group'),queue='frozen24',state='frozen',
            provenance=dict(source_dataset=original.get('dataset_id'),source_record_hash=lineage.get(e.email_id,{}).get('source_record_hash'),reference_record_hash=digest(f))))
    topics={'safety':r'safety|sparks?|smoke|handle detached|安全|火花|冒烟|碰撞',
        'repair_warranty':r'repair|warranty|维修|保修','billing':r'invoice|billing|发票|账单',
        'contact_failure':r'callback|no answer|unanswered|contact|回电|回复|联系',
        'delivery':r'parcel|courier|delivery|包裹|快递|物流','refund':r'refund|compensation|退款|赔偿',
        'fit':r'fit|size|尺码|尺寸','service_visit':r'appointment|installation|collection|预约|安装|回收',
        'privacy':r'privacy|personal data|address|隐私|个人信息|地址'}
    for n in nodes:n['topic_candidates']=[name for name,pattern in topics.items() if re.search(pattern,n['body'],re.I)]
    parent={n['id']:n['id'] for n in nodes};edges=[];exact=[];near=[]
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def connect(a,b,kind,score=None):
        edges.append(dict(a=a['id'],b=b['id'],kind=kind,similarity=score))
        parent[find(a['id'])]=find(b['id'])
    for k,a in enumerate(nodes):
        for b in nodes[:k]:
            kinds=[]
            if a['logical_id']==b['logical_id']:kinds.append('supersedes_rewrite')
            if a['input_hash']==b['input_hash']:kinds.append('exact_input')
            if a['semantic'] and a['semantic']==b['semantic']:kinds.append('semantic_family_conservative')
            if a['narrative'] and a['narrative']==b['narrative']:kinds.append('narrative_translation_lineage')
            if set(a['topic_candidates'])&set(b['topic_candidates']):kinds.append('topic_overlap_conservative_not_proven_common_origin')
            ta,tb=normalize(a['body']),normalize(b['body'])
            if ta==tb:exact.append([a['id'],b['id']]);kinds.append('normalized_exact')
            else:
                m=SequenceMatcher(None,ta,tb,autojunk=False)
                if m.quick_ratio()>=.86:
                    score=m.ratio()
                    if score>=.86:near.append(dict(ids=[a['id'],b['id']],similarity=score));kinds.append('near_duplicate')
            for kind in kinds:connect(a,b,kind)
    components={}
    for n in nodes:components.setdefault(find(n['id']),[]).append(n['id'])
    cross=[e for e in edges if e['a'].startswith('frozen:') != e['b'].startswith('frozen:')]
    return dict(version='p38-leakage-1',manifest_hash=manifest['manifest_hash'],nodes=nodes,edges=edges,components=list(components.values()),
        exact_duplicates=exact,near_duplicates=near,frozen_input_count=len(frozen),frozen_candidate_links=cross,
        frozen_lineage_records=len(lineage),frozen_direct_origin_links=[e for e in cross if e['kind']!='topic_overlap_conservative_not_proven_common_origin'],
        translation_check='Shared semantic/narrative family and explicit rewrite lineage connected conservatively; unrecorded translations require human review',
        limitations='Lexical threshold .86 and topic heuristics cannot prove independence or shared origin. Topic links are conservative split grouping, not proof of contamination. Unrecorded translation/rewrite needs human audit. Every candidate is development-exposed; no holdout claim.',
        counts=counts(manifest),independent_holdout='PENDING')
