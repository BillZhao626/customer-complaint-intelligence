from src.infrastructure.research_paths import research_path
"""Read-only views over existing CSV/JSON evidence. No provider or database writes.

Rankings and cross tables reuse the I5C pure aggregators. Membership and status
denominators follow P3; legacy labels retain their original taxonomy.
"""
import csv
import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from src.dataset.build_i5c_deepseek_prediction_dashboard_stats_v1 import (
    store_ranking, product_ranking, store_product_matrix, is_true)
from src.domain.contracts import EmailInput, digest

FIELDS = ('sentiment', 'urgency', 'is_complaint', 'store_location', 'product_category', 'complaint_reason', 'source_attribution')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    ids = [r['email_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate email identity')
    return rows


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def member_metric(rows, denominator, name):
    ids = sorted(r['id'] for r in rows)
    den = sorted(r['id'] for r in denominator)
    if len(ids) != len(set(ids)) or not set(ids) <= set(den):
        raise ValueError('Invalid membership')
    return dict(numerator=len(ids), denominator=len(den), rate=len(ids)/len(den) if den else None,
                denominator_name=name, member_ids=ids, denominator_ids=den)


class ResearchInsights:
    def __init__(self, root):
        self.root = Path(root)
        self.sources = {}
        self.records = {}
        self._load()

    def add(self, key, label, identity, records, paths, version):
        if not records:
            return
        ids = [r['id'] for r in records]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate source member')
        self.records[key] = records
        self.sources[key] = dict(id=key, label=label, identity=identity, count=len(records), version=version,
            input_files={str(p.relative_to(self.root)).replace('\\','/'):file_hash(p) for p in paths},
            time_basis='analysis_run_created_at' if any(r.get('created_at') for r in records) else 'UNAVAILABLE: original email date not recorded',
            dataset_hash=digest([dict(id=r['id'], input_hash=r['input_hash'], output_hash=r['output_hash']) for r in records]))

    def _load(self):
        root = self.root
        emails_path = research_path(root, 'data/synthetic/customer_emails_full_v1.csv')
        if emails_path.exists():
            emails = {e['email_id']:e for e in read_csv(emails_path)}
            for key, label, path, reference in (
                ('template400','历史模板参考 · 400封 / 55模板',root/'data/golden/golden_labels_full_auto_v1.csv',True),
                ('model400','历史 DeepSeek · 400封预测',root/'outputs/i4g_full_pool_deepseek_predictions_v1.csv',False),
                ('review80','历史 DeepSeek · reviewed 80预测',research_path(root, 'outputs/i4e2_reviewed_80_raw_predictions_v1.csv'),False)):
                if not path.exists(): continue
                records=[]
                for p in read_csv(path):
                    e=emails[p['email_id']]
                    email=EmailInput(email_id=e['email_id'], subject=e['subject'], body=e['email_body'])
                    pred={f:p.get(f) or 'unavailable' for f in FIELDS}
                    pred['is_complaint']=is_true(p['is_complaint'])
                    accepted=reference or all(is_true(p.get(k, 'true')) for k in ('parse_success','schema_validation_success'))
                    records.append(dict(id=e['email_id'], email=email.model_dump(),input_hash=email.input_hash,
                        output_hash=digest(p), prediction=pred if accepted else None, raw=p, issues=[],
                        evidence_status='UNAVAILABLE: legacy CSV has no validated evidence spans',
                        status='succeeded' if accepted else 'failed', created_at=None, scenario=e.get('edge_case_type'),
                        template=e['generation_template_id'], run_id=None, reply=p.get('suggested_reply'),
                        model=p.get('model_name','template_program'), config=None))
                self.add(key,label,'TEMPLATE_AUTOMATIC_REFERENCE_NOT_GOLD' if reference else 'HISTORICAL_MODEL_ON_SYNTHETIC_NOT_GOLD',records,[emails_path,path],
                    'historical-reference-v1' if reference else 'historical-legacy-raw-taxonomy')
        groups = [('p36-'+arm, '分类开发 · P36 '+arm, root/'.local/p36'/arm, 'run-*.json') for arm in ('baseline-v1','catalog-v2','draft-v3')]
        groups += [('r2-'+arm,'R2 真实历史 · '+arm,root/'.local/p5b5r2'/arm,'*/run.json') for arm in ('R1','R2','R3','B2-SCENARIO','FINAL','UI','UI-FOLLOWUP')]
        groups += [('r2-B2','B2 Champion · 已保存真实历史',root/'.local/p5b5-live-20261030-v1/B2','*/run.json')]
        for key,label,directory,pattern in groups:
            paths=sorted(directory.glob(pattern))
            records=[]
            for path in paths:
                r=json.loads(path.read_text(encoding='utf-8')); config=r['config']
                a=next((r['metadata'][k] for k in ('analysis_v32','analysis_v31','analysis_v3') if k in r['metadata']),{})
                records.append(dict(id=r['run_id'],run_id=r['run_id'],email=r['email'],input_hash=r['input_hash'],
                    output_hash=digest(r['result']) if r['result'] else None,prediction=r['result'],raw=r,
                    issues=a.get('issues',[]),global_sentiment=a.get('email_sentiment') or a.get('sentiment'),
                    evidence_status='MODEL_SPANS: literal validity does not prove semantic support',
                    status='fallback' if r['metadata'].get('fallback') else r['status'],created_at=r['created_at'],
                    template=None,model=config['model_id'],config=config,reply=(r['result'] or {}).get('suggested_reply')))
            # Prevent accidental config/experiment mixing even within a directory.
            by_config=defaultdict(list)
            for r in records:
                config=dict(r['config'])
                # Full message hash changes with each input, not with the model or
                # prompt version. Preserve it in the member, not the cohort key.
                config['parameters']={k:v for k,v in (config.get('parameters') or {}).items() if k!='messages_hash'}
                if key.startswith('r2-') and config['parameters'].get('freeze_hash'):
                    # R2 hashes system messages including per-case tool context.
                    # The frozen source manifest identifies the implementation.
                    config.pop('prompt_hash',None)
                by_config[digest(config)].append(r)
            for h, rows in by_config.items():
                source_key=key if len(by_config)==1 else key+'-'+h[:8]
                config=dict(rows[0]['config']);config['parameters']={k:v for k,v in (config.get('parameters') or {}).items() if k!='messages_hash'}
                if key.startswith('r2-') and config['parameters'].get('freeze_hash'):config.pop('prompt_hash',None)
                self.add(source_key,label+(' / '+h[:8] if len(by_config)>1 else ''),'SAVED_REAL_MODEL_DEVELOPMENT_SYNTHETIC',rows,paths,
                         dict(config,cohort_grouping_note='R2: freeze_hash + prompt_version identifies implementation; per-request system prompt_hash and messages_hash include case/tool context and remain in full member config. Other run cohorts use complete config.'))
                manifest=directory/'manifest.json'
                if key.startswith('p36-') and manifest.is_file():
                    declared=json.loads(manifest.read_text(encoding='utf-8')).get('input_ids',[])
                    seen={r['email']['email_id'] for r in rows}
                    self.sources[source_key]['declared_input_count']=len(declared)
                    self.sources[source_key]['unattempted_input_ids']=sorted(set(declared)-seen)
                    self.sources[source_key]['unattempted_scope']='manifest inputs without saved run; outside business-run denominators'
                    self.sources[source_key]['input_files'][manifest.relative_to(self.root).as_posix()]=file_hash(manifest)

    def catalog(self):
        return list(self.sources.values())

    def member(self, source, member_id):
        return next(r for r in self.records[source] if r['id']==member_id)

    def snapshot(self, source, *, store=None, product=None, sentiment=None, status=None, start=None, end=None):
        from src.application.attribution_service import timestamp
        if source not in self.sources: raise ValueError('Unknown source')
        if status not in (None,'succeeded','failed','fallback','running','interrupted_or_unknown'):raise ValueError('Unknown run status')
        if (start or end) and not any(r.get('created_at') for r in self.records[source]):
            raise ValueError('Time unavailable for this source; no invented email dates')
        if start: timestamp(start)
        if end: timestamp(end)
        if start and end and timestamp(start)>timestamp(end): raise ValueError('Start must precede end')
        latest={}
        eligible=[r for r in self.records[source] if (not start or timestamp(r['created_at'])>=timestamp(start)) and (not end or timestamp(r['created_at'])<=timestamp(end))]
        for r in sorted(eligible,key=lambda x:(x['created_at'] or '',x['id'])):
            latest[(r['email']['email_id'],r['input_hash'])]=r
        base=list(latest.values())
        selected=[r for r in base if (not status or r['status']==status) and all(v is None or (r['prediction'] and r['prediction'][f]==v) for f,v in [('store_location',store),('product_category',product),('sentiment',sentiment)])]
        valid=[r for r in selected if r['status']=='succeeded' and r['prediction']]
        complaints=[r for r in valid if r['prediction']['is_complaint']]
        negative=[r for r in valid if r['prediction']['sentiment']=='negative']
        rows=[dict(r['prediction'],_id=r['id']) for r in valid]
        groups={}
        def dist(name, subset, fields, den_name):
            buckets=defaultdict(list)
            for r in subset: buckets[tuple(r['prediction'].get(f,'unavailable') for f in fields)].append(r)
            groups[name]=[dict(values=dict(zip(fields,values)),count=member_metric(members,subset,den_name),
                negative=member_metric([r for r in members if r['prediction']['sentiment']=='negative'],members,'group_successful_nonfallback'),
                complaints=member_metric([r for r in members if r['prediction']['is_complaint']],members,'group_successful_nonfallback')) for values,members in sorted(buckets.items())]
        for f in ('sentiment','store_location','product_category','complaint_reason','source_attribution'):
            dist(f, complaints if f in ('complaint_reason','source_attribution') else valid,[f],'complaint_emails' if f in ('complaint_reason','source_attribution') else 'successful_nonfallback')
        dist('store_product',valid,['store_location','product_category'],'successful_nonfallback')
        options={f:sorted({r['prediction'][f] for r in base if r['prediction']}) for f in ('store_location','product_category','sentiment')}
        return dict(source=self.sources[source],unit='latest run per email_id + input_hash; distinct revisions remain separate',
            statistics_version='I5C-rankings+P3-membership/p5b6-v1',prefilter=len(base),selected=len(selected),options=options,
            metrics=dict(emails=member_metric(selected,selected,'all_selected_email_revisions'),successful=member_metric(valid,selected,'all_selected_email_revisions'),
                negative=member_metric(negative,selected,'all_selected_email_revisions'),complaints=member_metric(complaints,selected,'all_selected_email_revisions')),
            states={s:member_metric([r for r in selected if r['status']==s],selected,'all_selected_email_revisions') for s in ('succeeded','failed','fallback','running','interrupted_or_unknown')},
            unknown={f:member_metric([r for r in valid if r['prediction'].get(f) in ('unknown','unavailable')],valid,'successful_nonfallback') for f in FIELDS if f!='is_complaint'},
            groups=groups,product_ranking=product_ranking(rows),store_ranking=store_ranking(rows),cross=store_product_matrix(rows),
            members=[dict(id=r['id'],email_id=r['email']['email_id'],subject=r['email']['subject'],status=r['status'],prediction=r['prediction'],input_hash=r['input_hash'],output_hash=r['output_hash']) for r in selected])
