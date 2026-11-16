"""Prepare blank blind annotation materials, never predictions or human labels.

Inputs: an array of {email_id, subject, body, source_kind, source_ref,
template_family, semantic_family, parent_ids}. No paid mode, no auto-freeze.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.domain.contracts import EmailInput, digest
from src.evaluation.core import FIELDS


def prepare(records, out, exposed=None):
    if not records: raise ValueError('Nonempty inputs required')
    exposed = exposed or {'input_hashes': [], 'template_families': [], 'semantic_families': []}
    samples = []
    for record in records:
        email = EmailInput.model_validate({k: record[k] for k in ('email_id', 'subject', 'body')})
        for k in ('source_kind', 'source_ref', 'template_family', 'semantic_family'):
            if not isinstance(record.get(k), str) or not record[k].strip(): raise ValueError('Explicit source/family metadata required')
        samples.append(dict(email=email.model_dump(), input_hash=email.input_hash,
            text_sha256=sha256((email.subject+'\n'+email.body).encode()).hexdigest(),
            provenance={k: record[k] for k in ('source_kind','source_ref','template_family','semantic_family')},
            parent_ids=record.get('parent_ids', []), exposure='pending_custodian_review',
            known_overlap=(email.input_hash in exposed.get('input_hashes', [])
                or record['template_family'] in exposed.get('template_families', [])
                or record['semantic_family'] in exposed.get('semantic_families', []))))
    if len({s['email']['email_id'] for s in samples}) != len(samples): raise ValueError('Duplicate email ID')
    if len({s['text_sha256'] for s in samples}) != len(samples): raise ValueError('Duplicate text, including changed IDs')
    # No operator can turn exposure metadata into a holdout by running this tool.
    manifest = dict(protocol='p5-preflight-v1', dataset_hash=digest(samples), samples=samples,
        independent_holdout=False, gold_frozen=False, human_signatures=0, paid_calls=0,
        known_overlap_count=sum(s['known_overlap'] for s in samples),
        next_gate='Custodian verifies all family/semantic leakage and provenance; two humans annotate independently')
    out = Path(out).resolve()
    if any(out.is_relative_to(ROOT / p) for p in ('data', 'outputs', 'docs')):
        raise ValueError('Use a new private preparation directory outside research assets/docs')
    out.mkdir(parents=True, exist_ok=False)
    def write(name, data):
        with (out / name).open('x', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    write('manifest.json', manifest)
    blank = [dict(sample_id=s['email']['email_id'], input_hash=s['input_hash'], email=s['email'], status='pending',
        seven_fields={f:dict(value=None, evidence=[], rationale=None, certainty=None) for f in FIELDS},
        complaint_status=None, issue_inventory=None, relations=None,
        summary_required_facts=None, reply_required_facts=None, reply_forbidden_claims=None,
        risk_policy_notes=None, abstention_reason=None) for s in samples]
    for slot in ('A', 'B'):
        write('reviewer-'+slot+'.json', dict(protocol='p5-preflight-v1', dataset_hash=manifest['dataset_hash'],
            reviewer=None, signed_at=None, human_declaration=False, independent_of_predictions=False,
            annotations=blank))
    write('adjudication.json', dict(protocol='p5-preflight-v1', dataset_hash=manifest['dataset_hash'],
        reviewer=None, signed_at=None, human_declaration=False, status='pending', packet_hashes=None,
        disagreements=None, decisions=None, final_annotations=None))
    write('content-review-template.json', dict(protocol='p5-preflight-v1', reviewer=None, signed_at=None,
        human_declaration=False, entries=[], entry_fields=['sample_id','input_hash','run_id','raw_hash','draft_hash',
        'anonymous_arm','facts_0_2','coverage_0_2','evidence_support_0_2','safety_0_2','authority_0_2',
        'clarity_tone_language_0_2','edit_readiness_0_2','critical_error','evidence','rationale']))
    return manifest


def check_packet(manifest, packet):
    """Binding/completeness check only; never certify real human independence."""
    if digest(manifest['samples']) != manifest['dataset_hash']:
        raise ValueError('Manifest content hash mismatch')
    samples = {s['email']['email_id']: s for s in manifest['samples']}
    if not samples or len(samples) != len(manifest['samples']):
        raise ValueError('Nonempty unique manifest samples required')
    for s in samples.values():
        if EmailInput.model_validate(s['email']).input_hash != s['input_hash']:
            raise ValueError('Manifest input hash mismatch')
    if packet.get('dataset_hash') != manifest['dataset_hash']: raise ValueError('Dataset hash mismatch')
    annotations = packet.get('annotations', [])
    if len(annotations)!=len(samples) or {a['sample_id'] for a in annotations}!=set(samples):
        raise ValueError('Annotation coverage mismatch')
    for a in annotations:
        s = samples[a['sample_id']]
        if a.get('input_hash') != s['input_hash'] or a.get('email') != s['email']:
            raise ValueError('Input binding mismatch')
    complete = all(a.get('status')=='reviewed' and a.get('complaint_status') is not None
        and isinstance(a.get('issue_inventory'), list)
        and set(a.get('seven_fields', {}))==set(FIELDS)
        and all(a['seven_fields'][f].get('value') is not None and a['seven_fields'][f].get('rationale') for f in FIELDS)
        for a in annotations)
    declarations = bool(packet.get('reviewer') and packet.get('signed_at') and packet.get('human_declaration') is True
                        and packet.get('independent_of_predictions') is True)
    return dict(binding_valid=True, declarations_present=declarations, basic_fields_complete=complete,
        independently_certified=False, status='ready_for_human_audit' if complete and declarations else 'pending',
        limitation='Does not verify identity, independence, semantic labels, Evidence, or adjudication; no Gold freeze')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare'); p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--exposed',type=Path)
    p=sub.add_parser('check');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--packet',type=Path,required=True)
    args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    if args.command=='prepare':
        result=prepare(load(args.inputs),args.out,load(args.exposed) if args.exposed else None)
        result={k:v for k,v in result.items() if k!='samples'}
    else: result=check_packet(load(args.manifest),load(args.packet))
    print(json.dumps(result,ensure_ascii=False,indent=2))
