from src.infrastructure.research_paths import research_path
"""Opt-in multi-axis view of immutable B8 analysis; old cohorts are unchanged."""
import json,copy
from collections import defaultdict
from src.application.p5b7_research import B7Insights,canonical_store
from src.application.research_insights import member_metric
from src.domain.contracts import EmailInput,digest

SOURCE='b8-r5-audited'
VERSION='r5-issue-targeted-store-v1'
def store_target(issue,mentioned):
    """Conservative association. A global complaint does not implicate a store."""
    if issue['issue_kind']!='complaint' or not mentioned:return False
    # Product damage, logistics and product support do not count as store service.
    return issue['business_process']=='store service issue' or issue['object_type']=='store'

def grouped(records,key,eligible):
    buckets=defaultdict(list)
    for r in records:
        for value in sorted(set(key(r))):buckets[value].append(r)
    return [dict(values={eligible[0]:k},count=member_metric(rs,records,'successful_nonfallback'),
                 negative=member_metric([r for r in rs if eligible[1](r,k)],rs,'emails_mentioning_entity'),
                 complaints=member_metric([r for r in rs if eligible[2](r,k)],rs,'emails_mentioning_entity')) for k,rs in sorted(buckets.items())]

class R5Insights(B7Insights):
    def __init__(self,root,*,policy_overlays=None):
        self.policy_overlays=policy_overlays or []
        super().__init__(root)
    def _load(self):
        super()._load();paths=sorted((research_path(self.root, '.local/p5b8/analysis')).glob('B7-*.json'));records=[]
        for p in paths:
            a=json.loads(p.read_text('utf-8'));eid=p.stem;d=json.loads((research_path(self.root, '.local/p5b7/dataset')/(eid+'.json')).read_text('utf-8'))
            e=EmailInput(email_id=eid,subject=d['subject'],body=d['body']);data=a.get('data');issues=[]
            if data:
                for issue in data['issues']:
                    spans=[]
                    for q in issue['evidence']:
                        field='body' if q in e.body else 'subject';text=getattr(e,field);start=text.find(q)
                        spans.append(dict(field=field,start=start,end=start+len(q),quote=q))
                    issues.append(dict(issue,evidence=spans))
            product=next((i['category'] for i in issues if i['object_type']=='product'),'unknown')
            pred=dict(sentiment=data['expressed_sentiment'],experience_polarity=data['experience_polarity'],complaint_intent=data['complaint_intent'],
                      urgency=data['urgency'],is_complaint=data['complaint_intent']=='yes',store_location=canonical_store(data['mentioned_store'] or 'unknown'),
                      product_category=product,complaint_reason='unavailable',source_attribution='unavailable') if data else None
            records.append(dict(id=a['call']['run_id'],run_id=a['call']['run_id'],email=e.model_dump(),input_hash=e.input_hash,output_hash=digest(data),
                prediction=pred,issues=issues,raw=a,global_sentiment=data['expressed_sentiment'] if data else None,
                status='succeeded' if data else 'failed',created_at=a['call']['metadata'].get('dispatch_at'),template=d.get('family'),
                model=a['call']['metadata'].get('resolved_model'),config=dict(schema='p5b8-calibration-1',statistics=VERSION),reply=None,
                evidence_status='LLM_SYNTHETIC; MODEL_PROVISIONAL; evidence spans checked literally, semantic review pending'))
        self.add(SOURCE,'客户邮件 · 90封LLM合成 / 情绪与体验分轴','LLM_SYNTHETIC_SAVED_REAL_ANALYSIS_NOT_HUMAN_GOLD',records,paths,VERSION)
        if self.policy_overlays:
            corrected=copy.deepcopy(records)
            for row in corrected:
                for overlay in self.policy_overlays:
                    if row['input_hash']!=overlay['input_hash']:continue
                    if overlay['source_identity']!='OWNER_EXPLICIT':raise ValueError('Unsigned overlay cannot change production statistics')
                    known={i['issue_id'] for i in row['issues']}
                    if not set(overlay['exclude_store_target_issue_ids'])<=known:raise ValueError('Overlay issue identity mismatch')
                    row['store_target_exclusions']=overlay['exclude_store_target_issue_ids']
                    row['audit_overlay']=overlay
            self.add('b8-r6-policy','客户邮件 · Owner政策校正 / 原始预测保留','OWNER_EXPLICIT_TARGET_OVERLAY_NOT_NEW_GOLD',corrected,paths,'r6-target-overlay-1')
    def snapshot(self,source,**filters):
        if source=='b8-r6-policy':
            view=copy.copy(self);view.records=dict(self.records);view.records[SOURCE]=self.records[source]
            s=view.snapshot(SOURCE,**filters);s['source']=self.sources[source];s['statistics_version']='r6-target-overlay-1';return s
        product=filters.get('product')
        if source==SOURCE and product:
            # The compatibility projection has only one category. Filter native
            # Issues instead, without mutating the shared read-only catalog.
            view=copy.copy(self);view.records=dict(self.records)
            view.records[source]=[r for r in self.records[source] if any(i['object_type']=='product' and i['category']==product for i in r['issues'])]
            s=super(R5Insights,view).snapshot(source,**dict(filters,product=None))
            broad=super().snapshot(source,**dict(filters,product=None))
            s['prefilter']=broad['prefilter'];s['options']=broad['options']
        else:s=super().snapshot(source,**filters)
        if source!=SOURCE:return s
        ids={m['id'] for m in s['members']};valid=[r for r in self.records[source] if r['id'] in ids and r['status']=='succeeded']
        s['groups']['product_category']=grouped(valid,lambda r:[i['category'] for i in r['issues'] if i['object_type']=='product'],
           ('product_category',lambda r,k:any(i['category']==k and i['object_type']=='product' and i['experience_polarity']=='negative' for i in r['issues']),
            lambda r,k:any(i['category']==k and i['object_type']=='product' and i['issue_kind']=='complaint' for i in r['issues'])))
        s['groups']['store_location']=grouped(valid,lambda r:[r['prediction']['store_location']],
           ('store_location',lambda r,k:r['prediction']['experience_polarity']=='negative',
            lambda r,k:k!='unknown' and any(i['issue_id'] not in r.get('store_target_exclusions',[]) and store_target(i,r['prediction']['store_location']) for i in r['issues'])))
        s['axes']={f:{v:member_metric([r for r in valid if r['prediction'][f]==v],valid,'successful_nonfallback') for v in sorted({r['prediction'][f] for r in valid})}
                   for f in ('sentiment','experience_polarity','complaint_intent')}
        s['unattributed_store_complaints']=member_metric([r for r in valid if r['prediction']['store_location']=='unknown' and any(
            i['issue_kind']=='complaint' and i['business_process']=='store service issue' for i in r['issues'])],
            [r for r in valid if r['prediction']['store_location']=='unknown'],'emails_with_unknown_store')
        complaint_issue_emails=[r for r in valid if any(i['issue_kind']=='complaint' for i in r['issues'])]
        processes=sorted({i['business_process'] for r in complaint_issue_emails for i in r['issues'] if i['issue_kind']=='complaint'})
        s['groups']['source_attribution']=[dict(values=dict(source_attribution=k),count=member_metric(
            [r for r in complaint_issue_emails if any(i['issue_kind']=='complaint' and i['business_process']==k for i in r['issues'])],complaint_issue_emails,'emails_with_complaint_issue')) for k in processes]
        s['groups']['complaint_reason']=[dict(values=dict(complaint_reason='unavailable'),count=member_metric(complaint_issue_emails,complaint_issue_emails,'emails_with_complaint_issue'))]
        s['statistics_version']=VERSION
        s['ranking_note']='产品：负面体验Issue关联，每封每类去重。门店：明确指向门店服务的投诉Issue；提及门店与投诉邮件相关性另列。混合体验单列。'
        return s
