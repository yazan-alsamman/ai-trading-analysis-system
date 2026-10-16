import { EMPTY_CONTEXT, type AssistantReply } from '@/domain/assistant';
import { getInstrument } from '@/domain/instruments';
import type { Candle } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import { computePredictionStats, type PredictionStats } from '@/domain/predictions';
import { invalidationNotes, missingNotes, type ResearchNote } from '@/domain/research';
import { computeTradeRisk, DEFAULT_RISK_PROFILE, planFromOpportunity, type RiskProfile, type TradeRisk } from '@/domain/risk';
import { DEFAULT_SIGNAL_PROFILE, evaluateSignal, type SignalEvaluation } from '@/domain/signalProfile';
import { aggregate, createSimulationState, generateHistory } from '@/fixtures/marketSimulation';
import { buildDemoOpportunity } from '@/fixtures/opportunities';
import { buildDemoPredictionHistory } from '@/fixtures/predictions';
import { formatPrice } from '@/lib/format';
import { composeReply } from '@/services/demo/assistant';

/**
 * The public website's product demonstration data.
 *
 * Everything here is produced by the SAME simulated fixtures and domain code
 * the application uses in demo mode, at a fixed point in time, so every
 * visitor sees the same, reproducible example. It is SIMULATED — never live
 * market data and never the trained model — and the UI labels it so.
 */

/** 14 Oct 2026 14:00 UTC: the fixtures produce a detected XAU/USD 1h setup with a projection here. */
export const SHOWCASE_ANCHOR = 1_791_986_400;
export const SHOWCASE_SYMBOL = 'XAUUSD' as const;
export const SHOWCASE_TIMEFRAME = '1h' as const;

/** Illustrative account used only for the demonstration (not a recommendation). */
export const SHOWCASE_PROFILE: RiskProfile = {
  ...DEFAULT_RISK_PROFILE,
  capital: 25_000,
  currency: 'USD',
  openRisk: 0,
  realisedLossToday: 0,
  openPositions: 0,
  contractSizes: {},
  volumeStep: null,
};

export interface Showcase {
  candles: Candle[];
  opportunity: Opportunity;
  plan: { entry: number; stop: number; target: number };
  risk: TradeRisk;
  evaluation: SignalEvaluation;
  stats: PredictionStats;
  invalidation: ResearchNote[];
  missing: ResearchNote[];
  assistant: AssistantReply;
}

let cached: Showcase | null = null;

export function buildShowcase(): Showcase {
  if (cached) return cached;
  const inst = getInstrument(SHOWCASE_SYMBOL);
  const all = aggregate(generateHistory(createSimulationState(SHOWCASE_SYMBOL), SHOWCASE_ANCHOR, 96 * 10), SHOWCASE_TIMEFRAME);
  const opportunity = buildDemoOpportunity(SHOWCASE_SYMBOL, SHOWCASE_TIMEFRAME, all);
  const plan = planFromOpportunity(opportunity);
  if (!plan) throw new Error('Showcase anchor no longer yields a setup — update SHOWCASE_ANCHOR.');
  const sized = computeTradeRisk(SHOWCASE_PROFILE, { instrument: inst, ...plan, riskPct: 1, quoteToAccountRate: null });
  if (sized.kind !== 'ok') throw new Error('Showcase plan could not be sized.');
  const now = opportunity.generatedAt;
  const stats = computePredictionStats(buildDemoPredictionHistory(now));
  const context = { ...EMPTY_CONTEXT, symbol: SHOWCASE_SYMBOL, timeframe: SHOWCASE_TIMEFRAME, lastPrice: all[all.length - 1]?.close ?? null, priceProvenance: 'demo' as const, opportunity, confluence: [opportunity] };
  cached = {
    // The last candle is still forming; the chart shows the closed history up to the signal.
    candles: all.slice(-61, -1),
    opportunity,
    plan,
    risk: sized.risk,
    evaluation: evaluateSignal(opportunity, DEFAULT_SIGNAL_PROFILE, SHOWCASE_PROFILE, now),
    stats,
    invalidation: invalidationNotes(opportunity, [], now, (v) => formatPrice(v, inst.pricePrecision)),
    missing: missingNotes({ opportunity, priceProvenance: 'demo', feedStatus: 'demo', confluenceCount: 1, symbol: SHOWCASE_SYMBOL, nowMs: now }),
    assistant: composeReply('What would invalidate this projection?', context, now),
  };
  return cached;
}
