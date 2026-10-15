/**
 * SIMULATED AI opportunities for demo mode.
 *
 * Produced by a transparent heuristic over the simulated candles (EMA trend,
 * RSI, Bollinger position, ATR). This is NOT the project's model: probabilities,
 * bands and explanations are placeholders that demonstrate the Feature 12
 * output shape, and the UI labels them as simulated.
 */
import { getInstrument, type InstrumentSymbol } from '@/domain/instruments';
import { timeframeSeconds, type Candle, type Timeframe } from '@/domain/market';
import {
  expectedValueInR,
  type ExplanationFactor,
  type ForecastPoint,
  type Opportunity,
  type RiskLevel,
  type SetupType,
} from '@/domain/opportunity';
import { atr, bollinger, closes, ema, rsi } from '@/lib/indicators';
import { createRandom, hashSeed } from '@/lib/random';
import { sessionName } from './marketSimulation';

export const DEMO_MODEL_VERSION = 'demo-heuristic-0.1';
const HORIZON_CANDLES = 20; // spec §3.4: e.g. 20 candles on 15m
const RISK_REWARD = 2; // spec §3.4: fixed 1:2

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)] ?? 0;
}

/**
 * @param candles full series; the LAST candle is still forming, so the signal is
 *                computed on the previous (closed) candle.
 */
