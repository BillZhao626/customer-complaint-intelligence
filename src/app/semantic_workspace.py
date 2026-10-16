"""Read-only history -> original mail -> issue cards -> unsigned review draft."""
import json
import os
from pathlib import Path
import streamlit as st
from src.domain.contracts import digest
from src.infrastructure.dashboard_sources import ReadOnlyRepository


def bound_review(run, packet):
    from src.evaluation.semantic_review import validate_review
    validate_review(run,packet)
    if (packet.get('run_id')!=run.run_id or packet.get('input_hash')!=run.input_hash
            or packet.get('config_hash')!=digest(run.config.model_dump())
            or packet.get('output_hash')!=run.metadata.get('analysis_v3_hash')
            or packet.get('raw_hashes')!=[digest(a.raw_output) for a in run.attempts]):
        raise ValueError('Review/source binding mismatch')
    if packet.get('human_status')!='pending' or packet.get('human_reviewer') is not None:
        raise ValueError('This workspace displays unsigned preparation only')
    return packet


def render_semantic_workspace(root):
    source=Path(os.getenv('COMPLAINT_P37_SOURCE',str(root/'.local/p36')))
    review_path=Path(os.getenv('COMPLAINT_P37_REVIEW',str(root/'.local/p37/review-v1/semantic-review24.json')))
    with st.expander('P3.7 semantic review · 已存真实输出与Bad Case（只读）'):
        st.caption('本入口不调用模型、不登记预算、不更改历史run。原始输出、派生兼容视图与AI候选审阅分别标识。')
        choices=[n for n in ('draft-v3','catalog-v2','baseline-v1') if (source/n/'runs.sqlite3').is_file()]
        if not choices:
            st.info('没有本机历史实验；不会自动生成或调用模型。');return
        experiment=st.selectbox('历史模型/Prompt实验',choices,key='p37_history_experiment')
        try:runs=ReadOnlyRepository(source/experiment/'runs.sqlite3').list_runs()
        except (ValueError,OSError):st.error('历史数据库不可读或绑定验证失败。');return
        try:
            reviews=json.loads(review_path.read_text(encoding='utf8')) if review_path.is_file() else []
            if not isinstance(reviews,list):raise ValueError('Expected review list')
            indexed={p['run_id']:p for p in reviews}
            if len(indexed)!=len(reviews):raise ValueError('Duplicate review run')
        except (ValueError,OSError,TypeError,KeyError):
            st.error('审核包无法解析；原始历史结果仍可读，未导入审核。');indexed={}
        group=st.selectbox('审核队列',['全部历史输出','有AI候选风险','正式契约失败'],key='p37_queue')
        if group=='有AI候选风险':runs=[r for r in runs if indexed.get(r.run_id,{}).get('max_ai_severity') in ('medium','high','critical')]
        elif group=='正式契约失败':runs=[r for r in runs if r.status!='succeeded']
        if not runs:st.info('此队列没有记录；没有审核包的输出仍可在全部历史输出中查看。');return
        runs=sorted(runs,key=lambda r:(r.email.email_id,r.created_at))
        run_id=st.selectbox('选择具体样本 / 原始run',[r.run_id for r in runs],
            format_func=lambda rid:next(f'{r.email.email_id} · {r.status} · {r.run_id[:8]}' for r in runs if r.run_id==rid),key='p37_history_run')
        run=next(r for r in runs if r.run_id==run_id)
        st.caption(f'{run.config.model_id} / {run.config.prompt_version} · cohort {run.cohort_id}')
        st.write(f'Original run: {run.run_id} · {run.status}')
        st.write('原始邮件');st.text(run.email.subject);st.text(run.email.body)
        if run.result:
            from src.app.v3_view import show_v3
            show_v3(run,'review')
        else:
            st.error('无正式接受预测。原始返回仅用于失败归因，不能当成成功分析或内容评分。')
            with st.expander('失败原始provider返回 / 校验阶段'):
                for attempt in run.attempts:
                    st.caption(f'attempt {attempt.attempt_no} · {attempt.stage} · {attempt.error.error_type if attempt.error else "unknown"}')
                    st.text(attempt.raw_output or 'No provider content')
        packet=indexed.get(run_id)
        if packet:
            try:bound_review(run,packet)
            except (ValueError,KeyError,TypeError):st.error('审核包与原始输出不匹配，拒绝展示。');return
            st.write('AI候选审阅 · 人工评分待审')
            for dimension,item in packet['dimensions'].items():
                st.write(f'{dimension}: {item["severity"]} · {item["opinion"]}')
                for evidence in item['evidence']:
                    st.text(f'{evidence["source"]} [{evidence["start"]}:{evidence["end"]}]: {evidence["quote"]}')
            st.download_button('Download unsigned semantic review · 待审清单',json.dumps(packet,ensure_ascii=False,indent=2),
                               f'{run.run_id}-p37-pending.json','application/json',key='p37_review_download')
        else:st.caption('此run尚无P3.7内容审核包；不是已审核或正确输出。')
