"""Customer-facing views. All durable operations use application services."""
import difflib
from uuid import uuid4
import pandas as pd
import streamlit as st
from src.app.product_workspace import store, label, show_analysis, historical_catalog
from src.application.copilot_demo import SCENARIOS, TITLES, FOLLOWUP, CopilotFake, example
from src.application.mail_threads import MailThreads
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.infrastructure.repository import Repository
from src.domain.contracts import EmailInput, digest


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


def review(db, c):
    st.subheader('回复助手')
    if not c['draft']:
        st.error('没有可审核草稿。分析失败，请转人工处理；原输入已保留。')
        return
    if c['receipt']:
        st.success('模拟发送已完成 · 未投递真实邮件')
        st.text(c['receipt']['body'])
        st.caption(f"已保存回复 v{c['receipt']['version']} · {c['receipt']['created_at']}")
        return
    quality = c['quality']
    key = f"p4_reply_{c['case_id']}_{c['current_version']}"
    edited = st.text_area('回复草稿（保存修改后须重新审核）', value=c['draft']['body'], height=180, key=key)
    dirty = edited != c['draft']['body']
    analysis_block = any(f['severity'] == 'block' and f['scope'] == 'analysis' for f in quality['findings'])
    if analysis_block:
        st.error('分析存在错误，需人工介入。修改回复不能解除阻断；可拒绝该草稿并保留记录。')
    elif quality['status'] == 'blocked':
        st.error('回复存在未验证承诺或安全问题。请修改并保存，再重新审核。')
    elif dirty:
        st.info('下一步：保存修改，生成新版本后重新审核。')
    elif c['state'] == 'approved':
        st.info('下一步：模拟发送已批准的这一版本。')
    elif c['state'] == 'rejected':
        st.info('草稿已拒绝；如需继续，必须编辑并保存新版本。')
    else:
        st.caption('下一步：核对右侧原文依据，完成审核后使用建议。')
    # Keep the primary action near the draft. Review fields remain below it.
    action_area = st.container()
    with st.expander('人工核对与审核说明', expanded=c['state'] != 'approved'):
        actor_type = st.selectbox('审核身份类型', ['demo_test', 'local_human'],
            format_func=lambda x: '演示验收（不计真人评价）' if x == 'demo_test' else '本地人工审核', key='p4_actor_type')
        actor = st.text_input('本地审核人标识', value='demo_operator', key='p4_actor')
        reason = st.text_area('审核/退回/拒绝原因', key=f"p4_reason_{c['case_id']}", height=68)
        checks = {
            'facts_evidence': st.checkbox('已逐项核对事实、Evidence、情绪、原因、状态与主次', key=f"p4_facts_{c['case_id']}_{c['current_version']}"),
            'authority_privacy': st.checkbox('已核对商家资料责任、渠道、隐私及未执行动作承诺', key=f"p4_authority_{c['case_id']}_{c['current_version']}"),
            'all_issues': st.checkbox('回复覆盖所有诉求且未虚构退款、联系或未来执行能力', key=f"p4_issues_{c['case_id']}_{c['current_version']}"),
        }
        if quality['safety_review_required']:
            checks['safety'] = st.checkbox('已核对可预见严重伤害、停止使用建议及不复现危险故障', key=f"p4_safety_{c['case_id']}_{c['current_version']}")
    with action_area:
        primary = 'save_edit' if dirty else 'simulate_send' if c['state'] == 'approved' else 'approve'
        actions = [('保存新版本', 'save_edit'), ('批准草稿', 'approve'), ('模拟发送', 'simulate_send')]
        for column, (title, action) in zip(st.columns(3), actions):
            disabled = (not dirty if action == 'save_edit' else
                dirty or quality['status'] == 'blocked' or (c['state'] != 'approved' if action == 'simulate_send' else c['state'] not in ('pending_review', 'changes_requested')))
            if column.button(title, key='p4_' + action, disabled=disabled, type='primary' if action == primary else 'secondary', width='stretch'):
                act(db, c, action, actor, actor_type, reason, checks, edited)
    with st.expander('放弃建议或退回修改'):
        for column, (title, action) in zip(st.columns(2), [('退回修改', 'request_changes'), ('拒绝草稿', 'reject')]):
            if column.button(title, key='p4_' + action):
                act(db, c, action, actor, actor_type, reason, checks, edited)


