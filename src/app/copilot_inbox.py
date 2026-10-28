"""Chinese inbox. UI buffers are case/version scoped; services own every write."""
from datetime import datetime
from html import escape
from uuid import uuid4
import difflib
import streamlit as st
from src.app.product_workspace import store, label
from src.app.copilot_workspace import select_case, provenance, understanding, versions, thread_panel, act
from src.application.copilot_demo import SCENARIOS, CopilotFake, example
from src.application.copilot_drafts import insert_suggestion
from src.application.mail_threads import MailThreads
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.infrastructure.repository import Repository
from src.domain.contracts import EmailInput, digest
from src.application.copilot_service import CopilotService
from src.application.service_scenarios import SCENARIOS as SERVICE_SCENARIOS, example as service_example, ServiceCopilotFake, strategy, CUSTOM_SCENARIO
from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, example as v2_example, ServiceCopilotFake as V2Fake, strategy as v2_strategy
from src.application.service_triage import triage, request_handoff, take_over, quick_confirm_and_simulate


def preview(value):
    """Escape untrusted mail inside Markdown button labels (including images)."""
    value=value.replace('\\','\\\\')
    for char in ('`','*','[',']','!','_'):
        value=value.replace(char,'\\'+char)
    return value


def is_service(c):
    return bool(c and c['run'].config.parameters.get('service_policy_version'))


def status(c):
    if is_service(c) and c['state'] not in ('simulated_sent','rejected') and triage(c)['handoff']=='requested':
        return '等待人工'
    if is_service(c) and c['state'] not in ('simulated_sent','rejected','approved','changes_requested'):
        routing = triage(c)
        if routing['handoff']=='taken_over': return '人工已接管'
        if routing['handoff']=='requested': return '等待人工'
        return routing['label']
    if not c['accepted'] or c['quality']['status'] == 'blocked':
        return '需人工介入'
    if c['state']=='pending_review' and c['current_version']==1:
        return '待处理'
    return {'pending_review':'待审核', 'changes_requested':'需要修改', 'approved':'审核通过',
            'simulated_sent':'已模拟发送', 'rejected':'已拒绝'}.get(c['state'], '待处理')


def time_label(value):
    # Saved UTC timestamps are displayed with an explicit local timezone.
    from zoneinfo import ZoneInfo
    return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%m-%d %H:%M')


def buffer_id(c):
    return c['case_id'] + ':' + str(c['current_version'])


def remember(c, key):
    st.session_state.setdefault('p46_buffers', {})[buffer_id(c)] = st.session_state[key]


def editor_value(c):
    if not c['draft']: return ''
    buffers = st.session_state.setdefault('p46_buffers', {})
    key = f"p4_reply_{c['case_id']}_{c['current_version']}"
    if key in st.session_state:
        return st.session_state[key]
    # Imported v1 is an internal suggestion. The operator explicitly inserts it.
    untouched_import = not is_service(c) and c['current_version']==1 and c['state']=='pending_review' and len(c['events'])==1
    default = '' if untouched_import else c['draft']['body']
    return buffers.get(buffer_id(c), default)


def opened(c):
    select_case(c)
    st.session_state['p46_next_region'] = '对话'
    st.session_state.pop('p46_review', None)


def perform_insert(db, c, request, mode):
    current_text = editor_value(c)
    if current_text != request['editor_text'] or digest(current_text) != request['editor_hash']:
        st.error('编辑器内容已变化，请重新选择插入方式。'); return
    try:
        result = insert_suggestion(db, request['case_id'], expected_revision=request['revision'],
            editor_text=current_text, expected_editor_hash=request['editor_hash'], mode=mode,
            actor=st.session_state.get('p4_actor', 'demo_operator'), actor_type=st.session_state.get('p4_actor_type', 'demo_test'),
            operation_id=request['operation_id'])
        st.session_state.setdefault('p46_buffers', {})[buffer_id(result)] = result['draft']['body']
        st.session_state.pop('p46_insertion_request', None)
        opened(result)
        st.session_state['p4_notice'] = 'AI内部建议已插入并保存新版本；仍需人工审核。'
        st.rerun()
    except ValueError as exc:
        st.error('已拒绝的草稿必须修改后再提交审核。' if str(exc)=='Rejected draft must be edited before a new review' else str(exc))
    except Exception as exc:
        st.error(f'插入保存未确认（{type(exc).__name__}）。请保留编辑并重读状态后重试；不会自动发送。')


def dismiss_insertion():
    st.session_state.pop('p46_insertion_request',None)


def dismiss_review():
    st.session_state.pop('p46_review',None)


