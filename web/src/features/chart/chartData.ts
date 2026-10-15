import type { BarData, HistogramData, LineData, UTCTimestamp, WhitespaceData } from 'lightweight-charts';
import type { IndicatorId } from '@/domain/indicators';
import type { Candle, ChartType } from '@/domain/market';
import { bollinger, closes, ema, rsi, sma, type Series } from '@/lib/indicators';

/** Pure conversions from domain candles to chart series data (unit-tested). */

export const ts = (seconds: number) => seconds as UTCTimestamp;

export type MainPoint = BarData<UTCTimestamp> | LineData<UTCTimestamp>;

export function toMainPoint(c: Candle, chartType: ChartType): MainPoint {
  if (chartType === 'line' || chartType === 'area') return { time: ts(c.time), value: c.close };
  return { time: ts(c.time), open: c.open, high: c.high, low: c.low, close: c.close };
}

export function toVolumePoint(c: Candle, upColor: string, downColor: string): HistogramData<UTCTimestamp> {
  return { time: ts(c.time), value: c.volume, color: c.close >= c.open ? upColor : downColor };
}

type LinePoint = LineData<UTCTimestamp> | WhitespaceData<UTCTimestamp>;

/** Null warm-up values become whitespace so the time axis stays aligned. */
function toLine(candles: readonly Candle[], values: Series): LinePoint[] {
  return candles.map((c, i) => {
    const v = values[i];
    return v === null || v === undefined ? { time: ts(c.time) } : { time: ts(c.time), value: v };
  });
}

export interface IndicatorData {
  sma20?: LinePoint[];
  ema50?: LinePoint[];
  bbUpper?: LinePoint[];
  bbMiddle?: LinePoint[];
  bbLower?: LinePoint[];
  rsi14?: LinePoint[];
}

export function computeIndicatorData(candles: readonly Candle[], enabled: readonly IndicatorId[]): IndicatorData {
  const cl = closes(candles);
  const out: IndicatorData = {};
  if (enabled.includes('sma20')) out.sma20 = toLine(candles, sma(cl, 20));
  if (enabled.includes('ema50')) out.ema50 = toLine(candles, ema(cl, 50));
  if (enabled.includes('bb20')) {
    const bb = bollinger(cl, 20, 2);
    out.bbUpper = toLine(candles, bb.map((p) => p?.upper ?? null));
    out.bbMiddle = toLine(candles, bb.map((p) => p?.middle ?? null));
    out.bbLower = toLine(candles, bb.map((p) => p?.lower ?? null));
  }
  if (enabled.includes('rsi14')) out.rsi14 = toLine(candles, rsi(cl, 14));
  return out;
}