def act(db, c, action, actor, actor_type, reason, checks, edited):
    try:
        result = db.act(c['case_id'], action, expected_revision=c['revision'], actor=actor, actor_type=actor_type,
                        reason=reason, checks=checks, body=edited if action == 'save_edit' else None, operation_id=str(uuid4()))
        select_case(result)
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
    try:
        db = store(root)
        threads = MailThreads(db)
        cases = db.list_cases()
    except Exception as exc:
        st.error(f'接待工作库不可用（{type(exc).__name__}）。未开始分析或审核。'); return
    if st.session_state.get('p4_notice'):
        st.success(st.session_state.pop('p4_notice'))
    by_id = {c['case_id']: c for c in cases}
    current = st.session_state.get('p4_case') or st.query_params.get('case_id')
    c = by_id.get(current)
    left, center, right = st.columns([1.05, 2.5, 1.5], gap='medium')
    with left:
        st.subheader('客户邮件')
        if 'p45_select_history' in st.session_state:
            st.session_state['p4_history'] = st.session_state.pop('p45_select_history')
        if cases:
            choices = [f"{i}:{by_id[i]['revision']}" for i in by_id]
            selected = st.selectbox('已保存的邮件', choices, index=list(by_id).index(current) if current in by_id else 0,
                format_func=lambda v: f"{label(by_id[v.split(':')[0]]['state'])} · {by_id[v.split(':')[0]]['run'].email.subject}", key='p4_history')
            if st.button('打开历史案例', key='p4_open', width='stretch'):
                select_case(by_id[selected.split(':')[0]]); st.rerun()
            if c:
                st.caption(f"{label(c['state'])} · 未解决投诉/未知问题 {unresolved(c)} 项")
                if c['quality']['status'] == 'blocked':
                    st.warning('需人工介入')
        else:
            st.caption('从一个案例开始，体验完整处理过程。')
        scenario = st.selectbox('演示场景', SCENARIOS, key='p4_scenario')
        email, data = example(scenario)
        if st.button('载入邮件与回复建议', key='p4_analyze', type='primary' if not c else 'secondary', width='stretch'):
            try:
                if scenario == SCENARIOS[6]:
                    subject, body = st.session_state.get('p4_subject', '新客户邮件'), st.session_state.get('p4_body', '')
                    email = EmailInput(email_id='manual-' + digest(dict(subject=subject, body=body))[:24], subject=subject, body=body)
                repo = Repository(db.path.with_name(db.path.stem + '-analysis.sqlite3'))
                select_case(ProductAnalysis(AnalysisService(repo, CopilotFake(email, scenario)), db).submit(email)); st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f'邮件保存未确认（{type(exc).__name__}）。请重读历史或重试同一输入；未发起真实请求。')
        st.caption('预写示例，无模型调用。新邮件仅存 unknown，需人工处理。')
        if scenario == SCENARIOS[6]:
            st.text_input('邮件主题', value='新客户邮件', key='p4_subject')
            st.text_area('客户邮件正文', key='p4_body', height=140)
        st.caption('选择场景后点击载入。已有邮件和审核记录会保留。')
    with center:
        if c:
            messages = threads.messages(c['case_id'])
            latest = next(m for m in reversed(messages) if m['role'] == 'customer')
            st.subheader(latest['subject'])
            st.caption(provenance(c))
            with st.container(border=True):
                st.text(latest['body'])
            review(db, c)
            versions(c)
            thread_panel(threads, c)
        else:
            st.subheader(email.subject)
            st.caption('离线预写案例预览 · 尚未保存或审核')
            with st.container(border=True):
                st.text(email.body)
            st.subheader('回复助手')
            st.text(data['suggested_reply'] if scenario != SCENARIOS[6] else '新邮件未进行模型分析。请在左侧输入正文，保存后人工编辑。')
            st.info('下一步：点击左侧「载入邮件与回复建议」，开始编辑与审核。')
    with right:
        understanding(c['analysis'] if c and c['accepted'] else None if c or scenario == SCENARIOS[6] else data, c['quality'] if c else None)


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
