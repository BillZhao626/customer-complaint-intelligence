"""P4 product boundary: rendering only; durable transitions live in ProductStore."""
import difflib
import os
from pathlib import Path
from uuid import uuid4
import pandas as pd
import streamlit as st
from src.application.product_workflow import ProductStore, Conflict
from src.application.product_demo import SCENARIOS, ProductFake, example
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis, SnapshotPending
from src.infrastructure.repository import Repository
from src.domain.contracts import EmailInput


@st.cache_data(show_spinner=False)
def historical_catalog(root, stamps):
    from src.application.product_sources import catalog
    return catalog(Path(root))


def store(root):
    return ProductStore(os.getenv('COMPLAINT_PRODUCT_DB', str(root / '.local/p4/product.sqlite3')))


LABELS = {
    'camera': '相机', 'drawer': '抽屉', 'old bed collection': '旧床取件', 'invoice': '发票',
    'baking tray': '烤盘', 'desk lamp': '台灯', 'delivered package': '已送达包裹', 'folding bicycle': '折叠车',
    'pending_review': '待审核', 'changes_requested': '待修改', 'approved': '已批准',
    'rejected': '已拒绝', 'simulated_sent': '已模拟发送', 'analysis_failed': '分析失败',
    'negative': '负面', 'positive': '正面', 'neutral': '中性', 'mixed': '混合', 'unknown': '未知',
    'low': '低', 'medium': '中', 'high': '高', 'none': '无', 'minor': '轻微', 'severe': '严重',
    'unspecified': '未明确', 'primary': '主要', 'secondary': '次要', 'equal': '同等重要',
    'no_complaint': '非投诉', 'current_unresolved': '当前未解决投诉',
    'historical_resolved': '历史已解决', 'mixed_status': '混合状态',
    'offline_fake': '离线示例 / unknown占位', 'legacy_mock': '旧规则 Mock',
    'real_replay': '历史真实结果重放', 'real_new_analysis': '新真实分析',
    'offline_mock_http': '离线 Mock HTTP（真实SDK）',
    'inquiry': '咨询', 'complaint': '投诉', 'praise': '表扬',
    'product quality': '商品质量', 'health or safety issue': '健康或安全问题',
    'delivery delay': '配送延迟', 'customer service': '客户服务',
    'billing or payment': '账单或付款', 'not_applicable': '不适用',
    'reported': '客户报告，未核实', 'unclear': '不明确',
    'product issue': '商品问题', 'store service issue': '门店服务问题',
    'delivery/logistics issue': '配送/物流问题', 'billing/invoice issue': '账单/发票问题',
    'after-sales service': '售后服务', 'other': '其他',
}


def label(value):
    return LABELS.get(value, value or '未提供')


def show_analysis(c):
    run = c['run']
    st.subheader('原始邮件与分析结论')
    st.caption(f"来源：{label(c['source_kind'])} · 原契约：{'接受' if c['accepted'] else '失败'}（不代表语义认证）")
    st.text(run.email.subject)
    st.text(run.email.body)
    if c['accepted']:
        data = c['analysis']
        cols = st.columns(3)
        for col, title, field in zip(cols, ('情绪', '投诉状态', '紧急度'), ('sentiment', 'complaint_status', 'urgency')):
            col.metric(title, label(data.get(field)))
        st.text(data.get('summary', ''))
        st.caption('业务来源与建议处理顺序均不等于已核实责任；客户重要性单独保留。')
        for i in data.get('issues', []):
            with st.expander(f"问题 {i['issue_id']} · {i.get('object_name', '')} · Evidence 原文证据", expanded=True):
                st.write(f"类型：{label(i.get('issue_kind'))} ｜ 原因：{label(i.get('reason'))} ｜ 风险：{label(i.get('risk_level'))}")
                st.write(f"处理顺序：{i.get('handling_priority')} ｜ 客户重要性：{label(i.get('customer_importance'))} ｜ 紧急度：{label(i.get('urgency'))}")
                for field, title in (('evidence', '判断依据'), ('risk_evidence', '风险依据'), ('urgency_evidence', '紧急度依据'), ('importance_evidence', '重要性依据')):
                    for e in i.get(field, []):
                        st.text(f"{title} · {e['field']}[{e['start']}:{e['end']}]: {e['quote']}")
                for field, title in (('risk_rationale', '风险说明'), ('priority_rationale', '处理顺序说明'), ('missing_evidence', '待补证据')):
                    value = i.get(field)
                    st.write(title + '：' + ('；'.join(value) if isinstance(value, list) else str(value or '无')))
    else:
        st.error('分析失败或结构化输出无效；raw 仅供诊断，不进入正式统计或发送。')
    with st.expander('Developer Details · 运行身份、原始输出与校验记录'):
        st.json(dict(case_id=c['case_id'], run_id=run.run_id, input_hash=run.input_hash,
                     source_snapshot_hash=c['snapshot_hash'], source_kind=c['source_kind'],
                     created_at=run.created_at, config=run.config.model_dump(), attempts=[a.model_dump() for a in run.attempts],
                     analysis=c['analysis'], quality=c['quality']))


