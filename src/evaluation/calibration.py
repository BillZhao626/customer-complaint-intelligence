"""Owner calibration receipts are not independent human Gold."""
from pathlib import Path
import json
from hashlib import sha256
from src.domain.contracts import EmailInput,digest

KIND='RESEARCH_OWNER_CALIBRATION_DECISION'


def exclusive_json(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)


def freeze_snapshot(source_dir,decisions,output,request_hash):
    root=Path(source_dir);sources={};samples=[]
    for name in sorted(root.iterdir()):
        if name.is_file(): sources[name.name]=sha256(name.read_bytes()).hexdigest()
    for group in ('complex','legacy'):
        batch=json.loads((root/f'{group}-candidates.json').read_text(encoding='utf-8'))
        for slot in ('a','b'):
            packet=json.loads((root/f'{group}-reviewer-{slot}.json').read_text(encoding='utf-8'))
            if packet['reviewer'] is not None or packet['human_declaration'] or packet['independent_of_predictions']:
                raise ValueError('Expected blank independent review packet')
            if [(r['sample_id'],r['input_hash']) for r in packet['annotations']] != [(r['sample_id'],r['input_hash']) for r in batch]:
                raise ValueError('Annotation/source identity mismatch')
            if any(a['status']!='pending' or any(f['value'] is not None for f in a['fields'].values()) for a in packet['annotations']):
                raise ValueError('Original annotations are no longer blank')
        samples.extend(batch)
    if len(samples)!=24 or len({r['sample_id'] for r in samples})!=24: raise ValueError('Expected 24 distinct inputs')
    if set(decisions)!={r['sample_id'] for r in samples}: raise ValueError('Decision coverage mismatch')
    records=[]
    for row in samples:
        email=EmailInput(email_id=row['sample_id'],subject=row['subject'],body=row['email_body'])
        if email.input_hash!=row['input_hash']: raise ValueError('Input hash mismatch')
        records.append(dict(sample_id=email.email_id,input_hash=email.input_hash,source_record_hash=digest(row),
                            original=row,decision=decisions[email.email_id]))
    payload=dict(version='calibration-decision-v1',kind=KIND,request_sha256=request_hash,source_files_sha256=sources,
        independent_expert_forms_received=False,human_gold_status='HUMAN_GOLD_PENDING',kappa=None,records=records)
    payload['payload_hash']=digest(payload)
    exclusive_json(output,payload)
    return verify_snapshot(output,root)


def verify_snapshot(path,source_dir=None):
    payload=json.loads(Path(path).read_text(encoding='utf-8'));copy=dict(payload);claim=copy.pop('payload_hash')
    if digest(copy)!=claim or payload['kind']!=KIND or payload['independent_expert_forms_received'] or payload['kappa'] is not None:
        raise ValueError('Invalid owner decision receipt')
    if len(payload['records'])!=24 or len({r['sample_id'] for r in payload['records']})!=24:
        raise ValueError('Invalid decision coverage')
    for r in payload['records']:
        s=r['original'];email=EmailInput(email_id=s['sample_id'],subject=s['subject'],body=s['email_body'])
        if r['sample_id']!=email.email_id or email.input_hash!=r['input_hash'] or digest(s)!=r['source_record_hash']:
            raise ValueError('Original record changed')
        if payload['version']=='calibration-decision-v1.1':
            decision=r['decision'];item=decision['supplemental_record']
            if decision['owner_confirmed']!=item['seven_fields_v2_compatibility'] or item['sample_id']!=r['sample_id']:
                raise ValueError('Supplement decision mismatch')
            if item['input']!={'subject':email.subject,'email_body':email.body,'input_hash':email.input_hash}:
                raise ValueError('Supplement source mismatch')
            for e in decision['evidence']:
                if getattr(email,e['field'])[e['start']:e['end']]!=e['quote']:raise ValueError('Decision evidence mismatch')
    if source_dir:
        for name,h in payload['source_files_sha256'].items():
            if sha256((Path(source_dir)/name).read_bytes()).hexdigest()!=h: raise ValueError('Calibration source changed')
    return payload


