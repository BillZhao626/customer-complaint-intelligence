"""Read-only integrity checks for the P5-Q DEV review package, never semantic scoring.

No provider, network, environment loading, database, or report writes. The CLI
prints JSON; the caller can retain it in a NEW evidence directory.
"""
import csv
import hashlib
import json
from pathlib import Path

from src.domain.contracts import digest, EmailInput

ANCHOR_REPLY_SHA256 = {
    'R01': '87b73a4c4bd06c01c4ca1a5a749ea562cb4d36d3b256559211c37a9f1212315a',
    'R02': '00a59ca238175886113cd80217f9542ecce3e8865a8432cfcc80c8cbbc93568b',
    'R03': '24ec951acdefa0fc7c756ed8bddc67c972cc00df2c205ca8ecb39704692f795d',
}
KINDS = {'SINGLE': ('cases_dev.json', 'case_id', 48), 'CONVERSATION': ('conversations_dev.json', 'conversation_id', 6),
         'BAD_CASE': ('bad_cases.json', 'bad_case_id', 3), 'KNOWLEDGE': ('knowledge_drafts.json', 'knowledge_id', 4)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def unique(rows, key):
    result = {r[key]:r for r in rows}
    require(len(rows)==len(result), 'Duplicate '+key)
    return result


def validate(root):
    root = Path(root)
    package = root/'docs/p5q'
    sources = root/'resources/p5a'
    index = read(package/'CASE_INDEX_v1.json')
    require(index['identity']=='DEV_DIAGNOSTIC', 'Index identity')
    for name, h in index['source_files_sha256'].items():
        require(Path(name).name==name, 'Unsafe source name')
        require(hashlib.sha256((sources/name).read_bytes()).hexdigest()==h, 'Source file hash: '+name)
    manifest = read(sources/'manifest.json')
    for name, h in manifest['files'].items():
        require(hashlib.sha256((sources/name).read_bytes()).hexdigest()==h, 'Original P5-A manifest: '+name)
    originals = {}
    for kind, (filename, key, count) in KINDS.items():
        entries = read(sources/filename)
        mapping = unique(entries, key)
        require(len(mapping)==count, 'Source coverage '+kind)
        originals.update({cid:(kind,c) for cid,c in mapping.items()})
    with (package/'DEV_CASE_AUDIT.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    audit = unique(rows, 'record_id')
    idx = unique(index['records'], 'id')
    require(set(audit)==set(idx)==set(originals), 'Audit/index/source coverage')
    for cid, (kind, original) in originals.items():
        r, entry = audit[cid], idx[cid]
        require(r['identity']=='DEV_DIAGNOSTIC' and entry['kind']==kind==r['record_type'], 'Record identity '+cid)
        require(r['source_record_hash']==entry['source_hash']==digest(original), 'Record hash '+cid)
        require(r['observed_action']=='UNKNOWN', 'Unproven execution '+cid)
        require(all(r[k]=='' for k in ('human_scores','human_decision','researcher_signature')), 'Human fields filled '+cid)
        require(r['diagnosis'] and r['suggested_revision'] and r['human_question'], 'Missing review '+cid)
        for dimension in [f'A{i}' for i in range(1,7)]+[f'B{i}' for i in range(1,6)]:
            require(r[dimension] in ('0','1','2','N/A','UNKNOWN'), 'Invalid score '+cid)
            if dimension.startswith('B') and kind!='KNOWLEDGE':
                require(r[dimension] in ('0','1','2','UNKNOWN'), 'Reply dimension N/A '+cid)
        if kind=='SINGLE':
            require(original['split']=='DEV' and original['model_call_count']==0, 'Single source status')
            require(all(original['evaluation'][k] is None for k in ('naturalness_human','usefulness_human','independent_gold','owner_signoff')), 'Original human blanks')
            require(r['input_hash']==EmailInput(email_id=cid, subject=original['subject'],body=original['body']).input_hash, 'Input hash')
            require(r['reply_hash']==entry['reply_sha256']==hashlib.sha256(original['customer_reply'].encode()).hexdigest(), 'Reply hash')
            require(entry['semantic_group_proposal'], 'Missing semantic group')
            checks=json.loads(r['hard_error_checks_json'])
            require(set(checks)=={'H01','H02','H03','H04','H05','H06','H07'}, 'Hard-error checklist')
            require(set(checks.values()) <= {'PRESENT','ABSENT','UNKNOWN','NOT_ASSESSED'}, 'Hard-error states')
        if kind=='CONVERSATION':
            require(original['human_gold'] is None and original['human_naturalness'] is None and original['model_calls']==0, 'Conversation source status')
            require(r['state_update'] and r['first_reply_diagnosis'] and set(json.loads(r['first_reply_scores_json']))=={f'B{i}' for i in range(1,6)}, 'Both turns reviewed')
        if kind=='BAD_CASE':
            require(original['human_scores'] is None and original['owner_acceptance'] is None, 'Bad case human status')
            for field in ('before_reply','after_reply_candidate'):
                saved=original['before_reply_hash' if field=='before_reply' else 'after_reply_hash']
                # Historical P5-A uses canonical JSON digest(str), including quotes.
                # New raw text SHA-256 fields must not reinterpret that old identity.
                require(digest(original[field])==saved, 'Bad reply hash')
            require(r['before_reply_hash']==original['before_reply_hash'] and r['before_scores_json'], 'Before/after review')
        if kind=='KNOWLEDGE':
            require(original['owner_approval']=='OWNER_PENDING' and original['use_in_model']=='NO' and original['approved_by'] is None, 'Unapproved knowledge used')
        for ev in json.loads(r['evidence_json']):
            field=ev['field']
            if field=='claims':
                text=json.dumps(original['claims'], ensure_ascii=False)
            elif field in ('turns[0].body','turns[2].body'):
                text=original['turns'][int(field[6])]['body']
            else:
                text=original[field]
            require(type(ev['start']) is int and type(ev['end']) is int and 0<=ev['start']<ev['end']<=len(text) and text[ev['start']:ev['end']]==ev['quote'], 'Evidence span '+cid)

    refs=read(package/'owner_accepted_references_v1.json')
    anchors=unique(refs['anchors'], 'id')
    require(refs['identity']=='OWNER_ACCEPTED_DEV_REFERENCE' and refs['independent_gold'] is False, 'Anchor identity')
    require(refs['human_scores'] is None and refs['researcher_signature'] is None, 'Anchor unsigned fields')
    require(set(anchors)==set(ANCHOR_REPLY_SHA256), 'Three anchors required')
    md=(package/'GOLD_ANCHORS_v1.md').read_text(encoding='utf-8')
    for rid,a in anchors.items():
        require(a['customer']==originals[a['source_case_id']][1]['body'], 'Anchor customer '+rid)
        require(hashlib.sha256(a['reply'].encode()).hexdigest()==ANCHOR_REPLY_SHA256[rid], 'Frozen owner reply '+rid)
        require('> '+a['customer'] in md and '> '+a['reply'].replace('\n','\n> ') in md, 'Full markdown anchor '+rid)
        require(a['acceptance_conditions'] in md and a['revision_suggestion_only'] in md, 'Anchor conditions')

    overlay=read(package/'DEV_RECORD_CORRECTIONS_v1.json')
    corrections=unique(overlay['records'], 'case_id')
    singles={cid for cid,(k,_) in originals.items() if k=='SINGLE'}
    require(set(corrections)==singles and overlay['applied_to_product'] is False, 'Overlay coverage/application')
    for cid,c in corrections.items():
        require(c['human_approval'] is None and c['source_record_hash']==digest(originals[cid][1]), 'Overlay approval/binding')
        change=c['changes'][0]
        require(change['path']=='understanding.customer_goal' and change['before']==originals[cid][1]['understanding']['customer_goal'] and change['after'], 'Overlay diff')

    pack=read(package/'HUMAN_CALIBRATION_PACK_v1.json')
    require(pack['identity']=='DEV_DIAGNOSTIC' and pack['blind'] is False and pack['human_calibration_status']=='PENDING', 'Calibration identity')
    packets=unique(pack['packets'],'record_id')
    require(12<=len(packets)<=16, 'Calibration size')
    pack_md=(package/'HUMAN_CALIBRATION_PACK.md').read_text(encoding='utf-8')
    for cid,p in packets.items():
        require(p['original']==originals[cid][1] and p['source_record_hash']==digest(p['original']), 'Full packet original '+cid)
        require(all(str(p['diagnostic'].get(k,''))==v for k,v in audit[cid].items()), 'Packet diagnosis binding '+cid)
        require(all(p[k] is None for k in ('human_scores','human_hard_errors','human_actions','human_decision','reviewer','researcher_signature')), 'Calibration human fields filled')
        c=p['original']
        texts=[c['body'],c['customer_reply']] if 'body' in c else [t['body'] for t in c['turns']]+[c['turn2_customer_reply']]
        require(all('> '+t.replace('\n','\n> ') in pack_md for t in texts), 'Full packet markdown '+cid)
    summary=read(package/'AUDIT_SUMMARY_v1.json')
    require(summary['coverage']=={k:v[2] for k,v in KINDS.items()} and summary['audit_rows']==61, 'Summary counts')
    require(summary['direct_answer_runtime_count']==0 and summary['known_facts_full_body_count']==45 and summary['single_cases_with_whole_issue_span']==45, 'Summary source findings')
    require(summary['human_scores_filled']==0 and summary['human_threshold_status']=='OWNER_PENDING' and summary['quality_improvement_claim'] is False, 'Unjustified quality claim')
    return dict(status='PASS', identity='DEV_DIAGNOSTIC', semantic_certification=False, coverage=summary['coverage'],
                anchors_exact=3, calibration_records=len(packets), human_scores_filled=0,
                independent_gold_created=False, new_paid_calls=0, real_email_sends=0)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    print(json.dumps(validate(parser.parse_args().root), ensure_ascii=False, indent=2))