@st.dialog('已有回复内容：选择插入方式', on_dismiss=dismiss_insertion)
def insertion_dialog(db, c, request):
    if request['case_id'] != c['case_id']:
        st.error('会话已切换，请重新插入。'); return
    st.caption('已有内容不会静默覆盖。替换或追加都会保存新版本，撤销原审核；不会发送。')
    st.text(request['editor_text'])
    mode = st.radio('插入方式', ['追加到末尾', '替换当前草稿'], key='p46_insert_mode')
    a, b = st.columns(2)
    if a.button('确认插入', type='primary', key='p46_insert_confirm'):
        perform_insert(db, c, request, 'append' if mode == '追加到末尾' else 'replace')
    if b.button('保留原稿', key='p46_insert_cancel'):
        st.session_state.pop('p46_insertion_request', None); st.rerun()


@st.dialog('人工审核回复', width='large', on_dismiss=dismiss_review)
def review_dialog(db, c):
    if is_service(c):
        service_review(db,c)
        return
    st.caption(f"{c['run'].email.subject} · 当前草稿 v{c['current_version']} · {status(c)}")
    if c['quality']['status'] == 'blocked':
        st.error('当前质量门禁阻断，不能批准或模拟发送。请先人工核实分析问题；改写回复或勾选无法解除。')
        st.caption('下一步：查看详情中的阻断原因，保留原文与处理记录。')
    with st.expander('查看当前草稿',expanded=False):st.text(c['draft']['body'])
    reason = st.text_area('处理备注（批准、退回或拒绝时必填）', key=f"p4_reason_{c['case_id']}", height=68)
    with st.expander('历史来源详细核对与操作者',expanded=False):
        actor_type = st.selectbox('审核身份类型', ['demo_test', 'local_human'],
            format_func=lambda x:'演示验收（不计真人评价）' if x == 'demo_test' else '本地人工审核', key='p4_actor_type')
        if 'p4_actor' not in st.session_state: st.session_state['p4_actor']='demo_operator'
        actor = st.text_input('本地审核人标识', key='p4_actor')
        checks = {
            'facts_evidence':st.checkbox('已核对原文事实与分析', key=f"p4_facts_{c['case_id']}_{c['current_version']}"),
            'authority_privacy':st.checkbox('已核对权限、隐私及未执行动作', key=f"p4_authority_{c['case_id']}_{c['current_version']}"),
            'all_issues':st.checkbox('已核对全部诉求与处理范围', key=f"p4_issues_{c['case_id']}_{c['current_version']}"),
        }
        if c['quality']['safety_review_required']:
            checks['safety'] = st.checkbox('已核对停止使用、不复现及后续安全处理', key=f"p4_safety_{c['case_id']}_{c['current_version']}")
    a,b,d = st.columns(3)
    if a.button('批准草稿', key='p4_approve', type='primary', disabled=c['quality']['status']=='blocked' or c['state']=='rejected'):
        act(db,c,'approve',actor,actor_type,reason,checks,c['draft']['body'])
    if b.button('退回修改', key='p4_request_changes', disabled=c['state']=='rejected'):
        act(db,c,'request_changes',actor,actor_type,reason,checks,c['draft']['body'])
    if d.button('拒绝草稿', key='p4_reject'):
        act(db,c,'reject',actor,actor_type,reason,checks,c['draft']['body'])


