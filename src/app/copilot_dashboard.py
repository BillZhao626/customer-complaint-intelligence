"""Business dashboard separated from single-email reception."""
import pandas as pd
import streamlit as st
from src.app.product_workspace import store, label, show_analysis
from src.application.copilot_statistics import summarize


def render(root):
    st.subheader('客户问题与处理进度')
    db = store(root)
    dashboard = db.dashboard()
    st.caption('演示/研究工作案例，不是真实经营统计。每个完整来源版本组独立计算；同一邮件的新分析属于新案例，不是新增客户。')
    if not dashboard['groups']:
        st.info('尚无已保存案例。请先在智能接待载入邮件。'); return
    groups = {g['source_kind'] + ':' + g['cohort_id']: g for g in dashboard['groups']}
    group_keys = list(groups)
    # Keep the domain selection separate from the widget identity. Streamlit
    # recreates a selectbox when options change after a new case is saved.
    previous_group = st.session_state.get('business_cohort_choice')
    selected_group = st.selectbox('来源与分析版本', group_keys, key='business_cohort',
        index=group_keys.index(previous_group) if previous_group in groups else 0,
        format_func=lambda k: f"{label(groups[k]['source_kind'])} · {groups[k]['prompt']} · {groups[k]['total']} 个分析案例 · {groups[k]['cohort_id'][:8]}")
    st.session_state['business_cohort_choice'] = selected_group
    group = groups[selected_group]
    cols = st.columns(4)
    for col, title, key in zip(cols, ['分析案例', '可统计分母', '分析失败', '需人工介入'], ['total', 'business_denominator', 'failed', 'blocked']):
        col.metric(title, group[key])
    st.caption(f"未知情绪 {group['unknown_sentiment']} · 回退 {group['fallback']} · 分析阻断 {group['analysis_blocked']} · 回复阻断 {group['reply_blocked']}。失败与分析阻断不进入业务分母，unknown保留；回复阻断仍进入。")
    cases = [db.get(i) for i in group['member_case_ids']]
    state = st.selectbox('处理状态筛选', ['全部', '待处理', '需人工介入', '已模拟发送'], key='business_state')
    filtered = [c for c in cases if state == '全部' or
        state == '需人工介入' and c['quality']['status'] == 'blocked' or
        state == '已模拟发送' and c['state'] == 'simulated_sent' or
        state == '待处理' and c['state'] != 'simulated_sent']
    st.caption(f'当前筛选 {len(filtered)} / 本版本组 {len(cases)} 案例；模拟发送不表示业务问题已解决。')
    dimension = st.radio('查看维度', ['商品', '门店', '问题原因', '业务来源', '情绪', '日期'], horizontal=True, key='business_dimension')
    rows = summarize(filtered, dimension)
    if rows:
        st.dataframe(pd.DataFrame([{'分组': label(r['name']), '邮件分析案例': r['total'], '负面反馈': r['negative'], '投诉案例': r['complaints'], '含未解决问题': r['unresolved']} for r in rows]), hide_index=True, width='stretch')
        st.caption('每组按case去重，多问题可跨组；组间数量不可直接相加。商品仅统计product对象，未提供信息归unknown。日期为案例保存日（UTC），不冒充客户来信时间或真实经营趋势。')
    members = filtered
    if members:
        member_map = {c['case_id'] + ':' + str(c['revision']): c for c in members}
        selected_member = st.selectbox('下钻查看原文', list(member_map),
            format_func=lambda k: f"{member_map[k]['run'].email.subject} · {label(member_map[k]['state'])}",
            key='business_member_' + selected_group + '_' + state)
        member = member_map[selected_member]
        with st.expander('原始邮件与判断依据', expanded=True):
            show_analysis(member)
            st.link_button('在智能接待打开此邮件', '?case_id=' + member['case_id'])
    with st.expander('开发者统计口径与身份'):
        st.json(dashboard)
        st.caption(str(db.path))
