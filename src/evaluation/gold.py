"""Independent annotation files, disagreement and append-only freeze manifests.

The tool validates declarations; human identity/independence is a procedural control.
"""
from collections import Counter
from pathlib import Path
import json
from src.domain.contracts import digest
from src.evaluation.core import FIELDS
from src.evaluation.e2e_schema import ExpectedSeven, ContentReference, validate_dataset, dataset_hash

def blank_queue(samples,slot):
    return dict(protocol='human-gold-v1',slot=slot,reviewer=None,human_declaration=False,independent_of_predictions=False,
        annotations=[dict(sample_id=s.sample_id,input_hash=s.input_hash,taxonomy_version=s.taxonomy_version,
            annotation_version='human-gold-v1',status='pending',fields={f:dict(value=None,evidence=[],certainty=None,rationale=None) for f in FIELDS},
            summary_reference={},reply_reference={},attribution_reference={}) for s in samples])

def validate_annotations(samples,packet):
    if not packet.get('reviewer') or packet.get('human_declaration') is not True or packet.get('independent_of_predictions') is not True:
        raise ValueError('Real independent reviewer declarations required')
    if packet.get('protocol')!='human-gold-v1':raise ValueError('Annotation protocol mismatch')
    rows=packet.get('annotations',[]);index={r['sample_id']:r for r in rows}
    if len(index)!=len(rows) or set(index)!={s.sample_id for s in samples}:raise ValueError('Annotation coverage mismatch')
    for sample in samples:
        row=index[sample.sample_id]
        if row.get('input_hash')!=sample.input_hash or row.get('taxonomy_version')!=sample.taxonomy_version or row.get('annotation_version')!='human-gold-v1' or row.get('status')!='reviewed':
            raise ValueError('Annotation binding/status mismatch')
        fields=row.get('fields',{})
        if set(fields)!=set(FIELDS):raise ValueError('All seven annotations required')
        expected={f:fields[f].get('value') for f in FIELDS}
        ExpectedSeven.model_validate(expected)
        if any(v is None for v in expected.values()):raise ValueError('Gold cannot be pending')
        text=sample.subject+'\n'+sample.email_body
        for field,annotation in fields.items():
            if annotation.get('certainty') not in ('high','medium','low') or not annotation.get('rationale') or not annotation.get('evidence'):
                raise ValueError('Evidence, certainty and rationale required')
            if any(not isinstance(span,str) or not span or span not in text for span in annotation['evidence']):
                raise ValueError('Evidence must be a verbatim input span')
        for kind in ('summary','reply','attribution'):
            ref=ContentReference.model_validate(row.get(kind+'_reference',{}))
            if ref.status!='approved' or ref.reviewer!=packet['reviewer']:raise ValueError('Human content reference approval required')
    return index

def compare(samples,a,b):
    a_index=validate_annotations(samples,a);b_index=validate_annotations(samples,b)
    if a['reviewer']==b['reviewer']:raise ValueError('Distinct independent reviewers required')
    result={};disagreements=[]
    for field in FIELDS:
        pairs=[(a_index[s.sample_id]['fields'][field]['value'],b_index[s.sample_id]['fields'][field]['value']) for s in samples]
        n=len(pairs);observed=sum(x==y for x,y in pairs)/n
        ca=Counter(x for x,y in pairs);cb=Counter(y for x,y in pairs)
        chance=sum(ca[k]*cb[k] for k in ca.keys()|cb.keys())/(n*n)
        result[field]=dict(n=n,agreement=observed,cohen_kappa=(observed-chance)/(1-chance) if chance<1 else None)
        disagreements.extend(dict(sample_id=s.sample_id,field=field,a=x,b=y) for s,(x,y) in zip(samples,pairs) if x!=y)
    for sample in samples:
        for kind in ('summary','reply','attribution'):
            left=dict(a_index[sample.sample_id][kind+'_reference']);right=dict(b_index[sample.sample_id][kind+'_reference'])
            left.pop('reviewer',None);right.pop('reviewer',None)
            if left!=right:disagreements.append(dict(sample_id=sample.sample_id,field=kind+'_reference',a=left,b=right))
    return dict(fields=result,disagreements=disagreements,n=len(samples),reviewers=[a['reviewer'],b['reviewer']])