def show_case(db, c):
    st.subheader(f"{label(c['state'])} · 回复草稿 v{c['current_version']}")
    show_analysis(c)
    quality = c['quality']
    st.subheader('质量门禁与人工审核')
    st.warning('每份回复均为草稿。词面检查未命中不能证明语义正确；五项政策批准不等于完整回复批准。')
    if quality['status'] == 'blocked':
        st.error('存在阻断问题：必须修订回复；分析本身错误则拒绝当前案例，保留原预测。')
    if quality['findings']:
        st.dataframe(pd.DataFrame(quality['findings'])[['severity', 'scope', 'code', 'quote', 'reason']], hide_index=True, width='stretch')
    st.caption(f"{quality['version']} · {quality['policy_version']} · {quality['policy_hash'][:16]} · 复杂语义仍需逐项人工核对")
    if c['draft']:
        key = f"p4_reply_{c['case_id']}_{c['current_version']}"
        edited = st.text_area('回复草稿（保存修改后须重新审核）', value=c['draft']['body'], height=190, key=key, disabled=c['state'] == 'simulated_sent')
        actor_type = st.selectbox('审核身份类型', ['demo_test', 'local_human'],
                                 format_func=lambda x: '演示/自动化验收（不计真人评价）' if x == 'demo_test' else '本地人工审核', key='p4_actor_type')
        actor = st.text_input('本地审核人标识', value='demo_operator', key='p4_actor')
        reason = st.text_area('审核/退回/拒绝原因', key=f"p4_reason_{c['case_id']}")
        checks = {
            'facts_evidence': st.checkbox('已逐项核对事实、Evidence、情绪、原因、状态与主次', key=f"p4_facts_{c['case_id']}_{c['current_version']}"),
            'authority_privacy': st.checkbox('已核对商家资料责任、渠道、隐私及未执行动作承诺', key=f"p4_authority_{c['case_id']}_{c['current_version']}"),
            'all_issues': st.checkbox('回复覆盖所有诉求且未虚构退款、联系或未来执行能力', key=f"p4_issues_{c['case_id']}_{c['current_version']}"),
        }
        if quality['safety_review_required']:
            checks['safety'] = st.checkbox('已核对可预见严重伤害、停止使用建议及不复现危险故障', key=f"p4_safety_{c['case_id']}_{c['current_version']}")
        dirty = edited != c['draft']['body']
        if dirty:
            st.info('有未保存修改；请先保存新版本后再审核或模拟发送。')
        cols = st.columns(5)
        actions = [('保存新版本', 'save_edit'), ('批准草稿', 'approve'), ('退回修改', 'request_changes'), ('拒绝草稿', 'reject'), ('模拟发送', 'simulate_send')]
        for col, (action_label, action) in zip(cols, actions):
            disabled = c['state'] == 'simulated_sent'
            if action == 'approve':
                disabled |= dirty or quality['status'] == 'blocked' or c['state'] not in ('pending_review', 'changes_requested')
            elif action == 'simulate_send':
                disabled |= dirty or quality['status'] == 'blocked' or c['state'] != 'approved'
            if col.button(action_label, key='p4_' + action, disabled=disabled):
                try:
                    db.act(c['case_id'], action, expected_revision=c['revision'], actor=actor, actor_type=actor_type,
                           reason=reason, body=edited if action == 'save_edit' else None, checks=checks,
                           operation_id=str(uuid4()))
                    st.session_state['p4_notice'] = f'{action_label}已持久化；真实邮件发送次数为 0。'
                    st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc) if isinstance(exc, ValueError) else '写入失败；保留当前编辑，未确认成功。请重读状态后重试。')
                except Exception as exc:
                    st.error(f'操作未确认成功（{type(exc).__name__}）；保留编辑并重读最新状态。')
    if c['receipt']:
        st.success('模拟发送已完成 · 没有网络投递或外部系统操作')
        with st.expander('Developer Details · 模拟回执'):
            st.json(c['receipt'])
    with st.expander('草稿版本与修改前后内容', expanded=False):
        for d in c['drafts']:
            st.write(f"v{d['version']} · {d['created_at']} · {d['editor']} / {d['actor_type']}")
            st.text(d['body'])
            if d['version'] > 1:
                before = c['drafts'][d['version'] - 2]['body']
                st.code('\n'.join(difflib.unified_diff(before.splitlines(), d['body'].splitlines(), fromfile=f"v{d['version']-1}", tofile=f"v{d['version']}", lineterm='')), language='diff')
    with st.expander('操作记录（演示操作不计独立人工评分）'):
        st.json(c['events'])


