"""Read-only, multi-finding quality diagnostics. Never creates predictions or Gold."""
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator
from src.application.live_execution import strict_json
from src.application.urgency_context_v1 import signals, visible, bare_help
from src.application.reply_review import inspect_reply, check
from src.application.research_policy_v2 import requested_language, language
from src.domain.analysis_v31 import AnalysisV31
from src.domain.analysis_v31_context import ContextAnalysisV31
from src.domain.contracts import EmailInput, digest
from src.evaluation.semantic_review_v2 import GUIDANCE

VERSION = 'p310-multiple-findings-v1'


def acceptance(raw, email, profile='original'):
    stage = 'parsing'
    try:
        data = strict_json(raw)
        stage = 'schema_cross_fields'
        if profile == 'corrected':
            from src.domain.analysis_v31_recovery import RecoveryAnalysisV31
            cls = RecoveryAnalysisV31
        elif profile == 'original':
            cls = ContextAnalysisV31
        elif profile == 'policy-v2':
            cls = AnalysisV31
        else:
            raise ValueError('Unknown diagnostic profile')
        value = cls.model_validate(data)
        stage = 'source_semantics'
        value.validate_input(email)
        stage = 'reply_gate'
        check(value)
        return dict(accepted=True, stage='accepted', error=None, diagnostic_only=True)
    except (ValueError, TypeError) as exc:
        return dict(accepted=False, stage=stage, error=str(exc), diagnostic_only=True)


