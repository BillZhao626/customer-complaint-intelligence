import test from 'node:test';
import assert from 'node:assert/strict';
import { rankRows, percentageWidth } from '../src/research-ranking.ts';

const row = (name: string, n: number, den: number) => ({
  values: { name }, negative: { numerator: n, denominator: den, rate: den ? n / den : null, member_ids: [name] },
});

test('count order resolves unequal denominators by rate, then stable name', () => {
  const input = [row('Clothing', 6, 11), row('Electronics', 6, 10), row('Beauty', 6, 8), row('Zeta', 2, 2), row('Alpha', 2, 2)];
  const saved = structuredClone(input);
  const sorted = rankRows(input, 'negative');
  assert.deepEqual(sorted.map(r => r.values.name), ['Beauty', 'Electronics', 'Clothing', 'Alpha', 'Zeta']);
  assert.deepEqual(input, saved);
  assert.strictEqual(sorted[0].negative.member_ids, input[2].negative.member_ids);
});

test('fixed percentage tracks agree with the visible rounded percentages', () => {
  assert.deepEqual([6 / 8, 6 / 10, 6 / 11, 2 / 11].map(percentageWidth), [75, 60, 54.5, 18.2]);
  for (const [n, den] of [[6, 8], [6, 10], [6, 11], [2, 11], [1, 20]]) {
    assert.equal(percentageWidth(n / den).toFixed(1), (100 * n / den).toFixed(1));
  }
});

test('zero and empty denominators do not create a visible minimum bar', () => {
  assert.deepEqual([0, null, undefined, NaN].map(percentageWidth), [0, 0, 0, 0]);
  assert.equal(percentageWidth(1), 100);
});

test('explicit rate mode keeps count and name tie-breaks, without changing widths', () => {
  const input = [row('A', 1, 2), row('B', 6, 8), row('C', 2, 2)];
  assert.deepEqual(rankRows(input, 'negative', 'rate').map(r => r.values.name), ['C', 'B', 'A']);
  assert.deepEqual(rankRows(input, 'negative').map(r => r.values.name), ['B', 'C', 'A']);
  assert.equal(percentageWidth(input[1].negative.rate), 75);
});
