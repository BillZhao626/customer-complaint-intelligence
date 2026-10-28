"""Bounded evidence Q&A. Saved predictions are attributed, never certified facts."""
import re
import json
from src.application.mail_threads import MailThreads
from src.domain.contracts import digest

VERSION = 'copilot-evidence-v1'
GUIDE = dict(id='demo-guide-v1', title='演示操作边界 v1',
             text='仅演示：依据客户陈述核实资料；所有回复须保存版本与人工审核；仅模拟发送。未接入商品规格、订单、退货政策或CRM。')
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
    return dict(result, context_hash=digest(result))


def offline_answer(context, question):
    """Natural language routed to explicit evidence operations; no generative model."""
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
                actions=actions, model='deterministic_rules', prompt=VERSION, usage=None)