def build_freeze(samples,a,b,adjudication):
    samples=validate_dataset(samples)
    if not isinstance(a,dict) or not isinstance(b,dict):raise ValueError('Reviewer packets required')
    agreement=compare(samples,a,b)
    if (not adjudication.get('reviewer') or adjudication.get('human_declaration') is not True
        or adjudication.get('status')!='approved' or adjudication.get('dataset_hash')!=dataset_hash(samples)
        or adjudication.get('packet_hashes')!=[digest(a),digest(b)]):
        raise ValueError('Bound human adjudication approval required')
    final=adjudication.get('final_packet')
    if not isinstance(final,dict) or final.get('reviewer')!=adjudication['reviewer']:raise ValueError('Final adjudicated packet required')
    final_index=validate_annotations(samples,final)
    decisions=adjudication.get('decisions',[])
    required={(d['sample_id'],d['field']) for d in agreement['disagreements']}
    # Changing an agreed label/reference also needs an explicit adjudication reason.
    for packet in (a,b):
        for row in packet['annotations']:
            final_row=final_index[row['sample_id']]
            for field in FIELDS:
                if row['fields'][field]['value']!=final_row['fields'][field]['value']:
                    required.add((row['sample_id'],field))
            for kind in ('summary','reply','attribution'):
                key=kind+'_reference';before=dict(row[key]);after=dict(final_row[key])
                before.pop('reviewer',None);after.pop('reviewer',None)
                if before!=after:required.add((row['sample_id'],key))
    keys=[(d.get('sample_id'),d.get('field')) for d in decisions]
    if len(keys)!=len(set(keys)) or set(keys)!=required or any(not d.get('rationale') for d in decisions):
        raise ValueError('Every disagreement requires a unique reasoned decision')
    frozen=[]
    freeze_id=digest(dict(dataset=dataset_hash(samples),a=digest(a),b=digest(b),adjudication=digest(adjudication)))
    for sample in samples:
        row=final_index[sample.sample_id];data=sample.model_dump()
        data.update(expected={f:row['fields'][f]['value'] for f in FIELDS},reference_status='human_gold',
            annotation_version='human-gold-v1',reviewer=[a['reviewer'],b['reviewer']],adjudication='accepted',freeze_id=freeze_id,
            **{kind+'_reference':row[kind+'_reference'] for kind in ('summary','reply','attribution')})
        frozen.append(data)
    validated=validate_dataset(frozen)
    manifest=dict(protocol='human-gold-freeze-v1',freeze_id=freeze_id,source_dataset_hash=dataset_hash(samples),
        source_samples=[s.model_dump() for s in samples],
        dataset_hash=dataset_hash(validated),samples=[s.model_dump() for s in validated],agreement=agreement,
        packets=dict(a=a,b=b,adjudication=adjudication),
        independent_holdout=all(s.split=='holdout' and s.provenance.independent and s.provenance.exposure=='sealed' for s in validated))
    manifest['payload_hash']=digest(manifest)
    return manifest

def freeze(samples,a,b,adjudication,path):
    manifest=build_freeze(samples,a,b,adjudication)
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
    return manifest

def verify_freeze(manifest):
    data=dict(manifest);saved=data.pop('payload_hash',None)
    if saved!=digest(data):raise ValueError('Freeze manifest tampered')
    samples=validate_dataset(data['samples'])
    if dataset_hash(samples)!=data['dataset_hash']:raise ValueError('Frozen dataset differs')
    packets=data['packets']
    rebuilt=build_freeze(data['source_samples'],packets['a'],packets['b'],packets['adjudication'])
    if rebuilt!=manifest:raise ValueError('Freeze provenance or adjudication mismatch')
    return samples
