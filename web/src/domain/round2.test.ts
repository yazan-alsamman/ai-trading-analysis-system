import { describe, expect, it } from 'vitest';
import { crossesLevel } from './alertRules';
import { alignedPairs, confluenceSummary, type Opportunity } from './opportunity';
import { sessionStates, sessionSummary } from './sessions';

describe('price alert crossing', () => {
  const above = { condition: 'crosses_above' as const, price: 1.1 };
  const below = { condition: 'crosses_below' as const, price: 1.1 };

  it('fires when price moves through or onto the level in the alert direction', () => {
    expect(crossesLevel(above, 1.0999, 1.1001)).toBe(true);
    expect(crossesLevel(above, 1.0999, 1.1)).toBe(true);
    expect(crossesLevel(below, 1.1001, 1.0999)).toBe(true);
  });

  it('does not fire when already beyond the level or moving the other way', () => {
    expect(crossesLevel(above, 1.1001, 1.1002)).toBe(false);
    expect(crossesLevel(above, 1.1001, 1.0999)).toBe(false);
    expect(crossesLevel(below, 1.0999, 1.1001)).toBe(false);
  });
});

describe('FX sessions', () => {
  const at = (iso: string) => Date.parse(iso);

  it('reports London/New York overlap mid-afternoon UTC on a weekday', () => {
    expect(sessionSummary(at('2026-10-15T14:00:00Z'))).toBe('London · New York overlap');
  });

  it('handles the Sydney session wrapping past midnight', () => {
    const open = sessionStates(at('2026-10-15T23:00:00Z')).filter((s) => s.open).map((s) => s.id);
    expect(open).toEqual(['sydney']);
  });

  it('is closed at the weekend', () => {
    expect(sessionSummary(at('2026-10-17T12:00:00Z'))).toBe('Market closed (weekend)');
    expect(sessionStates(at('2026-10-17T12:00:00Z')).some((s) => s.open)).toBe(false);
  });
});

describe('timeframe alignment', () => {
  const o = (symbol: Opportunity['symbol'], timeframe: Opportunity['timeframe'], direction: Opportunity['direction'], status: Opportunity['status'] = 'detected') =>
    ({ symbol, timeframe, direction, status }) as Opportunity;

  it('counts agreement on the dominant direction', () => {
    expect(confluenceSummary([o('EURUSD', '15m', 'long'), o('EURUSD', '1h', 'short'), o('EURUSD', '4h', 'short')])).toEqual({ agree: 2, direction: 'short' });
    expect(confluenceSummary([o('EURUSD', '15m', 'neutral', 'not_detected')])).toEqual({ agree: 0, direction: null });
  });

  it('lists only pairs where all three timeframes detect the same direction', () => {
    const items = [
      o('EURUSD', '15m', 'long'),
      o('EURUSD', '1h', 'long'),
      o('EURUSD', '4h', 'long'),
      o('GBPUSD', '15m', 'short'),
      o('GBPUSD', '1h', 'short'),
      o('GBPUSD', '4h', 'neutral', 'not_detected'),
    ];
    expect(alignedPairs(items)).toEqual([{ symbol: 'EURUSD', direction: 'long' }]);
  });
});
