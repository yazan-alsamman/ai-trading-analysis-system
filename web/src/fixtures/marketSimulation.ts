/**
 * SIMULATED market data for demo mode.
 *
 * Prices come from a seeded random walk (geometric Brownian motion with a
 * slowly varying drift and session-dependent volatility). They are NOT real
 * quotes and are always labelled as simulated in the UI.
 */
import type { InstrumentSymbol } from '@/domain/instruments';
import { bucketStart, isFxMarketOpen, timeframeSeconds, type Candle, type Timeframe } from '@/domain/market';
import { createRandom, gaussian, hashSeed } from '@/lib/random';

interface SimulationProfile {
  /** Starting level of the simulated walk (illustrative only). */
  start: number;
  /** Approximate daily volatility as a fraction of price. */
  dailyVol: number;
  /** Typical tick volume per 15-minute bar. */
  baseVolume: number;
}

const PROFILES: Record<InstrumentSymbol, SimulationProfile> = {
  EURUSD: { start: 1.085, dailyVol: 0.0045, baseVolume: 1800 },
  GBPUSD: { start: 1.27, dailyVol: 0.0055, baseVolume: 1600 },
  USDJPY: { start: 149.5, dailyVol: 0.006, baseVolume: 1700 },
  USDCHF: { start: 0.885, dailyVol: 0.005, baseVolume: 900 },
  AUDUSD: { start: 0.66, dailyVol: 0.0065, baseVolume: 1100 },
  USDCAD: { start: 1.36, dailyVol: 0.0045, baseVolume: 1000 },
  NZDUSD: { start: 0.605, dailyVol: 0.0065, baseVolume: 700 },
  XAUUSD: { start: 2350, dailyVol: 0.01, baseVolume: 2600 },
};

export const BASE_TIMEFRAME: Timeframe = '15m';
const BASE_SECONDS = timeframeSeconds(BASE_TIMEFRAME);
const BARS_PER_DAY = 96;
const SUBSTEPS = 6;

/** Relative activity by UTC hour: Asian session quieter, London/NY overlap busiest. */
export function sessionActivity(epochSeconds: number): number {
  const hour = new Date(epochSeconds * 1000).getUTCHours();
  if (hour >= 12 && hour < 16) return 1.35; // London / New York overlap
  if (hour >= 7 && hour < 12) return 1.15; // London
  if (hour >= 16 && hour < 21) return 1.0; // New York
  return 0.7; // Asian / late
}

export function sessionName(epochSeconds: number): string {
  const hour = new Date(epochSeconds * 1000).getUTCHours();
  if (hour >= 12 && hour < 16) return 'London / New York overlap';
  if (hour >= 7 && hour < 12) return 'London session';
  if (hour >= 16 && hour < 21) return 'New York session';
  return 'Asian session';
}

/** Open times of the last `count` 15m bars during market hours, ending at or before `endSeconds`. */
export function openBarTimes(endSeconds: number, count: number): number[] {
  const times: number[] = [];
  let t = bucketStart(endSeconds, BASE_TIMEFRAME);
  // Hard stop prevents an infinite loop on bad input.
  for (let guard = 0; times.length < count && guard < count * 3; guard++) {
    if (isFxMarketOpen(t)) times.push(t);
    t -= BASE_SECONDS;
  }
  return times.reverse();
}

export interface SimulationState {
  price: number;
  drift: number;
  random: () => number;
  profile: SimulationProfile;
}

export function createSimulationState(symbol: InstrumentSymbol): SimulationState {
  const profile = PROFILES[symbol];
  return { price: profile.start, drift: 0, random: createRandom(hashSeed(`ata-demo-${symbol}`)), profile };
}

/** Advance the walk by one sub-step and return the new price. */
export function stepPrice(state: SimulationState, epochSeconds: number, stepsPerBar = SUBSTEPS): number {
  const sigma = (state.profile.dailyVol / Math.sqrt(BARS_PER_DAY * stepsPerBar)) * sessionActivity(epochSeconds);
  // Drift is a slow AR(1) process → visible trends and ranges.
  state.drift = state.drift * 0.995 + gaussian(state.random) * sigma * 0.02;
  // Gentle pull towards the start level keeps long runs within a plausible band.
  const pull = (Math.log(state.profile.start) - Math.log(state.price)) * 0.0004;
  state.price *= Math.exp(state.drift + pull + gaussian(state.random) * sigma);
  return state.price;
}

export function simulateBar(state: SimulationState, time: number): Candle {
  const open = state.price;
  let high = open;
  let low = open;
  for (let s = 0; s < SUBSTEPS; s++) {
    const p = stepPrice(state, time);
    high = Math.max(high, p);
    low = Math.min(low, p);
  }
  const close = state.price;
  const move = Math.abs(close - open) / open / (state.profile.dailyVol / Math.sqrt(BARS_PER_DAY));
  const volume = Math.round(
    state.profile.baseVolume * sessionActivity(time) * (0.6 + state.random() * 0.8) * (1 + Math.min(move, 3) * 0.25),
  );
  return { time, open, high, low, close, volume };
}

/** Generate `count` simulated 15m candles ending at the bar containing `endSeconds`. */
export function generateHistory(state: SimulationState, endSeconds: number, count: number): Candle[] {
  return openBarTimes(endSeconds, count).map((t) => simulateBar(state, t));
}

/** Aggregate 15m candles into a higher timeframe. */
export function aggregate(candles: readonly Candle[], timeframe: Timeframe): Candle[] {
  if (timeframe === BASE_TIMEFRAME) return candles.map((c) => ({ ...c }));
  const out: Candle[] = [];
  for (const c of candles) {
    const bucket = bucketStart(c.time, timeframe);
    const last = out[out.length - 1];
    if (last && last.time === bucket) {
      last.high = Math.max(last.high, c.high);
      last.low = Math.min(last.low, c.low);
      last.close = c.close;
      last.volume += c.volume;
    } else {
      out.push({ ...c, time: bucket });
    }
  }
  return out;
}
