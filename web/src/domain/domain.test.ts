import { describe, expect, it } from 'vitest';
import { getInstrument, INSTRUMENTS, matchesInstrument } from './instruments';
import { bucketStart, isFxMarketOpen } from './market';
import { expectedValueInR, isOpportunityStale, zoneMid, type Opportunity } from './opportunity';
import { computePredictionStats, predictionError, type PredictionRecord } from './predictions';

describe('instruments', () => {
  it('covers exactly the eight instruments from the Feature 12 spec', () => {
    expect(INSTRUMENTS.map((i) => i.symbol)).toEqual(['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'XAUUSD']);
  });

  it('uses JPY and gold conventions', () => {
    expect(getInstrument('USDJPY')).toMatchObject({ pricePrecision: 3, pipSize: 0.01, display: 'USD/JPY' });
    expect(getInstrument('XAUUSD')).toMatchObject({ pricePrecision: 2, kind: 'metal' });
  });

  it('matches by symbol with or without slash, and by name', () => {
    const eur = getInstrument('EURUSD');
    expect(matchesInstrument(eur, 'eur/usd')).toBe(true);
    expect(matchesInstrument(eur, 'EURU')).toBe(true);
    expect(matchesInstrument(eur, 'euro')).toBe(true);
    expect(matchesInstrument(eur, 'gold')).toBe(false);
  });
});

describe('market calendar', () => {
  it('is closed from Friday 22:00 to Sunday 22:00 UTC', () => {
    const at = (iso: string) => Date.parse(iso) / 1000;
    expect(isFxMarketOpen(at('2026-10-16T21:59:00Z'))).toBe(true); // Friday
    expect(isFxMarketOpen(at('2026-10-16T22:00:00Z'))).toBe(false);
    expect(isFxMarketOpen(at('2026-10-17T12:00:00Z'))).toBe(false); // Saturday
    expect(isFxMarketOpen(at('2026-10-18T21:59:00Z'))).toBe(false); // Sunday
    expect(isFxMarketOpen(at('2026-10-18T22:00:00Z'))).toBe(true);
  });

  it('floors timestamps to the timeframe bucket', () => {
    const t = Date.parse('2026-10-15T14:37:12Z') / 1000;
    expect(new Date(bucketStart(t, '15m') * 1000).toISOString()).toBe('2026-10-15T14:30:00.000Z');
    expect(new Date(bucketStart(t, '4h') * 1000).toISOString()).toBe('2026-10-15T12:00:00.000Z');
  });
});

describe('opportunity maths', () => {
  it('computes EV in R as p·RR − (1−p)', () => {
    expect(expectedValueInR(0.5, 2)).toBeCloseTo(0.5);
    expect(expectedValueInR(1 / 3, 2)).toBeCloseTo(0);
    expect(expectedValueInR(0.25, 2)).toBeCloseTo(-0.25);
  });

  it('reports staleness after validUntil', () => {
    const opp = { validUntil: 1000 } as Opportunity;
    expect(isOpportunityStale(opp, 999)).toBe(false);
    expect(isOpportunityStale(opp, 1001)).toBe(true);
    expect(zoneMid({ low: 1, high: 2 })).toBe(1.5);
  });
});

describe('prediction statistics', () => {
  const rec = (probability: number, outcome: PredictionRecord['outcome'], realizedR?: number): PredictionRecord => ({
    id: Math.random().toString(),
    symbol: 'EURUSD',
    timeframe: '15m',
    direction: 'long',
    probability,
    riskReward: 2,
    generatedAt: 0,
    outcome,
    ...(realizedR !== undefined ? { realizedR } : {}),
    requestedByUser: false,
    modelVersion: 't',
    provenance: 'demo',
  });

  it('computes hit rate, Brier score and mean R over resolved predictions only', () => {
    const stats = computePredictionStats([rec(0.8, 'tp_hit', 2), rec(0.6, 'sl_hit', -1), rec(0.7, 'open')]);
    expect(stats).toMatchObject({ total: 3, resolved: 2, open: 1 });
    expect(stats.hitRate).toBeCloseTo(0.5);
    expect(stats.meanPredicted).toBeCloseTo(0.7);
    expect(stats.brierScore).toBeCloseTo(((0.8 - 1) ** 2 + 0.6 ** 2) / 2);
    expect(stats.meanRealizedR).toBeCloseTo(0.5);
  });

  it('returns nulls, not zeros, when nothing is resolved', () => {
    const stats = computePredictionStats([rec(0.7, 'open')]);
    expect(stats.hitRate).toBeNull();
    expect(stats.brierScore).toBeNull();
    expect(stats.calibration).toEqual([]);
  });

  it('bins calibration without floating-point gaps (0.7 lands in 70–80%)', () => {
    const stats = computePredictionStats([rec(0.7, 'tp_hit'), rec(0.79, 'sl_hit'), rec(1, 'tp_hit')]);
    const bin = stats.calibration.find((b) => b.from === 0.7);
    expect(bin?.count).toBe(2);
    expect(stats.calibration.find((b) => b.from === 0.9)?.count).toBe(1);
  });

  it('gives a per-prediction squared error', () => {
    expect(predictionError(rec(0.7, 'tp_hit'))).toBeCloseTo(0.09);
    expect(predictionError(rec(0.7, 'expired'))).toBeCloseTo(0.49);
    expect(predictionError(rec(0.7, 'open'))).toBeNull();
  });
});
