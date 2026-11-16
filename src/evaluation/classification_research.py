from src.infrastructure.research_paths import research_path
"""Offline classification research. References remain development references."""
import json
import re
from collections import Counter
from pathlib import Path

from src.application.research_insights import FIELDS, read_csv, file_hash
from src.dataset.build_i5c_deepseek_prediction_dashboard_stats_v1 import product_ranking, store_ranking
from src.domain.contracts import EmailInput


def norm(value):
    return str(value).strip().lower()


def classification(pairs):
    """Missing predictions are errors; absent true labels are outside scope."""
    pairs=[(norm(g),norm(p) if p is not None else '__failed__') for g,p in pairs if g is not None]
    labels=sorted({v for pair in pairs for v in pair if v!='__failed__'})
    columns=labels+(['__failed__'] if any(p=='__failed__' for _,p in pairs) else [])
    matrix=[[sum(g==a and p==b for g,p in pairs) for b in columns] for a in labels]
    per={}
    for label in labels:
        tp=sum(g==p==label for g,p in pairs);support=sum(g==label for g,p in pairs);predicted=sum(p==label for g,p in pairs)
        precision=tp/predicted if predicted else 0.;recall=tp/support if support else 0.
        per[label]=dict(precision=precision,recall=recall,f1=2*precision*recall/(precision+recall) if precision+recall else 0.,support=support,predicted=predicted,tp=tp)
    n=len(pairs);correct=sum(g==p for g,p in pairs)
    return dict(n=n,correct=correct,accuracy=correct/n if n else None,macro_f1=sum(r['f1'] for r in per.values())/len(labels) if labels else None,
        prediction_coverage=sum(p!='__failed__' for _,p in pairs)/n if n else None,classes=per,labels=labels,columns=columns,confusion=matrix,
        macro_definition='union of observed reference and predicted labels, excluding __failed__; zero division=0; failures remain false negatives')


def phenomena(text):
    tags=[]
    for label,pattern in [('negation',r'\bnot\b|\bno\b|never|不|没|无'),('mixed_or_contradictory',r'\bbut\b|however|但是|但|虽然'),('sarcasm_candidate',r'great job|wonderful|真棒|讽刺'),('multi_turn',r'\[customer|\[assistant|之前|上次')]:
        if re.search(pattern,text,re.I):tags.append(label)
    tags.append('zh_or_mixed' if re.search('[\u4e00-\u9fff]',text) else 'en')
    return tags