def diagnostics(raw, email):
    """Each predicate runs independently; invalid shape doesn't hide other fields.

    Rules below diagnose bounded engineering constraints. Semantic support still
    needs a source reader. No caller can promote these findings into an old run.
    """
    findings = []

    def add(stage, code, path, explanation, evidence=None, owner='model_or_prompt', certainty='deterministic'):
        findings.append(dict(stage=stage, mechanism=code, path=path, explanation=explanation,
                             evidence=evidence, owner=owner, certainty=certainty,
                             severity_candidate='major', human_confirmed=None))

    try:
        data = strict_json(raw)
    except (ValueError, TypeError) as exc:
        add('parsing', 'invalid_json', '$', 'Strict JSON parsing failed')
        if str(exc)!='Duplicate JSON key':return findings
        # Readable duplicate-key raw can still expose other independent defects.
        # Last-key interpretation is diagnostic only; strict acceptance stays
        # rejected and the original raw is never rewritten or persisted as a run.
        try:data=json.loads(raw)
        except (ValueError,TypeError):return findings
        add('parsing','duplicate_key_diagnostic_interpretation','$','Additional field checks use a last-key diagnostic interpretation; ambiguous duplicates need correction',certainty='diagnostic_only_not_prediction')
    for error in Draft202012Validator(AnalysisV31.model_json_schema()).iter_errors(data):
        add('shape', 'required_or_shape', '$.'+'.'.join(map(str, error.absolute_path)), error.message)
    if not isinstance(data, dict):
        return findings
    issues = data.get('issues')
    issues = issues if isinstance(issues, list) else []
    issues = [(n,i) for n,i in enumerate(issues) if isinstance(i, dict)]
    signatures = []; ids = []

    def evs(obj, field):
        v = obj.get(field, [])
        return [e for e in v if isinstance(e, dict)] if isinstance(v,list) else []

    def quotes(obj, field):
        return '\n'.join(e.get('quote','') for e in evs(obj,field) if isinstance(e.get('quote'),str))

    def valid_span(e):
        field=e.get('field'); start=e.get('start'); end=e.get('end'); quote=e.get('quote')
        return (field in ('subject','body') and type(start) is int and type(end) is int
                and 0<=start<end<=len(getattr(email,field)) and getattr(email,field)[start:end]==quote)

    for n, i in issues:
        path=f'$.issues.{n}'; ids.append(i.get('issue_id'))
        evidence=evs(i,'evidence')
        signatures.append(tuple(sorted((e.get('field',''),str(e.get('start')),str(e.get('end')),str(e.get('quote'))) for e in evidence)))
        if not evidence or i.get('extraction_basis','native')!='native':
            add('cross_fields','native_evidence',path,'Native issue must have source evidence')
        if i.get('issue_kind')=='complaint' and i.get('reason')=='none':
            add('cross_fields','complaint_reason',path,'Complaint reason cannot be none')
        if i.get('customer_importance') not in ('unspecified',None) and not evs(i,'importance_evidence'):
            add('cross_fields','importance_without_evidence',path,'Importance needs evidence')
        if (i.get('handling_priority') is None)!=(i.get('priority_rationale') is None):
            add('cross_fields','priority_rationale_pair',path,'Priority/rationale must be supplied together')
        for field in ('risk_rationale','priority_rationale'):
            if isinstance(i.get(field),str) and not i[field].strip():
                add('cross_fields','blank_text',path+'.'+field,'Required explanation cannot be blank')
        if i.get('business_process') in ('unclear','unknown') and not i.get('missing_evidence'):
            add('cross_fields','missing_uncertainty',path,'Uncertain attribution needs missing evidence')
        risk=i.get('risk_level'); urgency=i.get('urgency'); basis=i.get('urgency_basis')
        if risk in ('minor','severe') and not evs(i,'risk_evidence'):
            add('cross_fields','risk_without_evidence',path,'Risk needs original evidence')
        if i.get('reason')=='health or safety issue' and risk not in ('minor','severe'):
            add('cross_fields','safety_reason_risk',path,'Safety reason contradicts risk assessment')
        if risk=='severe' and urgency!='high':
            add('cross_fields','severe_not_high',path,'Severe risk requires high urgency')
        if i.get('reason')=='billing/invoice issue' or i.get('business_process')=='billing/invoice issue':
            if (i.get('reason'),i.get('business_process'),i.get('routing_team'))!=('billing/invoice issue','billing/invoice issue','customer_support'):
                add('cross_fields','billing_coordination',path,'Invoice type and customer_support coordination required')
        for field in ('evidence','importance_evidence','urgency_evidence','risk_evidence'):
            for k,e in enumerate(evs(i,field)):
                if not valid_span(e):
                    add('source_spans','source_span',path+f'.{field}.{k}','Span differs from original or is out of bounds',e)
        joined='\n'.join(visible(getattr(email,e['field']))[e['start']:e['end']] for e in evs(i,'urgency_evidence') if valid_span(e))
        facts=signals(joined,already_visible=True)
        if basis=='general_help' and (not bare_help(email.body) or not facts['bare_help']):
            add('source_semantics','general_help_specific',path,'Concrete matter is not undifferentiated help',quotes(i,'urgency_evidence'))
        if basis=='general_help' and risk!='severe' and urgency!='medium':
            add('source_semantics','basis_label_conflict',path,'Bare help defaults to medium')
        for name,key in (('explicit_urgent','urgent'),('explicit_relaxed','relaxed'),('repeated_failure','repeated_failure')):
            if basis==name and not facts[key]:
                add('source_semantics','unsupported_'+name,path,'Named basis lacks bounded source support; independently inspect false rejection',quotes(i,'urgency_evidence'),certainty='bounded_validator_finding')
        if basis=='safety' and (risk not in ('minor','severe') or not evs(i,'risk_evidence')):
            add('source_semantics','safety_basis',path,'Safety basis needs assessed risk and source')
        if basis=='unknown' and urgency not in ('unknown',None):
            add('source_semantics','unknown_basis_known_urgency',path,'Known urgency cannot use unknown basis')
        if risk!='severe' and not facts['ambiguous']:
            bad=(basis=='explicit_urgent' and urgency!='high'
                 or basis=='explicit_relaxed' and urgency!='low' and not (facts['urgent'] or facts['deadline'])
                 or basis=='repeated_failure' and urgency!='medium' and not (facts['urgent'] or facts['deadline'] or facts['relaxed']))
            if bad: add('source_semantics','basis_label_conflict',path,'Urgency contradicts unqualified basis')
        if i.get('customer_importance')=='equal' and not re.search(r'equal|equally|same importance|同等重要|一样重要|同样重要',quotes(i,'importance_evidence'),re.I):
            add('source_semantics','together_not_equal',path,'Together does not establish equal importance',quotes(i,'importance_evidence'))
    if len(set(map(str,ids)))!=len(ids): add('cross_fields','duplicate_issue_id','$.issues','Duplicate issue IDs')
    if len(set(signatures))!=len(signatures): add('cross_fields','duplicate_event_evidence','$.issues','Identical evidence lists cannot distinguish events')
    unresolved=any(i.get('issue_kind')=='complaint' and i.get('resolution')=='unresolved' for _,i in issues)
    if (unresolved and data.get('complaint_status') in ('resolved','no_complaint')
        or not unresolved and data.get('complaint_status')=='current_unresolved'):
        add('cross_fields','email_issue_resolution','$.complaint_status','Email status conflicts with issue kinds/resolution')
    if any(i.get('urgency')=='high' for _,i in issues) and data.get('urgency')!='high':
        add('cross_fields','email_hides_high','$.urgency','Email urgency hides a high urgency issue')
    for field in ('mentioned_store','summary','suggested_reply'):
        if isinstance(data.get(field),str) and not data[field].strip(): add('cross_fields','blank_text','$.'+field,'Blank required text is not unknown')
    relations=data.get('relations',[])
    for n,r in enumerate(relations if isinstance(relations,list) else []):
        if not isinstance(r,dict): continue
        ends=(r.get('from_issue'),r.get('to_issue'))
        if ends[0]==ends[1] or any(e not in ids for e in ends): add('cross_fields','relation_endpoints',f'$.relations.{n}','Invalid relation endpoints')
        if r.get('kind')=='equal_importance' and any(i.get('customer_importance')!='equal' for _,i in issues if i.get('issue_id') in ends):
            add('cross_fields','relation_importance',f'$.relations.{n}','Equal relation contradicts issue importance')
        for k,e in enumerate(evs(r,'evidence')):
            if not valid_span(e): add('source_spans','source_span',f'$.relations.{n}.evidence.{k}','Relation span mismatch',e)
    global_facts=signals(email.subject+'\n'+email.body)
    if global_facts['severe'] and not any(i.get('risk_level')=='severe' and i.get('urgency')=='high' and signals(quotes(i,'risk_evidence'))['severe'] for _,i in issues):
        add('source_semantics','severe_anchor_downgrade','$.issues','Explicit severe source anchor omitted or downgraded',global_facts['severe'])
    reply=data.get('suggested_reply','')
    if isinstance(reply,str):
        want=requested_language(email.body);actual=language(reply)
        if want in ('en','zh') and actual in ('en','zh') and want!=actual:
            add('source_semantics','reply_language','$.suggested_reply','Wrong customer reply language',dict(want=want,actual=actual))
        if data.get('reply_language') in ('en','zh') and actual in ('en','zh') and data['reply_language']!=actual:
            add('source_semantics','declared_language','$.reply_language','Reply language differs from declaration')
        for f in inspect_reply(reply)['findings']:
            add('reply_gate',f['kind'],'$.suggested_reply','Unverified reply claim requires review',f,certainty='lexical_review_candidate')
    return findings


