import { describe, expect, it } from 'vitest';
import { getInstrument } from './instruments';
import type { Opportunity } from './opportunity';
import {
  computeTradeRisk,
  DEFAULT_RISK_PROFILE,
  evaluateLimits,
  floorToStep,
  planFromOpportunity,
  remainingRiskCapacity,
  resolveConversion,
  validateRiskProfile,
  worstStatus,
  type RiskProfile,
  type TradePlanInput,
} from './risk';
import { DEFAULT_SIGNAL_PROFILE, evaluateSignal } from './signalProfile';

const profile = (patch: Partial<RiskProfile> = {}): RiskProfile => ({ ...DEFAULT_RISK_PROFILE, capital: 10_000, ...patch });
const plan = (symbol: Parameters<typeof getInstrument>[0], patch: Partial<TradePlanInput>): TradePlanInput => ({
  instrument: getInstrument(symbol),
  entry: null,
  stop: null,
  target: null,
  riskPct: 1,
  quoteToAccountRate: null,
  ...patch,
});

function ok(result: ReturnType<typeof computeTradeRisk>) {
  if (result.kind !== 'ok') throw new Error(`expected ok, got ${result.kind}: ${JSON.stringify(result.issues)}`);
  return result.risk;
}

describe('position sizing', () => {
  it('sizes gold in ounces on a USD account without any broker metadata', () => {
    const r = ok(computeTradeRisk(profile(), plan('XAUUSD', { entry: 2350, stop: 2340, target: 2370 })));
    expect(r.direction).toBe('long');
    expect(r.riskBudget).toBe(100);
    expect(r.units).toBeCloseTo(10, 10); // $100 / $10 per ounce
    expect(r.monetaryRisk).toBeCloseTo(100, 10);
    expect(r.potentialReward).toBeCloseTo(200, 10);
    expect(r.riskReward).toBeCloseTo(2, 10);
    expect(r.notional).toBeCloseTo(23_500, 6);
    expect(r.riskPctOfCapital).toBeCloseTo(1, 10);
    expect(r.lots).toBeNull();
    expect(r.conversion.method).toBe('same_currency');
  });

  it('shows lots only with a user-entered contract size, and rounds DOWN to the volume step', () => {
    const p = profile({ contractSizes: { XAUUSD: 100 }, volumeStep: 0.01 });
    const exact = ok(computeTradeRisk(p, plan('XAUUSD', { entry: 2350, stop: 2340 })));
    expect(exact.lots).toEqual({ contractSize: 100, exact: 0.1, rounded: 0.1, step: 0.01 });

    // $100 / $15 = 6.67 oz = 0.0667 lots → 0.06 lots → 6 oz → $90 at risk.
    const rounded = ok(computeTradeRisk(p, plan('XAUUSD', { entry: 2350, stop: 2335 })));
    expect(rounded.lots?.rounded).toBe(0.06);
    expect(rounded.units).toBeCloseTo(6, 10);
    expect(rounded.monetaryRisk).toBeCloseTo(90, 10);
    expect(rounded.riskPctOfCapital).toBeCloseTo(0.9, 10);
  });

  it('flags a risk budget smaller than one volume step', () => {
    const p = profile({ capital: 100, contractSizes: { XAUUSD: 100 }, volumeStep: 0.01 });
    const res = computeTradeRisk(p, plan('XAUUSD', { entry: 2350, stop: 2300 }));
    expect(res.kind).toBe('ok');
    if (res.kind === 'ok') {
      expect(res.risk.lots?.rounded).toBe(0);
      expect(res.risk.monetaryRisk).toBe(0);
      expect(res.notes.join(' ')).toMatch(/cannot be taken/);
    }
  });

  it('sizes EUR/USD in EUR units on a USD account', () => {
    const r = ok(computeTradeRisk(profile({ contractSizes: { EURUSD: 100_000 } }), plan('EURUSD', { entry: 1.1, stop: 1.095 })));
    expect(r.units).toBeCloseTo(20_000, 6); // $100 / 0.005
    expect(r.lots?.exact).toBeCloseTo(0.2, 10);
  });

  it('converts USD/JPY P/L to USD at the exit price (exact, no guessed rate)', () => {
    // Short: stop above entry. Loss at stop: units × 1 JPY ÷ 151 = $100 → units = 15,100.
    const r = ok(computeTradeRisk(profile(), plan('USDJPY', { entry: 150, stop: 151, target: 148 })));
    expect(r.direction).toBe('short');
    expect(r.conversion.method).toBe('base_is_account');
    expect(r.units).toBeCloseTo(15_100, 6);
    expect(r.monetaryRisk).toBeCloseTo(100, 8);
    expect(r.potentialReward).toBeCloseTo((15_100 * 2) / 148, 8);
    expect(r.riskReward).toBeCloseTo(2, 10);
  });

  it('requires a user rate when neither currency is the account currency', () => {
    const missing = computeTradeRisk(profile({ currency: 'EUR' }), plan('GBPUSD', { entry: 1.25, stop: 1.245 }));
    expect(missing.kind).toBe('incomplete');
    if (missing.kind !== 'ok') expect(missing.issues[0]?.field).toBe('conversion');

    const withRate = ok(computeTradeRisk(profile({ currency: 'EUR' }), plan('GBPUSD', { entry: 1.25, stop: 1.245, quoteToAccountRate: 0.92 })));
    expect(withRate.conversion.method).toBe('user_rate');
    expect(withRate.units).toBeCloseTo(100 / (0.005 * 0.92), 6);
  });

  it('names every missing input instead of computing a partial result', () => {
    const res = computeTradeRisk({ ...DEFAULT_RISK_PROFILE }, plan('XAUUSD', { riskPct: null }));
    expect(res.kind).toBe('incomplete');
    if (res.kind !== 'ok') expect(res.issues.map((i) => i.field)).toEqual(['capital', 'entry', 'stop', 'riskPct']);
  });

  it('rejects inconsistent plans', () => {
    const same = computeTradeRisk(profile(), plan('XAUUSD', { entry: 2350, stop: 2350 }));
    expect(same.kind).toBe('invalid');
    const wrongTarget = computeTradeRisk(profile(), plan('XAUUSD', { entry: 2350, stop: 2340, target: 2345 }));
    expect(wrongTarget.kind).toBe('invalid');
    if (wrongTarget.kind !== 'ok') expect(wrongTarget.issues[0]?.field).toBe('target');
    const tooMuch = computeTradeRisk(profile(), plan('XAUUSD', { entry: 2350, stop: 2340, riskPct: 150 }));
    expect(tooMuch.kind).toBe('invalid');
  });

  it('resolves conversions only from known facts', () => {
    expect(resolveConversion(getInstrument('XAUUSD'), 'USD', 2350, null)?.method).toBe('same_currency');
    expect(resolveConversion(getInstrument('XAUUSD'), 'EUR', 2350, null)).toBeNull();
    expect(resolveConversion(getInstrument('USDCHF'), 'USD', 0.9, null)?.method).toBe('base_is_account');
  });

  it('floors to the step without floating-point drift', () => {
    expect(floorToStep(0.3, 0.1)).toBe(0.3);
    expect(floorToStep(0.07, 0.01)).toBe(0.07);
    expect(floorToStep(0.299999, 0.01)).toBe(0.29);
    expect(floorToStep(1.23456, 0.001)).toBe(1.234);
  });
});

