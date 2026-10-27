"""Deterministic per-cohort issue summaries; no inferred cause or resolution."""
from collections import defaultdict


def summarize(cases, dimension):
    groups = defaultdict(lambda: dict(members=set(), negative=set(), complaints=set(), unresolved=set()))
    for c in cases:
        if not c['accepted'] or any(f['scope'] == 'analysis' and f['severity'] == 'block' for f in c['quality']['findings']):
            continue
        data = c['analysis']
        if dimension == '日期':
            values = [(c['created_at'][:10], None)]
        elif dimension == '门店':
            values = [(data.get('mentioned_store', 'unknown'), None)]
        else:
            field = {'商品': 'object_name', '问题原因': 'reason', '业务来源': 'business_process', '情绪': 'sentiment'}[dimension]
            values = [(i.get(field) or 'unknown', i) for i in data.get('issues', [])
                      if dimension != '商品' or i.get('object_type') == 'product']
            if not values:
                values = [('unknown', None)]
        for value, issue in values:
            g = groups[value]; cid = c['case_id']; g['members'].add(cid)
            if (issue or data).get('sentiment') == 'negative': g['negative'].add(cid)
            if (issue or {}).get('issue_kind') == 'complaint' or issue is None and data.get('complaint_status') in ('current_unresolved', 'mixed_status'):
                g['complaints'].add(cid)
            if ((issue or {}).get('resolution') == 'unresolved' or
                    issue is None and any(i.get('resolution') == 'unresolved' for i in data.get('issues', []))):
                g['unresolved'].add(cid)
    return [dict(name=name, total=len(g['members']), negative=len(g['negative']), complaints=len(g['complaints']),
                 unresolved=len(g['unresolved']), member_ids=sorted(g['members']))
            for name, g in sorted(groups.items(), key=lambda kv: (-len(kv[1]['complaints']), kv[0]))]