def normalized_dimension(value, scope):
    label=value.get('verdict_candidate','UNVERIFIED').upper()
    state=('not_applicable' if 'NOT_APPLICABLE' in label else 'defect_candidate' if any(x in label for x in ('MAJOR','MINOR','CRITICAL','DEFECT','REJECT','CONCERN')) else 'supported_candidate' if any(x in label for x in ('PASS','ACCEPTABLE','NO_ISSUE_OBSERVED')) else 'unresolved')
    severity=('critical' if 'CRITICAL' in label else 'major' if any(x in label for x in ('MAJOR','DEFECT','REJECT')) else 'minor' if 'MINOR' in label else None)
    return dict(state=state,severity_candidate=severity,scope=scope,reason=value.get('ai_opinion',''),
                evidence=value.get('evidence_quote',''),structured_evidence=value.get('evidence',[]),original_label=label,human_score=None,human_critical_error=None,
                adjudication='assistant_candidate_pending_human')


def build(report, notes):
    rows=[]
    for member in report['members']:
        raw=member['attempts'][-1]['raw_output'];email=EmailInput.model_validate(member['original_email'])
        source=member['assistant_semantic_review']
        if (member['input_hash']!=email.input_hash or source['raw_sha256']!=sha256(raw.encode()).hexdigest()
            or source['run_id']!=member['run_id'] or set(source['dimensions'])!=set(GUIDANCE)):
            raise ValueError('Historical input/raw/review binding drift')
        scope='accepted_output' if member['state']=='succeeded' else 'failed_raw_diagnostic_only'
        independent=diagnostics(raw,email)
        original=acceptance(raw,email)
        if original['accepted']!=(member['state']=='succeeded'): raise ValueError('Original acceptance replay drift')
        note=notes[str(member['pair'])]
        dimensions={k:normalized_dimension(v,scope) for k,v in source['dimensions'].items()}
        stage_order={k:n for n,k in enumerate(('parsing','shape','cross_fields','source_spans','source_semantics','reply_gate'))}
        row=dict(pair=member['pair'],sample_id=member['sample_id'],arm=member['arm'],run_id=member['run_id'],
                 input_hash=email.input_hash,raw_sha256=sha256(raw.encode()).hexdigest(),config_hash=member['config_hash'],
                 original_status=member['state'],original_earliest_failure=member['diagnosis'],
                 original_email=email.model_dump(),raw_output=raw,raw_prediction=strict_json(raw),
                 findings=independent,earliest_deterministic_stage=min((f['stage'] for f in independent),key=stage_order.get) if independent else None,
                 independent_findings_count=len(independent),dimensions=dimensions,
                 source_review_hash=digest(source),reading_note=note,
                 suggested_adjudication=note['common']+' '+note.get(member['arm'],''),
                 source_factual_failure_status='see source-cited18 dimensions and reading note; engine stage is not proof of factual onset',
                 likely_common_mechanisms=sorted(set(f['mechanism'] for f in independent)),
                 reference_or_policy_ambiguity='F176 source naturalness; inquiry process domain; identical whole-sentence evidence policy; see reading note',
                 confirmed_model_errors=[f for f in independent if f['certainty']=='deterministic'],
                 possible_validator_false_rejections=[f for f in independent if f['certainty']=='bounded_validator_finding'],
                 original_profile=original,policy_v2_profile=acceptance(raw,email,'policy-v2'),
                 corrected_profile=acceptance(raw,email,'corrected'),
                 human_semantic_score=None,human_review='pending',prediction_substituted=False)
        rows.append(row)
    if len(rows)!=64 or sum(r['original_status']=='succeeded' for r in rows)!=34:
        raise ValueError('Frozen64 coverage drift')
    cluster=Counter(f['mechanism'] for r in rows for f in r['findings'])
    affected=Counter(k for r in rows for k in set(f['mechanism'] for f in r['findings']))
    changes=[dict(pair=r['pair'],arm=r['arm'],run_id=r['run_id'],old=r['original_profile']['accepted'],new=r['corrected_profile']['accepted'],
                  review=r['suggested_adjudication'],human_semantics=None) for r in rows if r['original_profile']['accepted']!=r['corrected_profile']['accepted']]
    body=dict(version=VERSION,source_manifest_hash=report['manifest_hash'],source_runtime_hash=report['runtime_hash'],
              denominator=64,rejected=30,accepted=34,dimensions=18,human_scores=None,
              multi_error_runs=sum(len(r['findings'])>1 for r in rows),clusters={k:dict(findings=v,affected_runs=affected[k]) for k,v in cluster.items()},
              validator_differential=changes,added_diagnostic_accepts=sum(not x['old'] and x['new'] for x in changes),
              removed_diagnostic_accepts=sum(x['old'] and not x['new'] for x in changes),
              new_erroneous_accepts_human_confirmed=None,records=rows)
    return dict(body,packet_hash=digest(body))