def render_legacy(root):
    st.header('客诉处理工作台 · P4 候选版')
    st.caption('输入 → 分析与证据 → 草稿版本 → 人工审核 → 模拟发送 → 历史重读')
    st.info('本轮付费调用已禁用。可重放历史真实结果，或使用明确标识的 Offline Fake。真实 SMTP / CRM 未接入。')
    try:
        db = store(root)
    except Exception as exc:
        st.error(f'工作库不可用（{type(exc).__name__}）；不会开始分析或审核。')
        return
    notice = st.session_state.pop('p4_notice', None)
    if notice:
        st.success(notice)
    mode = st.radio('分析方式', ['Offline Fake / 离线演示', '真实历史run / 只读重放'], horizontal=True, key='p4_mode')
    if mode.startswith('Offline'):
        scenario = st.selectbox('演示场景', SCENARIOS, key='p4_scenario')
        if st.session_state.get('p4_loaded_scenario') != scenario:
            e, _ = example(scenario)
            st.session_state.update(p4_subject=e.subject, p4_body=e.body, p4_email=e.email_id, p4_loaded_scenario=scenario)
        email_id = st.text_input('客户邮件编号', key='p4_email')
        subject = st.text_input('邮件主题', key='p4_subject')
        body = st.text_area('客户邮件正文', height=120, key='p4_body')
        st.caption('固定场景为显式编写的工程fixture。修改正文请选“自定义邮件”，它只保存unknown占位，不推定模型理解。')
        if st.button('分析并保存草稿', key='p4_analyze', type='primary'):
            try:
                email = EmailInput(email_id=email_id, subject=subject, body=body)
                expected, _ = example(scenario)
                if scenario != SCENARIOS[-1] and (email.subject, email.body) != (expected.subject, expected.body):
                    raise ValueError('固定fixture正文或主题已改变；请选择自定义unknown模式。')
                repository = Repository(db.path.with_name(db.path.stem + '-analysis.sqlite3'))
                c = ProductAnalysis(AnalysisService(repository, ProductFake(email, scenario)), db).submit(email)
                st.session_state['p4_case'] = c['case_id']
                st.session_state['p4_history'] = c['case_id'] + ':' + str(c['revision'])
                st.query_params['case_id'] = c['case_id']
                st.rerun()
            except SnapshotPending as exc:
                st.error(f'分析已保存，产品快照待恢复。运行编号：{exc.run_id}；可通过 ProductAnalysis.recover 重建，不重复请求。')
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f'分析保存未确认（{type(exc).__name__}）；请检查历史，未发起真实模型调用。')
    else:
        from src.application.product_sources import sources, read_run
        paths = sources(root)
        items = historical_catalog(str(root), tuple((str(p), p.stat().st_mtime_ns) for p in paths))
        if items:
            item = st.selectbox('选择历史真实运行', items, format_func=lambda i: f"{i['email_id']} · {i['arm']} · {i['status']} · {i['run_id']}", key='p4_source_run')
            if st.button('重放并建立未审核工作副本', key='p4_replay'):
                try:
                    c = db.create(read_run(item['path'], item['run_id']), item['path'])
                    st.session_state['p4_case'] = c['case_id']
                    st.session_state['p4_history'] = c['case_id'] + ':' + str(c['revision'])
                    st.query_params['case_id'] = c['case_id']
                    st.rerun()
                except Exception as exc:
                    st.error(f'重放失败（{type(exc).__name__}）；原实验库保持只读。')
        else:
            st.caption('此检出没有本地真实run；使用离线fixture，不制造真实结果。')
    try:
        cases = db.list_cases()
        st.subheader('工作历史')
        if cases:
            ids = [c['case_id'] for c in cases]
            by_id = {c['case_id']: c for c in cases}
            current_id = st.session_state.get('p4_case') or st.query_params.get('case_id')
            # Include revision: a stable option otherwise retains its old label.
            choices = [f"{i}:{by_id[i]['revision']}" for i in ids]
            selected_option = st.selectbox('选择工作案例', choices, index=ids.index(current_id) if current_id in ids else 0,
                                    format_func=lambda option: f"{by_id[option.split(':')[0]]['run'].email.email_id} · {label(by_id[option.split(':')[0]]['source_kind'])} · {label(by_id[option.split(':')[0]]['state'])} · {option[:8]}", key='p4_history')
            selected = selected_option.split(':')[0]
            if st.button('打开历史案例', key='p4_open'):
                st.session_state['p4_case'] = selected
                st.query_params['case_id'] = selected
                st.rerun()
            if current_id in by_id:
                show_case(db, by_id[current_id])
        else:
            st.caption('暂无工作案例。')
        show_dashboard(db)
    except Exception as exc:
        st.error(f'历史读取或一致性检查失败（{type(exc).__name__}）；不生成虚假成功记录。')