def inbox(db, cases, c, scenario):
    st.html('<div class="inbox-heading">会话收件箱 <span class="inbox-dot"></span></div>')
    visible_cases=[i for i in cases if not is_service(c) or is_service(i) or st.session_state.get('p47_show_history',False)]
    pending = sum(i['state'] not in ('simulated_sent','rejected') for i in visible_cases)
    st.caption(f'{pending} 待处理 · {len(visible_cases)} 个会话')
    search=st.text_input('搜索会话',placeholder='搜索主题或客户来信',key='p47_search',label_visibility='collapsed')
    a,b = st.columns([1.1,1])
    with a:
        state = st.selectbox('会话筛选',['全部','待处理','待审核','需要修改','审核通过','已模拟发送','需人工介入','AI 建议处理','需人工确认','需人工接管','等待人工','人工已接管','已拒绝'], key='p46_filter',label_visibility='collapsed')
    with b:
        order = st.selectbox('会话排序',['最近更新','最早更新'],format_func=lambda x:'最新' if x=='最近更新' else '最早',
            help='按最后一次处理事件的时间排序',key='p46_order',label_visibility='collapsed')
    selected = [i for i in visible_cases if (state=='全部' or status(i)==state) and (not search.strip() or search.casefold() in (i['run'].email.subject+' '+i['run'].email.body).casefold())]
    selected.sort(key=lambda i:(i['events'][-1]['created_at'],i['case_id']),reverse=order=='最近更新')
    with st.container(height=390, border=False, key='inbox_scroll'):
        for item in selected:
            latest = next(m for m in reversed(MailThreads(db).messages(item['case_id'])) if m['role']=='customer')
            snippet = preview(' '.join(latest['body'].split())[:46])
            title = preview(item['run'].email.subject)
            with st.container(key='selected_case' if c and item['case_id']==c['case_id'] else 'row_'+item['case_id']):
                if st.button(f"**{title}**\n\n{snippet}…\n\n{status(item)} · {time_label(item['events'][-1]['created_at'])}",
                             key='case_'+item['case_id'],width='stretch'):
                    opened(item); st.rerun()
        if not selected:
            st.caption('暂无匹配会话。选择一个演示场景，开始处理。')
    with st.expander('＋ 新建会话',expanded=not cases):
        st.selectbox('邮件场景',(SERVICE_SCENARIOS[0],V2_SCENARIOS[3])+SERVICE_SCENARIOS[2:4]+V2_SCENARIOS[:3]+SERVICE_SCENARIOS[5:]+(SERVICE_SCENARIOS[1],SERVICE_SCENARIOS[4])+SCENARIOS,key='p4_scenario',format_func=lambda n:n if n in SERVICE_SCENARIOS+V2_SCENARIOS else '历史工程样例 · '+n)
        if scenario in (SCENARIOS[6],CUSTOM_SCENARIO):
            st.text_input('邮件主题',value='新客户邮件',key='p4_subject')
            st.text_area('客户邮件正文',key='p4_body',height=120)
        if st.button('分析邮件',key='p4_analyze',width='stretch'):
            try:
                chosen=st.session_state['p4_scenario']
                email,_=(v2_example(chosen) if chosen in V2_SCENARIOS else service_example(chosen) if chosen in SERVICE_SCENARIOS else example(chosen))
                if chosen in (SCENARIOS[6],CUSTOM_SCENARIO):
                    subject,body=st.session_state.get('p4_subject','新客户邮件'),st.session_state.get('p4_body','')
                    email=EmailInput(email_id='manual-'+digest(dict(subject=subject,body=body))[:24],subject=subject,body=body)
                repo=Repository(db.path.with_name(db.path.stem+'-analysis.sqlite3'))
                analyzer=V2Fake(email,chosen) if chosen in V2_SCENARIOS else ServiceCopilotFake(email,chosen) if chosen in SERVICE_SCENARIOS else CopilotFake(email,chosen)
                result=ProductAnalysis(AnalysisService(repo,analyzer),db).submit(email)
                st.session_state['p46_next_filter']='全部'
                opened(result);st.rerun()
            except ValueError as exc: st.error(str(exc))
            except Exception as exc: st.error(f'保存未确认（{type(exc).__name__}），请重读后重试同一输入。')
        st.caption('本地合成案例 · AI建议为离线预写。自定义邮件需人工阅读；未接入邮箱或真实坐席。')
    # Stable compatibility/search entry; ordinary navigation is one-click rows.
    if cases:
        with st.expander('历史会话'):
            st.checkbox('显示历史工程会话',key='p47_show_history',help='旧版本与故意错误样例只用于工程复核')
            choices={i['case_id']+':'+str(i['revision']):i for i in cases}
            pending_choice=st.session_state.pop('p45_select_history',None)
            if pending_choice in choices: st.session_state['p4_history']=pending_choice
            if st.session_state.get('p4_history') not in choices:
                st.session_state['p4_history']=next((k for k,i in choices.items() if c and i['case_id']==c['case_id']),next(iter(choices)))
            choice=st.selectbox('已保存的邮件',list(choices),format_func=lambda k:choices[k]['run'].email.subject,key='p4_history')
            if st.button('打开历史案例',key='p4_open'):
                opened(choices[choice]);st.rerun()


def conversation(threads,c,email):
    st.html(f'<div class="conversation-title">{escape(email.subject)}</div>')
    st.caption((status(c)+' · '+provenance(c)) if c else '待处理 · 合成演示预览，尚未保存')
    messages=threads.messages(c['case_id']) if c else [dict(role='customer',body=email.body,at=None)]
    single=len(messages)==1
    with st.container(height='content' if single else 280,border=False,
                      key='conversation_single' if single else 'conversation',autoscroll=not single):
        for m in messages:
            outgoing=m['role']=='assistant_simulation'
            identity='知诉客服 · 已模拟发送' if outgoing else '客户来信'
            when=' · '+time_label(m['at']) if m['at'] else ' · 演示预览'
            st.html(f'<div class="message {"outgoing" if outgoing else "incoming"}"><div class="message-meta">{identity}{when}</div>{escape(m["body"])}</div>')
    # A stable block keeps the composer at the same Streamlit delta path when
    # the next action changes after editing, approval or sending.
    with st.container(key='next_action'):
        next_action(c)
        if c and not c['receipt'] and not is_service(c) and (not c['accepted'] or c['quality']['status']=='blocked'):
            route=triage(c)
            if route['handoff']!='taken_over':
                if st.button('接管会话',key='p47_take_over'):service_action(threads.store,c,'take_over')
            else:st.caption('本地人工已接管 · 分析阻断仍有效')


