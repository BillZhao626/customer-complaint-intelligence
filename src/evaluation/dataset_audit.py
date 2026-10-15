"""Read-only template-pool audit. Similarity is lexical, never human semantics."""
from collections import Counter, defaultdict
from hashlib import sha256
from difflib import SequenceMatcher
import csv
from pathlib import Path
import re
from src.domain.contracts import EmailInput
from src.evaluation.e2e_schema import ExpectedSeven

def normalized_body(row):
    text=row['email_body'].lower()
    values=[row.get(k,'') for k in ('product_name','store_location','purchase_channel','purchase_timeframe','customer_name')]
    for value in sorted(filter(None,values),key=len,reverse=True):
        text=re.sub(r'(?<!\w)'+re.escape(value.lower())+r'(?!\w)','<slot>',text)
    text=re.sub(r'\bf\d{3}\b','<id>',text)
    return ' '.join(text.split())

def group_rows(rows,threshold=.92):
    ids=[r['email_id'] for r in rows]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate email IDs')
    parent={i:i for i in ids}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    exact=defaultdict(list);normalized=defaultdict(list);templates=defaultdict(list);families=defaultdict(list)
    for row in rows:
        exact[row['email_body']].append(row['email_id'])
        normalized[normalized_body(row)].append(row['email_id'])
        templates[row.get('generation_template_id') or row['email_id']].append(row['email_id'])
        families[row.get('scenario_type') or row.get('generation_template_id') or row['email_id']].append(row['email_id'])
    for groups in (exact,normalized,templates,families):
        for members in groups.values():
            for i in members[1:]:union(members[0],i)
    keys=sorted(normalized);near=[]
    for i,a in enumerate(keys):
        for b in keys[i+1:]:
            score=SequenceMatcher(None,a,b,autojunk=False).ratio()
            if score>=threshold:
                union(normalized[a][0],normalized[b][0])
                near.append(dict(left=normalized[a],right=normalized[b],similarity=round(score,6)))
    return dict(method='slot-masked exact and SequenceMatcher >= threshold, union with template IDs AND scenario families; conservative transitive components',
        threshold=threshold,groups={i:'group-'+find(i) for i in ids},
        template_groups=dict(templates),template_families=dict(families),exact_duplicates=[v for v in exact.values() if len(v)>1],
        normalized_duplicates=[v for v in normalized.values() if len(v)>1],near_relations=near,
        semantic_duplicate_status='Lexical/template proxy only; semantic equivalence requires human review')

def expected(row):
    return dict(sentiment=row['expected_sentiment'],urgency=row['expected_urgency'],
        is_complaint={'true':True,'false':False}[row['expected_is_complaint']],store_location=row['store_location'],
        product_category=row['product_category'],complaint_reason=row['expected_complaint_reason'],source_attribution=row['expected_source_attribution'])

