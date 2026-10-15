import { INSTRUMENT_SYMBOLS, type InstrumentSymbol } from './instruments';
import type { Provenance, Timeframe } from './market';

/**
 * Output of AI Feature 12 — "Predicting high-probability trading opportunities".
 * Field names follow the feature specification (§1 Core idea, §2.3 Outputs).
 * The backend contract is not final; see docs/API_INTEGRATION.md.
 */

export type Direction = 'long' | 'short' | 'neutral';
export type OpportunityStatus = 'detected' | 'not_detected';
/** Strategy profiles listed in spec §2.1. */
export type SetupType = 'trend_following' | 'mean_reversion' | 'breakout' | 'scalping';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface PriceZone {
  low: number;
  high: number;
}

/** One contributing signal (SHAP attribution turned into text). */
export interface ExplanationFactor {
  id: string;
  label: string;
  detail: string;
  /** Signed weight; positive supports the stated direction, negative opposes it. */
  contribution: number;
}

export interface ForecastPoint {
  /** Epoch seconds, aligned to the timeframe grid, strictly after the signal candle. */
  time: number;
  value: number;
}

export interface Opportunity {
  id: string;
  symbol: InstrumentSymbol;
  timeframe: Timeframe;
  status: OpportunityStatus;
  direction: Direction;
  setupType: SetupType;
  riskLevel: RiskLevel;
  /** Probability (0–1) that TP is reached before SL within the horizon. */
  probability: number;
  /** Only present when the model provides one. Never synthesised by the UI. */
  confidenceBand?: { low: number; high: number };
  entryZone: PriceZone;
  stopLossZone: PriceZone;
  takeProfitZone: PriceZone;
  /** Reward-to-risk multiple, e.g. 2 means 1:2. */
  riskReward: number;
  /** Expected value in R (multiples of the amount risked). */
  expectedValueR?: number;
  /** Top contributing signals (spec: top 5). */
  factors: ExplanationFactor[];
  /** Optional projected path. Only rendered when the model supplies it. */
  forecast?: ForecastPoint[];
  /** Max holding period in candles (spec §3.4). */
  horizonCandles: number;
  /** Open time (epoch s) of the candle the signal was computed on. */
  signalCandleTime: number;
  /** When the analysis was produced (epoch ms). */
  generatedAt: number;
  /** After this time (epoch ms) the analysis is considered stale. */
  validUntil: number;
  modelVersion: string;
  provenance: Provenance;
}

export const SETUP_LABELS: Record<SetupType, string> = {
  trend_following: 'Trend following',
  mean_reversion: 'Mean reversion',
  breakout: 'Breakout',
  scalping: 'Scalping',
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

export function zoneMid(zone: PriceZone): number {
  return (zone.low + zone.high) / 2;
}

/** EV in R for a binary TP/SL outcome: p·RR − (1−p)·1. */
export function expectedValueInR(probability: number, riskReward: number): number {
  return probability * riskReward - (1 - probability);
}

export function isOpportunityStale(opportunity: Opportunity, nowMs: number): boolean {
  return nowMs > opportunity.validUntil;
}

/** How many timeframes agree on the dominant detected direction. */
export function confluenceSummary(items: readonly Opportunity[]): { agree: number; direction: Direction | null } {
  const dirs = items.filter((o) => o.status === 'detected').map((o) => o.direction);
  const longs = dirs.filter((d) => d === 'long').length;
  const shorts = dirs.filter((d) => d === 'short').length;
  if (longs === 0 && shorts === 0) return { agree: 0, direction: null };
  return longs >= shorts ? { agree: longs, direction: 'long' } : { agree: shorts, direction: 'short' };
}

/** Pairs whose 15m, 1h and 4h analyses all detect the same direction. */
export function alignedPairs(items: readonly Opportunity[]): { symbol: InstrumentSymbol; direction: Direction }[] {
  return INSTRUMENT_SYMBOLS.flatMap((symbol) => {
    const own = items.filter((o) => o.symbol === symbol);
    if (own.length < 3 || own.some((o) => o.status !== 'detected')) return [];
    const dirs = new Set(own.map((o) => o.direction));
    return dirs.size === 1 ? [{ symbol, direction: own[0]?.direction ?? 'neutral' }] : [];
  });
}