def next_action(c):
    if c and not c['receipt']:
        if is_service(c):
            route=triage(c)
            st.html('<div class="next-step"><b>'+escape(route['label'])+'</b> · '+escape(route['next_step'])+'</div>')
            return
        guidance=('转人工核对风险与分析阻断，再处理回复。' if not c['accepted'] or c['quality']['status']=='blocked' else
                  '审核已通过，核对当前版本后可模拟发送。' if c['state']=='approved' else
                  '修改回复并保存新版本，再提交人工审核。' if c['state'] in ('rejected','changes_requested') else
                  '核对当前草稿，保存修改后提交人工审核。' if editor_value(c).strip() else
                  '查看AI建议并插入草稿，核实资料后提交人工审核。')
        st.html('<div class="next-step">下一步 · '+guidance+'</div>')
        if c['accepted'] and c['quality']['status']!='blocked' and not editor_value(c).strip() and st.button('查看AI建议',key='p461_view_advice'):
            st.session_state['p46_next_region']='AI助手'
            st.session_state['p461_assistant_tab']='AI助手';st.rerun()


def composer(db,c):
    with st.container(key='composer'):
        if c['receipt']:
            st.success('模拟发送已完成 · 未投递真实邮件')
            st.caption(f"回复 v{c['receipt']['version']} · {time_label(c['receipt']['created_at'])} · 回执已保存")
            thread_panel(MailThreads(db),c)
            return
        if is_service(c):
            service_composer(db,c)
            return
        if not c['draft']:
            st.error('分析失败，需人工处理。原文已保留，没有可审核草稿。'); return
        st.html('<div class="composer-heading">回复客户 <span class="pill">草稿 · 尚未发送</span></div>')
        key=f"p4_reply_{c['case_id']}_{c['current_version']}"
        if key not in st.session_state: st.session_state[key]=editor_value(c)
        edited=st.text_area('回复草稿',key=key,height=124,on_change=remember,args=(c,key),
            placeholder='从右侧插入回复建议，或在此撰写；保存后须人工审核。')
        dirty=edited!=c['draft']['body']
        origin=next((e['details'].get('draft_source') for e in reversed(c['events']) if e['version']==c['current_version'] and e['details'].get('draft_source')),None)
        st.caption(f"v{c['current_version']} · "+('来自AI内部建议 · ' if origin else '内部建议 / 人工编辑 · ')+('尚未撰写' if not edited.strip() else '有未保存修改' if dirty else status(c)))
        action,more=st.columns([1.4,1])
        with action:
            if dirty:
                if edited.strip() and st.button('保存草稿',key='p4_save_edit',type='primary',width='stretch'):
                    act(db,c,'save_edit',st.session_state.get('p4_actor','demo_operator'),st.session_state.get('p4_actor_type','demo_test'),'人工编辑草稿',{},edited)
                elif not edited.strip(): st.caption('请插入建议或撰写回复')
            elif c['state']=='approved':
                if st.button('模拟发送',key='p4_simulate_send',type='primary',disabled=c['quality']['status']=='blocked',width='stretch'):
                    act(db,c,'simulate_send',st.session_state.get('p4_actor','demo_operator'),st.session_state.get('p4_actor_type','demo_test'),'',{},edited)
            elif st.button('人工处理' if c['quality']['status']=='blocked' else '提交审核',key='p46_review_open',type='primary',width='stretch'):
                st.session_state['p46_review']=dict(case_id=c['case_id'],revision=c['revision']);st.rerun()
        with more:
            with st.popover('版本与处理',width='stretch'):
                versions(c)
                if dirty:
                    st.code('\n'.join(difflib.unified_diff(c['draft']['body'].splitlines(),edited.splitlines(),fromfile=f"v{c['current_version']}",tofile='未保存编辑',lineterm='')),language='diff')
                if st.button('审核 / 退回 / 拒绝',key='p46_more_review',disabled=dirty and bool(edited.strip())):
                    st.session_state['p46_review']=dict(case_id=c['case_id'],revision=c['revision']);st.rerun()
        if c['quality']['status']=='blocked': st.caption('安全门禁阻断 · 修改回复无法解除分析错误')