def audit_dataset(path):
    path=Path(path)
    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    if not rows:raise ValueError('Empty dataset')
    grouping=group_rows(rows);issues=[];samples=[]
    for row in rows:
        sid=row['email_id'];body=row['email_body'];low=body.lower();flags=[]
        try:
            EmailInput(email_id=sid,subject=row['subject'],body=body)
            ExpectedSeven.model_validate(expected(row))
        except (ValueError,KeyError):flags.append('invalid_input_or_label')
        missing=[k for k,v in row.items() if v is None or not v.strip()]
        if missing:flags.append('empty_columns')
        if row['edge_case_type']=='mixed praise plus complaint' and 'some good points' not in low and 'i appreciate' not in low:
            flags.append('mixed_tag_without_praise_in_body')
        if row['expected_urgency']=='high' and row['expected_complaint_reason']!='health or safety issue' and not re.search(r'urgent|unsafe|burn|danger|immediately|injur',low):
            flags.append('high_urgency_without_explicit_text_evidence')
        if row['product_category']=='Service/Other' and row['scenario_type'] in ('negative_product_quality','negative_safety_health','negative_wrong_item'):
            flags.append('service_object_physical_issue_requires_review')
        if row['scenario_type']=='negative_wrong_item' and 'store staff' not in low:
            flags.append('store_attribution_not_explicit_in_wrong_item_text')
        if 'I I ' in body or 'I is ' in body or 'I needs ' in body or 'but it received' in body or 'but it was told' in body:
            flags.append('template_grammar_or_subject_anomaly')
        if flags:issues.append(dict(sample_id=sid,flags=flags,empty_columns=missing,template=row['generation_template_id'],
            evidence=dict(product=row['product_name'],scenario=row['scenario_type'],urgency=row['expected_urgency'],body=body)))
        samples.append(dict(sample_id=sid,input_hash=EmailInput(email_id=sid,subject=row['subject'],body=body).input_hash,
            body_chars=len(body),body_words=len(body.split()),language_proxy='English_template' if body.isascii() else 'non_ascii_review',
            template_group=row['generation_template_id'],semantic_group=grouping['groups'][sid],flags=flags))
    dimensions=('expected_sentiment','expected_urgency','expected_is_complaint','product_category','store_location',
                'expected_complaint_reason','expected_source_attribution','scenario_type','edge_case_type','generation_template_id',
                'purchase_channel','product_name')
    coverage={}
    def add(name,ids,status,basis):coverage[name]=dict(status=status,count=len(ids),sample_ids=ids,evidence_basis=basis)
    for dim in ('expected_sentiment','expected_urgency','expected_is_complaint','product_category','expected_complaint_reason','expected_source_attribution'):
        for label in sorted({r[dim] for r in rows}):
            add(dim+':'+label,[r['email_id'] for r in rows if r[dim]==label],'covered_template_only','metadata distribution; semantic validity pending')
    add('missing_store',[r['email_id'] for r in rows if not r['store_location'] or r['store_location']=='unknown'],'not_covered','explicit field check')
    add('missing_product',[r['email_id'] for r in rows if not r['product_name'] or r['product_name']=='unknown'],'not_covered','explicit field check')
    for name,pattern in [('mixed_sentiment',r'some good points|i appreciate'),('negation',r'\bnot broken\b|\bnot requesting\b'),
        ('sarcasm',r'great job.*(?:broken|delay)'),('prompt_injection',r'ignore.*instructions|system prompt|output only'),
        ('multiple_issues',r'already resolved|main problem|also.*but')]:
        ids=[r['email_id'] for r in rows if re.search(pattern,r['email_body'],re.I)]
        add(name,ids,'insufficient' if ids else 'not_covered','pattern + generator template inspection; not a semantic detector')
    add('safety_health',[r['email_id'] for r in rows if r['scenario_type']=='negative_safety_health'],'insufficient','five generic templates with semantically questionable product/service combinations')
    add('reply_refund_commitment_risk',[r['email_id'] for r in rows if r['scenario_type'] in ('negative_refund_request','negative_after_sales')],
        'insufficient','refund/repair triggers exist; no approved policy, deadlines or human rubric')
    for name in ('human_summary_reference','human_reply_reference','independent_gold','non_english','real_consumer_data'):
        add(name,[],'not_covered','no independent human reference; local generator produces English synthetic templates')
    sizes=[s['body_chars'] for s in samples]
    return dict(version='dataset-audit-v1',input_file=path.name,input_sha256=sha256(path.read_bytes()).hexdigest(),
        n=len(rows),unique_ids=len({r['email_id'] for r in rows}),template_count=len(grouping['template_groups']),
        leakage_components=len(set(grouping['groups'].values())),
        distributions={k:dict(sorted(Counter(r[k] for r in rows).items())) for k in dimensions},
        length_chars=dict(min=min(sizes),max=max(sizes),mean=sum(sizes)/len(sizes)),
        language=dict(Counter(s['language_proxy'] for s in samples)),
        null_counts={k:sum(not (r.get(k) or '').strip() for r in rows) for k in rows[0]},
        issue_counts=dict(Counter(f for i in issues for f in i['flags'])),issues=issues,samples=samples,grouping=grouping,coverage=coverage,
        disposition='Engineering regression and human annotation candidates only; template expected labels are not Human Gold')