describe('risk limits', () => {
  const p = profile({ openRisk: 300, realisedLossToday: 100, openPositions: 2 });

  it('evaluates each limit for the worst case (the stop is hit)', () => {
    const checks = evaluateLimits(p, 100);
    const by = Object.fromEntries(checks.map((c) => [c.id, c]));
    expect(by.per_trade?.status).toBe('ok'); // exactly at 1 % is the intended size
    expect(by.daily_loss).toMatchObject({ used: 400, after: 500, limit: 300, status: 'breach', remaining: 0 });
    expect(by.open_risk).toMatchObject({ used: 300, after: 400, limit: 500, status: 'caution', remaining: 100 });
    expect(by.positions).toMatchObject({ used: 2, after: 3, limit: 3, status: 'caution' });
    expect(worstStatus(checks)).toBe('breach');
  });

  it('flags a per-trade breach when the trade risks more than the maximum', () => {
    const per = evaluateLimits(profile(), 150).find((c) => c.id === 'per_trade');
    expect(per?.status).toBe('breach');
  });

  it('reports the remaining permitted risk and the limit that binds', () => {
    expect(remainingRiskCapacity(profile())).toEqual({ money: 100, pctOfCapital: 1, binding: 'per_trade' });
    expect(remainingRiskCapacity(p)).toEqual({ money: 0, pctOfCapital: 0, binding: 'daily_loss' });
    // 3 % daily limit is already exceeded by 450 of open risk; with a 10 % daily limit the 5 % open-risk limit binds.
    expect(remainingRiskCapacity(profile({ openRisk: 450 }))).toMatchObject({ money: 0, binding: 'daily_loss' });
    expect(remainingRiskCapacity(profile({ openRisk: 450, dailyLossLimitPct: 10 }))).toMatchObject({ binding: 'open_risk' });
    expect(remainingRiskCapacity(profile({ openRisk: 450, dailyLossLimitPct: 10 }))?.money).toBeCloseTo(50, 10);
    expect(remainingRiskCapacity(profile({ openPositions: 3 }))?.binding).toBe('positions');
    expect(remainingRiskCapacity(DEFAULT_RISK_PROFILE)).toBeNull();
  });

  it('validates the profile', () => {
    expect(validateRiskProfile(profile())).toEqual({});
    const errors = validateRiskProfile(profile({ capital: -5, maxRiskPerTradePct: 6, maxOpenRiskPct: 5, maxOpenPositions: 0, openRisk: -1 }));
    expect(Object.keys(errors).sort()).toEqual(['capital', 'maxOpenPositions', 'maxRiskPerTradePct', 'openRisk']);
  });
});