def assistant(db,c,data):
    a,q,b=st.tabs(['AI助手','证据问答','详情'],key='p461_assistant_tab',on_change='rerun')
    with a:
        with st.container(height=600,border=False,key='assistant_scroll'):
            if not is_service(c):st.caption((provenance(c) if c else '离线预写建议')+' · 仅供内部参考')
            if not data or (c and not c['accepted']):
                st.warning('没有可信建议，请人工阅读原文。')
            else:
                if is_service(c):
                    service_advice(db,c,data)
                else:
                    legacy_advice(db,c,data)
    with q:
        evidence_questions(db,c)
    with b:
        if c:
            understanding(data,c['quality'])
            versions(c)
            with st.expander('来源与编排链路'):
                st.caption(provenance(c))
                st.markdown('客户邮件 → 版本化提示/上下文 → LangChain适配 → 结构化输出与原文证据 → 项目门禁 → 草稿/审核/本地回执。')
                st.caption('本页预写建议经过RunnableLambda；证据问答为离线规则。历史模型重放不发新请求。ChatOpenAI真实调用仅具备接入能力，当前关闭。')
                st.json(dict(run_id=c['run'].run_id,config=c['run'].config.model_dump(),snapshot_hash=c['snapshot_hash']))


def legacy_advice(db,c,data):
    issues=data.get('issues',[])
    st.html('<div class="section-label">客户诉求</div>')
    for i in issues:
        st.html('<div class="need">'+escape('；'.join(i.get('customer_requests',[])) or '需人工判断')+'</div>')
    st.caption(data.get('summary','暂无理解'))
    st.markdown('**建议处理策略**')
    if any(i.get('risk_level')=='severe' for i in issues) or c and c['quality']['status']=='blocked':
        st.warning('先核对安全风险与质量门禁；存在分析阻断时转人工，不得放行。')
    else: st.caption('依据原文逐项回应，补齐必要信息，再由人工核实可用处理方案。')
    with st.container(key='suggestion_card'):
        st.html('<div class="section-label">回复建议 · 未发送</div>')
        st.text(data.get('suggested_reply','暂无回复'))
        if c and c['draft'] and not c['receipt']:
            if st.button('插入回复草稿',key='p46_insert',width='stretch',type='primary' if not editor_value(c).strip() else 'secondary'):
                value=editor_value(c)
                request=dict(case_id=c['case_id'],revision=c['revision'],editor_text=value,editor_hash=digest(value),operation_id=str(uuid4()))
                if value.strip():
                    st.session_state['p46_insertion_request']=request;st.rerun()
                else: perform_insert(db,c,request,'replace')
        elif not c: st.caption('先在左侧分析邮件，即可插入、编辑与审核。')
    with st.expander('回复依据与待补信息',expanded=False):
        for n,i in enumerate(issues,1):
            st.markdown(f'**诉求 {n} · 原文事实**')
            for e in i.get('evidence',[]): st.text(e['quote'])
            st.caption('还需补充：'+'；'.join(i.get('missing_evidence',[])))
    if c and c['quality']['status']=='blocked': st.error('不可放行：请转人工处理。')

def operator_settings():
    with st.expander('操作者设置'):
        st.caption('本地演示无登录；自动验收一律标记演示身份。')
        actor_type=st.selectbox('审核身份类型',['demo_test','local_human'],format_func=lambda x:'演示验收' if x=='demo_test' else '本地人工',key='p4_actor_type')
        if 'p4_actor' not in st.session_state:st.session_state['p4_actor']='demo_operator'
        actor=st.text_input('本地审核人标识',key='p4_actor')
    return actor,actor_type


def service_action(db,c,action):
    actor=st.session_state.get('p4_actor','demo_operator')
    kind=st.session_state.get('p4_actor_type','demo_test')
    try:
        fn=take_over if action=='take_over' else request_handoff
        result=fn(db,c['case_id'],expected_revision=c['revision'],actor=actor,actor_type=kind,
                  reason='操作者接管本地会话' if action=='take_over' else '操作者请求人工处理',operation_id=str(uuid4()))
        opened(result);st.rerun()
    except ValueError as exc:st.error(str(exc))
    except Exception as exc:st.error(f'接管保存未确认（{type(exc).__name__}）。请保留编辑并重读当前会话。')