def export(packet,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'quality-ledger.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf8')
    for state,name in (('failed','REJECTED30.md'),('succeeded','ACCEPTED34.md')):
        lines=['# P3.10 '+name,'','助手逐条候选审核；人工分数null，历史状态不改。每项含完整原文、完整raw、18维判断及独立工程错误。','']
        for r in packet['records']:
            if r['original_status']!=state: continue
            lines += [f"## {r['pair']} / {r['arm']} / {r['sample_id']}",'',r['suggested_adjudication'],'',
                      '```json',json.dumps(r,ensure_ascii=False,indent=2),'```','']
        (out/name).write_text('\n'.join(lines),encoding='utf8')
    pairs=[]
    for n in range(1,33):
        pair=[r for r in packet['records'] if r['pair']==n]
        pairs.append(dict(pair=n,outcome='/'.join(r['original_status'] for r in sorted(pair,key=lambda r:r['arm'])),
                          records=[r['run_id'] for r in pair],review=pair[0]['reading_note'],semantic_winner=None,human_judgment=None))
    (out/'PAIRS32.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2),encoding='utf8')
    summary={k:v for k,v in packet.items() if k!='records'}
    (out/'SUMMARY.md').write_text('# P3.10 全64审计\n\n```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n',encoding='utf8')
    parts=['<!doctype html><meta charset="utf-8"><title>P3.10 complete quality audit</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}article{border-top:1px solid #aaa;padding:15px}</style><h1>P3.10 complete64 quality audit</h1><p>Assistant candidates; all human scores null. Original states preserved. All replies unsent.</p>']
    for r in packet['records']:
        parts.append('<article><h2>'+escape(f"{r['pair']} {r['arm']} {r['sample_id']} {r['original_status']}")+'</h2><p>'+escape(r['suggested_adjudication'])+'</p><h3>Original email</h3><pre>'+escape(r['original_email']['subject']+'\n'+r['original_email']['body'])+'</pre><h3>Complete prediction and reply</h3><pre>'+escape(json.dumps(r['raw_prediction'],ensure_ascii=False,indent=2))+'</pre><details><summary>Every diagnostic and18 review dimensions</summary><pre>'+escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details></article>')
    (out/'REVIEW.html').write_text('\n'.join(parts),encoding='utf8')
    return summary
