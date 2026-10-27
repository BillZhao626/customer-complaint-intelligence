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


def preview(value):
    """Escape untrusted mail inside Markdown button labels (including images)."""
    value=value.replace('\\','\\\\')
    for char in ('`','*','[',']','!','_'):
        value=value.replace(char,'\\'+char)
    return value


def status(c):
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
    buffers = st.session_state.setdefault('p46_buffers', {})
    key = f"p4_reply_{c['case_id']}_{c['current_version']}"
    if key in st.session_state:
        return st.session_state[key]
    # Imported v1 is an internal suggestion. The operator explicitly inserts it.
    untouched_import = c['current_version']==1 and c['state']=='pending_review' and len(c['events'])==1
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
    st.caption(f"{c['run'].email.subject} · 当前草稿 v{c['current_version']} · {status(c)}")
    st.text(c['draft']['body'])
    actor_type = st.selectbox('审核身份类型', ['demo_test', 'local_human'],
        format_func=lambda x:'演示验收（不计真人评价）' if x == 'demo_test' else '本地人工审核', key='p4_actor_type')
    if 'p4_actor' not in st.session_state: st.session_state['p4_actor']='demo_operator'
    actor = st.text_input('本地审核人标识', key='p4_actor')
    reason = st.text_area('审核/退回/拒绝原因', key=f"p4_reason_{c['case_id']}", height=68)
    checks = {
        'facts_evidence':st.checkbox('已逐项核对事实、原文证据、情绪、原因、状态与主次', key=f"p4_facts_{c['case_id']}_{c['current_version']}"),
        'authority_privacy':st.checkbox('已核对商家资料、隐私及未执行动作承诺', key=f"p4_authority_{c['case_id']}_{c['current_version']}"),
        'all_issues':st.checkbox('回复覆盖所有诉求，未编造退款、联系或执行能力', key=f"p4_issues_{c['case_id']}_{c['current_version']}"),
    }
    if c['quality']['safety_review_required']:
        checks['safety'] = st.checkbox('已核对严重伤害、停止使用建议及不复现故障', key=f"p4_safety_{c['case_id']}_{c['current_version']}")
    if c['quality']['status'] == 'blocked':
        st.error('当前质量门禁阻断，不能批准或模拟发送。分析错误需人工另行核实，改写回复无法解除。')
    a,b,d = st.columns(3)
    if a.button('批准草稿', key='p4_approve', type='primary', disabled=c['quality']['status']=='blocked' or c['state']=='rejected'):
        act(db,c,'approve',actor,actor_type,reason,checks,c['draft']['body'])
    if b.button('退回修改', key='p4_request_changes', disabled=c['state']=='rejected'):
        act(db,c,'request_changes',actor,actor_type,reason,checks,c['draft']['body'])
    if d.button('拒绝草稿', key='p4_reject'):
        act(db,c,'reject',actor,actor_type,reason,checks,c['draft']['body'])


