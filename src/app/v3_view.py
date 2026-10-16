"""Presentation only: input, issues, customer priorities and operational suggestions."""
import os
import streamlit as st
from src.domain.analysis_v3 import stored_analysis
from src.application.v3_statistics import snapshot


def show_v3(run,key_prefix='v3'):
    value=stored_analysis(run)
    st.subheader('Analysis-v3: issue details')
    st.caption('Customer importance and suggested handling order are separate. Routing is not verified responsibility. Draft is unsent and unreviewed.')
    from src.application.v3_remediation import derive,HANDLING_POLICY
    from src.application.reply_review import inspect_reply
    import json
    modes=['原始模型输出','保守兼容视图','业务兼容视图','已授权业务顺序预览']
    mode=st.radio('View identity · 原始与派生版本',modes,horizontal=True,key=f'{key_prefix}_view_{run.run_id}')
    derived=None
    if mode!=modes[0]:
        policy='customer-primary-v2-safe' if mode==modes[1] else 'owner-operational-v2-safe'
        derived=derive(run,policy,HANDLING_POLICY if mode==modes[3] else None)
        from src.domain.analysis_v3 import AnalysisV3
        value=AnalysisV3.model_validate(derived['analysis'])
        st.info('确定性派生视图；原 run、模型输出和历史成绩均未改变。')
        st.caption(f'Rule: {derived["rule_version"]} · Projection: {policy} · Derived ID: {derived["derived_id"]}')
        st.write({'v2门店兼容值':derived['projection']['store_location'],'v2业务来源兼容值':derived['projection']['source_attribution']})
        if derived['changes']:st.write('业务顺序变更（客户重要性保持原文）：',derived['changes'])
        st.download_button('Download derived view · 独立派生身份',json.dumps(derived,ensure_ascii=False,indent=2),
            f'{derived["derived_id"]}.json','application/json',key=f'{key_prefix}_derived_{run.run_id}')
    st.write(f'Complaint: {value.complaint_status} · Sentiment: {value.sentiment} · Urgency: {value.urgency}')
    st.caption(f'Store: {value.mentioned_store} ({value.store_verification}) · Contact: {value.contact_channel} · Purchase: {value.purchase_channel}')
    st.write('Summary');st.text(value.summary)
    for issue in sorted(value.issues,key=lambda i:i.handling_priority or 999):
        with st.expander(f'{issue.issue_id}: {issue.object_name}',expanded=True):
            left,right=st.columns(2)
            left.markdown(f'**Customer importance · 客户重要性**\n\n{issue.customer_importance}')
            right.markdown(f'**Suggested handling order · 业务建议顺序**\n\n{issue.handling_priority or "unspecified"}')
            st.write(f'{issue.reason} · {issue.sentiment} · {issue.urgency} · {issue.resolution}')
            certainty={'reported':'客户报告，未核实','inferred':'推断，未核实','unclear':'不明确','unknown':'缺少信息','not_applicable':'不适用'}[issue.attribution_certainty]
            if issue.attribution_certainty in ('unclear','unknown'):st.warning(f'归属：{certainty}；流程域 {issue.business_process} 不能当成已确定原因。')
            else:st.caption(f'归属：{certainty} · 流程域：{issue.business_process}')
            st.caption(f'建议团队：{issue.routing_team} · Responsibility: {issue.responsibility}（没有责任核实证据）')
            if issue.customer_requests:st.write('Customer requests: '+'; '.join(issue.customer_requests))
            if issue.missing_evidence:st.caption('Needs verification: '+'; '.join(issue.missing_evidence))
            if issue.priority_rationale:st.text(issue.priority_rationale)
            st.caption('引用对应本问题的对象/原因/情绪/状态/归属判断；逐字合法与语义支持需要分别审核。')
            for e in issue.evidence:st.text(f'Evidence · {e.field}[{e.start}:{e.end}]: {e.quote}')
            for e in issue.importance_evidence:st.caption('Customer importance evidence: '+e.quote)
    if value.relations:
        st.write('Issue relations')
        for relation in value.relations:st.write(f'{relation.from_issue} ↔ {relation.to_issue}: {relation.kind}')
    st.warning('Unreviewed reply · 未审核、未发送；无人工批准记录。')
    st.text(value.suggested_reply)
    screening=inspect_reply(value.suggested_reply)
    if screening['findings']:
        st.warning('回复词面复核：'+screening['status']+'；属于新规则诊断，不回写历史通过/失败。')
        for finding in screening['findings']:st.text(f'{finding["severity"]} · {finding["kind"]}: {finding["quote"]}')
    else:st.caption('新门禁未检出词面信号；内容仍待人工审，不代表回复正确或已批准。')
    with st.expander('Technical provenance / compatibility'):
        st.json({'run_id':run.run_id,'backend':run.config.backend,'model':run.config.model_id,
                 'resolved_model':run.metadata.get('resolved_model'),'prompt':run.config.prompt_version,
                 'cohort':run.cohort_id,'cost_cny_estimate':run.metadata.get('cost_cny'),
                 'input_hash':run.input_hash,'output_hash':run.metadata.get('analysis_v3_hash'),
                 'compatibility':run.metadata['compatibility_diagnostics']},expanded=False)


