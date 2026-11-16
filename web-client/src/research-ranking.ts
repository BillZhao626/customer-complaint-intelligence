/** Presentation only: preserve API metrics and membership arrays unchanged. */
type Row = Record<string, any>;

function stableName(row: Row): string {
  return Object.keys(row.values).sort().map(key => String(row.values[key])).join('\u0000');
}

export function rankRows<T extends Row>(rows: readonly T[], measure: string, mode = 'count'): T[] {
  return [...rows].sort((a, b) => {
    const count = b[measure].numerator - a[measure].numerator;
    const rate = (b[measure].rate ?? -1) - (a[measure].rate ?? -1);
    const an = stableName(a), bn = stableName(b);
    const name = an < bn ? -1 : an > bn ? 1 : 0;
    return mode === 'rate' ? rate || count || name : count || rate || name;
  });
}

/** Same one-decimal percentage as the visible Fraction label; never max-normalize. */
export function percentageWidth(rate: number | null | undefined): number {
  if (rate == null || !Number.isFinite(rate)) return 0;
  return Number((100 * Math.min(1, Math.max(0, rate))).toFixed(1));
}