const opp = (patch: Partial<Opportunity> = {}): Opportunity => ({
  id: 'o1',
  symbol: 'XAUUSD',
  timeframe: '1h',
  status: 'detected',
  direction: 'long',
  setupType: 'trend_following',
  riskLevel: 'medium',
  probability: 0.68,
  entryZone: { low: 2349, high: 2351 },
  stopLossZone: { low: 2339, high: 2341 },
  takeProfitZone: { low: 2369, high: 2371 },
  riskReward: 2,
  factors: [],
  horizonCandles: 20,
  signalCandleTime: 0,
  generatedAt: 1_000,
  validUntil: 10_000,
  modelVersion: 'test',
  provenance: 'demo',
  ...patch,
});

describe('plans from model output', () => {
  it('uses the zone midpoints, matching the model reward : risk', () => {
    expect(planFromOpportunity(opp())).toEqual({ entry: 2350, stop: 2340, target: 2370 });
    expect(planFromOpportunity(opp({ status: 'not_detected' }))).toBeNull();
  });
});

describe('personalised signal checks', () => {
  it('passes a signal that meets every preference and risk limit', () => {
    const e = evaluateSignal(opp(), DEFAULT_SIGNAL_PROFILE, profile(), 5_000);
    expect(e.failed).toBe(0);
    expect(e.matches).toBe(true);
    expect(e.checks.map((c) => c.id)).toEqual([
      'detected',
      'fresh',
      'symbol',
      'timeframe',
      'direction',
      'probability',
      'reward_risk',
      'sizable',
      'limit_daily_loss',
      'limit_open_risk',
      'limit_positions',
    ]);
  });

  it('reports each failed preference with the actual values', () => {
    const e = evaluateSignal(opp({ probability: 0.55, riskReward: 1.2 }), DEFAULT_SIGNAL_PROFILE, profile(), 5_000);
    const failed = e.checks.filter((c) => c.status === 'fail');
    expect(failed.map((c) => c.id)).toEqual(['probability', 'reward_risk']);
    expect(failed[0]?.detail).toBe('Model probability 55% vs your minimum 60%.');
    expect(e.matches).toBe(false);
  });

  it('marks risk checks "not evaluated" without capital instead of guessing', () => {
    const e = evaluateSignal(opp(), DEFAULT_SIGNAL_PROFILE, DEFAULT_RISK_PROFILE, 5_000);
    expect(e.checks.find((c) => c.group === 'risk')?.status).toBe('not_evaluated');
    expect(e.matches).toBe(true);
  });

  it('excludes signals that would breach a limit only when the profile requires it', () => {
    const full = profile({ openPositions: 3 });
    expect(evaluateSignal(opp(), DEFAULT_SIGNAL_PROFILE, full, 5_000).matches).toBe(false);
    expect(evaluateSignal(opp(), { ...DEFAULT_SIGNAL_PROFILE, requireRiskFit: false }, full, 5_000).matches).toBe(true);
  });

  it('fails stale and not-detected analyses', () => {
    expect(evaluateSignal(opp(), DEFAULT_SIGNAL_PROFILE, profile(), 20_000).checks.find((c) => c.id === 'fresh')?.status).toBe('fail');
    const none = evaluateSignal(opp({ status: 'not_detected', direction: 'neutral' }), DEFAULT_SIGNAL_PROFILE, profile(), 5_000);
    expect(none.matches).toBe(false);
    expect(none.checks.some((c) => c.group === 'risk')).toBe(false);
  });
});
