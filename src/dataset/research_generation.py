"""Reproducible generation plan and response acceptance; never opens a provider.

Future authorized runners can import bound saved response envelopes.
The shipping CLI exposes offline smoke only, so no old budget can be reused.
"""
import json
import math
import re
from pathlib import Path
from collections import Counter
from src.domain.contracts import digest

SCENARIOS=[
    ('praise-product','positive','Electronics','Alder Store','en'),
    ('praise-service','positive','Clothing','Birch Store','zh'),
    ('fault','negative','Home Appliances','Cedar Store','zh'),
    ('delivery','negative','Furniture','Alder Store','en'),
    ('refund','negative','Sports/Outdoor','Birch Store','zh'),
    ('inquiry','neutral','Service/Other',None,'en'),
    ('missing-product','negative',None,'Cedar Store','zh'),
    ('missing-store','negative','Beauty/Personal Care',None,'en'),
    ('mixed-experience','mixed','Food/Beverage','Alder Store','zh'),
]
SYSTEM='Write one natural fictional customer email for retail research. Return JSON with subject and body only. No labels, markdown, real personal data or reference answers. Use ordinary customer language. Do not turn it into a checklist. One main situation is enough; allow plausible omissions, varied intensity and background. Do not force a resolution or invent company policy.'


def plan():
    jobs=[]
    for scenario,mood,product,store,language in SCENARIOS:
        config=dict(scenario=scenario,intended_tone=mood,product=product,store=store,language=language,
            omission_policy='null fields must remain unspecified; other metadata need not be stated explicitly')
        messages=[dict(role='system',content=SYSTEM),dict(role='user',content=json.dumps(config,ensure_ascii=False))]
        jobs.append(dict(id='gen-'+scenario,config=config,messages=messages,messages_hash=digest(messages)))
    data=dict(version='llm-email-generation-p5b6-v1',status='LIVE_GENERATION_PENDING',model='deepseek-flash',
        parameters=dict(temperature=0.7,max_tokens=900,response_format={'type':'json_object'},max_retries=0,thinking={'type':'disabled'}),
        sample_rationale='Nine single-situation cells cover praise, complaints, inquiry, missing entities and one mixed experience, both zh/en; not population-representative.',
        authorization=None,request_limit=None,budget_cny=None,jobs=jobs)
    return dict(data,plan_hash=digest(data))


def accept_response(job, raw, *, model, parameters, request_id, usage):
    data=json.loads(raw)
    if set(data)!={'subject','body'} or any(not isinstance(data[k],str) or not data[k].strip() for k in data):
        raise ValueError('Expected subject/body only')
    return dict(email_id=job['id'],**data,input_hash=digest(data),raw=raw,raw_hash=digest(raw),
        source='LLM_GENERATED_SYNTHETIC_CANDIDATE_NOT_GOLD',review_status='HUMAN_NATURALNESS_PENDING',
        model=model,parameters=parameters,request_id=request_id,usage=usage,
        messages=job['messages'],messages_hash=job['messages_hash'],scenario_intent=job['config'],independent_labels=None)


def collect_responses(generation_plan, responses, out, *, identity, baseline_texts=()):
    """Append-only response ingestion, not a dispatcher. Reject unbound inputs.

    `responses` are saved response envelopes from an authorized future runner or
    explicit offline fixtures. Nothing here can construct a client or use .env.
    """
    if identity not in ('OFFLINE_TRANSPORT_FIXTURE','AUTHORIZED_SAVED_RESPONSE_IMPORT'):
        raise ValueError('Explicit response identity required')
    if generation_plan['plan_hash']!=digest({k:v for k,v in generation_plan.items() if k!='plan_hash'}):
        raise ValueError('Generation plan drift')
    if identity=='AUTHORIZED_SAVED_RESPONSE_IMPORT' and not all(generation_plan.get(k) for k in ('authorization','request_limit','budget_cny')):
        raise ValueError('Live import requires new explicit authorization metadata')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    jobs={j['id']:j for j in generation_plan['jobs']};seen=set();records=[]
    baseline={' '.join(t.lower().split()) for t in baseline_texts};fingerprints=set(baseline)
    for response in responses:
        key=response['job_id']
        if key not in jobs or key in seen or response['messages_hash']!=jobs[key]['messages_hash']:
            raise ValueError('Unknown, duplicate or changed generation job')
        seen.add(key)
        raw=response['raw'];record=accept_response(jobs[key],raw,model=response['model'],parameters=generation_plan['parameters'],request_id=response.get('request_id'),usage=response.get('usage'))
        text=' '.join(record['body'].lower().split())
        record.update(source='OFFLINE_TRANSPORT_FIXTURE_NOT_LLM_DATA' if identity=='OFFLINE_TRANSPORT_FIXTURE' else record['source'],
            exact_duplicate_of_baseline=text in baseline,exact_duplicate_seen=text in fingerprints,
            plan_hash=generation_plan['plan_hash'],response_identity=identity,
            model_snapshot=response.get('model_snapshot','unavailable'),authorization=generation_plan.get('authorization'))
        fingerprints.add(text);records.append(record)
        with (out/(key+'.json')).open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    manifest=dict(version='generation-response-collection-v1',identity=identity,plan_hash=generation_plan['plan_hash'],
        n_received=len(records),n_planned=len(jobs),missing_jobs=sorted(set(jobs)-seen),independent_gold=False,
        live_generated_count=0 if identity=='OFFLINE_TRANSPORT_FIXTURE' else len(records),
        input_hashes={r['email_id']:r['input_hash'] for r in records},audit=audit([r['body'] for r in records]))
    with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
    return manifest


def audit(texts):
    normalized=[' '.join(t.lower().split()) for t in texts]
    grams=[{t[i:i+4] for i in range(max(1,len(t)-3))} for t in normalized]
    tokens=[re.findall(r'[a-z]+|[\u4e00-\u9fff]',t.lower()) for t in texts]
    counts=Counter(t for ts in tokens for t in ts);total=sum(counts.values())
    near=[]
    for i,a in enumerate(normalized):
        for j in range(i):
            # Long common template text is intentionally counted; no semantic claim.
            union=grams[i]|grams[j]
            score=len(grams[i]&grams[j])/len(union) if union else 1.
            if score>=0.9:near.append(dict(i=i,j=j,similarity=score))
    return dict(n=len(texts),exact_duplicates=len(texts)-len(set(normalized)),near_duplicate_pairs=near,threshold=0.9,
        vocabulary=len(counts),tokens=total,type_token_ratio=len(counts)/total if total else None,
        token_entropy=-sum((n/total)*math.log2(n/total) for n in counts.values()) if total else None,
        naturalness=None,naturalness_status='HUMAN_REVIEW_PENDING',classification_difficulty=None,
        metric_limits='Near duplicates: normalized character-4-gram Jaccard >=0.9. Lexical heuristics; zh characters and en words use different units; compare within language. Not naturalness or semantic diversity scores.')
