"""Customer-facing views. All durable operations use application services."""
import difflib
from uuid import uuid4
import streamlit as st
from src.app.product_workspace import store, label, show_analysis, historical_catalog
from src.application.copilot_demo import SCENARIOS, FOLLOWUP, example
from src.application.mail_threads import MailThreads


def select_case(c):
    st.session_state['p4_case'] = c['case_id']
    st.session_state['p45_select_history'] = c['case_id'] + ':' + str(c['revision'])
    st.query_params['case_id'] = c['case_id']


def provenance(c):
    if c['source_kind'] == 'offline_fake':
        params = c['run'].config.parameters or {}
        if params.get('product_scenario') == SCENARIOS[6]:
            return '未进行AI理解 · unknown流程占位'
        return '离线预写案例 · 无实时模型推理'
    return label(c['source_kind']) + ' · 本次未发起模型请求'


def unresolved(c):
    return sum(i.get('resolution') in ('unresolved', 'unknown') for i in (c['analysis'] or {}).get('issues', []))


def act(db, c, action, actor, actor_type, reason, checks, edited):
    try:
        result = db.act(c['case_id'], action, expected_revision=c['revision'], actor=actor, actor_type=actor_type,
                        reason=reason, checks=checks, body=edited if action == 'save_edit' else None, operation_id=str(uuid4()))
        select_case(result)
        st.session_state.pop('p46_review', None)
        st.session_state['p4_notice'] = '已保存操作记录；真实邮件发送次数为 0。'
        st.rerun()
    except ValueError as exc:
        translations = {
            'Review checklist and a reason are required; no automatic approval': '请填写审核说明，并完成全部核对项后再批准。系统不会自动批准。',
            'Rejection or return requires a reason': '请先在审核说明中填写拒绝或退回原因。',
            'Stale page: reload current case before changing it': '此邮件状态已更新，请重新打开最新案例后再操作。',
            'Rejected draft must be edited before a new review': '已拒绝的草稿必须编辑并保存新版本后才能重新审核。',
        }
        st.error(translations.get(str(exc), str(exc)))
    except Exception as exc:
        st.error(f'保存未确认（{type(exc).__name__}）。请保留编辑，重读状态后重试。')


def versions(c):
    with st.expander('草稿版本与修改前后内容'):
        for d in c['drafts']:
            st.caption(f"v{d['version']} · {d['created_at']} · {d['editor']} / {d['actor_type']}")
            st.text(d['body'])
            if d['version'] > 1:
                before = c['drafts'][d['version'] - 2]['body']
                st.code('\n'.join(difflib.unified_diff(before.splitlines(), d['body'].splitlines(), fromfile=f"v{d['version']-1}", tofile=f"v{d['version']}", lineterm='')), language='diff')


def understanding(data, quality=None):
    st.subheader('理解与依据')
    if not data:
        st.info('无法形成可信的结构化判断，请人工阅读原邮件。')
        return
    st.write(data.get('summary', '尚无摘要'))
    st.caption(f"{label(data.get('complaint_status'))} · 情绪{label(data.get('sentiment'))} · 紧急度{label(data.get('urgency'))}")
    st.caption('提及门店（待核实）：' + label(data.get('mentioned_store', data.get('store_location', 'unknown'))))
    if not data.get('issues') and data.get('product_name'):
        st.caption('商品或服务：' + label(data['product_name']))
    st.caption('判断来自当前标示来源；业务来源不等于已证实原因或责任。')
    issues = data.get('issues', [])
    for n, i in enumerate(issues, 1):
        with st.expander(f"{n}. {label(i.get('object_name'))} · {label(i.get('issue_kind'))} · Evidence", expanded=n == 1):
            st.write('客户诉求：' + '；'.join(i.get('customer_requests', [])))
            st.write(f"风险：{label(i.get('risk_level'))} · 处理顺序：{i.get('handling_priority') or '待判断'}")
            st.caption(f"客户重要性：{label(i.get('customer_importance'))} · 业务来源：{label(i.get('business_process'))}")
            for e in i.get('evidence', []):
                st.text(e['quote'])
            st.write('还需补充：' + '；'.join(i.get('missing_evidence', [])))
            st.caption('以上是待核实信息，不代表已查询订单、已退款或已安排服务。')
    if quality:
        for f in quality['findings']:
            reason = {
                'potential_injury_downgrade': '承重结构失效须按严重风险/高紧急度复核；无人受伤不能降级。',
                'severe_safety_review': '需要人工安全复核：停止使用，不复现危险故障。',
                'unavailable_future_action': '回复承诺了本系统尚不能执行的联系或后续操作。',
                'missing_stop_use_advice': '严重风险回复缺少停止使用提醒。',
                'analysis_not_accepted': '分析未通过结构校验，不能审核或模拟发送。',
            }.get(f['code'], f['reason'])
            (st.error if f['severity'] == 'block' else st.warning)(reason)
        st.caption('规则只提供有限诊断；未发现问题不代表语义正确。')