def show_dashboard(db, key='workspace'):
    st.subheader('工作台统计 · 按来源与版本分组')
    with st.expander('Developer Details · 数据库位置'):
        st.caption(str(db.path))
    d = db.dashboard()
    st.write({'工作案例总数': d['total'], '审核状态': {label(k): v for k, v in d['states'].items()}})
    st.caption('契约接受数 accepted + 失败数 failed = 全部案例。blocked 可与 accepted 重叠；分析阻断排除出业务分母，回复阻断不排除。unknown 保留在业务分母并单列；负面数 / 业务分母不是仅已知情绪样本的负面率。')
    if d['groups']:
        names = dict(source_kind='来源', cohort_id='版本组ID', total='全部案例', accepted='契约接受', failed='失败',
                     blocked='任意阻断', analysis_blocked='分析阻断', reply_blocked='回复阻断', business_denominator='业务分母',
                     unknown_sentiment='未知情绪', negative='负面', fallback='回退次数', model='模型', prompt='Prompt版本')
        rows = [{names.get(k, k): label(v) if k == 'source_kind' else v for k, v in g.items()
                 if k not in ('member_case_ids', 'business_member_case_ids', 'denominator')} for g in d['groups']]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
        group = st.selectbox('选择统计版本组', d['groups'], key=key + '_group',
                            format_func=lambda g: f"{label(g['source_kind'])} · {g['cohort_id'][:12]} · {g['total']}案例")
        members = [db.get(i) for i in group['member_case_ids']]
        member = st.selectbox('查看统计成员原文与证据', members, key=key + '_member',
                             format_func=lambda c: f"{c['run'].email.email_id} · {label(c['state'])} · {c['case_id'][:8]}")
        with st.expander('成员原始邮件、Issue 与 Evidence', expanded=False):
            show_analysis(member)
            st.link_button('进入该案例的审核工作台', '?case_id=' + member['case_id'])
        with st.expander('Developer Details · 完整统计分母与成员ID'):
            st.json(d)
    st.caption('契约成功不表示语义通过。离线示例、Mock HTTP、新真实分析、历史重放及不同完整版本组分别统计。工作流计数不是独立真人评价。')


def render(root):
    from src.app.copilot_workspace import render as copilot
    copilot(root)
