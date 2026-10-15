import type { Candle } from '@/domain/market';

/**
 * Pure indicator maths. Each function returns one value per input candle,
 * `null` where there is not yet enough history (warm-up period).
 */

export type Series = (number | null)[];

export function sma(values: readonly number[], period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i] ?? 0;
    if (i >= period) sum -= values[i - period] ?? 0;
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

/** EMA seeded with the SMA of the first `period` values. */
export function ema(values: readonly number[], period: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (values.length < period) return out;
  const k = 2 / (period + 1);
  let prev = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period - 1] = prev;
  for (let i = period; i < values.length; i++) {
    prev = (values[i] ?? prev) * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

export interface BollingerPoint {
  upper: number;
  middle: number;
  lower: number;
}

/** Bollinger Bands with population standard deviation. */
export function bollinger(values: readonly number[], period = 20, multiplier = 2): (BollingerPoint | null)[] {
  const middle = sma(values, period);
  return values.map((_, i) => {
    const m = middle[i];
    if (m === null || m === undefined) return null;
    let variance = 0;
    for (let j = i - period + 1; j <= i; j++) variance += ((values[j] ?? m) - m) ** 2;
    const sd = Math.sqrt(variance / period);
    return { upper: m + multiplier * sd, middle: m, lower: m - multiplier * sd };
  });
}

/** RSI with Wilder smoothing. */
export function rsi(values: readonly number[], period = 14): Series {
  const out: Series = new Array(values.length).fill(null);
  if (values.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = (values[i] ?? 0) - (values[i - 1] ?? 0);
    if (d >= 0) gain += d;
    else loss -= d;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  const toRsi = () => (avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
  out[period] = toRsi();
  for (let i = period + 1; i < values.length; i++) {
    const d = (values[i] ?? 0) - (values[i - 1] ?? 0);
    avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
    out[i] = toRsi();
  }
  return out;
}

/** Average true range (Wilder). Used by the demo fixtures for zone sizing. */
export function atr(candles: readonly Candle[], period = 14): Series {
  const tr = candles.map((c, i) => {
    const prevClose = i > 0 ? (candles[i - 1]?.close ?? c.close) : c.close;
    return Math.max(c.high - c.low, Math.abs(c.high - prevClose), Math.abs(c.low - prevClose));
  });
  const out: Series = new Array(candles.length).fill(null);
  if (candles.length < period) return out;
  let prev = tr.slice(0, period).reduce((a, b) => a + b, 0) / period;
  out[period - 1] = prev;
  for (let i = period; i < tr.length; i++) {
    prev = (prev * (period - 1) + (tr[i] ?? 0)) / period;
    out[i] = prev;
  }
  return out;
}

export const closes = (candles: readonly Candle[]): number[] => candles.map((c) => c.close);
