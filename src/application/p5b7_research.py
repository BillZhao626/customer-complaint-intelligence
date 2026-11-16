"""Add new saved runs to existing insights; historical cohorts stay isolated."""
import json
from src.application.research_insights import ResearchInsights,member_metric
from src.domain.contracts import digest

STORE_ALIASES={
    'Shanghai Pudong Store':['Pudong store','浦东店','浦东门店','Shanghai Pudong Store'],
    'Hangzhou West Lake Store':['West Lake store','Hangzhou West Lake store','杭州西湖店'],
    'Beijing Chaoyang Store':['朝阳门店','Beijing Chaoyang store'],
    'Ningbo Tianyi Store':['宁波天一店','Ningbo Tianyi store'],
    'Shenzhen Nanshan Store':['深圳南山店','Shenzhen Nanshan store','南山店'],
    'Nanjing Xinjiekou Store':['南京新街口店','Xinjiekou store'],
    'Suzhou Industrial Park Store':['苏州工业园区店','苏州工业园店','Suzhou Industrial Park store'],
    'Wenzhou Lucheng Store':['温州鹿城店','Wenzhou Lucheng store']}
def canonical_store(value):
    return next((key for key,values in STORE_ALIASES.items() if value.casefold() in {x.casefold() for x in values}),value)

class B7Insights(ResearchInsights):
    def snapshot(self,source,**filters):
        snapshot=super().snapshot(source,**filters)
        if not source.startswith('b7-'):return snapshot
        # Optional derived view. Preserve the historical primary-issue projection.
        selected={r['id'] for r in snapshot['members']};groups={}
        for r in self.records[source]:
            if r['id'] not in selected or r['status']!='succeeded':continue
            categories={i['category'] for i in r['issues'] if i['object_type']=='product'}
            for category in categories:
                g=groups.setdefault(category,dict(all=[],negative=[],complaints=[]));g['all'].append(r)
                issues=[i for i in r['issues'] if i['object_type']=='product' and i['category']==category]
                if any(i['sentiment']=='negative' for i in issues):g['negative'].append(r)
                if any(i['issue_kind']=='complaint' for i in issues):g['complaints'].append(r)
        snapshot['groups']['product_negative_association']=[dict(values=dict(product_category=k),count=member_metric(g['all'],g['all'],'emails_with_this_product_issue'),
            negative=member_metric(g['negative'],g['all'],'emails_with_this_product_issue'),complaints=member_metric(g['complaints'],g['all'],'emails_with_this_product_issue')) for k,g in sorted(groups.items())]
        snapshot['product_association_definition']='Only successful native product issues; deduplicate email revision per category. Negative issue association, not primary projection or causal responsibility. Multiple categories may share an email. No failed raw extraction.'
        return snapshot

    def _load(self):
        super()._load()
        for arm in ('B2','R3'):
            paths=sorted((self.root/'.local/p5b7'/arm).glob('B7-*/run.json'));records=[]
            for p in paths:
                r=json.loads(p.read_text(encoding='utf-8'));a=r['metadata'].get('analysis_v32',{})
                prediction=dict(r['result'],store_location=canonical_store(r['result']['store_location'])) if r['result'] else None
                records.append(dict(id=r['run_id'],run_id=r['run_id'],email=r['email'],input_hash=r['input_hash'],output_hash=digest(r['result']) if r['result'] else None,
                    prediction=prediction,raw=r,raw_projection=r['result'],store_normalization='p5b7-scoped-store-aliases-1',issues=a.get('issues',[]),global_sentiment=a.get('sentiment'),evidence_status='模型原文引用，语义仍待复核；门店只作本实验显式别名归并，原始投影保留',
                    status=r['status'],created_at=r['created_at'],template=None,model=r['config']['model_id'],config=r['config'],reply=(r['result'] or {}).get('suggested_reply')))
            self.add('b7-'+arm,'本轮 LLM 合成邮件 · '+arm+(' 正式链' if arm=='B2' else ' 配对子集（未晋升）'),'LLM_SYNTHETIC_REAL_LANGCHAIN_RUN_NOT_HUMAN_GOLD',records,paths,
                dict(prompt='p5b7-'+arm,schema='analysis-v3.2',taxonomy='complaint-issues-v3.1',freeze_file='.local/p5b7/freeze.json',first_attempts_only=True))