def freeze_owner_supplement(source_dir,supplement_dir,previous_snapshot,output):
    """Append a final owner-confirmed development adjudication without signing expert forms."""
    from src.domain.contracts import AnalysisResult
    root=Path(supplement_dir)
    manifest=json.loads(next(root.glob('*manifest.json')).read_text(encoding='utf-8-sig'))
    for name,receipt in manifest['files'].items():
        data=(root/name).read_bytes()
        if len(data)!=receipt['bytes'] or sha256(data).hexdigest()!=receipt['sha256']:
            raise ValueError('Supplement checksum mismatch')
    for name,h in manifest['source_md_sha256'].items():
        if sha256((Path(source_dir)/name).read_bytes()).hexdigest()!=h: raise ValueError('Supplement original worksheet mismatch')
    packet=json.loads(next(p for p in root.glob('*.json') if 'manifest' not in p.name).read_text(encoding='utf-8-sig'))
    previous=verify_snapshot(previous_snapshot,source_dir)
    originals={r['sample_id']:r for r in previous['records']}
    if len(packet['items'])!=24 or {i['sample_id'] for i in packet['items']}!=set(originals): raise ValueError('Supplement coverage mismatch')
    fields={'sentiment','urgency','is_complaint','store_location','product_category','complaint_reason','source_attribution'}
    records=[]
    for item in packet['items']:
        old=originals[item['sample_id']];source=old['original'];inp=item['input']
        if (inp['subject'],inp['email_body'],inp['input_hash'])!=(source['subject'],source['email_body'],source['input_hash']):
            raise ValueError('Supplement input mismatch')
        labels=item['seven_fields_v2_compatibility']
        if set(labels)!=fields: raise ValueError('Incomplete seven-field decision')
        AnalysisResult.model_validate(dict(labels,product_name='unknown',key_information=[],summary='validation only',suggested_reply='validation only',confidence=0.0))
        if not item['owner_review']['owner_reviewed'] or not item['owner_review']['not_expert_independent_gold']:
            raise ValueError('Owner confirmation provenance missing')
        evidence=[]
        for field,v in item['field_evidence_ai_compiled'].items():
            for quote in v['verbatim_spans']:
                where='body' if quote in source['email_body'] else 'subject'
                text=source['email_body'] if where=='body' else source['subject']
                if not quote or quote not in text: raise ValueError('Supplement quotation mismatch')
                start=text.index(quote);evidence.append(dict(label_field=field,field=where,start=start,end=start+len(quote),quote=quote))
        records.append(dict(sample_id=item['sample_id'],input_hash=source['input_hash'],source_record_hash=old['source_record_hash'],
            original=source,decision=dict(owner_confirmed=labels,owner_rationale=item['case_reasoning_ai_compiled'],
                evidence=evidence,quality_flags=item['quality_flags'],exclude_clean_semantic=not item['eligible_for_clean_semantic_dev_eval'],
                supplemental_record=item,content_reference_status='AI_ASSISTED_WORKING_REFERENCE_HUMAN_SCORING_PENDING')))
    payload=dict(version='calibration-decision-v1.1',kind=KIND,previous_payload_hash=previous['payload_hash'],
        source_files_sha256=previous['source_files_sha256'],supplement_files=manifest['files'],
        status='FINAL_OWNER_CONFIRMED_EXPERT_CONCLUSIONS_DEVELOPMENT_FREEZE',expert_consensus='reported and finally confirmed by research owner',
        independent_expert_forms_received=False,kappa=None,human_gold_status='HUMAN_GOLD_PENDING',
        records=records)
    payload['payload_hash']=digest(payload);exclusive_json(output,payload)
    return verify_snapshot(output,source_dir)