def thread_panel(threads, c):
    messages = threads.messages(c['case_id'])
    if len(messages) > 1:
        with st.expander(f'邮件往来 · {len(messages)}条（客服回复仅模拟）'):
            for m in messages:
                st.caption(('客户' if m['role'] == 'customer' else '客服 · 模拟回复') + ' · ' + m['at'])
                st.text(m['body'])
    child = threads.child(c['case_id'])
    if child:
        if st.button('打开客户后续邮件', key='thread_open'):
            select_case(threads.store.get(child)); st.rerun()
    elif c['state'] == 'simulated_sent':
        with st.expander('录入客户后续邮件', expanded=True):
            preset = c['run'].email == example(SCENARIOS[0])[0]
            st.caption('相机预设第二轮仅为编写的演示；其他内容只存 unknown 上下文，不做动态模型理解。')
            body = st.text_area('客户新增信息', value=FOLLOWUP if preset else '', key='followup_' + c['case_id'])
            if st.button('保存后续邮件并载入建议', type='primary', key='thread_submit'):
                try:
                    select_case(threads.follow_up(c['case_id'], 'Re: ' + c['run'].email.subject, body)); st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f'后续邮件保存未确认（{type(exc).__name__}）。内容保留；请重试同一输入，已存分析不会重复请求。')


def render(root):
    from src.app.copilot_inbox import render as render_inbox
    render_inbox(root)


def research(root):
    st.subheader('运行来源与执行说明')
    st.caption('付费请求关闭。四类来源独立：离线预写 Fixture、历史真实重放、真实SDK＋Mock HTTP、新真实请求（本轮未启用）。')
    st.markdown('真实调用适配：输入邮件 → 版本化消息构造 → **ChatOpenAI.ainvoke** → 严格 Issue / Evidence 校验 → ProductAnalysis → 人工审核。\n\n当前演示：显式邮件上下文组装 → **RunnableLambda 返回预写结果/unknown** → 同一校验与审核。旧兼容链的 ChatPromptTemplate 是独立入口；三者没有组成一条实时链。')
    db = store(root)
    mode = st.radio('分析方式', ['Offline Fake / 离线演示', '真实历史run / 只读重放'], key='p4_mode', horizontal=True)
    if mode.startswith('真实'):
        from src.application.product_sources import sources, read_run
        paths = sources(root)
        items = historical_catalog(str(root), tuple((str(p), p.stat().st_mtime_ns) for p in paths))
        if items:
            item = st.selectbox('选择历史真实运行', items, format_func=lambda i: f"{i['email_id']} · {i['arm']} · {i['status']} · {i['run_id']}", key='p4_source_run')
            if st.button('重放并建立未审核工作副本', key='p4_replay'):
                select_case(db.create(read_run(item['path'], item['run_id']), item['path'])); st.rerun()
        else:
            st.info('此检出无历史真实结果。')
    current = st.session_state.get('p4_case') or st.query_params.get('case_id')
    c = db.get(current) if current else None
    if c:
        with st.expander('当前案例：完整运行、Prompt、Schema 与原始输出'):
            show_analysis(c)
            st.json(c['run'].model_dump())
            st.json(dict(events=c['events'], receipt=c['receipt'], thread=MailThreads(db).link(c['case_id'])))
