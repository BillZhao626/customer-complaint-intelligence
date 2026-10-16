"""P3.8 presentation: separate versions, queues, unsigned review and zero budget."""
import json
import os
from pathlib import Path
import streamlit as st


def show_v31(run,key_prefix='v31'):
    from src.domain.analysis_v31 import stored_analysis
    value=stored_analysis(run)
    st.subheader('Analysis-v3.1 · research-owner-policy-v2')
    st.info(f'原始分析器预测 · {run.config.backend} · 1封邮件 / {len(value.issues)}个Issue；兼容v2为独立有损派生。')
    st.caption(f'紧急程度 {value.urgency} · 原始预测hash {run.metadata["analysis_v31_hash"]}')
    st.text(value.summary)
    for issue in sorted(value.issues,key=lambda i:i.handling_priority or 999):
        with st.expander(f'{issue.issue_id}: {issue.object_name}',expanded=True):
            a,b,c=st.columns(3)
            a.write('客户重要性: '+issue.customer_importance)
            b.write('建议处理顺序: '+str(issue.handling_priority or 'unspecified'))
            c.write('风险: '+issue.risk_level+' / 紧急度: '+issue.urgency)
            st.write(f'{issue.reason} · {issue.resolution} · {issue.business_process}')
            st.caption(f'建议路由 {issue.routing_team} · 归属 {issue.attribution_certainty} · 责任 unverified；流程分类不是已证实因果或法律责任。')
            st.text(issue.risk_rationale)
            if issue.priority_rationale:st.text(issue.priority_rationale)
            for label,events in [('问题证据',issue.evidence),('风险证据',issue.risk_evidence),('紧急度依据 '+issue.urgency_basis,issue.urgency_evidence),('客户重要性证据',issue.importance_evidence)]:
                for ev in events:st.text(f'{label} · {ev.field}[{ev.start}:{ev.end}]: {ev.quote}')
    st.warning('生成回复：未审核、未发送 · unreviewed / unsent')
    st.caption('候选回复语言: '+value.reply_language);st.text(value.suggested_reply)
    with st.expander('v3.1 provenance / v2 projection'):
        st.json(dict(schema=run.config.schema_version,config=run.config.model_dump(),input_hash=run.input_hash,
            original_prediction_hash=run.metadata['analysis_v31_hash'],derived_projection_hash=run.metadata['projection_hash'],
            projection=run.result.model_dump(),diagnostics=run.metadata['compatibility_diagnostics']))