def service_review(db,c):
    routing=triage(c)
    st.caption('当前回复 v'+str(c['current_version'])+' · '+routing['label'])
    st.write('；'.join(routing['reasons']))
    if c['quality']['status']=='blocked':
        st.error('分析或回复仍有阻断，接管不能解除门禁。请在详情核对原因。')
    with st.expander('查看待审核回复',expanded=False):st.text(c['draft']['body'])
    confirmed=st.checkbox('我已核对原文与全部诉求，回复事实准确、权限和隐私表述适当。',key=f"p47_confirm_{c['case_id']}_{c['current_version']}")
    checks=dict(facts_evidence=confirmed,authority_privacy=confirmed,all_issues=confirmed)
    if c['quality']['safety_review_required']:
        checks['safety']=st.checkbox('已核对停止使用、不复现故障与后续安全处理路径。',key=f"p47_safety_{c['case_id']}_{c['current_version']}")
    reason=st.text_area('处理备注（退回或拒绝时必填）',key=f"p4_reason_{c['case_id']}",height=68)
    actor,kind=st.session_state.get('p4_actor','demo_operator'),st.session_state.get('p4_actor_type','demo_test')
    st.caption('操作者：'+actor+' · '+('演示验收' if kind=='demo_test' else '本地人工审核'))
    a,b,d=st.columns(3)
    blocked=c['quality']['status']=='blocked' or c['state'] in ('rejected','changes_requested') or (routing['requires_takeover'] and routing['handoff']!='taken_over')
    if a.button('确认回复',key='p4_approve',type='primary',disabled=blocked or not confirmed or (c['quality']['safety_review_required'] and not checks.get('safety'))):
        act(db,c,'approve',actor,kind,reason.strip() or '操作者已核对原文、全部诉求、权限与隐私；本地回复确认',checks,c['draft']['body'])
    if b.button('退回修改',key='p4_request_changes',disabled=c['state']=='rejected'):
        act(db,c,'request_changes',actor,kind,reason,checks,c['draft']['body'])
    if d.button('拒绝草稿',key='p4_reject'):
        act(db,c,'reject',actor,kind,reason,checks,c['draft']['body'])


def service_composer(db,c):
    routing=triage(c)
    if not c['draft']:
        st.warning('分析未完成，请人工阅读客户来信。')
        st.caption('转人工状态：'+{'none':'待转交','requested':'等待接管','taken_over':'人工已接管'}[routing['handoff']]+' · 分析失败时不能批准或发送')
        if routing['handoff']=='none':
            if st.button('转人工处理',key='p47_handoff'):service_action(db,c,'request_handoff')
        elif routing['handoff']=='requested':
            if st.button('接管会话',key='p47_take_over'):service_action(db,c,'take_over')
        return
    st.html('<div class="composer-heading">回复客户 <span class="draft-label">'+('人工接管' if routing['handoff']=='taken_over' else 'AI辅助拟稿')+' · 未发送</span></div>')
    key=f"p4_reply_{c['case_id']}_{c['current_version']}"
    if key not in st.session_state:st.session_state[key]=editor_value(c)
    edited=st.text_area('回复草稿',key=key,height=188,on_change=remember,args=(c,key),label_visibility='collapsed')
    dirty=edited!=c['draft']['body']
    st.caption('v'+str(c['current_version'])+' · '+('有未保存修改' if dirty else '已保存草稿')+' · 本地模拟，不会投递邮件')
    if routing['handoff']=='requested':st.info('已进入本地人工待办。接管后继续编辑和确认；未连接真实坐席。')
    if routing['requires_takeover'] and routing['handoff']!='taken_over':
        if st.button('接管会话',key='p47_take_over',type='primary'):service_action(db,c,'take_over')
    if dirty:
        if st.button('保存修改',key='p4_save_edit',type='primary',disabled=not edited.strip(),width='stretch'):
            act(db,c,'save_edit',st.session_state.get('p4_actor','demo_operator'),st.session_state.get('p4_actor_type','demo_test'),'人工编辑草稿',{},edited)
    elif c['state']=='approved':
        if st.button('模拟发送',key='p4_simulate_send',type='primary',disabled=c['quality']['status']=='blocked' or (routing['requires_takeover'] and routing['handoff']!='taken_over'),width='stretch'):
            act(db,c,'simulate_send',st.session_state.get('p4_actor','demo_operator'),st.session_state.get('p4_actor_type','demo_test'),'',{},edited)
    elif routing['can_quick_confirm']:
        confirmed=st.checkbox('已核对原文、全部诉求及回复权限与隐私。',key=f"p47_quick_check_{c['case_id']}_{c['current_version']}")
        if st.button('确认并模拟发送',key='p47_quick_send',type='primary',disabled=not confirmed,width='stretch'):
            operation=st.session_state.setdefault('p47_quick_operation_'+buffer_id(c),str(uuid4()))
            try:
                result=quick_confirm_and_simulate(db,c['case_id'],expected_revision=c['revision'],confirmed=confirmed,
                    actor=st.session_state.get('p4_actor','demo_operator'),actor_type=st.session_state.get('p4_actor_type','demo_test'),operation_id=operation)
                opened(result);st.rerun()
            except ValueError as exc:st.error(str(exc))
            except Exception as exc:st.error(f'操作结果待确认（{type(exc).__name__}）。请重新打开会话核对；已保存步骤会保留。')
    elif c['state'] in ('rejected','changes_requested'):
        st.warning('此稿已退回或拒绝，请编辑回复并保存新版本后重新确认。')
        decision=next((e for e in reversed(c['events']) if e['action'] in ('request_changes','reject')),None)
        if decision:st.caption('处理备注：'+decision['reason'])
    else:
        if st.button('核对并确认回复' if routing['handoff']=='taken_over' else '人工确认回复',key='p46_review_open',type='primary',
                     disabled=routing['requires_takeover'] and routing['handoff']!='taken_over',width='stretch'):
            st.session_state['p46_review']=dict(case_id=c['case_id'],revision=c['revision']);st.rerun()
    a,b=st.columns(2)
    with a:
        if st.button('转人工',key='p47_handoff',disabled=routing['handoff']!='none',width='stretch'):service_action(db,c,'request_handoff')
    with b:
        with st.popover('版本与更多',width='stretch'):
            versions(c)
            operator_settings()
            if st.button('审核 / 退回 / 拒绝',key='p46_more_review',disabled=dirty):
                st.session_state['p46_review']=dict(case_id=c['case_id'],revision=c['revision']);st.rerun()
    if c['quality']['status']=='blocked':st.caption('门禁阻断仍有效 · 修改回复不能解除分析错误')


