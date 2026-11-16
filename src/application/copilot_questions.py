"""Bounded evidence Q&A. Saved predictions are attributed, never certified facts."""
import re
import json
from src.application.mail_threads import MailThreads
from src.domain.contracts import digest

VERSION = 'copilot-evidence-v1'
P47_VERSION = 'copilot-service-evidence-p47-v1'
GUIDE = dict(id='demo-guide-v1', title='演示操作边界 v1',
             text='仅演示：依据客户陈述核实资料；所有回复须保存版本与人工审核；仅模拟发送。未接入商品规格、订单、退货政策或CRM。')
P47_GUIDE = dict(id='demo-guide-p47-v1', title='客服协作演示边界 P4.7 v1',
                 text='仅本地演示：普通建议核对后显式轻确认；需人工确认时审核，高风险或明确人工请求须先接管。'
                      '保存编辑会撤销原批准，分析阻断不能靠回复或问答解除。仅模拟发送，未连接真实坐席、订单、SMTP或CRM。'
                      '预写场景策略和演示售后申请规则不是真实商家条款，也不能证明处理资格、批准结果或独立人工质量。')
QUALITY_REASONS = {
    'potential_injury_downgrade':'原分析低估了承重结构失效的潜在伤害；无人受伤不能作为降级依据。',
    'severe_safety_review':'须人工核对安全风险，停止使用且不要复现危险故障。',
    'analysis_not_accepted':'原分析未通过校验，不能据此批准或模拟发送。',
    'missing_stop_use_advice':'严重风险回复缺少停止使用提醒。',
    'unavailable_future_action':'回复包含本系统尚不能执行的后续操作承诺。',
}


def context_for(store, case_id):
    case = store.get(case_id)
    if case is None:
        raise ValueError('案例不存在')
    messages = MailThreads(store).messages(case_id)
    refs = [dict(id='M'+str(n), kind=m['role'], text=m['body'], source=m['source'])
            for n, m in enumerate(messages, 1)]
    issues = []
    for n, issue in enumerate(((case['analysis'] or {}) if case['accepted'] else {}).get('issues', []), 1):
        evidence = []
        for ev in issue.get('evidence', []):
            quote = ev.get('quote', '')
            # Never cite an outgoing simulation as evidence of a customer fact.
            if quote and any(quote in m['body'] for m in messages if m['role'] == 'customer'):
                ref = dict(id=f'I{n}E{len(evidence)+1}', kind='customer_quote', text=quote,
                           source='已保存Evidence · 客户陈述，非独立核实')
                refs.append(ref); evidence.append(ref['id'])
        issues.append(dict(id=f'I{n}', kind=issue.get('issue_kind', 'unknown'),
                           requests=issue.get('customer_requests', []), missing=issue.get('missing_evidence', []),
                           risk=issue.get('risk_level', 'unknown'), evidence=evidence))
    refs.append(dict(id='Q', kind='quality', text=json.dumps(case['quality'], ensure_ascii=False), source='已保存质量门禁'))
    refs.append(dict(id='G', kind='demo_guide', text=GUIDE['text'], source=GUIDE['title']))
    result = dict(case_id=case_id, revision=case['revision'], analysis_run=case['run'].run_id,
                  input_hash=case['run'].input_hash, source=case['source_kind'], accepted=case['accepted'],
                  quality=case['quality'], issues=issues, references=refs, guide=GUIDE,
                  draft_version=case['current_version'], draft=case['draft']['body'] if case['draft'] else None)
    # Keep every legacy context field and serialization untouched. New workflow
    # guidance is an additive, source-version-bound QA identity only for P4.7.
    from src.application.service_triage import is_p47_case, service_strategy, triage
    if is_p47_case(case):
        policy, route = service_strategy(case), triage(case)
        refs[-1] = dict(id='G', kind='demo_guide', text=P47_GUIDE['text'], source=P47_GUIDE['title'])
        refs.append(dict(id='T', kind='service_triage', text=json.dumps(route, ensure_ascii=False),
                         source='本案当前本地分流与接管记录 · ' + route['version']))
        if policy is not None:
            refs.append(dict(id='P', kind='service_strategy', text=json.dumps(policy, ensure_ascii=False),
                             source='原输入与策略hash绑定的预写演示策略 · ' + policy['version']))
        result.update(qa_version=P47_VERSION, guide=P47_GUIDE, service_strategy=policy, service_triage=route,
                      workflow_state=case['state'], simulation_completed=bool(case['receipt']))
    return dict(result, context_hash=digest(result))


