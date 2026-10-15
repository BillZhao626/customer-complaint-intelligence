"""Presentation only: input, issues, customer priorities and operational suggestions."""
import os
import streamlit as st
from src.domain.analysis_v3 import stored_analysis
from src.application.v3_statistics import snapshot


def show_v3(run):
    value=stored_analysis(run)
    st.subheader('Analysis-v3: issue details')
    st.caption('Customer importance and suggested handling order are separate. Routing is not verified responsibility. Draft is unsent and unreviewed.')
    st.write(f'Complaint: {value.complaint_status} · Sentiment: {value.sentiment} · Urgency: {value.urgency}')
    st.caption(f'Store: {value.mentioned_store} ({value.store_verification}) · Contact: {value.contact_channel} · Purchase: {value.purchase_channel}')
    for issue in value.issues:
        with st.expander(f'{issue.issue_id}: {issue.object_name}',expanded=True):
            st.write(f'Customer importance: {issue.customer_importance} · Suggested handling order: {issue.handling_priority or "unspecified"}')
            st.write(f'{issue.reason} · {issue.sentiment} · {issue.urgency} · {issue.resolution}')
            st.caption(f'Route to: {issue.routing_team} · Responsibility: {issue.responsibility}')
            if issue.priority_rationale:st.text(issue.priority_rationale)
            for e in issue.evidence:st.text(f'{e.field}[{e.start}:{e.end}]: {e.quote}')
            st.json(issue.model_dump(),expanded=False)
    st.write('Issue relations');st.json([r.model_dump() for r in value.relations],expanded=False)
    st.write('Unsent reply draft');st.text(value.suggested_reply)
    st.warning('Compatibility projection: '+'; '.join(run.metadata['compatibility_diagnostics']))


def render_v3_demo(root):
    from src.application.v3_demo import DEMO_EMAIL,demo_result,ReplayV3
    from src.application.analysis_service import AnalysisService
    from src.infrastructure.repository import Repository
    from src.infrastructure.dashboard_sources import ReadOnlyRepository
    render_candidate_review(root)
    with st.expander('P3.5 multi-issue offline workspace'):
        st.caption('Explicit synthetic fixture, no language-model quality claim. New v3 runs use a separate local database.')
        st.text(DEMO_EMAIL.subject);st.text(DEMO_EMAIL.body)
        path=os.getenv('COMPLAINT_V3_DB_PATH',str(root/'.local/p35-ui/runs.sqlite3'))
        if st.button('Analyze v3 fixture',key='v3_analyze'):
            repo=Repository(path)
            run=AnalysisService(repo,ReplayV3({DEMO_EMAIL.input_hash:demo_result().model_dump()})).analyze(DEMO_EMAIL)
            st.session_state['v3_run_id']=run.run_id
            st.query_params['v3_run_id']=run.run_id
        lookup=st.text_input('V3 run ID to reopen',key='v3_lookup')
        if st.button('Load v3 run',key='v3_load'):
            st.session_state['v3_run_id']=lookup.strip();st.query_params['v3_run_id']=lookup.strip()
        from pathlib import Path
        if not Path(path).exists(): return
        repo=ReadOnlyRepository(path)
        run_id=st.session_state.get('v3_run_id') or st.query_params.get('v3_run_id')
        if run_id:
            run=repo.get(run_id)
            if run and run.config.schema_version=='analysis-v3' and run.result:
                st.caption(f'Run ID: {run.run_id}')
                st.json({'input_hash':run.input_hash,'config':run.config.model_dump()},expanded=False)
                st.text(run.email.subject);st.text(run.email.body);show_v3(run)
            else: st.warning('No successful v3 result found.')
        runs=[r for r in repo.list_runs() if r.config.schema_version=='analysis-v3']
        if runs:
            cohorts={r.cohort_id:r.config for r in runs}
            cohort=st.selectbox('V3 source / version',list(cohorts),key='v3_cohort')
            selected=[r for r in runs if r.cohort_id==cohort]
            report=snapshot(selected,cohort,cohorts[cohort].parameters['dataset_id'])
            a,b,c=st.columns(3)
            a.metric('Email revisions',report['email_revisions']);b.metric('Successful emails',report['successful_email_revisions']);c.metric('Issues',report['issue_count'])
            st.caption('Store groups count email revisions; category/reason/process groups count issues. Unknown and unclear remain distinct.')
            st.json(report,expanded=False)
            import json
            st.download_button('Download v3 statistics',json.dumps(report,ensure_ascii=False,indent=2),'v3-statistics.json','application/json',key='v3_download')


def render_candidate_review(root):
    from pathlib import Path
    import json
    from src.evaluation.e2e_v3 import validate_candidates,dataset_hash
    path=Path(os.getenv('COMPLAINT_V3_CANDIDATES',str(root/'.local/p35/dataset-candidate-v2/candidates.json')))
    with st.expander('P3.5 candidate review'):
        if not path.exists():
            st.caption('Set COMPLAINT_V3_CANDIDATES to a local candidate manifest to review. Candidate text is not distributed in the public repository.')
            return
        try: rows=validate_candidates(json.loads(path.read_text(encoding='utf-8-sig')))
        except (ValueError,OSError):
            st.error('Candidate manifest failed validation.');return
        st.warning('Development-exposed synthetic candidates. Human review pending; no independent holdout or model quality claim.')
        selected=st.selectbox('Candidate ID',[r.sample_id for r in rows],key='v3_candidate')
        r=next(r for r in rows if r.sample_id==selected)
        st.text(r.subject);st.text(r.body)
        if r.exclusion_reason:
            st.warning('Excluded from clean semantic evaluation: '+r.exclusion_reason)
        st.write({'input_hash':r.input_hash,'scenarios':r.scenarios,'semantic_family':r.semantic_family,'review_status':r.review_status,'quality_flags':r.quality_flags})
        notes=st.text_area('Human review notes (unsaved draft)',key='v3_review_notes_'+selected)
        packet=dict(protocol='p35-candidate-human-review-v1',reviewer=None,human_declaration=False,dataset_hash=dataset_hash(rows),
                    items=[dict(sample_id=r.sample_id,input_hash=r.input_hash,status='pending',notes=notes)])
        st.download_button('Download pending review draft',json.dumps(packet,ensure_ascii=False,indent=2),f'{selected}-pending-review.json','application/json',key='v3_review_download')
