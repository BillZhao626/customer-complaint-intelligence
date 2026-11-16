export type Buffer = { body: string; base: string; bodyHash: string };

export function displayNextStep(value: string): string {
  const labels: Record<string, string> = {
    ASK_HUMAN_INPUT: '请内部人员核实资料', ASK_CLARIFICATION: '请客户补充必要资料',
    HANDOFF: '由人工接管处理', HARD_BLOCK: '先停止自动处理并核实安全问题', ANSWER: '根据已核实资料答复',
  };
  return value.replace(/\b(ASK_HUMAN_INPUT|ASK_CLARIFICATION|HANDOFF|HARD_BLOCK|ANSWER)\b/g, code => labels[code]);
}

export function formatTime(value: string): string {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

export function reconcileBuffer(buffer: Buffer | undefined, savedBody: string, bodyHash: string): Buffer {
  // A changed server version never silently overwrites an unsaved local edit.
  if (buffer && buffer.body !== buffer.base) return buffer;
  return { body: savedBody, base: savedBody, bodyHash };
}

export function isDirty(buffer: Buffer | undefined): boolean {
  return !!buffer && buffer.body !== buffer.base;
}

export function followupError(body: string): string {
  if (!body.trim()) return '请填写客户回复正文。';
  if (body.length > 20000) return '正文过长，请缩短到 20,000 字以内。';
  return '';
}

export function uniqueMessages<T extends { hash: string }>(messages: T[]): T[] {
  const seen = new Set<string>();
  return messages.filter(message => {
    if (seen.has(message.hash)) return false;
    seen.add(message.hash); return true;
  });
}
