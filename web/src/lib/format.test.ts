import { describe, expect, it } from 'vitest';
import {
  formatClock,
  formatCompact,
  formatPercent,
  formatPercentChange,
  formatPips,
  formatPrice,
  formatPriceChange,
  formatProbabilityBand,
  formatR,
  formatRelative,
  formatRiskReward,
  MINUS,
  MISSING,
  timeZoneLabel,
  trendOf,
} from './format';

describe('price formatting', () => {
  it('uses the instrument precision and keeps trailing zeros', () => {
    expect(formatPrice(1.0855, 5)).toBe('1.08550');
    expect(formatPrice(149.5, 3)).toBe('149.500');
    expect(formatPrice(2345.678, 2)).toBe('2,345.68');
  });

  it('shows a dash for missing or invalid values — never 0', () => {
    expect(formatPrice(undefined, 5)).toBe(MISSING);
    expect(formatPrice(null, 5)).toBe(MISSING);
    expect(formatPrice(Number.NaN, 5)).toBe(MISSING);
    expect(formatPrice(Number.POSITIVE_INFINITY, 5)).toBe(MISSING);
  });

  it('signs changes with + and a true minus sign', () => {
    expect(formatPriceChange(0.00087, 5)).toBe('+0.00087');
    expect(formatPriceChange(-0.00087, 5)).toBe(`${MINUS}0.00087`);
    expect(formatPriceChange(0, 5)).toBe('0.00000');
  });

  it('does not show a sign for values that round to zero', () => {
    expect(formatPriceChange(0.000001, 5)).toBe('0.00000');
    expect(formatPercentChange(0.000001)).toBe('0.00%');
  });
});

describe('percent, probability and risk formatting', () => {
  it('formats signed and unsigned percentages', () => {
    expect(formatPercentChange(0.0042)).toBe('+0.42%');
    expect(formatPercentChange(-0.0042)).toBe(`${MINUS}0.42%`);
    expect(formatPercent(0.683)).toBe('68%');
    expect(formatPercent(0.6834, 1)).toBe('68.3%');
  });

  it('formats bands, R multiples and reward:risk', () => {
    expect(formatProbabilityBand({ low: 0.61, high: 0.74 })).toBe('61–74%');
    expect(formatProbabilityBand(undefined)).toBe(MISSING);
    expect(formatR(0.36)).toBe('+0.36R');
    expect(formatR(-1)).toBe(`${MINUS}1.00R`);
    expect(formatRiskReward(2)).toBe('1 : 2.0');
  });

  it('converts distances to pips using the pip size', () => {
    expect(formatPips(0.00124, 0.0001)).toBe('12.4 pips');
    expect(formatPips(-0.5, 0.01)).toBe('50.0 pips');
  });

  it('compacts large counts', () => {
    expect(formatCompact(1234)).toBe('1.2K');
    expect(formatCompact(2_500_000)).toBe('2.5M');
  });
});

describe('time formatting', () => {
  const t = Date.UTC(2026, 9, 15, 14, 30, 5);

  it('formats clock time in the requested zone', () => {
    expect(formatClock(t, 'UTC')).toBe('14:30:05');
    expect(formatClock(t, 'Asia/Tokyo', false)).toBe('23:30');
  });

  it('labels zones', () => {
    expect(timeZoneLabel('UTC')).toBe('UTC');
    expect(timeZoneLabel('Asia/Tokyo', t)).toBe('GMT+9');
  });

  it('formats relative times', () => {
    expect(formatRelative(t - 2_000, t)).toBe('just now');
    expect(formatRelative(t - 42_000, t)).toBe('42s ago');
    expect(formatRelative(t - 5 * 60_000, t)).toBe('5m ago');
    expect(formatRelative(t - 3 * 3_600_000, t)).toBe('3h ago');
  });
});

describe('trendOf', () => {
  it('classifies direction for colour + arrow choice', () => {
    expect(trendOf(0.1)).toBe('up');
    expect(trendOf(-0.1)).toBe('down');
    expect(trendOf(0)).toBe('flat');
    expect(trendOf(undefined)).toBe('flat');
  });
});

describe('money and position units (round 3)', () => {
  it('formats account money with currency rules and true minus sign', async () => {
    const { formatMoney, formatUnits, formatPct } = await import('./format');
    expect(formatMoney(1234.5, 'USD')).toBe('$1,234.50');
    expect(formatMoney(-90, 'EUR')).toBe('−€90.00');
    expect(formatMoney(15100, 'JPY')).toBe('¥15,100');
    expect(formatMoney(12.345, 'USD', { signed: true })).toBe('+$12.35');
    expect(formatMoney(null, 'USD')).toBe('—');
    expect(formatUnits(10, 'XAU')).toBe('10.00 oz');
    expect(formatUnits(20000.4, 'EUR')).toBe('20,000 EUR');
    expect(formatPct(1)).toBe('1%');
    expect(formatPct(0.9)).toBe('0.9%');
  });
});