def inbox(db, cases, c, scenario):
    st.subheader('收件箱')
    pending = sum(i['state'] not in ('simulated_sent','rejected') for i in cases)
    st.caption(f'{pending} 待处理 · {len(cases)} 个本地案例')
    a,b = st.columns([1.1,1])
    with a:
        state = st.selectbox('会话筛选',['全部','待处理','待审核','需要修改','审核通过','已模拟发送','需人工介入','已拒绝'], key='p46_filter',label_visibility='collapsed')
    with b:
        order = st.selectbox('会话排序',['最近更新','最早更新'],format_func=lambda x:'最新' if x=='最近更新' else '最早',
            help='按最后一次处理事件的时间排序',key='p46_order',label_visibility='collapsed')
    selected = [i for i in cases if state=='全部' or status(i)==state]
    selected.sort(key=lambda i:(i['events'][-1]['created_at'],i['case_id']),reverse=order=='最近更新')
    with st.container(height=390, border=False, key='inbox_scroll'):
        for item in selected:
            latest = MailThreads(db).messages(item['case_id'])[-1]
            snippet = preview(' '.join(latest['body'].split())[:46])
            title = preview(item['run'].email.subject)
            with st.container(key='selected_case' if c and item['case_id']==c['case_id'] else 'row_'+item['case_id']):
                if st.button(f"**{title}**\n\n{snippet}…\n\n{status(item)} · {time_label(item['events'][-1]['created_at'])}",
                             key='case_'+item['case_id'],width='stretch'):
                    opened(item); st.rerun()
        if not selected:
            st.caption('暂无匹配会话。选择一个演示场景，开始处理。')
    with st.expander('新增案例 / 导入邮件',expanded=not cases):
        st.selectbox('演示场景',SCENARIOS,key='p4_scenario')
        if scenario==SCENARIOS[6]:
            st.text_input('邮件主题',value='新客户邮件',key='p4_subject')
            st.text_area('客户邮件正文',key='p4_body',height=120)
        if st.button('分析邮件',key='p4_analyze',width='stretch'):
            try:
                email,_=example(st.session_state['p4_scenario'])
                if st.session_state['p4_scenario']==SCENARIOS[6]:
                    subject,body=st.session_state.get('p4_subject','新客户邮件'),st.session_state.get('p4_body','')
                    email=EmailInput(email_id='manual-'+digest(dict(subject=subject,body=body))[:24],subject=subject,body=body)
                repo=Repository(db.path.with_name(db.path.stem+'-analysis.sqlite3'))
                result=ProductAnalysis(AnalysisService(repo,CopilotFake(email,st.session_state['p4_scenario'])),db).submit(email)
                st.session_state['p46_next_filter']='全部'
                opened(result);st.rerun()
            except ValueError as exc: st.error(str(exc))
            except Exception as exc: st.error(f'保存未确认（{type(exc).__name__}），请重读后重试同一输入。')
        st.caption('合成预写演示；任意新邮件仅保存为未知占位，不执行模型理解。')
    # Stable compatibility/search entry; ordinary navigation is one-click rows.
    if cases:
        with st.expander('按标题查找已保存会话'):
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
    with st.container(height=350,border=False,key='conversation',autoscroll=True):
        if c:
            messages=threads.messages(c['case_id'])
        else:
            messages=[dict(role='customer',body=email.body,at=None)]
        st.html('<div class="system-event">本地客户会话 · 客服消息仅来自已保存模拟回执</div>')
        for m in messages:
            outgoing=m['role']=='assistant_simulation'
            identity='客服 · 已模拟发送' if outgoing else '客户 · 原始来信'
            when=' · '+time_label(m['at']) if m['at'] else ' · 演示预览'
            st.html(f'<div class="message {"outgoing" if outgoing else "incoming"}"><div class="message-meta">{identity}{when}</div>{escape(m["body"])}</div>')
        if c:
            st.html(f'<div class="system-event">{len(c["events"])} 条处理记录 · {status(c)} · 草稿不会显示为已发送消息</div>')


def composer(db,c):
    with st.container(key='composer'):
        if c['receipt']:
            st.success('模拟发送已完成 · 未投递真实邮件')
            st.caption(f"回复 v{c['receipt']['version']} · {time_label(c['receipt']['created_at'])} · 回执已保存")
            thread_panel(MailThreads(db),c)
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
    a,b=st.tabs(['AI助手','详情'])
    with a:
        with st.container(height=520,border=False,key='assistant_scroll'):
            st.caption((provenance(c) if c else '离线预写建议')+' · 仅供内部参考')
            if not data or (c and not c['accepted']):
                st.warning('没有可信建议，请人工阅读原文。')
            else:
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
        st.text_input('向AI追问',placeholder='当前离线模式不支持任意追问',disabled=True,key='p46_question')
        st.caption('本次只读建议，不支持实时追问。' if c and c['source_kind']!='offline_fake' else '固定场景建议，不是实时AI推理。')
    with b:
        with st.container(height=600,border=False):
            understanding(data if not c or c['accepted'] else None,c['quality'] if c else None)
            if c:
                with st.expander('线程与处理记录'):
                    link=MailThreads(db).link(c['case_id'])
                    st.caption('关联上一封邮件' if link else '首轮邮件')
                    if link and st.button('打开上一轮',key='p46_parent'):
                        opened(db.get(link['parent_id']));st.rerun()
                    child=MailThreads(db).child(c['case_id'])
                    if child and st.button('打开下一轮',key='p46_child'):
                        opened(db.get(child));st.rerun()
                    names={'created':'建立未审核案例','save_edit':'保存人工编辑','insert_suggestion':'插入AI内部建议','approve':'批准草稿','simulate_send':'模拟发送','request_changes':'退回修改','reject':'拒绝草稿'}
                    for e in c['events']:
                        st.caption(f"{time_label(e['created_at'])} · {names.get(e['action'],e['action'])} · v{e['version']} · {e['actor_type']}")
                with st.expander('Developer Details · 来源与运行身份'):
                    st.caption(provenance(c))
                    st.markdown('客户邮件/显式历史 → 输入与提示词组装 → LangChain ChatOpenAI 适配 → DeepSeek 输出 → Issue/原文证据 → 业务质量校验 → 草稿与人工审核。')
                    st.caption('当前分支使用 RunnableLambda 返回预写 Fixture/unknown；历史真实重放、SDK Mock HTTP 与未来实时 DeepSeek 分开。本轮实时调用关闭。')
                    st.json(dict(case_id=c['case_id'],run_id=c['run'].run_id,config=c['run'].config.model_dump(),snapshot_hash=c['snapshot_hash']))


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
    scenario=st.session_state.get('p4_scenario',SCENARIOS[0]);email,data=example(scenario)
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
        left,center,right=st.columns([1.05,2.45,1.5],gap='medium')
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