def service_answer(context, question):
    """Answer only the added workflow/material operations from bound snapshots."""
    q = question.casefold()
    route, policy = context['service_triage'], context.get('service_strategy')
    blocked = not context['accepted'] or context['quality']['status'] == 'blocked'
    state = context['workflow_state']
    citations = ['T', 'Q', 'G']
    actions = []
    if re.search(r'已(?:经)?提供|已知|已经知道|不用重复|不再重复|重复(?:问|索要)|already|known', q):
        # Known-information intent must precede the broad materials keyword.
        # These are customer statements, not independently verified records.
        customer = [r for r in context['references'] if r['kind'] == 'customer']
        answer = ('以下信息已由客户写入当前线程，已有内容无需重复索要；未独立核实：\n'
                  + '\n'.join('['+r['id']+'] '+r['text'] for r in customer))
        citations = [r['id'] for r in customer] or ['G']
    elif re.search(r'真实|实际|商家.*(?:条款|政策)|运费|期限|几天|多少天|资格|能否退款|退款.*(?:了|吗)|退货政策|merchant|shipping fee|deadline|eligible', q):
        answer = ('当前没有真实商家的订单记录、适用条款、退货期限、运费承担或批准结果，不能据此确认资格或实际进度。'
                  '需要有权限的人工核对实际商家资料。')
        if policy and policy.get('demo_aftersales_policy'):
            answer += ' 本案仅绑定了演示售后申请规则；提出申请不代表符合条件或已经获批。'
            citations.append('P')
    elif re.search(r'下一步|怎么办|如何处理|怎么处理|建议|next|recommend', q):
        if context['simulation_completed']:
            answer = '本地模拟发送已完成，回执对应的回复版本已保存；没有投递真实邮件。可查看处理记录或接收后续来信。'
        elif state in ('changes_requested', 'rejected'):
            answer = '当前草稿已退回或拒绝，请依据处理意见实际修改并保存新版本，再重新确认或审核。'
        elif blocked:
            answer = '先由人工核对当前质量阻断；接管、问答或改写回复都不能解除分析错误，不能批准或模拟发送。'
        elif route['requires_takeover'] and not route['takeover_complete']:
            answer = '先点击“接管会话”，再核对客户原文、回复与必要资料；接管仅在本地演示，不代表已转接真实坐席。'
        elif state == 'approved':
            answer = '当前回复已通过审核，核对获批版本后可点击“模拟发送”；修改正文须保存新版本并重新审核。'
        elif route['can_quick_confirm']:
            answer = '当前回复草稿已有预写建议。对照原文核对事实、权限和诉求覆盖，必要时编辑并保存；明确勾选确认后点击“确认并模拟发送”。'
        else:
            answer = '核对当前回复和必要资料；如修改正文先保存新版本，完成必要人工审核后再模拟发送。'
        if policy and not blocked and not context['simulation_completed']:
            answer += '\n建议处理：' + '；'.join(policy.get('next_actions', []))
            citations.append('P')
        actions = (['查看已保存的模拟回执或后续来信'] if context['simulation_completed'] else
                   ['实际修改并保存新版本后重新审核'] if state in ('changes_requested', 'rejected') else
                   ['核对当前获批版本后模拟发送'] if state == 'approved' and not blocked else [route['next_step']])
    elif re.search(r'人工|风险|阻断|拦截|risk|block', q):
        answer = route['label'] + '：' + '；'.join(route['reasons'])
        answer += '\n' + ('已有本地操作者接管，仍需核对当前版本；接管不等于批准。' if route['takeover_complete'] else
                          '需要接管时先点击“接管会话”；尚未连接真实人工坐席。' if route['requires_takeover'] else
                          '根据当前分流核对回复，普通问题可使用显式轻确认。' if route['can_quick_confirm'] else
                          '当前路径需要人工核对后审核。')
        actions = [route['next_step']]
    elif re.search(r'缺|补|资料|missing|lack', q):
        if policy:
            answer = ('客户可补充（已有内容无需重复索要）：\n' + '；'.join(policy.get('customer_info', []))
                      + '\n商家或人工内部核实：\n' + '；'.join(policy.get('internal_verification', [])))
            citations.append('P')
            citations.extend(e for i in context['issues'] for e in i['evidence'])
        else:
            answer = '没有与本案身份匹配的资料策略；请人工阅读客户原文，分别确认客户可补资料和商家需核实记录。'
    elif re.search(r'演示.*(?:规则|政策)|售后.*(?:申请|路径)|怎么申请|维修|更换|退货申请|application', q):
        demo = policy.get('demo_aftersales_policy') if policy else None
        if demo:
            answer = (demo['title'] + '（项目编写的本地演示规则，非真实商家条款）：\n'
                      + '可提出的申请：' + '、'.join(demo['options']) + '。\n'
                      + '；'.join(policy.get('next_actions', [])) + '\n' + demo['approval_boundary'])
            citations.append('P')
        else:
            answer = '本案没有绑定演示售后申请规则。售后选项、资格和执行步骤需要有权限的人工核实实际商家资料。'
    else:
        return None
    if blocked:
        answer = '【需人工介入】当前分析不可放行；以下仅辅助查阅。\n' + answer
    return dict(answer=answer.strip(), citations=list(dict.fromkeys(citations)),
                uncertainty=['客户陈述与来源分析未独立核实，不是人工Gold；本地分流与演示规则不能证明真实商家政策或批准结果。'],
                actions=actions, model='deterministic_rules', prompt=P47_VERSION, usage=None)