def render(root):
    from src.application.v31_demo import EMAIL,fixture,ReplayV31
    from src.application.analysis_service import AnalysisService
    from src.infrastructure.repository import Repository
    from src.infrastructure.dashboard_sources import ReadOnlyRepository
    from src.application.v3_statistics import snapshot
    from src.dataset.adoption_v3 import validate
    from src.evaluation.p38_ab import preflight
    space=Path(os.getenv('COMPLAINT_P38_PREPARED',str(root/'.local/p38/prepared-final-v4')))
    db=Path(os.getenv('COMPLAINT_V31_DB_PATH',str(root/'.local/p38/ui/runs.sqlite3')))
    with st.expander('P3.8 policy v2 · v3.1 / 数据采用 / 内容审核'):
        st.caption('POLICY_V2_OWNER_APPROVED · 新增真实模型预算 0次 / 0元。旧v3与冻结24题独立保留。')
        st.text(EMAIL.body)
        if st.button('Analyze v3.1 offline fixture',key='v31_analyze'):
            a=ReplayV31({EMAIL.input_hash:fixture().model_dump()})
            r=AnalysisService(Repository(db),a).analyze(EMAIL)
            st.session_state['v31_run_id']=r.run_id;st.query_params['v31_run_id']=r.run_id
        lookup=st.text_input('V3.1 saved run ID',key='v31_lookup')
        if st.button('Load v3.1 saved run',key='v31_load'):
            st.session_state['v31_run_id']=lookup.strip();st.query_params['v31_run_id']=lookup.strip()
        if db.is_file():
            repo=ReadOnlyRepository(db);id=st.session_state.get('v31_run_id') or st.query_params.get('v31_run_id')
            if id:
                try:
                    r=repo.get(id)
                    if r and r.config.schema_version=='analysis-v3.1' and r.result:
                        st.caption('Run ID: '+r.run_id);show_v31(r)
                        same=repo.list_runs(cohort_id=r.cohort_id)
                        stats=snapshot(same,r.cohort_id,r.config.parameters['dataset_id'])
                        a,b=st.columns(2);a.metric('v3.1 complaint emails',stats['current_complaints']['numerator']);b.metric('v3.1 issues',stats['issue_count'])
                        st.download_button('Download v3.1 statistics',json.dumps(stats,ensure_ascii=False,indent=2),'v31-statistics.json','application/json',key='v31_stats')
                    else:st.warning('未找到本版本已接受预测。')
                except (ValueError,KeyError,TypeError):st.error('v3.1运行绑定失败，拒绝显示。')
        if (space/'dataset-v3.json').is_file():
            try:
                dataset=validate(json.loads((space/'dataset-v3.json').read_text(encoding='utf8')))
                st.write(dataset['counts'])
                queue=st.selectbox('P3.8 dataset queue',['natural','adversarial','quarantine','superseded'],key='v31_dataset_queue')
                rows=[r for r in dataset['records'] if (r['state']=='superseded' if queue=='superseded' else r['state']=='current' and r['queue']==queue)]
                chosen=st.selectbox('P3.8 candidate version',[r['record_id'] for r in rows],key='v31_candidate')
                r=next(r for r in rows if r['record_id']==chosen)
                st.text(r['source_record']['subject']);st.text(r['source_record']['body'])
                st.json({k:r[k] for k in ('record_id','logical_id','input_hash','supersedes','quality_status','semantic_review_status','reference','prediction')})
                st.caption('文本质量采用不等于独立Gold；对抗、隔离和旧版本不计入自然邮件分母。')
            except (OSError,ValueError,KeyError,TypeError):st.error('数据集manifest绑定失败；拒绝导入。')
        else:st.caption('尚无本机P3.8采用包；可用 scripts/p38.py prepare 生成新目录。')
        if (space/'ab-manifest.json').is_file():
            try:
                check=preflight(json.loads((space/'ab-manifest.json').read_text(encoding='utf8')))
                st.write('同v3.1迁移基线A / 业务优化B；真实A/B待新授权。');st.json(check)
            except (ValueError,KeyError,TypeError):st.error('A/B身份发生漂移，需要生成新实验版本。')
        render_review(root,space)


def render_review(root,space):
    path=space/'semantic-review-v2.json'
    if not path.is_file():return
    from src.evaluation.semantic_review_v2 import validate_review
    from src.infrastructure.dashboard_sources import ReadOnlyRepository
    try:
        packets=json.loads(path.read_text(encoding='utf8'))
        chosen=st.selectbox('P3.8 content review · 18 independent dimensions',[p['sample_id'] for p in packets],key='v31_content_sample')
        packet=next(p for p in packets if p['sample_id']==chosen)
        parents=json.loads((root/'.local/p37/review-v1/semantic-review24.json').read_text(encoding='utf8'))
        parent=next(p for p in parents if p['run_id']==packet['run_id'])
        run=ReadOnlyRepository(root/'.local/p36/draft-v3/runs.sqlite3').get(packet['run_id'])
        validate_review(run,parent,packet)
        st.caption(f'审核对象为旧{packet["source_schema"]}原始输出；v2政策候选评价，非v3.1新预测。真人评分pending。')
        st.text(run.email.body)
        if run.result:
            from src.app.v3_view import show_v3
            show_v3(run,'p38_content_original')
        else:st.warning('失败保留；无正式接受内容，不计成功内容评分。')
        for name,item in packet['dimensions'].items():
            with st.expander(name):
                st.write(item['ai_opinion'])
                for e in item['evidence']:st.text(f'{e["source"]}[{e["start"]}:{e["end"]}]: {e["quote"]}')
        notes=st.text_area('P3.8 human notes · unsigned draft',key='v31_human_notes_'+chosen)
        from src.domain.contracts import digest
        draft=dict(review_packet=packet,human_notes_draft=notes,human_status='pending')
        draft['draft_hash']=digest(draft)
        st.download_button('Download P3.8 unsigned review',json.dumps(draft,ensure_ascii=False,indent=2),chosen+'-p38-pending.json','application/json',key='v31_content_download')
    except (OSError,ValueError,TypeError,KeyError,StopIteration):st.error('内容审核包/来源绑定失败；拒绝显示。')