def render_v3_demo(root):
    from src.application.v3_demo import DEMO_EMAIL,demo_result,ReplayV3
    from src.application.analysis_service import AnalysisService
    from src.infrastructure.repository import Repository
    from src.infrastructure.dashboard_sources import ReadOnlyRepository
    render_candidate_review(root)
    from src.app.semantic_workspace import render_semantic_workspace
    render_semantic_workspace(root)
    render_v3_live(root)
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
                st.text(run.email.subject);st.text(run.email.body);show_v3(run,'demo')
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


def render_v3_live(root):
    """Opt-in ordinary text entry. Reads only until the explicit paid submit."""
    import json
    from pathlib import Path
    from src.domain.contracts import EmailInput
    from src.infrastructure.dashboard_sources import ReadOnlyRepository
    from src.infrastructure.p36_budget import DevelopmentBudget
    space=root/'.local/p36'
    with st.expander('P3.6 real Analysis-v3 · 真实模型开发入口'):
        st.caption('普通邮件文本输入，区别于下方预设演示结果。仅允许已登记白名单的虚构开发样本。人工参考与模型预测分开，所有回复仍待审核。')
        experiment=st.text_input('Frozen experiment identity',value=os.getenv('COMPLAINT_P36_EXPERIMENT','draft-v3'),key='p36_experiment')
        # Experiment identifiers are local directory names, never paths.
        if not experiment or Path(experiment).name!=experiment or experiment in ('.','..') or '/' in experiment or '\\' in experiment:
            st.error('Invalid experiment identity');return
        manifest_path=space/experiment/'manifest.json'
        if not manifest_path.is_file() or not (space/'inputs-v1.json').is_file():
            st.info('尚未初始化本机独立试点。参见 docs/p36 的准备步骤；默认不会调用模型。');return
        try:
            manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            budget=DevelopmentBudget(space/'budget.sqlite3');state=budget.summary()
            inputs=json.loads((space/'inputs-v1.json').read_text(encoding='utf8'))['inputs']
        except (OSError,ValueError):
            st.error('Pilot configuration unavailable');return
        config=manifest['config']
        st.write(f'Real model: {config["model_id"]} · Prompt: {config["prompt_version"]} · Experiment: {experiment}')
        st.caption(f'已预留请求 {state["reserved_attempts"]}/40 · 保守费用预留 ¥{state["reserved_upper_cny"]:.6f}/15（实际扣账未知；失败也占预算）')
        st.caption(f'Budget state: {state["halted"] or "available"} · Frozen cohort/config bound in persistent ledger')
        email_id=st.text_input('V3 email ID',key='p36_email_id')
        subject=st.text_input('V3 subject',key='p36_subject')
        body=st.text_area('V3 original email',key='p36_body')
        enabled=st.checkbox('Explicitly enable paid real-model analysis for this fictional input',value=False,key='p36_enable')
        server_enabled=os.getenv('COMPLAINT_ENABLE_LIVE','false')=='true'
        allowed=False
        try:
            email=EmailInput(email_id=email_id,subject=subject,body=body)
            allowed=any(x['input_hash']==email.input_hash and x['email']['email_id']==email.email_id for x in inputs)
        except ValueError:email=None
        if body and not allowed:st.warning('输入未匹配冻结白名单，无法外发。新虚构输入需先建立独立冻结实验。')
        if not server_enabled:st.caption('服务器真实模式未启用（COMPLAINT_ENABLE_LIVE）；可读取已有结果。')
        if st.button('Analyze real v3 and save · 付费提交',key='p36_analyze',disabled=not (server_enabled and enabled and allowed and not state['halted'] and not state['active_lease'])):
            try:
                from scripts.p36 import frozen_service
                service=frozen_service(experiment)
                # Do not resubmit failed/unknown inputs from UI; review the retained attempt.
                previous=[r for r in service.repository.list_runs() if r.email==email]
                run=previous[0] if previous else service.analyze(email)
                st.session_state['p36_run_id']=run.run_id
            except Exception as exc:st.error(f'Analysis unavailable ({type(exc).__name__}); inspect retained attempt and ledger.')
        lookup=st.text_input('Real v3 saved run ID',key='p36_lookup')
        if st.button('Load real v3 result',key='p36_load'):st.session_state['p36_run_id']=lookup.strip()
        path=space/experiment/'runs.sqlite3'
        run_id=st.session_state.get('p36_run_id')
        if not run_id or not path.exists():return
        try:run=ReadOnlyRepository(path).get(run_id)
        except ValueError:st.error('Stored result binding failed');return
        if not run:st.info('Run not found in this experiment');return
        st.write(f'真实模型预测 · {run.status} · Run {run.run_id}')
        st.text(run.email.subject);st.text(run.email.body)
        st.caption(f'Tokens: {sum(a.metadata.get("total_tokens") or 0 for a in run.attempts)} · Peak cost estimate: {run.metadata.get("cost_cny")} CNY')
        if run.result:show_v3(run,'live')
        else:st.warning('模型输出未通过正式契约或调用失败；无可用预测，不能作为正确分析。')
        packet=dict(sample_id=run.email.email_id,run_id=run.run_id,input_hash=run.input_hash,
                    cohort_id=run.cohort_id,output_hash=run.metadata.get('analysis_v3_hash'),
                    input=run.email.model_dump(),prediction=run.metadata.get('analysis_v3'),
                    status='pending',reviewer=None,human_declaration=False,rubric_version='p36-semantic-content-v1',
                    review_dimensions=['问题数量/漏识别/重复','对象与原因','情绪/解决状态','处理顺序/归属不确定性',
                                       '证据语义支持（区别于跨度合法）','摘要重要事实/编造','回复诉求/安全/虚构退款赔偿承诺'],
                    scores=None,evidence_notes=[],critical_errors=[])
        st.download_button('Download pending content / evidence review · 待审入口',json.dumps(packet,ensure_ascii=False,indent=2),
                           f'{run.run_id}-pending-review.json','application/json',key='p36_review_download')
        item=next((x for x in inputs if x['input_hash']==run.input_hash),None)
        with st.expander('人工开发参考（独立于模型预测）'):
            if item and item['expected']:
                st.caption('研究者冻结的七字段开发裁决；问题级、摘要和回复人工评价仍待审。')
                st.json(item['expected'],expanded=False)
            else:st.caption('无审核参考，仅展示真实输出与待审状态。')
