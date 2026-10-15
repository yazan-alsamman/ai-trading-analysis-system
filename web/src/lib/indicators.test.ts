import { describe, expect, it } from 'vitest';
import type { Candle } from '@/domain/market';
import { atr, bollinger, ema, rsi, sma } from './indicators';

describe('sma', () => {
  it('averages the trailing window and leaves the warm-up empty', () => {
    expect(sma([1, 2, 3, 4, 5], 3)).toEqual([null, null, 2, 3, 4]);
  });
});

describe('ema', () => {
  it('is seeded with the SMA and weights recent values more', () => {
    const out = ema([1, 2, 3, 4, 5], 3);
    expect(out.slice(0, 2)).toEqual([null, null]);
    expect(out[2]).toBeCloseTo(2);
    // k = 0.5 → 4*0.5 + 2*0.5 = 3, then 5*0.5 + 3*0.5 = 4
    expect(out[3]).toBeCloseTo(3);
    expect(out[4]).toBeCloseTo(4);
  });

  it('returns only nulls when there is not enough data', () => {
    expect(ema([1, 2], 5)).toEqual([null, null]);
  });
});

describe('bollinger', () => {
  it('has zero width on a flat series and symmetric bands', () => {
    const flat = bollinger(Array(25).fill(10), 20, 2);
    expect(flat[24]).toEqual({ upper: 10, middle: 10, lower: 10 });
    const series = Array.from({ length: 30 }, (_, i) => 10 + Math.sin(i));
    const p = bollinger(series, 20, 2)[29];
    expect(p).not.toBeNull();
    if (p) expect(p.upper - p.middle).toBeCloseTo(p.middle - p.lower);
  });
});

describe('rsi', () => {
  it('is 100 for a series that only rises and 0 for one that only falls', () => {
    const up = Array.from({ length: 20 }, (_, i) => i);
    const down = Array.from({ length: 20 }, (_, i) => 20 - i);
    expect(rsi(up, 14)[19]).toBe(100);
    expect(rsi(down, 14)[19]).toBeCloseTo(0);
  });

  it('stays within 0–100', () => {
    const series = Array.from({ length: 200 }, (_, i) => 100 + Math.sin(i / 3) * 5 + (i % 7));
    const values = rsi(series, 14).filter((v): v is number => v !== null);
    expect(Math.min(...values)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...values)).toBeLessThanOrEqual(100);
  });
});

describe('atr', () => {
  it('equals the constant range for identical candles', () => {
    const candles: Candle[] = Array.from({ length: 20 }, (_, i) => ({ time: i, open: 1, high: 1.5, low: 0.5, close: 1, volume: 1 }));
    expect(atr(candles, 14)[19]).toBeCloseTo(1);
  });
});
