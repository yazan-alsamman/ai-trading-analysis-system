import type { InstrumentSymbol } from './instruments';
import type { Provenance, Timeframe } from './market';
import type { Direction } from './opportunity';

/** SF14 / SF15 — prediction history and evaluation. */

export type PredictionOutcome = 'tp_hit' | 'sl_hit' | 'expired' | 'open';

export const OUTCOME_LABELS: Record<PredictionOutcome, string> = {
  tp_hit: 'Target reached',
  sl_hit: 'Stop reached',
  expired: 'Expired',
  open: 'Open',
};

export interface PredictionRecord {
  id: string;
  symbol: InstrumentSymbol;
  timeframe: Timeframe;
  direction: Exclude<Direction, 'neutral'>;
  probability: number;
  riskReward: number;
  generatedAt: number;
  resolvedAt?: number;
  outcome: PredictionOutcome;
  /** Realised result in R once resolved (TP = +RR, SL = −1, expired = mark-to-market). */
  realizedR?: number;
  /** True when the current user explicitly requested this prediction (SF15). */
  requestedByUser: boolean;
  modelVersion: string;
  provenance: Provenance;
}

export interface CalibrationBin {
  /** Inclusive lower bound of the predicted-probability bin. */
  from: number;
  to: number;
  count: number;
  meanPredicted: number;
  /** Fraction of predictions in the bin whose target was reached. */
  observedRate: number;
}

export interface PredictionStats {
  total: number;
  resolved: number;
  open: number;
  /** Target reached ÷ resolved predictions. */
  hitRate: number | null;
  meanPredicted: number | null;
  /** Mean squared error of probability vs outcome (lower is better; 0.25 = coin flip at 50%). */
  brierScore: number | null;
  meanRealizedR: number | null;
  calibration: CalibrationBin[];
}

/** 1 when the target was reached, 0 for stop/expiry; null while open. */
export function outcomeValue(outcome: PredictionOutcome): 0 | 1 | null {
  if (outcome === 'open') return null;
  return outcome === 'tp_hit' ? 1 : 0;
}

/** Per-prediction Brier error: (p − y)². Null while the prediction is open. */
export function predictionError(record: PredictionRecord): number | null {
  const y = outcomeValue(record.outcome);
  return y === null ? null : (record.probability - y) ** 2;
}

const mean = (values: number[]): number | null =>
  values.length === 0 ? null : values.reduce((a, b) => a + b, 0) / values.length;

export function computePredictionStats(records: readonly PredictionRecord[], binWidth = 0.1): PredictionStats {
  const resolved = records.filter((r) => r.outcome !== 'open');
  const ys = resolved.map((r) => outcomeValue(r.outcome) ?? 0);

  const bins: CalibrationBin[] = [];
  const binCount = Math.round(1 / binWidth);
  for (let k = 0; k < binCount; k++) {
    // Integer arithmetic avoids floating drift (0.1 + 0.2 ≠ 0.3).
    const from = k / binCount;
    const to = (k + 1) / binCount;
    const isLast = k === binCount - 1;
    const inBin = resolved.filter((r) => r.probability >= from && (r.probability < to || (isLast && r.probability <= 1)));
    if (inBin.length === 0) continue;
    bins.push({
      from,
      to,
      count: inBin.length,
      meanPredicted: mean(inBin.map((r) => r.probability)) ?? 0,
      observedRate: mean(inBin.map((r) => outcomeValue(r.outcome) ?? 0)) ?? 0,
    });
  }

  return {
    total: records.length,
    resolved: resolved.length,
    open: records.length - resolved.length,
    hitRate: mean(ys),
    meanPredicted: mean(resolved.map((r) => r.probability)),
    brierScore: mean(resolved.map((r, i) => (r.probability - (ys[i] ?? 0)) ** 2)),
    meanRealizedR: mean(resolved.flatMap((r) => (r.realizedR === undefined ? [] : [r.realizedR]))),
    calibration: bins,
  };
}
