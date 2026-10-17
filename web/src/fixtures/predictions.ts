/**
 * SIMULATED prediction history for demo mode (SF14 / SF15).
 * Outcomes are random draws — these numbers say nothing about the real model.
 */
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';
import { TIMEFRAMES, timeframeSeconds } from '@/domain/market';
import type { PredictionOutcome, PredictionRecord } from '@/domain/predictions';
import { createRandom } from '@/lib/random';
import { DEMO_MODEL_VERSION } from './opportunities';

const pick = <T>(items: readonly T[], r: number): T => items[Math.floor(r * items.length) % items.length] as T;

export function buildDemoPredictionHistory(nowMs: number, count = 180): PredictionRecord[] {
  const random = createRandom(20261015);
  const spanMs = 30 * 24 * 3600 * 1000;
  const records: PredictionRecord[] = [];

  for (let i = 0; i < count; i++) {
    const symbol = pick(INSTRUMENT_SYMBOLS, random());
    const timeframe = pick(TIMEFRAMES, random()).id;
    const direction = random() > 0.5 ? 'long' : 'short';
    const probability = Number((0.52 + random() * 0.3).toFixed(3));
    const generatedAt = Math.round(nowMs - random() * spanMs);
    const horizonMs = timeframeSeconds(timeframe) * 20 * 1000;
    const riskReward = 2;

    let outcome: PredictionOutcome;
    let realizedR: number | undefined;
    let resolvedAt: number | undefined;
    if (generatedAt + horizonMs > nowMs && random() < 0.7) {
      outcome = 'open';
    } else {
      // Simulated model is slightly over-confident (hit rate ≈ 0.9 × p).
      const r = random();
      outcome = r < probability * 0.9 ? 'tp_hit' : r < 0.93 ? 'sl_hit' : 'expired';
      realizedR = outcome === 'tp_hit' ? riskReward : outcome === 'sl_hit' ? -1 : Number((random() * 1.4 - 0.6).toFixed(2));
      resolvedAt = Math.min(nowMs, generatedAt + Math.round(random() * horizonMs));
    }

    records.push({
      id: `demo-pred-${i.toString().padStart(4, '0')}`,
      symbol,
      timeframe,
      direction,
      probability,
      riskReward,
      generatedAt,
      ...(resolvedAt !== undefined ? { resolvedAt } : {}),
      outcome,
      ...(realizedR !== undefined ? { realizedR } : {}),
      requestedByUser: random() < 0.3,
      modelVersion: DEMO_MODEL_VERSION,
      provenance: 'demo',
    });
  }
  return records.sort((a, b) => b.generatedAt - a.generatedAt);
}
