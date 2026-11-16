export type Summary = {
  case_id: string; subject: string; preview: string; status: string; state: string;
  revision: number; updated_at: string; blocked: boolean; source_kind: string;
};
export type Source = { id: string; label: string; body: string };
export type Finding = { code?: string; message?: string; detail?: string; severity: string };
export type Detail = {
  source_kind?: string;
  validation_reason?: string;
  case_id: string; subject: string; status: string; state: string; revision: number;
  current_version: number; draft: { body: string; body_hash: string } | null;
  suggestion: string; summary: string;
  messages: { role: string; body: string; subject: string; at: string; hash: string }[];
  triage: { level: string; requires_takeover: boolean; takeover_complete: boolean;
    can_quick_confirm: boolean; handoff: string; next_step: string; reasons: string[] };
  quality: { status: string; safety_review_required: boolean; findings: Finding[] };
  sources: Source[]; events: unknown[]; drafts: unknown[]; receipt: unknown;
  allowed_actions: string[];
  business_tasks?: { task_id: string; event_id: string; status: string; decision: { kind: string; owner: string; priority: string; question: string } }[];
  run_trace?: unknown;
  knowledge_tasks?: { kind: string; body: string; created_at: string; owner_status: string; use_in_model: boolean }[];
  ai?: { summary?: string; next_step?: string; suggestion?: string; source_label?: string;
    knowledge_status?: string; missing_facts?: string[] };
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

let sessionToken: string | undefined;
export async function api<T>(path: string, payload?: Record<string, unknown>): Promise<T> {
  if (payload && !sessionToken) {
    const session = await api<{ token: string }>('/api/session');
    sessionToken = session.token;
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method: payload ? 'POST' : 'GET',
      headers: payload ? { 'Content-Type': 'application/json', 'X-P5-Token': sessionToken! } : {},
      body: payload ? JSON.stringify(payload) : undefined,
      cache: 'no-store',
    });
  } catch {
    throw new ApiError('暂时无法连接本地服务，请检查服务后重试。草稿仍保留在当前页面。', 0);
  }
  let result: unknown;
  try { result = await response.json(); } catch {
    throw new ApiError('本地服务返回异常，请稍后重试。', response.status);
  }
  if (!response.ok) {
    const data = result as { message?: unknown; detail?: unknown; error?: unknown };
    const candidate = data.message ?? data.detail ?? data.error;
    // Never render raw validation objects or implementation traces as customer UI.
    const message = typeof candidate === 'string' && candidate.length < 600
      ? candidate : '操作未完成，请检查输入或刷新当前会话。';
    if (response.status === 403) sessionToken = undefined;
    throw new ApiError(message, response.status);
  }
  return result as T;
}
