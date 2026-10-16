"""Unsigned AI opinion packets with exact input/output citations, never Gold."""
from src.domain.analysis_v3 import stored_analysis
from src.domain.contracts import digest

DIMENSIONS=('important_issues','evidence_support','summary_facts','reply_requests',
            'repeated_information','unauthorized_claims','language_and_tone','safety_privacy_multi')
LEVELS=('none','low','medium','high','critical')
VERSION='p37-semantic-preparation-1'


def source_text(run, path):
    if path=='input.subject':return run.email.subject
    if path=='input.body':return run.email.body
    if path.startswith('analysis.') and run.result:
        node=stored_analysis(run).model_dump()
        for part in path.split('.')[1:]:node=node[int(part)] if isinstance(node,list) else node[part]
        return str(node)
    raise ValueError('Unknown or unaccepted citation source')


def build_review(run, opinions=None):
    dimensions={}
    if run.result and (not opinions or set(opinions)!=set(DIMENSIONS)):
        raise ValueError('All eight independent content dimensions required')
    for name in DIMENSIONS:
        if not run.result:
            dimensions[name]=dict(severity='none',opinion='无正式接受输出；本维度不可评分，原始失败另行归因。',
                                  evidence=[],human_score=None,applicability='unaccepted_output')
            continue
        severity,opinion,quotes=opinions[name]
        if severity not in LEVELS or not opinion or not quotes:raise ValueError('Opinion needs severity and citations')
        evidence=[]
        for path,quote in quotes:
            text=source_text(run,path)
            if not quote or quote not in text:raise ValueError('AI citation absent from original: '+path)
            start=text.index(quote)
            evidence.append(dict(source=path,start=start,end=start+len(quote),quote=quote))
        dimensions[name]=dict(severity=severity,opinion=opinion,evidence=evidence,human_score=None,applicability='pending_human')
    packet=dict(protocol=VERSION,run_id=run.run_id,sample_id=run.email.email_id,input_hash=run.input_hash,
        config_hash=digest(run.config.model_dump()),cohort_id=run.cohort_id,output_hash=run.metadata.get('analysis_v3_hash'),
        raw_hashes=[digest(a.raw_output) for a in run.attempts],source_status=run.status,
        original_input=run.email.model_dump(),original_analysis=stored_analysis(run).model_dump() if run.result else None,
        dimensions=dimensions,max_ai_severity=max((d['severity'] for d in dimensions.values()),key=LEVELS.index),
        ai_opinions_only=True,human_status='pending',human_reviewer=None,human_declaration=False,
        official_semantic_accuracy=None,critical_errors_human_confirmed=None)
    packet['packet_hash']=digest(packet)
    return packet


def validate_review(run, packet):
    copy=dict(packet);claim=copy.pop('packet_hash')
    if digest(copy)!=claim:raise ValueError('Review packet hash mismatch')
    if packet['human_status']!='pending' or packet['human_reviewer'] is not None or packet['human_declaration']:
        raise ValueError('This is preparation, not a human approval importer')
    if set(packet['dimensions'])!=set(DIMENSIONS):raise ValueError('Missing review dimension')
    opinions={}
    for name,item in packet['dimensions'].items():
        if item['human_score'] is not None:raise ValueError('AI cannot sign human scores')
        for ev in item['evidence']:
            text=source_text(run,ev['source'])
            if text[ev['start']:ev['end']]!=ev['quote']:raise ValueError('Invalid review citation')
        opinions[name]=(item['severity'],item['opinion'],[(e['source'],e['quote']) for e in item['evidence']])
    expected=build_review(run,opinions if run.result else None)
    if expected!=packet:raise ValueError('Review/source identity mismatch')
    return packet
