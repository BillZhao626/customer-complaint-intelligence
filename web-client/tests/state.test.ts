import test from 'node:test';
import assert from 'node:assert/strict';
import { displayNextStep, followupError, formatTime, isDirty, reconcileBuffer, uniqueMessages } from '../src/state.ts';
import { api, ApiError } from '../src/api.ts';

test('operator next steps explain bounded action codes without changing the plan', () => {
  assert.equal(displayNextStep('ASK_HUMAN_INPUT；核实C200协议'), '请内部人员核实资料；核实C200协议');
  assert.equal(displayNextStep('HANDOFF；HARD_BLOCK'), '由人工接管处理；先停止自动处理并核实安全问题');
  assert.equal(displayNextStep('请先接管并核实'), '请先接管并核实');
});

test('case timestamps use Asia/Shanghai independently of the browser timezone', () => {
  assert.match(formatTime('2026-10-28T08:00:00Z'), /16:00/);
  assert.equal(formatTime(''), '');
  assert.equal(formatTime('invalid'), 'invalid');
});

test('a server refresh cannot destroy an unsaved reply, while clean drafts advance', () => {
  const editing = { body: 'operator edit', base: 'saved draft', bodyHash: 'v1' };
  assert.equal(reconcileBuffer(editing, 'someone else saved v2', 'v2'), editing);
  assert.equal(isDirty(editing), true);
  assert.deepEqual(reconcileBuffer({ body: 'v1', base: 'v1', bodyHash: 'h1' }, 'v2', 'h2'), { body: 'v2', base: 'v2', bodyHash: 'h2' });
});

test('whitespace-only followup is stopped with a nearby Chinese form error', () => {
  assert.equal(followupError(' \n\t'), '请填写客户回复正文。');
  assert.equal(followupError('The model is C200.'), '');
  assert.ok(followupError('字'.repeat(20001)));
});

test('the timeline keeps one copy per identity and retains distinct repeated wording', () => {
  const a = { hash: 'a', body: '谢谢' }; const b = { hash: 'b', body: '谢谢' };
  assert.deepEqual(uniqueMessages([a, a, b]), [a, b]);
});

test('POST acquires session token and forwards revision plus operation identity', async () => {
  const original = globalThis.fetch;
  const calls: [string, RequestInit | undefined][] = [];
  globalThis.fetch = async (input, init) => {
    calls.push([String(input), init]);
    return new Response(JSON.stringify(String(input) === '/api/session' ? { token: 'local-token' } : { revision: 4 }), { status: 200 });
  };
  try {
    await api('/api/cases/demo/actions', { revision: 3, operation_id: 'op1', action: 'save_edit', body: 'draft' });
    assert.equal(calls[0][0], '/api/session');
    assert.equal((calls[1][1]?.headers as Record<string, string>)['X-P5-Token'], 'local-token');
    assert.deepEqual(JSON.parse(calls[1][1]?.body as string), { revision: 3, operation_id: 'op1', action: 'save_edit', body: 'draft' });
  } finally { globalThis.fetch = original; }
});

test('stale page conflicts stay actionable; raw validation structures never leak to the UI', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: '页面版本已过期，请刷新当前会话。' }), { status: 409 });
    await assert.rejects(() => api('/api/cases/demo'), error => error instanceof ApiError && error.status === 409 && error.message.includes('刷新'));
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ type: 'string_too_short', loc: ['body'] }] }), { status: 422 });
    await assert.rejects(() => api('/api/cases/demo'), error => error instanceof ApiError && !error.message.includes('string_too_short') && !error.message.includes('loc'));
  } finally { globalThis.fetch = original; }
});