def service_advice(db,c,data):
    route=triage(c);plan=v2_strategy(c) or strategy(c) or {}
    st.html('<div class="copilot-orb">✧</div><div class="copilot-title">AI Copilot</div>')
    st.caption('离线预写建议 · 非实时模型推理')
    st.html('<div class="section-label">诉求理解</div>')
    st.write(data.get('summary','请人工阅读原文'))
    st.html('<div class="route-card"><b>'+escape(route['label'])+'</b><br>'+escape('；'.join(route['reasons']))+'</div>')
    st.markdown('**建议下一步**')
    for n,action in enumerate(plan.get('next_actions',[]),1):st.write(str(n)+'. '+action)
    with st.expander('回复建议',expanded=False):
        st.text(data.get('suggested_reply',''))
        if c['draft'] and not c['receipt'] and st.button('插入回复草稿',key='p46_insert',width='stretch'):
            value=editor_value(c);request=dict(case_id=c['case_id'],revision=c['revision'],editor_text=value,editor_hash=digest(value),operation_id=str(uuid4()))
            if value.strip():st.session_state['p46_insertion_request']=request;st.rerun()
            else:perform_insert(db,c,request,'replace')
    with st.expander('证据与待补资料'):
        for i in data.get('issues',[]):
            for e in i.get('evidence',[]):st.text('“'+e['quote']+'”')
        if plan.get('customer_info'):st.markdown('**向客户补充确认**');st.write('；'.join(plan['customer_info']))
        if plan.get('internal_verification'):st.markdown('**商家内部核实**');st.write('；'.join(plan['internal_verification']))
    if plan.get('demo_aftersales_policy'):
        policy=plan['demo_aftersales_policy']
        with st.expander('演示售后申请规则 · 非商家实际条款'):
            st.caption(policy['source'])
            st.write('可提出：'+' / '.join(policy['options']))
            for step in policy['application_steps']:st.write(step)
            st.caption(policy['approval_boundary'])
            st.caption('仍须核实：'+'、'.join(policy['unknown_terms']))
    st.caption('建议已放入中间草稿，可直接编辑。确认只生成本地回执。')


