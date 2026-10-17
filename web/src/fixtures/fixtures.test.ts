import { describe, expect, it } from 'vitest';
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';
import { isFxMarketOpen, TIMEFRAMES, timeframeSeconds } from '@/domain/market';
import { zoneMid } from '@/domain/opportunity';
import { aggregate, createSimulationState, generateHistory } from './marketSimulation';
import { buildDemoOpportunity } from './opportunities';
import { buildDemoPredictionHistory } from './predictions';

const END = Date.parse('2026-10-15T12:07:00Z') / 1000;

describe('simulated market data', () => {
  const candles = generateHistory(createSimulationState('EURUSD'), END, 2000);

  it('is deterministic for the same seed', () => {
    const again = generateHistory(createSimulationState('EURUSD'), END, 2000);
    expect(again).toEqual(candles);
  });

  it('produces valid, ordered OHLC bars only during market hours', () => {
    for (let i = 0; i < candles.length; i++) {
      const c = candles[i]!;
      expect(c.high).toBeGreaterThanOrEqual(Math.max(c.open, c.close));
      expect(c.low).toBeLessThanOrEqual(Math.min(c.open, c.close));
      expect(isFxMarketOpen(c.time)).toBe(true);
      if (i > 0) expect(c.time).toBeGreaterThan(candles[i - 1]!.time);
    }
  });

  it('aggregates to higher timeframes consistently', () => {
    const h4 = aggregate(candles, '4h');
    expect(h4.length).toBeLessThan(candles.length / 15);
    expect(h4[h4.length - 1]!.close).toBe(candles[candles.length - 1]!.close);
    for (const c of h4) expect(c.time % timeframeSeconds('4h')).toBe(0);
  });
});

describe('simulated opportunities', () => {
  it('always follows the Feature 12 shape and labels itself as demo', () => {
    for (const symbol of INSTRUMENT_SYMBOLS) {
      for (const { id: tf } of TIMEFRAMES) {
        const candles = aggregate(generateHistory(createSimulationState(symbol), END, 3000), tf);
        const o = buildDemoOpportunity(symbol, tf, candles);
        expect(o.provenance).toBe('demo');
        expect(o.probability).toBeGreaterThanOrEqual(0);
        expect(o.probability).toBeLessThanOrEqual(1);
        expect(o.factors).toHaveLength(5);
        expect(o.validUntil).toBeGreaterThan(o.generatedAt);
        if (o.status === 'detected') {
          const sign = o.direction === 'long' ? 1 : -1;
          // TP beyond entry beyond SL in the trade direction.
          expect(sign * (zoneMid(o.takeProfitZone) - zoneMid(o.entryZone))).toBeGreaterThan(0);
          expect(sign * (zoneMid(o.entryZone) - zoneMid(o.stopLossZone))).toBeGreaterThan(0);
          expect(o.confidenceBand!.low).toBeLessThanOrEqual(o.probability);
          expect(o.confidenceBand!.high).toBeGreaterThanOrEqual(o.probability);
          // Forecast starts at the forming (last) candle — never inside history.
          expect(o.forecast?.[0]?.time).toBe(candles[candles.length - 1]!.time);
        } else {
          expect(o.direction).toBe('neutral');
          expect(o.forecast).toBeUndefined();
        }
      }
    }
  });
});

describe('simulated prediction history', () => {
  it('is labelled demo and only resolved records carry results', () => {
    const records = buildDemoPredictionHistory(END * 1000);
    expect(records.length).toBeGreaterThan(100);
    for (const r of records) {
      expect(r.provenance).toBe('demo');
      if (r.outcome === 'open') expect(r.realizedR).toBeUndefined();
      else expect(r.realizedR).toBeDefined();
    }
  });
});
