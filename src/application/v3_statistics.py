"""Separate email-revision and issue denominators, with original-run membership."""
from collections import Counter
from src.domain.analysis_v3 import stored_analysis
from src.domain.contracts import digest,idempotency_key


def snapshot(runs,cohort_id,dataset_id):
    if not cohort_id or not dataset_id: raise ValueError('Explicit cohort and dataset required')
    selected=[];seen=set()
    for r in runs:
        if r.run_id in seen: raise ValueError('Duplicate run ID')
        seen.add(r.run_id)
        if r.cohort_id!=r.config.cohort_id or r.input_hash!=r.email.input_hash or r.idempotency_key!=idempotency_key(r.email,r.config):
            raise ValueError('Run binding mismatch')
        if r.cohort_id!=cohort_id: raise ValueError('Mixed cohorts rejected')
        if (r.config.parameters or {}).get('dataset_id')!=dataset_id: raise ValueError('Dataset binding mismatch')
        selected.append(r)
    latest={}
    for r in sorted(selected,key=lambda x:(x.created_at,x.run_id)):
        latest[(r.email.email_id,r.input_hash)]=r
    rows=list(latest.values());good=[];issues=[]
    for r in rows:
        if r.status=='succeeded' and r.result and not r.metadata.get('fallback'):
            a=stored_analysis(r);good.append((r,a))
            issues.extend((r,i) for i in a.issues)
    def metric(members,denominator,unit):
        return dict(numerator=len(members),denominator=len(denominator),rate=len(members)/len(denominator) if denominator else None,
                    unit=unit,members=members,denominator_members=denominator)
    email_ids=[r.run_id for r in rows];success_ids=[r.run_id for r,a in good]
    issue_ids=[{'run_id':r.run_id,'issue_id':i.issue_id} for r,i in issues]
    groups={}
    for dim in ('category','reason','business_process','sentiment','resolution'):
        groups[dim]={v:metric([{'run_id':r.run_id,'issue_id':i.issue_id} for r,i in issues if getattr(i,dim)==v],issue_ids,'issues')
                     for v in sorted({getattr(i,dim) for r,i in issues})}
    stores={v:metric([r.run_id for r,a in good if a.mentioned_store==v],success_ids,'email_revisions') for v in sorted({a.mentioned_store for r,a in good})}
    return dict(cohort_id=cohort_id,dataset_id=dataset_id,config=rows[0].config.model_dump() if rows else None,email_revisions=len(rows),successful_email_revisions=len(good),issue_count=len(issues),
        states=dict(Counter('fallback' if r.metadata.get('fallback') else r.status for r in rows)),
        current_complaints=metric([r.run_id for r,a in good if a.complaint_status=='current_unresolved'],email_ids,'email_revisions'),
        issue_groups=groups,store_groups=stores,
        members=[dict(run_id=r.run_id,email_id=r.email.email_id,input_hash=r.input_hash,cohort_id=r.cohort_id,
                      output_hash=r.metadata.get('analysis_v3_hash'),subject=r.email.subject,body=r.email.body) for r in rows],
        superseded_run_ids=[r.run_id for r in selected if r.run_id not in email_ids])
