"""Small Streamlit boundary; all analysis and statistics live in the service."""
import os
import pandas as pd
import streamlit as st
from src.application.analyzers import OfflineFake,LegacyMock
from src.infrastructure.deepseek import LiveError
from src.application.analysis_service import AnalysisService
from src.domain.contracts import EmailInput
from src.infrastructure.repository import Repository


def show_run(run):
    st.write({'run_id':run.run_id,'email_id':run.email.email_id,'backend':run.config.backend,'status':run.status,
              'input_hash':run.input_hash,'versions':run.config.model_dump()})
    st.text(run.email.subject)
    st.text(run.email.body)
    if run.status=='succeeded':
        label={'offline_fake':'Offline Fake / Demo','legacy_mock':'Legacy Mock / Rules Baseline','deepseek_live':'DeepSeek Live'}[run.config.backend]
        st.success(f'{label} saved successfully.')
        st.json(run.result.model_dump())
        if run.config.schema_version in ('analysis-v3','analysis-v3.1'):
            from src.app.v3_view import show_v3
            show_v3(run)
    elif run.status in ('running','interrupted_or_unknown'):
        st.warning('Running or interrupted / unknown: do not repeat a paid request. Inspect the saved attempts first.')
    else:
        error=run.attempts[-1].error if run.attempts else None
        st.error(f'Run failed: {error.message if error else run.metadata.get("error_type","unavailable")}')
    if run.config.backend=='deepseek_live':
        st.caption('Suggested reply is an unsent, unreviewed draft. Source attribution is not proven causation.')
        st.json(run.metadata)
    with st.expander('Stored raw output and validation stages'):
        st.json([a.model_dump() for a in run.attempts])


def render_offline_slice(root):
    st.subheader('Single Email Analysis')
    from src.app.v3_view import render_v3_demo
    render_v3_demo(root)
    st.info('Default: Offline Fake / Demo. DeepSeek Live requires server authorization and a frozen synthetic pilot input.')
    backend=st.selectbox('Analyzer', ['offline_fake','legacy_mock','deepseek_live'], key='offline_backend')
    if backend=='deepseek_live':
        st.warning('Paid API mode. Only authorized synthetic pilot inputs are allowed; the durable budget is shared with CLI runs.')
    st.caption('Demo tokens: [store:A] / [store:B], [negative] / [positive] / [neutral]. No store token means unknown. [fail] injects a failure.')
    email_id=st.text_input('Email ID',value='demo-A-negative',key='offline_email_id')
    subject=st.text_input('Subject',value='Synthetic demonstration',key='offline_subject')
    body=st.text_area('Customer email',value='[store:A] [negative] Synthetic: my headphones are broken.',height=180,key='offline_body')
    try:
        repo=Repository(os.environ.get('COMPLAINT_DB_PATH',str(root/'.local'/'runs.sqlite3')))
        service=AnalysisService(repo,OfflineFake())
    except Exception as exc:
        st.error(f'Storage unavailable ({type(exc).__name__}); no analysis saved.')
        return
    if st.button('Analyze email',type='primary',key='offline_analyze'):
        # Remove an old receipt before attempting a new write.
        st.session_state.pop('offline_run_id',None)
        st.query_params.pop('run_id',None)
        try:
            if backend=='deepseek_live':
                from src.infrastructure.deepseek import DeepSeekAnalyzer,LiveSettings
                from src.infrastructure.pilot_budget import PilotBudget
                analyzer=DeepSeekAnalyzer(LiveSettings.from_env())
                budget=PilotBudget(root/'.local'/'p2-pilot-v1'/'budget.sqlite3')
                service=AnalysisService(repo,analyzer,budget=budget)
            elif backend=='legacy_mock':
                service=AnalysisService(repo,LegacyMock())
            with st.spinner('Analyzing and saving run...'):
                run=service.analyze(EmailInput(email_id=email_id,subject=subject,body=body))
            st.session_state['offline_run_id']=run.run_id
            st.query_params['run_id']=run.run_id
        except LiveError as exc:
            st.error(f'Live mode unavailable: {exc.kind}. Enable server authorization and initialize the approved pilot ledger.')
        except ValueError:
            st.error('Invalid input: provide a nonblank email ID and body within the allowed length.')
        except Exception as exc:
            st.error(f'Save failed ({type(exc).__name__}); no success receipt was issued.')

    lookup=st.text_input('Run ID to reopen',key='offline_lookup')
    if st.button('Load saved run',key='offline_load'):
        st.session_state['offline_run_id']=lookup.strip()
        st.query_params['run_id']=lookup.strip()
    run_id=st.session_state.get('offline_run_id') or st.query_params.get('run_id')
    if run_id:
        run=repo.get(run_id)
        if run:
            show_run(run)
        else:
            st.warning('Saved run not found in the configured database.')

    st.markdown('### Saved runs and traceable statistics')
    all_runs=repo.list_runs()
    if not all_runs:
        st.caption('No saved runs yet.')
        return
    configs={r.cohort_id:r.config for r in all_runs}
    cohort=st.selectbox('Run source / version',list(configs),format_func=lambda key:f'{configs[key].backend} / {configs[key].model_id} / {configs[key].prompt_version} / {key[:10]}',key='offline_cohort')
    status=st.selectbox('Run status',['all','succeeded','failed','running','interrupted_or_unknown'],key='offline_status')
    cohort_runs=repo.list_runs(cohort_id=cohort)
    stores=sorted({r.result.store_location for r in cohort_runs if r.result})
    products=sorted({r.result.product_category for r in cohort_runs if r.result})
    store=st.selectbox('Store filter',['all',*stores],key='offline_store')
    product=st.selectbox('Product filter',['all',*products],key='offline_product')
    selected=repo.list_runs(cohort_id=cohort,status=None if status=='all' else status,
                           store=None if store=='all' else store,product=None if product=='all' else product)
    st.dataframe(pd.DataFrame([dict(run_id=r.run_id,email_id=r.email.email_id,status=r.status,backend=r.config.backend) for r in selected]),hide_index=True)
    dimension=st.selectbox('Statistic dimension',['store_location','product_category'],key='offline_dimension')
    st.caption('Negative rate = negative successful runs / all successful runs in the selected group. Failed runs are excluded. Versions/backends are never mixed. Changed email content creates a separate run.')
    groups=[] if status not in ('all','succeeded') else service.aggregate(cohort,dimension,None if store=='all' else store,None if product=='all' else product)
    if groups:
        st.dataframe(pd.DataFrame([{k:v for k,v in g.items() if k not in ('member_run_ids','negative_member_run_ids')} for g in groups]),hide_index=True)
        group=st.selectbox('Statistic group',[g['group'] for g in groups],key='offline_group')
        selected_group=next(g for g in groups if g['group']==group)
        st.write({'numerator':selected_group['numerator'],'denominator':selected_group['denominator'],'negative_rate':selected_group['negative_rate'],'source':selected_group['source'],'cohort_id':cohort})
        membership=st.radio('Members',['all denominator members','negative numerator members'],key='offline_membership')
        ids=selected_group['member_run_ids'] if membership.startswith('all') else selected_group['negative_member_run_ids']
        if ids:
            member=st.selectbox('Member run ID',ids,key='offline_member')
            if st.button('Open member original',key='offline_open_member'):
                st.session_state['offline_run_id']=member
                st.query_params['run_id']=member
                st.rerun()
