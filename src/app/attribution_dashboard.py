"""P3 UI: one cohort -> distributions -> membership -> immutable original."""
import json
import os
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

from src.infrastructure.dashboard_sources import sqlite_source, p2_source
from src.app.offline_slice import show_run


def render_attribution_dashboard(root):
    st.header('Evidence-grounded Attribution Dashboard')
    st.caption('Research prototype · Synthetic / Historical demonstrations are not real market rankings. Business attribution is not proven causation.')
    source = st.selectbox('Data source', ['Configured SQLite runs', 'P2 saved synthetic DeepSeek results'], key='p3_source')
    try:
        service = (p2_source(root) if source.startswith('P2') else sqlite_source(
            os.environ.get('COMPLAINT_DB_PATH',str(root/'.local/runs.sqlite3')),os.environ.get('COMPLAINT_DATASET_MANIFEST')))
    except (OSError, ValueError, sqlite3.Error) as exc:
        st.warning(f'Source unavailable ({type(exc).__name__}). Run the offline demo setup or select an available source.')
        return
    if not service.cohorts:
        st.info('P3分析库暂无运行。默认单条工作台的数据请到 P4 review workflow 查看；研究与旧版分析工具才写入此P3库。')
        return
    configs = service.cohorts
    cohort = st.selectbox('Model / experiment version',list(configs),key='p3_cohort',format_func=lambda k:
        ' / '.join(str(configs[k][f]) for f in ('backend','model_id','prompt_version','schema_version','taxonomy_version'))+' / '+k[:8])
    runs = [r for r in service.runs if r.cohort_id==cohort]
    if service.samples:
        st.info('Synthetic development data · '+service.samples[0].dataset_id+' · Human Gold pending')
    else:
        st.warning('Unregistered dataset/source provenance: unavailable. Do not interpret this selection as a verified research dataset.')
    cols = st.columns(3)
    filters = {}
    for col, field, label, key in zip(cols,('store_location','product_category','sentiment'),('Store','Product','Sentiment'),('store','product','sentiment')):
        values = sorted({getattr(r.result,field) for r in runs if r.result})
        selected = col.selectbox(label,['All',*values],key='p3_'+key)
        filters[key] = None if selected=='All' else selected
    status = st.selectbox('Analysis status',['All','succeeded','failed','fallback','running','interrupted_or_unknown'],key='p3_status')
    filters['status'] = None if status=='All' else status
    with st.expander('Time range (inclusive, ISO-8601 with timezone)'):
        filters['start'] = st.text_input('From',key='p3_start',placeholder='2026-10-15T00:00:00+08:00') or None
        filters['end'] = st.text_input('Through',key='p3_end',placeholder='2026-10-15T23:59:59+08:00') or None
    try:
        snapshot = service.snapshot(cohort,**filters)
    except ValueError as exc:
        st.error(str(exc));return
    st.subheader('Overview and denominators')
    st.caption('Count unit: latest run per email ID + input hash within time range. Modified content is a separate email revision. Failed and fallback runs stay in the all-email denominator; business rates also show the successful denominator. Empty denominator = unavailable.')
    rows = [dict(metric=name,**{k:v for k,v in m.items() if not k.endswith('run_ids')}) for name,m in snapshot['metrics'].items()]
    st.dataframe(pd.DataFrame(rows),hide_index=True)
    st.caption(f"Before business/status filters: {snapshot['prefilter_count']} · Excluded by filters: {snapshot['filtered_out']} · Superseded attempts: {len(snapshot['superseded_run_ids'])} · Unattempted manifest samples in this cohort/time: {len(snapshot['missing_sample_ids'])}")
    with st.expander('Dataset, versions, filters and status evidence'):
        st.json({k:v for k,v in snapshot.items() if k not in ('groups','members','metrics')})
    st.subheader('Find categories and inspect their members')
    dimension = st.selectbox('Breakdown',['store_location','product_category','complaint_reason','source_attribution','store_product','attribution_valid','attribution_states'],key='p3_dimension')
    st.caption('Reasons / source: complaint denominator. Store / product / cross: successful denominator. attribution_valid: concrete business attribution only. attribution_states: all successful outputs including none, unclear, unknown and legacy unavailable.')
    groups = snapshot['groups'][dimension]
    if groups:
        table = [dict(category=' × '.join(g['values'].values()),count=g['count']['numerator'],
            denominator=g['count']['denominator'],denominator_name=g['count']['denominator_name'],
            share=g['count']['rate'],negative=g['negative']['numerator'],negative_rate=g['negative']['rate'],
            complaints=g['complaints']['numerator']) for g in groups]
        st.bar_chart(pd.DataFrame(table).set_index('category')[['count']])
        st.dataframe(pd.DataFrame(table),hide_index=True)
    else:
        st.info('No eligible members for this breakdown. Rate unavailable.')
    choices = {}
    for name,m in snapshot['metrics'].items(): choices['Overview / '+name]=m
    for name,m in snapshot['states'].items(): choices['State / '+name]=m
    for name,m in snapshot['unknown'].items(): choices['Unknown / '+name]=m
    choices['Unavailable / attribution']=snapshot['attribution_unavailable']
    for g in groups:
        for name in ('count','negative','complaints'):
            choices[' × '.join(g['values'].values())+' / '+name]=g[name]
    choice = st.selectbox('Statistic to inspect',list(choices),key='p3_statistic')
    m = choices[choice]
    st.write({k:v for k,v in m.items() if not k.endswith('run_ids')})
    membership = st.radio('Member set',['Numerator','Denominator'],horizontal=True,key='p3_membership')
    ids = m['member_run_ids'] if membership=='Numerator' else m['denominator_run_ids']
    if ids:
        st.dataframe(pd.DataFrame([snapshot['members'][rid] for rid in ids]),hide_index=True)
        rid = st.selectbox('Email member',ids,format_func=lambda v:service.get(v).email.email_id+' / '+v,key='p3_member')
        if st.button('Open original and analysis',key='p3_open'):
            st.session_state['p3_opened']=(source,cohort,rid)
        if st.session_state.get('p3_opened') == (source,cohort,rid):
            st.subheader('Original email and saved analysis')
            show_run(service.get(rid))
            st.caption('Attribution and key_information are unreviewed predictions. Read the original to check support. Contact channel: unavailable. Reply: unreviewed, unsent draft.')
    else:
        st.caption('No members in the selected numerator/denominator.')
    st.download_button('Download statistics and member IDs',json.dumps(snapshot,ensure_ascii=False,indent=2),
        file_name='p3-statistics.json',mime='application/json',key='p3_download')
