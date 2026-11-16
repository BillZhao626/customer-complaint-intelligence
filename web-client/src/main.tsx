import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, ApiError, type Detail, type Summary } from './api';
import { displayNextStep, followupError, formatTime, isDirty, reconcileBuffer, uniqueMessages, type Buffer } from './state';
import './style.css';
import B4 from './p5b4';

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    inbox: <><path d="M4 4h16v15H4zM4 13h5l2 3h2l2-3h5" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>,
    spark: <><path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4z" /></>,
    send: <><path d="m3 4 18 8-18 8 3-8zM6 12h15" /></>,
    chevron: <path d="m9 5 7 7-7 7" />,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
    person: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    refresh: <><path d="M20 5v5h-5M4 19v-5h5" /><path d="M6 7a7 7 0 0 1 12-1l2 4M4 14l2 4a7 7 0 0 0 12-1" /></>,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z" /><path d="M12 8v5m0 3h.01" /></>,
    book: <><path d="M12 6v15M3 4h4a6 6 0 0 1 5 2 6 6 0 0 1 5-2h4v15h-4a6 6 0 0 0-5 2 6 6 0 0 0-5-2H3z" /></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 6 9 7 9-7" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.mail}</svg>;
}

function App() {
  const [cases, setCases] = useState<Summary[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<Detail | null>(null);
  const [buffers, setBuffers] = useState<Record<string, Buffer>>({});
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [view, setView] = useState('conversation');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [conflict, setConflict] = useState(false);
  const [modal, setModal] = useState<'tools' | 'review' | 'insert' | null>(null);
  const [scenarios, setScenarios] = useState<{ id: string; label: string }[]>([]);
  const [scenario, setScenario] = useState('');
  const [followup, setFollowup] = useState('');
  const [formError, setFormError] = useState('');
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [reviewReason, setReviewReason] = useState('');
  const [knowledgeInput, setKnowledgeInput] = useState('');
  const [knowledgeError, setKnowledgeError] = useState('');
  const [liveSubject, setLiveSubject] = useState('');
  const [liveBody, setLiveBody] = useState('');
  const [syntheticConfirmed, setSyntheticConfirmed] = useState(false);
  const request = useRef(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const selectedRef = useRef(selected); selectedRef.current = selected;
  const currentBuffer = detail ? buffers[detail.case_id] : undefined;
  const body = currentBuffer?.body ?? detail?.draft?.body ?? '';
  const dirty = isDirty(currentBuffer);
  const can = (action: string) => !!detail?.allowed_actions?.includes(action);
  const disabled = !!busy || loading;

  async function loadCases(preferred?: string) {
    const result = await api<{ cases: Summary[] }>('/api/cases');
    setCases(result.cases);
    const choose = preferred || selectedRef.current || result.cases[0]?.case_id;
    if (choose) setSelected(choose);
    else { setLoading(false); setDetail(null); }
  }

  function receive(value: Detail, replaceBuffer = false) {
    setDetail(value);
    setBuffers(previous => ({ ...previous, [value.case_id]: replaceBuffer
      ? reconcileBuffer(undefined, value.draft?.body || '', value.draft?.body_hash || '')
      : reconcileBuffer(previous[value.case_id], value.draft?.body || '', value.draft?.body_hash || '') }));
  }

  useEffect(() => {
    loadCases().catch(err => { setError(err.message); setLoading(false); });
    api<{ scenarios: { id: string; label: string }[] }>('/api/demo')
      .then(result => { setScenarios(result.scenarios); setScenario(result.scenarios[0]?.id || ''); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    const id = ++request.current;
    setLoading(true); setError(''); setNotice(''); setConflict(false);
    setKnowledgeInput(''); setKnowledgeError('');
    api<Detail>(`/api/cases/${selected}`).then(result => {
      if (id === request.current) receive(result);
    }).catch(err => { if (id === request.current) { setError(err.message); setDetail(null); } })
      .finally(() => { if (id === request.current) setLoading(false); });
  }, [selected]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (modal && dialog && !dialog.open) dialog.showModal();
    else if (!modal && dialog?.open) dialog.close();
  }, [modal]);

  useEffect(() => {
    function preventLoss(event: BeforeUnloadEvent) {
      if (Object.values(buffers).some(isDirty)) { event.preventDefault(); event.returnValue = ''; }
    }
    window.addEventListener('beforeunload', preventLoss);
    return () => window.removeEventListener('beforeunload', preventLoss);
  }, [buffers]);

  async function refresh() {
    if (!selected) { setLoading(true); await loadCases(); return; }
    setBusy('refresh'); setError('');
    try {
      const result = await api<Detail>(`/api/cases/${selected}`);
      receive(result); setConflict(false);
      setNotice('已读取最新版本；未保存的编辑仍保留。');
      await loadCases();
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(''); }
  }

  async function action(name: string, extra: Record<string, unknown> = {}) {
    if (!detail || busy) return;
    setBusy(name); setError(''); setNotice(''); setConflict(false);
    const target = detail.case_id;
    try {
      const result = await api<Detail>(`/api/cases/${target}/actions`, {
        action: name, revision: detail.revision, operation_id: crypto.randomUUID(), ...extra,
      });
      receive(result, name === 'save_edit' || name === 'insert_suggestion');
      setNotice(name === 'save_edit' ? '草稿已保存，需按当前版本确认。' : name === 'request_handoff'
        ? '已记录本地转人工请求，等待接管。' : name === 'take_over' ? '本地演示操作者已接管，请核对后继续处理。'
          : name === 'simulate_send' || name === 'quick_confirm' ? '回复已保存为本地模拟记录。' : '操作已完成。');
      setModal(null); await loadCases();
    } catch (err) {
      setError((err as Error).message); setConflict(err instanceof ApiError && err.status === 409);
    } finally { setBusy(''); }
  }

  async function createDemo() {
    if (!scenario || busy) return;
    setBusy('demo'); setFormError('');
    try {
      const result = await api<Detail>('/api/demo', { scenario });
      if (result.case_id === selectedRef.current) receive(result);
      await loadCases(result.case_id); setModal(null); setView('conversation');
    } catch (err) { setFormError((err as Error).message); } finally { setBusy(''); }
  }

  async function generateLive() {
    if (busy || !syntheticConfirmed) return;
    setBusy('live'); setFormError('');
    try {
      const result = await api<Detail>('/api/live', { subject: liveSubject, body: liveBody, synthetic_confirmed: true });
      await loadCases(result.case_id); setModal(null); setView('conversation');
    } catch (err) { setFormError((err as Error).message); }
    finally { setBusy(''); }
  }

  async function addFollowup(event: React.FormEvent) {
    event.preventDefault();
    const invalid = followupError(followup);
    if (invalid) { setFormError(invalid); return; }
    if (!detail || busy) return;
    setBusy('followup'); setFormError('');
    try {
      const result = await api<Detail>(`/api/cases/${detail.case_id}/followup`, {
        body: followup.trim(), revision: detail.revision, operation_id: crypto.randomUUID(),
      });
      await loadCases(result.case_id); setFollowup(''); setModal(null); setView('conversation');
    } catch (err) { setFormError((err as Error).message); } finally { setBusy(''); }
  }

  async function saveKnowledge(kind: 'request' | 'note') {
    if (!detail || busy) return;
    if (!knowledgeInput.trim()) { setKnowledgeError('请填写需要核实的问题或待审补充。'); return; }
    setKnowledgeError(''); setBusy('knowledge');
    try {
      const result = await api<Detail>(`/api/cases/${detail.case_id}/knowledge-notes`, {
        revision: detail.revision, operation_id: crypto.randomUUID(), kind, body: knowledgeInput.trim(),
      });
      receive(result); setKnowledgeInput('');
      setNotice(kind === 'request' ? '已记录本地知识核实问题，等待人工补充。' : '知识补充已保存为待审草案，尚未用于回复或模型。');
    } catch (err) { setKnowledgeError((err as Error).message); }
    finally { setBusy(''); }
  }

  async function supplyTask(taskId: string) {
    if (!detail || busy || !knowledgeInput.trim()) return;
    setBusy('knowledge'); setKnowledgeError('');
    try {
      receive(await api<Detail>(`/api/cases/${detail.case_id}/tasks/${taskId}`, { revision: detail.revision, operation_id: crypto.randomUUID(), kind: 'local_demo_verified_source', body: knowledgeInput.trim() }));
      setKnowledgeInput(''); setNotice('已保存本地模拟知识补充；可继续生成，不代表真实商家批准。');
    } catch (err) { setKnowledgeError((err as Error).message); } finally { setBusy(''); }
  }

  async function continueKnowledge() {
    if (!detail || busy) return;
    setBusy('continue');
    try { const result=await api<Detail>(`/api/cases/${detail.case_id}/continue`, {}); await loadCases(result.case_id); }
    catch (err) { setError((err as Error).message); } finally { setBusy(''); }
  }

  const filtered = cases.filter(item => (!query || `${item.subject} ${item.preview}`.toLowerCase().includes(query.toLowerCase()))
    && (filter === 'all' || filter === 'pending' && item.state !== 'simulated_sent' || filter === 'attention' && (item.blocked || item.status.includes('人工'))));
  const risk = detail?.quality.status === 'blocked';
  const approvalChecks = { facts_evidence: '事实与依据一致，已覆盖客户的主要诉求', authority_privacy: '没有越权承诺或泄露其他客户信息', all_issues: '重要问题和下一步均已回应', ...(detail?.quality.safety_review_required ? { safety: '已核对停止使用、安全处置和人工后续路径' } : {}) };
  const allChecked = Object.keys(approvalChecks).every(key => checks[key]);

  return <div className="app-shell">
    <header className="app-header">
      <a className="brand" href="/" aria-label="回声客服收件箱"><span className="brand-mark"><Icon name="inbox" size={22} /></span><b>回声</b><span className="brand-divider" /><span>客服工作台</span></a>
      <div className="app-context"><span className="status-dot" />{detail?.source_kind === 'real_new_analysis' ? '真实模型草稿' : detail?.source_kind === 'real_replay' ? '真实历史回复' : '离线开发候选'}<span className="context-divider">·</span><span>仅本地模拟</span></div>
      <button className="icon-button tools-button" title="更多与研究工具" aria-label="更多与研究工具" onClick={() => { setFormError(''); setModal('tools'); }}><Icon name="more" /></button>
    </header>

    <nav className="mobile-nav" aria-label="工作区切换">
      {[['inbox', '收件箱', 'inbox'], ['conversation', '会话', 'mail'], ['assistant', 'AI 建议', 'spark']].map(([id, title, icon]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)}><Icon name={icon} size={16} />{title}</button>)}
    </nav>

    <main className={`workspace view-${view}`}>
      <aside className="inbox-panel" aria-label="客户收件箱">
        <div className="inbox-heading"><h1>收件箱 <span className="count">{cases.length}</span></h1><button className="icon-button" title="刷新会话" aria-label="刷新会话" disabled={!!busy} onClick={refresh}><Icon name="refresh" size={17} /></button></div>
        <div className="search-box"><Icon name="search" size={17} /><input placeholder="搜索会话" aria-label="搜索会话" value={query} onChange={event => setQuery(event.target.value)} /></div>
        <div className="filters" aria-label="会话筛选">{[['all', '全部'], ['pending', '待处理'], ['attention', '需关注']].map(([key, title]) => <button key={key} className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>{title}</button>)}</div>
        <div className="conversation-list">
          {loading && cases.length === 0 ? <div className="empty-small">正在读取收件箱…</div> : filtered.map((item, index) => <button key={item.case_id} className={`conversation-row ${selected === item.case_id ? 'selected' : ''}`} disabled={!!busy} onClick={() => { setSelected(item.case_id); setView('conversation'); }} aria-current={selected === item.case_id ? 'true' : undefined}>
            <span className={`avatar avatar-${index % 4}`}><Icon name="person" size={17} /></span>
            <span className="conversation-copy"><span className="row-top"><span className="row-title">{item.subject || '无主题'}</span><span className="row-time">{formatTime(item.updated_at).split(' ')[0]}</span></span><span className="row-preview">{item.preview}</span><span className="row-bottom"><span className={`status-text ${item.blocked ? 'danger' : item.state === 'simulated_sent' ? 'done' : ''}`}>{item.blocked ? '需人工核实 · 已阻断' : item.status}</span>{buffers[item.case_id] && isDirty(buffers[item.case_id]) && <span className="unsaved-dot" title="有未保存编辑">未保存</span>}</span></span>
          </button>)}
          {!loading && filtered.length === 0 && <div className="empty-small">{cases.length ? '没有匹配的会话' : '收件箱暂无会话'}<button className="text-button" onClick={() => setModal('tools')}>打开演示工具</button></div>}
        </div>
        <div className="inbox-footer"><Icon name="shield" size={15} /><span>回复经确认后仅保存在本地</span></div>
      </aside>

      <section className="conversation-panel" aria-label="当前客户会话" aria-busy={loading}>
        {error && <div className="error-banner" role="alert"><span>{error}</span>{conflict && <button className="text-button" onClick={refresh}>读取最新版本</button>}<button className="icon-button" aria-label="关闭错误提示" onClick={() => setError('')}><Icon name="close" size={15} /></button></div>}
        {notice && <div className="notice-banner" role="status"><Icon name="check" size={16} /><span>{notice}</span><button className="icon-button" aria-label="关闭操作提示" onClick={() => setNotice('')}><Icon name="close" size={15} /></button></div>}
        {loading ? <div className="main-placeholder"><span className="loader" /><p>正在读取会话…</p></div> : !detail ? <div className="main-placeholder"><Icon name="inbox" size={36} /><h2>从一封来信开始</h2><p>选择会话，查看客户诉求与建议回复。</p><button className="primary" onClick={() => { setFormError(''); setModal('tools'); }}>打开演示工具</button></div> : <>
          <div className="conversation-header"><span className="avatar customer-avatar"><Icon name="person" size={21} /></span><div className="conversation-heading"><h2>{detail.subject || '无主题'}</h2><div><span className={`status-pill ${risk ? 'risk' : detail.state === 'simulated_sent' ? 'complete' : ''}`}>{detail.status}</span><span className="header-note">邮件会话</span></div></div><button className="icon-button" title="会话演示与审核记录" aria-label="会话演示与审核记录" onClick={() => { setFormError(''); setModal('tools'); }}><Icon name="more" /></button></div>
          {(risk || detail.triage.requires_takeover) && <div className={`routing-banner ${risk ? 'blocked' : ''}`}><Icon name={risk ? 'shield' : 'person'} size={18} /><div><strong>{detail.state === 'analysis_failed' ? '分析未通过，需要人工核实' : risk ? '安全阻断，需要人工核实' : detail.triage.handoff === 'requested' ? '等待人工接管' : '此会话需要人工处理'}</strong><p>{detail.validation_reason || detail.triage.next_step}</p></div>{can('take_over') && <button className="small-button" disabled={disabled} onClick={() => action('take_over', { reason: '操作者在客服工作台明确接管此会话。' })}>接管会话</button>}</div>}
          <div className="timeline" aria-label="唯一会话时间线">
            <div className="timeline-start"><span />会话记录<span /></div>
            {uniqueMessages(detail.messages).map(message => <article key={message.hash} className={`message ${message.role === 'customer' ? 'incoming' : 'outgoing'}`}><div className="message-meta"><span className={`mini-avatar ${message.role !== 'customer' ? 'agent-avatar' : ''}`}><Icon name={message.role === 'customer' ? 'person' : 'check'} size={14} /></span><b>{message.role === 'customer' ? '客户来信' : '客服回复'}</b>{message.role !== 'customer' && <span className="simulation-label">本地模拟</span>}<time>{formatTime(message.at)}</time></div><div className="message-body">{message.body}</div></article>)}
          </div>
          <section className={`composer ${detail.state === 'simulated_sent' ? 'sent-composer' : ''}`} aria-label="固定回复编辑器">
            <div className="composer-label"><span><Icon name="mail" size={16} /><b>回复客户</b></span><span className={`save-state ${dirty ? 'dirty' : ''}`}>{dirty ? '有未保存修改' : detail.current_version ? `草稿 v${detail.current_version} · 已保存` : '暂无草稿'}</span></div>
            <textarea aria-label="回复正文" placeholder="在此编辑回复，或插入右侧的 AI 建议…" value={body} disabled={disabled || detail.state === 'simulated_sent'} onChange={event => setBuffers(previous => ({ ...previous, [detail.case_id]: { body: event.target.value, base: currentBuffer?.base ?? detail.draft?.body ?? '', bodyHash: currentBuffer?.bodyHash ?? detail.draft?.body_hash ?? '' } }))} />
            <div className="composer-actions"><div className="secondary-actions">{can('save_edit') && <button className="secondary" disabled={disabled || !dirty || !body.trim()} onClick={() => action('save_edit', { body })}>{busy === 'save_edit' ? '保存中…' : '保存草稿'}</button>}{can('request_handoff') && <button className="text-button handoff-button" disabled={disabled} onClick={() => action('request_handoff', { reason: '客服操作者请求人工核实本案事实与后续处理路径。' })}><Icon name="person" size={15} />转人工</button>}</div><div className="primary-action">{can('quick_confirm') ? <button className="primary" disabled={disabled || dirty || !body.trim()} onClick={() => action('quick_confirm', { confirmed: true })}><Icon name="send" size={16} />{busy === 'quick_confirm' ? '正在保存…' : '确认并模拟发送'}</button> : can('simulate_send') ? <button className="primary" disabled={disabled || dirty} onClick={() => action('simulate_send')}><Icon name="send" size={16} />模拟发送</button> : can('approve') ? <button className="primary" disabled={disabled || dirty || !body.trim()} onClick={() => { setChecks({}); setReviewReason(''); setModal('review'); }}><Icon name="check" size={16} />审核回复</button> : can('take_over') ? <button className="primary" disabled={disabled} onClick={() => action('take_over', { reason: '操作者在客服工作台明确接管此会话。' })}><Icon name="person" size={16} />接管会话</button> : detail.state === 'simulated_sent' ? <span className="sent-note"><Icon name="check" size={16} />已记录本地模拟回复</span> : <span className="muted">{risk ? '当前分析阻断，不能发送' : '请先核实会话状态'}</span>}</div></div>
            <div className="composer-footnote">{dirty ? '请先保存修改，再按新版本确认。' : detail.state === 'simulated_sent' ? '未向客户邮箱发送。可在演示工具中添加客户后续邮件。' : can('quick_confirm') ? '点击确认即表示已核对事实、权限和诉求覆盖；仅本地模拟。' : '模拟记录不会发送到客户邮箱；接管不等于批准。'}</div>
          </section>
        </>}
      </section>

      <aside className="assistant-panel" aria-label="AI 建议">
        <div className="assistant-heading"><span className="assistant-symbol"><Icon name="spark" size={20} /></span><h2>AI 助手</h2><span className="assistant-mode">{detail?.source_kind?.startsWith('real_') ? '真实模型草稿' : '离线建议'}</span></div>
        {detail && !loading ? <div className="assistant-content"><div className="assistant-section"><span className="eyebrow">客户诉求</span><p className="intent">{detail.ai?.summary || detail.summary || '请先阅读客户原文，当前未形成可靠分析。'}</p></div><div className="assistant-section next-step"><span className="eyebrow">建议下一步</span><p>{displayNextStep(detail.ai?.next_step || detail.triage.next_step)}</p>{detail.ai?.knowledge_status && <span className="knowledge-status"><Icon name="book" size={14} />{detail.ai.knowledge_status}</span>}{!!detail.ai?.missing_facts?.length && <ul className="missing-list">{detail.ai.missing_facts.map(value => <li key={value}>{value}</li>)}</ul>}</div>
          <div className="assistant-section suggestion-section"><div className="suggestion-heading"><span className="eyebrow">回复建议</span><span>开发候选</span></div><p className="suggestion-text">{detail.suggestion || '当前没有可用建议，请人工阅读原文并拟稿。'}</p>{can('insert_suggestion') && <button className="suggestion-button" disabled={disabled || !detail.suggestion} onClick={() => body.trim() ? setModal('insert') : action('insert_suggestion', { body, mode: 'replace' })}>插入回复<Icon name="arrow" size={16} /></button>}</div>
          <details className="sources"><summary><Icon name="book" size={16} />查看依据<span>{detail.sources.length}</span><Icon name="chevron" size={14} /></summary><div className="sources-content"><p className="source-mode">{detail.ai?.source_label || '离线开发候选，未经真实模型质量验证'}</p>{detail.sources.map(source => <div className="source-item" key={source.id}><b>{source.label}</b><p>{source.body}</p></div>)}{detail.sources.length === 0 && <p>尚无可核实的业务知识来源。</p>}</div></details>
          <details className="sources" key={`knowledge-${detail.case_id}`}><summary><Icon name="book" size={16} />内部知识核实<span>{detail.knowledge_tasks?.length || 0}</span><Icon name="chevron" size={14} /></summary><div className="sources-content knowledge-form"><p className="source-mode">记录商家需要核实的规格与政策。补充内容保持待批准，不直接用于回复或模型。</p><label htmlFor="knowledge-note">核实问题或待审资料</label><textarea id="knowledge-note" value={knowledgeInput} onChange={event => { setKnowledgeInput(event.target.value); setKnowledgeError(''); }} placeholder="例如：请核对 C200 的有线连接协议及适用设备。" maxLength={4000} /><div className="knowledge-actions"><button className="secondary" disabled={disabled} onClick={() => saveKnowledge('request')}>记录核实问题</button><button className="secondary" disabled={disabled} onClick={() => saveKnowledge('note')}>保存待审补充</button></div>{knowledgeError && <p className="form-error" role="alert">{knowledgeError}</p>}{detail.knowledge_tasks?.map((task, index) => <div className="knowledge-task" key={index}><b>{task.kind === 'request' ? '待核实问题' : '待批准补充'} · {formatTime(task.created_at)}</b><p>{task.body}</p></div>)}</div></details>
          {detail.quality.findings.length > 0 && <details className="sources"><summary><Icon name="shield" size={16} />核对提示<span>{detail.quality.findings.length}</span><Icon name="chevron" size={14} /></summary><div className="sources-content">{detail.quality.findings.map((finding, index) => <p key={index}>{finding.message || finding.detail || '请人工核对当前分析与客户原文，安全阻断不能由改写回复解除。'}</p>)}</div></details>}
          {!!detail.business_tasks?.length && <details className="audit-details" open><summary>本地业务待办 {detail.business_tasks.length}</summary>{detail.business_tasks.map(t => <div key={t.task_id}><b>{t.decision.kind} · {t.decision.owner}</b><p>{t.status} · {t.decision.priority}</p><p>{t.decision.question}</p><small>任务 {t.task_id} · 事件 {t.event_id}</small>{t.decision.kind==='knowledge_request' && <div><label htmlFor="task-knowledge">本地模拟知识补充（含来源，仅限当前问题）</label><textarea id="task-knowledge" value={knowledgeInput} onChange={e => setKnowledgeInput(e.target.value)} /><button disabled={!!busy || !knowledgeInput.trim()} onClick={() => supplyTask(t.task_id)}>保存模拟知识</button><button disabled={!!busy || t.status!=='KNOWLEDGE_SUPPLIED_SIMULATION'} onClick={continueKnowledge}>根据补充继续生成</button></div>}</div>)}</details>}
          <details className="audit-details"><summary>Run Trace · 生成与校验</summary><pre>{JSON.stringify(detail.run_trace,null,2)}</pre></details>
          <div className="assistant-disclaimer">建议供客服审阅。本地待办只证明内部登记；人工补充为模拟资料，外部联系与实际业务结果仍需回执。</div>
        </div> : <div className="assistant-empty"><Icon name="spark" size={27} /><p>选中会话后<br />查看诉求与下一步建议</p></div>}
      </aside>
    </main>

    <dialog ref={dialogRef} onCancel={() => setModal(null)} onClose={() => setModal(null)} className={`modal modal-${modal || 'closed'}`} aria-labelledby="dialog-title">
      <div className="modal-heading"><h2 id="dialog-title">{modal === 'tools' ? '更多与研究工具' : modal === 'review' ? '核对当前回复' : '插入建议回复'}</h2><button className="icon-button" aria-label="关闭弹窗" disabled={!!busy} onClick={() => setModal(null)}><Icon name="close" /></button></div>
      {modal === 'tools' && <div className="modal-body"><p className="muted">仅限合成客户来信；历史演示与实时付费生成分别标识。</p><section className="tool-section"><h3>新邮件 · 现场 DeepSeek 生成</h3><label htmlFor="live-subject">新邮件主题</label><input id="live-subject" value={liveSubject} onChange={e => setLiveSubject(e.target.value)} /><label htmlFor="live-body">新邮件正文</label><textarea id="live-body" value={liveBody} onChange={e => setLiveBody(e.target.value)} /><label><input type="checkbox" checked={syntheticConfirmed} onChange={e => setSyntheticConfirmed(e.target.checked)} />确认是虚构商家与合成客户数据，使用本轮独立付费预算</label><button className="primary" disabled={!!busy || !syntheticConfirmed || !liveSubject.trim() || !liveBody.trim()} onClick={generateLive}>{busy === 'live' ? 'DeepSeek 正在分析，请勿重复提交…' : '现场分析并生成草稿'}</button></section><section className="tool-section"><h3>打开演示会话</h3><label htmlFor="demo-scenario">选择场景</label><select id="demo-scenario" value={scenario} onChange={event => setScenario(event.target.value)}>{scenarios.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select><button className="secondary" disabled={!!busy || !scenario} onClick={createDemo}>{busy === 'demo' ? '正在打开…' : '打开会话'}</button></section>
        <form className="tool-section" onSubmit={addFollowup}><h3>添加客户后续邮件</h3><p className="muted">先审核并完成本地模拟。启用B3实时服务时，新一轮携带本会话历史调用DeepSeek，计入同一预算。</p><label htmlFor="followup-body">客户回复正文</label><textarea id="followup-body" value={followup} onChange={event => { setFollowup(event.target.value); setFormError(''); }} placeholder="输入客户下一轮来信…" maxLength={20000} aria-describedby={formError ? 'form-error' : undefined} /><button className="secondary" type="submit" disabled={!!busy || !detail || detail.state !== 'simulated_sent'}>{busy === 'followup' ? '正在保存…' : '保存客户来信'}</button></form>
        {formError && <p className="form-error" id="form-error" role="alert">{formError}</p>}
        {detail && <details className="audit-details"><summary>草稿版本与审核记录</summary><pre>{JSON.stringify({ revision: detail.revision, current_version: detail.current_version, drafts: detail.drafts, events: detail.events }, null, 2)}</pre>{(can('request_changes') || can('reject')) && <div><label htmlFor="return-reason">退回或拒绝理由（必填）</label><textarea id="return-reason" value={reviewReason} onChange={event => setReviewReason(event.target.value)} placeholder="说明需要修改或不能采用的具体原因…" /><div className="modal-actions">{can('request_changes') && <button className="secondary" disabled={!!busy || !reviewReason.trim()} onClick={() => action('request_changes', { reason: reviewReason.trim() })}>退回修改</button>}{can('reject') && <button className="secondary" disabled={!!busy || !reviewReason.trim()} onClick={() => action('reject', { reason: reviewReason.trim() })}>拒绝当前草稿</button>}</div></div>}</details>}
        <div className="research-link"><Icon name="book" size={17} /><a href="http://127.0.0.1:8560" target="_blank" rel="noreferrer">打开 Streamlit 研究工具</a><span>独立服务</span></div></div>}
      {modal === 'review' && <div className="modal-body"><p>请按当前保存的草稿 v{detail?.current_version} 逐项核对。该操作记录本地审核，不计为独立人工质量评价。</p><div className="review-checks">{Object.entries(approvalChecks).map(([key, label]) => <label key={key}><input type="checkbox" checked={!!checks[key]} onChange={event => setChecks(previous => ({ ...previous, [key]: event.target.checked }))} /><span>{label}</span></label>)}</div><label htmlFor="review-reason">审核备注（可选）</label><textarea id="review-reason" value={reviewReason} onChange={event => setReviewReason(event.target.value)} placeholder="记录需要追溯的核实依据…" /><div className="modal-actions"><button className="secondary" onClick={() => setModal(null)}>返回编辑</button><button className="primary" disabled={!allChecked || !!busy} onClick={() => action('approve', { checks, reason: reviewReason || '操作者逐项核对当前草稿，仅用于本地模拟。' })}>确认审核</button></div></div>}
      {modal === 'insert' && <div className="modal-body"><p>编辑器已有回复内容。请选择如何插入建议；插入后将生成新的草稿版本，需重新确认。</p><div className="modal-actions"><button className="secondary" disabled={!!busy} onClick={() => action('insert_suggestion', { body, mode: 'append' })}>追加到末尾</button><button className="primary" disabled={!!busy} onClick={() => action('insert_suggestion', { body, mode: 'replace' })}>替换编辑器内容</button></div></div>}
      {modal !== 'tools' && error && <p className="form-error modal-error" role="alert">{error}</p>}
    </dialog>
  </div>;
}

createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).has('p5b4') ? <B4 /> : <App />);