def evaluate_cases(name, cases, identity, files):
    fields={f:classification([(c['expected'].get(f),(c['prediction'] or {}).get(f)) for c in cases]) for f in FIELDS}
    errors=[]
    for c in cases:
        mismatches=[dict(field=f,expected=c['expected'].get(f),prediction=(c['prediction'] or {}).get(f)) for f in FIELDS
                    if c['expected'].get(f) is not None and norm(c['expected'][f])!=norm((c['prediction'] or {}).get(f))]
        if mismatches: errors.append(dict(**c,mismatches=mismatches,phenomena=phenomena(c['email']['body']),interpretation='Lexical phenomenon tags are diagnostic candidates; not independently annotated error types'))
    expected=[c['expected'] for c in cases];predicted=[c['prediction'] for c in cases if c['prediction']]
    def rankings(rows):
        return dict(products=product_ranking(rows),stores=store_ranking(rows))
    expected_rank=rankings(expected);predicted_rank=rankings(predicted);rank_deltas={}
    for dim,key,count in [('products','product_category','negative_count'),('stores','store_location','complaint_count')]:
        a={r[key]:r for r in expected_rank[dim]};b={r[key]:r for r in predicted_rank[dim]}
        def rank(rows,value):return 1+sum(r[count]>value for r in rows)
        rank_deltas[dim]=dict(common_labels=[dict(label=k,reference_count=a[k][count],predicted_count=b[k][count],reference_rank=rank(a.values(),a[k][count]),predicted_rank=rank(b.values(),b[k][count])) for k in sorted(a.keys()&b.keys())],
            reference_only=sorted(a.keys()-b.keys()),prediction_only=sorted(b.keys()-a.keys()),tie_rule='competition rank by relevant count; identical counts share rank',
            interpretation='Common exact labels only; unmatched product taxonomy labels are not semantic ranking errors. Count discrepancies combine extraction, sentiment/complaint and missing-output effects; no isolated causal attribution.')
    strata={}
    for tag in sorted({t for c in cases for t in phenomena(c['email']['body'])}):
        subset=[c for c in cases if tag in phenomena(c['email']['body'])]
        strata[tag]=dict(n=len(subset),sentiment=classification([(c['expected'].get('sentiment'),(c['prediction'] or {}).get('sentiment')) for c in subset]),identity='LEXICAL_CANDIDATE_STRATUM_NOT_HUMAN_PHENOMENON_GOLD')
    clean=[c for c in cases if not c.get('exclude_clean_semantic')]
    accepted=[c for c in cases if c['prediction'] is not None]
    scopes=dict(accepted_only=dict(n=len(accepted),fields={f:classification([(c['expected'].get(f),c['prediction'].get(f)) for c in accepted]) for f in FIELDS},
        note='Conditional on accepted outputs; does not replace all-task or API reliability denominators'),
        clean_reference=dict(n=len(clean),excluded_ids=[c['email']['email_id'] for c in cases if c.get('exclude_clean_semantic')],
            fields={f:classification([(c['expected'].get(f),(c['prediction'] or {}).get(f)) for c in clean]) for f in FIELDS},
            note='Respects pre-existing reference exclusion flags; no new relabeling or exclusion'))
    return dict(id=name,identity=identity,n=len(cases),files=files,fields=fields,errors=errors,phenomenon_strata=strata,
        scope_metrics=scopes,
        prediction_states=dict(attempted=sum(bool(c.get('run_id') or c['prediction']) for c in cases),accepted=sum(c['prediction'] is not None for c in cases),not_run=sum(not c.get('run_id') and c['prediction'] is None for c in cases),
            rejected=sum(bool(c.get('run_id')) and c['prediction'] is None for c in cases)),
        case_ids=[c['email']['email_id'] for c in cases],input_hashes=[c['input_hash'] for c in cases],
        whole_email_correct=sum(all(c['expected'].get(f) is not None and c['prediction'] and norm(c['expected'][f])==norm(c['prediction'].get(f)) for f in FIELDS) for c in cases),
        rank_impact=dict(reference=expected_rank,prediction=predicted_rank,deltas=rank_deltas,reference_denominator=len(expected),prediction_denominator=len(predicted),
                         note='Same labeled development cohort; rejected/missing outputs excluded only from predicted business rates and explicitly counted. Not a causal/market finding.'),
        issue_accuracy=None,issue_accuracy_reason='No independent issue-level sentiment/matching labels; global/issue agreement is descriptive only')