def evidence_questions(db,c):
    st.markdown('**离线证据问答**')
    st.caption('读取本案保存资料 · 规则识别问题 · 内部参考，非人工Gold')
    if not c:
        st.caption('先选择已保存会话，再向助手提问。');return
    try:
        service=CopilotService(db)
        with st.form('qa_form_'+c['case_id']):
            quick=st.selectbox('常见问题',['自行输入','客户主要想解决什么？','为什么被判断为投诉或咨询？',
                '有哪些Issue及原文证据？','当前回复还缺哪些信息？','为什么需要人工介入或风险阻断？',
                '下一步怎么处理？','哪些信息已提供，不能重复询问？'],key='qa_quick_'+c['case_id'])
            question=st.text_input('向AI追问',placeholder='例如：客户已提供哪些信息？',key='p46_question_'+c['case_id'],max_chars=1000)
            submitted=st.form_submit_button('依据本案回答',width='stretch')
        if submitted:
            selected=question.strip() or (quick if quick!='自行输入' else '')
            if not selected: st.error('请输入问题或选择常见问题。')
            else:
                record=service.ask(c['case_id'],selected)
                if record['status']=='running': st.warning('该问答已登记但结果尚未确认；请重读记录，不会自动重试。')
        history=service.repository.history(c['case_id'])
        if history:
            with st.container(height=240,border=False,key='qa_history'):
                for record in reversed(history[-12:]):
                    st.text('问：'+record['question'])
                    result=record['result'] or {}
                    if record['status']=='succeeded':
                        st.text(result['answer'])
                        with st.expander('查看本次依据与不确定性'):
                            for ref in result['references']:
                                st.caption(ref['id']+' · '+ref['source']);st.text(ref['text'])
                            for item in result['uncertainty']: st.caption(item)
                            st.caption(f"资料快照 revision {record['context']['revision']} · {time_label(record['created_at'])}；不随后续编辑改写")
                    elif record['status']=='failed': st.error(result['message']+'（'+result['error']+'）')
                    else: st.warning('问答结果未确认；没有自动重试或发送。')
        st.caption('已保存问答可重启恢复 · 同问题同资料复用')
        with st.expander('实时AI追问 · 待授权'):
            st.caption('默认关闭。独立LangChain接口仅完成SDK Mock HTTP工程验证；真实Provider自由问答待独立付费授权及验证。')
            st.caption('问答仅内部参考。未提交输入不保证恢复；回复须明确插入、保存版本和人工审核。只展示最近12条问答，完整历史保存在本案独立问答库。')
    except Exception as exc:
        st.error(f'证据问答暂不可用（{type(exc).__name__}）；请保留问题后重试。草稿和审核不受影响。')


def render(root):
    # Keep operator preferences when a dialog closes (Streamlit cleans widgets
    # that are not rendered). Checklist state remains per version in the dialog.
    for preference in ('p4_actor','p4_actor_type','p46_insert_mode'):
        if preference in st.session_state:
            st.session_state[preference]=st.session_state[preference]
    try:
        db=store(root);threads=MailThreads(db);cases=db.list_cases()
    except Exception as exc:
        st.error(f'工作库暂不可用（{type(exc).__name__}）；未开始分析。');return
    # URL is authoritative on refresh/deep-link; explicit selection updates both.
    current=st.query_params.get('case_id') or st.session_state.get('p4_case')
    c=next((i for i in cases if i['case_id']==current),None)
    if c: st.session_state['p4_case']=c['case_id']
    scenario=st.session_state.get('p4_scenario',SERVICE_SCENARIOS[0])
    email,data=v2_example(scenario) if scenario in V2_SCENARIOS else service_example(scenario) if scenario in SERVICE_SCENARIOS else example(scenario)
    if not c and cases and not current:
        c=next((item for item in cases if is_service(item) and item['run'].config.parameters.get('service_scenario')==SERVICE_SCENARIOS[0]),cases[0])
        select_case(c)
    if c: email=c['run'].email;data=c['analysis']
    if st.session_state.get('p4_notice'): st.toast(st.session_state.pop('p4_notice'))
    if 'p46_next_region' in st.session_state:
        st.session_state['p46_region']=st.session_state.pop('p46_next_region')
    if 'p46_next_filter' in st.session_state:
        st.session_state['p46_filter']=st.session_state.pop('p46_next_filter')
    if 'p46_region' not in st.session_state: st.session_state['p46_region']='对话'
    with st.container(key='region_switch'):
        region=st.radio('工作区域',['收件箱','对话','AI助手'],horizontal=True,key='p46_region',label_visibility='collapsed')
    with st.container(key='layout_'+{'收件箱':'inbox','对话':'conversation','AI助手':'copilot'}[region]):
        left,center,right=st.columns([1.15,2.5,1.4],gap='medium')
        with left:
            with st.container(key='inbox_pane'): inbox(db,cases,c,scenario)
        with center:
            conversation(threads,c,email)
            if c: composer(db,c)
            else:
                with st.container(key='composer'):
                    st.html('<div class="composer-heading">回复客户</div>')
                    st.text_area('回复草稿',value='',disabled=True,height=124,placeholder='选择演示场景并分析邮件，开始回复。')
                    st.caption('第一步：左侧新增案例 → 分析邮件；第二步：右侧插入回复草稿。')
        with right:
            with st.container(key='copilot_pane'): assistant(db,c,data)
    if c and st.session_state.get('p46_insertion_request'):
        request=st.session_state['p46_insertion_request']
        if request['case_id']==c['case_id']: insertion_dialog(db,c,request)
        else: st.session_state.pop('p46_insertion_request',None)
    elif c and st.session_state.get('p46_review'):
        request=st.session_state['p46_review']
        if request==dict(case_id=c['case_id'],revision=c['revision']): review_dialog(db,c)
        else:
            st.session_state.pop('p46_review',None)
            st.warning('会话状态已变化，请核对最新草稿后重新打开审核。')