def offline_answer(context, question):
    """Natural language routed to explicit evidence operations; no generative model."""
    if context.get('qa_version') == P47_VERSION:
        answer = service_answer(context, question)
        if answer is not None:
            return answer
    q = question.casefold()
    refs = context['references']
    customer = [r for r in refs if r['kind'] == 'customer']
    issues = context['issues']
    supported = [i for i in issues if i['evidence']]
    citations = [r['id'] for r in customer]
    uncertainty = ['客户原文仅代表客户陈述；已保存分析为原来源预测，不是人工Gold。']
    actions = []
    blocked = not context['accepted'] or context['quality']['status'] == 'blocked'
    if re.search(r'规格|支持.*连接|有线.*能力|退款.*(了|吗)|订单状态|退货政策|specification|refund|wired.*support', q):
        answer = '无法依据现有资料确认商品规格、订单状态或退货政策。需要商家提供可核实的官方规格、订单记录或适用政策；客户询问和型号本身不能证明功能。'
        citations += ['G']
    elif re.search(r'人工|风险|阻断|拦截|risk|block', q):
        answer = ('此案例需人工介入，问答或修改草稿不能解除分析阻断。' if blocked else
                  '当前保存的质量状态为 '+context['quality']['status']+'；所有回复仍须人工审核。')
        findings = context['quality'].get('findings', [])
        answer += '\n' + '\n'.join(QUALITY_REASONS.get(f.get('code'), '已有质量诊断提示：需人工核对原文证据、回复事实与可执行范围。') for f in findings)
        citations = ['Q', *citations]; actions = ['核对质量诊断并转人工处理' if blocked else '逐项核对原文后审核']
    elif re.search(r'为什么|为何|判断|分类|投诉还是|咨询还是|why|classif', q):
        answer = '以下是已保存的分类及对应客户原文；属于来源分析结果，不能解释模型内部推理。\n'
        answer += ('\n'.join(i['id']+'：'+{'complaint':'投诉', 'inquiry':'咨询'}.get(i['kind'], i['kind']) for i in supported) or '没有可引用的分类证据，需人工判断。')
        citations = [e for i in supported for e in i['evidence']] or citations
    elif re.search(r'issue|evidence|原文|证据|哪些问题', q):
        answer = '已保存的Issue与原文对应如下（预测待核对）：\n' + '\n'.join(
            i['id']+'：'+'；'.join(i['requests'])+' ['+'、'.join(i['evidence'])+']' for i in supported)
        if not supported: answer += '没有可验证的Issue引用，需人工阅读客户原文。'
        citations = [e for i in supported for e in i['evidence']] or citations
    elif re.search(r'提供|重复|已知|知道|already|known', q):
        answer = '以下信息已由客户写入当前线程，不应重复索要其中已有的信息；未独立核实：\n' + '\n'.join(
            '['+r['id']+'] '+r['text'] for r in customer)
    elif re.search(r'缺|补|missing|lack', q):
        answer = '已保存分析标记的待补资料（先对照下方客户原文，已有内容不再索要）：\n' + '\n'.join(
            i['id']+'：'+'；'.join(i['missing']) for i in supported if i['missing'])
        if not any(i['missing'] for i in supported): answer += '没有可信的待补资料清单，需人工确认。'
        answer += '\n当前草稿是否完整仍需逐项人工核对，规则问答不能认证回复语义质量。'
        citations += [e for i in supported for e in i['evidence']]
    elif re.search(r'下一步|怎么办|如何处理|建议|next|recommend', q):
        answer = ('先转人工核对质量阻断；不要放行或宣称已执行处理。' if blocked else
                  '对照客户原文与待补资料，查看内部回复建议并明确插入草稿；编辑、保存新版本后提交人工审核。')
        answer += ' 商品能力和售后方案须有商家资料支持；当前没有已执行退款、联系或安排的证据。'
        citations += ['Q', 'G']; actions = ['转人工核对' if blocked else '查看建议并插入回复草稿']
    elif re.search(r'想|诉求|解决|主要|want|request|need', q):
        answer = '已保存分析记录的主要诉求（请核对客户原文）：\n' + '\n'.join(
            i['id']+'：'+'；'.join(i['requests']) for i in supported)
        if not supported: answer += '没有可信诉求记录；请人工阅读下方来信。'
        citations = [e for i in supported for e in i['evidence']] or citations
    else:
        answer = '无法依据现有资料回答该问题。离线证据问答支持诉求、分类、Issue原文、待补信息、风险、下一步和已提供信息。其他问题需要相关可核实资料或独立授权后的实时模型验证。'
        citations = ['G']; uncertainty.append('当前问题超出受限意图识别范围。')
    if blocked:
        answer = '【需人工介入】当前分析不可放行；以下仅辅助查阅。\n' + answer
        citations.append('Q')
    return dict(answer=answer.strip(), citations=list(dict.fromkeys(citations)), uncertainty=uncertainty,
                actions=actions, model='deterministic_rules', prompt=context.get('qa_version', VERSION), usage=None)