def build_report(root, insights):
    root=Path(root);reports=[]
    gpath=research_path(root, 'data/golden/golden_labels_review_sample_v1_reviewed.csv')
    gold={r['email_id']:r for r in read_csv(gpath)}
    emails={r['email_id']:r for r in read_csv(research_path(root, 'data/synthetic/customer_emails_full_v1.csv'))}
    for name,p in [('historical80-raw',research_path(root, 'outputs/i4e2_reviewed_80_raw_predictions_v1.csv')),('historical80-normalized',research_path(root, 'outputs/i4e2_reviewed_80_predictions_v1.csv'))]:
        if not p.exists():continue
        predictions={r['email_id']:r for r in read_csv(p)};cases=[]
        for eid,g in gold.items():
            e=emails[eid];email=EmailInput(email_id=eid,subject=e['subject'],body=e['email_body']);pred=predictions.get(eid)
            cases.append(dict(email=email.model_dump(),input_hash=email.input_hash,expected={f:g[f] for f in FIELDS},prediction=pred,
                template=e['generation_template_id'],reference_source=g.get('review_source'),reference_status=g.get('review_status')))
        reports.append(evaluate_cases(name,cases,'HISTORICAL_REVIEWED_PROJECT_REFERENCE_NOT_INDEPENDENT_GOLD',
            {str(x.relative_to(root)).replace('\\','/'):file_hash(x) for x in [gpath,p]}))
    spath=research_path(root, '.local/p35/calibration-decision-v1.1/snapshot.json')
    snapshot=json.loads(spath.read_text(encoding='utf-8'))
    adjudications=snapshot['records'];cases24=[]
    for r in adjudications:
        o=r['original'];email=EmailInput(email_id=r['sample_id'],subject=o['subject'],body=o['email_body'])
        if email.input_hash!=r['input_hash']:raise ValueError('Adjudication input mismatch')
        cases24.append(dict(email=email.model_dump(),input_hash=email.input_hash,expected=r['decision']['owner_confirmed'],scenarios=o.get('scenarios',[]),
            reference_status='RESEARCH_OWNER_REVIEWED_AI_ASSISTED_NOT_INDEPENDENT_GOLD',exclude_clean_semantic=r['decision']['exclude_clean_semantic']))
    for source in insights.catalog():
        if not source['id'].startswith('p36-'): continue
        records=insights.records[source['id']];by_input={}
        for r in sorted(records,key=lambda x:(x['created_at'],x['id'])):by_input[r['input_hash']]=r
        cases=[dict(c,prediction=by_input.get(c['input_hash'],{}).get('prediction'),run_id=by_input.get(c['input_hash'],{}).get('run_id')) for c in cases24]
        reports.append(evaluate_cases(source['id'],cases,'AI_ASSISTED_OWNER_DEVELOPMENT_ADJUDICATION_24_NOT_GOLD',dict(source['input_files'],**{str(spath.relative_to(root)).replace('\\','/'):file_hash(spath)})))
    overlap=[]
    reviewed_hashes={EmailInput(email_id=eid,subject=emails[eid]['subject'],body=emails[eid]['email_body']).input_hash:eid for eid in gold}
    hash_overlap=[dict(calibration_id=c['email']['email_id'],reviewed_id=reviewed_hashes[c['input_hash']]) for c in cases24 if c['input_hash'] in reviewed_hashes]
    for c in cases24:
        eid=c['email']['email_id']
        if eid in gold:
            e=emails[eid];overlap.append(dict(email_id=eid,same_input=EmailInput(email_id=eid,subject=e['subject'],body=e['email_body']).input_hash==c['input_hash'],
                changed_fields=[f for f in FIELDS if norm(gold[eid][f])!=norm(c['expected'][f])]))
    agreements=[]
    for s in insights.catalog():
        records=insights.records[s['id']];eligible=[r for r in records if r['issues'] and r.get('global_sentiment')]
        if eligible:
            agreements.append(dict(source=s['id'],emails=len(eligible),
                all_issues_same_as_global=sum(all(i['sentiment']==r['global_sentiment'] for i in r['issues']) for r in eligible),
                at_least_one_issue_differs=sum(any(i['sentiment']!=r['global_sentiment'] for i in r['issues']) for r in eligible),
                multi_issue=sum(len(r['issues'])>1 for r in eligible),identity='DESCRIPTIVE_MODEL_INTERNAL_AGREEMENT_NOT_ACCURACY'))
    templates=Counter(e['generation_template_id'] for e in emails.values())
    split_groups={t:{'reviewed80':sum(eid in gold for eid,e in emails.items() if e['generation_template_id']==t),'outside_reviewed80':sum(eid not in gold for eid,e in emails.items() if e['generation_template_id']==t)} for t in templates}
    shared=[t for t,c in split_groups.items() if c['reviewed80'] and c['outside_reviewed80']]
    common24=[c['email']['email_id'] for c in cases24 if all(any(r['input_hash']==c['input_hash'] for r in insights.records[s['id']]) for s in insights.catalog() if s['id'].startswith('p36-'))]
    paired=[]
    for source in insights.catalog():
        if not source['id'].startswith('p36-'):continue
        records=sorted(insights.records[source['id']],key=lambda x:(x['created_at'],x['id']))
        by_input={r['input_hash']:r for r in records}
        paired.append(dict(source=source['id'],n=len(common24),fields={f:classification([(c['expected'][f],(by_input.get(c['input_hash'],{}).get('prediction') or {}).get(f)) for c in cases24 if c['email']['email_id'] in common24]) for f in FIELDS}))
    return dict(version='classification-research-p5b6-v1',reports=reports,overlap=dict(n=len(overlap),cases=overlap,hash_matches=hash_overlap,calibration_ids_from400=[c['email']['email_id'] for c in cases24 if c['email']['email_id'] in emails],unique_case_ids=len(set(gold)|{c['email']['email_id'] for c in cases24}),pooled_score=None,reason='Different references, inputs and exposure; never pool cohort scores'),
        version_comparison=dict(common_observed_case_ids=common24,n_common=len(common24),paired=paired,note='Full24 scores include not-run failures; only common observed inputs support paired version comparison'),
        issue_global_consistency=agreements,leakage=dict(template_families=len(templates),shared_reviewed_vs_remaining=len(shared),shared_templates=shared,
            independent_holdout=False,note='All historical and calibration cases are development-exposed; full conversations grouped by case/input and experiment. Template overlap is not independent generalization.'),
        human_pending=dict(independent_gold='UNKNOWN',issue_sentiment='UNKNOWN',phenomenon_type_gold='UNKNOWN',naturalness='UNKNOWN',
            minimum_review='Review unique sentiment mismatches first; then independent cases covering praise/complaint/inquiry/negation/contradiction/multiple issues/multi-turn/missing objects and zh/en, without exposing model predictions. Do not reapprove old owner decisions.'))