export function buildDemoOpportunity(symbol: InstrumentSymbol, timeframe: Timeframe, candles: readonly Candle[]): Opportunity {
  const instrument = getInstrument(symbol);
  const tfSeconds = timeframeSeconds(timeframe);
  const closed = candles.slice(0, -1);
  const signal = closed[closed.length - 1];
  const forming = candles[candles.length - 1];
  if (!signal || !forming || closed.length < 60) {
    throw new Error('Not enough simulated history to build an opportunity');
  }

  const cl = closes(closed);
  const i = closed.length - 1;
  const ema20 = ema(cl, 20)[i] ?? signal.close;
  const ema50 = ema(cl, 50)[i] ?? signal.close;
  const rsiNow = rsi(cl, 14)[i] ?? 50;
  const bb = bollinger(cl, 20, 2)[i];
  const atrSeries = atr(closed, 14);
  const atrNow = atrSeries[i] ?? signal.high - signal.low;
  const atrMedian = median(atrSeries.slice(-60).filter((v): v is number => v !== null));
  const volRatio = atrMedian > 0 ? atrNow / atrMedian : 1;

  const trendStrength = (ema20 - ema50) / atrNow; // in ATR units
  const random = createRandom(hashSeed(`${symbol}-${timeframe}-${signal.time}`));
  const detected = Math.abs(trendStrength) >= 0.6;
  const direction = !detected ? 'neutral' : trendStrength > 0 ? 'long' : 'short';
  const sign = direction === 'short' ? -1 : 1;

  const probability = detected
    ? clamp(0.54 + Math.min(Math.abs(trendStrength), 2) * 0.08 + random() * 0.06, 0.52, 0.82)
    : clamp(0.42 + random() * 0.08, 0.35, 0.5);
  const halfBand = 0.05 + random() * 0.03;

  const bbWidth = bb ? (bb.upper - bb.lower) / atrNow : 4;
  const setupType: SetupType = Math.abs(trendStrength) > 1.2 ? 'trend_following' : bbWidth < 3 ? 'breakout' : 'mean_reversion';
  const riskLevel: RiskLevel = volRatio > 1.3 ? 'high' : volRatio < 0.8 ? 'low' : 'medium';

  const entry = signal.close;
  const zone = (mid: number, half: number) => ({ low: mid - half, high: mid + half });
  const entryZone = zone(entry, atrNow * 0.15);
  const stopLossZone = zone(entry - sign * atrNow * 1.5, atrNow * 0.1);
  const takeProfitZone = zone(entry + sign * atrNow * 1.5 * RISK_REWARD, atrNow * 0.1);

  const factors: ExplanationFactor[] = [
    {
      id: 'trend',
      label: ema20 >= ema50 ? 'EMA 20 above EMA 50' : 'EMA 20 below EMA 50',
      detail: `Moving-average spread of ${Math.abs(trendStrength).toFixed(2)} ATR on ${timeframe}.`,
      contribution: sign * clamp(trendStrength * 0.18, -0.35, 0.35),
    },
    {
      id: 'rsi',
      label: `RSI 14 at ${rsiNow.toFixed(0)}`,
      detail: rsiNow > 70 ? 'Overbought territory.' : rsiNow < 30 ? 'Oversold territory.' : 'Momentum within normal range.',
      contribution: sign * clamp((rsiNow - 50) / 100, -0.2, 0.2) - (rsiNow > 70 || rsiNow < 30 ? sign * 0.08 : 0),
    },
    {
      id: 'bollinger',
      label: bb && signal.close > bb.middle ? 'Close above Bollinger midline' : 'Close below Bollinger midline',
      detail: bb ? `Band width ${bbWidth.toFixed(1)} ATR.` : 'Insufficient history for bands.',
      contribution: bb ? sign * clamp(((signal.close - bb.middle) / atrNow) * 0.1, -0.15, 0.15) : 0,
    },
    {
      id: 'volatility',
      label: `Volatility ${volRatio.toFixed(2)}× its recent median`,
      detail: volRatio > 1.3 ? 'Elevated volatility widens stop distance.' : 'Volatility in a tradable range.',
      contribution: volRatio > 1.3 ? -0.09 : 0.05,
    },
    {
      id: 'session',
      label: sessionName(forming.time),
      detail: 'Session liquidity affects follow-through.',
      contribution: sessionName(forming.time).includes('Asian') ? -0.04 : 0.06,
    },
  ].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

  // Illustrative projected path from the forming candle toward (part of) the target.
  const forecast: ForecastPoint[] = detected
    ? Array.from({ length: 9 }, (_, k) => {
        const progress = k === 0 ? 0 : (1 - Math.exp(-k / 4)) * 0.55;
        const wobble = k === 0 ? 0 : Math.sin(k * 1.7) * atrNow * 0.12;
        const target = (takeProfitZone.low + takeProfitZone.high) / 2;
        return { time: forming.time + k * tfSeconds, value: forming.close + (target - forming.close) * progress + wobble };
      })
    : [];

  const generatedAt = (signal.time + tfSeconds) * 1000 + 4_000;
  return {
    id: `demo-${symbol}-${timeframe}-${signal.time}`,
    symbol,
    timeframe,
    status: detected ? 'detected' : 'not_detected',
    direction,
    setupType,
    riskLevel,
    probability: Number(probability.toFixed(3)),
    confidenceBand: {
      low: Number(clamp(probability - halfBand, 0, 1).toFixed(3)),
      high: Number(clamp(probability + halfBand, 0, 1).toFixed(3)),
    },
    entryZone: roundZone(entryZone, instrument.pricePrecision),
    stopLossZone: roundZone(stopLossZone, instrument.pricePrecision),
    takeProfitZone: roundZone(takeProfitZone, instrument.pricePrecision),
    riskReward: RISK_REWARD,
    expectedValueR: Number(expectedValueInR(probability, RISK_REWARD).toFixed(3)),
    factors,
    ...(forecast.length ? { forecast } : {}),
    horizonCandles: HORIZON_CANDLES,
    signalCandleTime: signal.time,
    generatedAt,
    // Valid until the forming candle closes plus one more candle.
    validUntil: generatedAt + tfSeconds * 2 * 1000,
    modelVersion: DEMO_MODEL_VERSION,
    provenance: 'demo',
  };
}

function roundZone(z: { low: number; high: number }, precision: number) {
  return { low: Number(z.low.toFixed(precision)), high: Number(z.high.toFixed(precision)) };
}
