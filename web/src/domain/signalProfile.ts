import { getInstrument, INSTRUMENT_SYMBOLS, type InstrumentSymbol } from './instruments';
import { TIMEFRAMES, type Timeframe } from './market';
import { isOpportunityStale, type Opportunity } from './opportunity';
import { computeTradeRisk, evaluateLimits, planFromOpportunity, type RiskProfile } from './risk';

/**
 * Personalised signals: the user's saved filter, applied to what the model
 * actually returned. Nothing here creates or alters a model output — it only
 * reports which of the user's checks each output passes.
 */
export interface SignalProfile {
  symbols: InstrumentSymbol[];
  timeframes: Timeframe[];
  directions: ('long' | 'short')[];
  /** Minimum model probability that TP is reached before SL (0–1). 0 = any. */
  minProbability: number;
  /** Minimum reward : risk multiple. 0 = any. */
  minRiskReward: number;
  /** When true, signals that would breach a risk limit are excluded from "For you". */
  requireRiskFit: boolean;
}

export const DEFAULT_SIGNAL_PROFILE: SignalProfile = {
  symbols: ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'],
  timeframes: TIMEFRAMES.map((t) => t.id),
  directions: ['long', 'short'],
  minProbability: 0.6,
  minRiskReward: 1.5,
  requireRiskFit: true,
};

export type CheckGroup = 'data' | 'preference' | 'risk';
export type CheckStatus = 'pass' | 'fail' | 'not_evaluated';

export interface SignalCheck {
  id: string;
  group: CheckGroup;
  label: string;
  status: CheckStatus;
  /** What was compared, in plain language with the actual values. */
  detail: string;
}

export interface SignalEvaluation {
  checks: SignalCheck[];
  /** Passes every data and preference check, and the risk checks (when required and evaluated). */
  matches: boolean;
  passed: number;
  failed: number;
  notEvaluated: number;
}

const pct = (p: number) => `${Math.round(p * 100)}%`;
const ratio = (r: number) => `1 : ${r.toFixed(1)}`;

export function evaluateSignal(opportunity: Opportunity, profile: SignalProfile, risk: RiskProfile, nowMs: number): SignalEvaluation {
  const inst = getInstrument(opportunity.symbol);
  const detected = opportunity.status === 'detected' && opportunity.direction !== 'neutral';
  const checks: SignalCheck[] = [];
  const add = (c: SignalCheck) => checks.push(c);

  // 1. Data — is there a current model output at all?
  add({
    id: 'detected',
    group: 'data',
    label: 'Model detected an opportunity',
    status: detected ? 'pass' : 'fail',
    detail: detected ? `The model returned a ${opportunity.direction} setup.` : 'The model returned “no opportunity” for this instrument and timeframe.',
  });
  const stale = isOpportunityStale(opportunity, nowMs);
  add({
    id: 'fresh',
    group: 'data',
    label: 'Analysis within its validity window',
    status: stale ? 'fail' : 'pass',
    detail: stale ? 'Older than the model’s validity window — refresh before relying on it.' : 'Generated recently enough to be current.',
  });

  // 2. Preferences — the user's saved profile.
  add({
    id: 'symbol',
    group: 'preference',
    label: 'Instrument on your list',
    status: profile.symbols.includes(opportunity.symbol) ? 'pass' : 'fail',
    detail: `${inst.display} ${profile.symbols.includes(opportunity.symbol) ? 'is' : 'is not'} in your instruments.`,
  });
  add({
    id: 'timeframe',
    group: 'preference',
    label: 'Timeframe on your list',
    status: profile.timeframes.includes(opportunity.timeframe) ? 'pass' : 'fail',
    detail: `${opportunity.timeframe} ${profile.timeframes.includes(opportunity.timeframe) ? 'is' : 'is not'} one of your timeframes.`,
  });
  if (detected) {
    const dirOk = profile.directions.includes(opportunity.direction as 'long' | 'short');
    add({ id: 'direction', group: 'preference', label: 'Direction allowed', status: dirOk ? 'pass' : 'fail', detail: `${opportunity.direction === 'long' ? 'Long' : 'Short'} ${dirOk ? 'is' : 'is not'} allowed by your profile.` });
    add({
      id: 'probability',
      group: 'preference',
      label: 'Probability at or above your minimum',
      status: opportunity.probability >= profile.minProbability ? 'pass' : 'fail',
      detail: `Model probability ${pct(opportunity.probability)} vs your minimum ${profile.minProbability > 0 ? pct(profile.minProbability) : 'any'}.`,
    });
    add({
      id: 'reward_risk',
      group: 'preference',
      label: 'Reward : risk at or above your minimum',
      status: opportunity.riskReward + 1e-9 >= profile.minRiskReward ? 'pass' : 'fail',
      detail: `Plan ${ratio(opportunity.riskReward)} vs your minimum ${profile.minRiskReward > 0 ? ratio(profile.minRiskReward) : 'any'}.`,
    });
  }

  // 3. Risk — would a trade sized at the user's per-trade risk fit their limits?
  if (detected) {
    const plan = planFromOpportunity(opportunity);
    if (risk.capital === null || !plan) {
      add({ id: 'risk_fit', group: 'risk', label: 'Fits your risk limits', status: 'not_evaluated', detail: 'Set your account capital in Capital & risk to evaluate this.' });
    } else {
      const sized = computeTradeRisk(risk, { instrument: inst, ...plan, riskPct: risk.maxRiskPerTradePct, quoteToAccountRate: null });
      if (sized.kind !== 'ok') {
        const reason = sized.issues[0]?.message ?? 'The position could not be sized.';
        add({ id: 'sizable', group: 'risk', label: 'Position can be sized', status: 'not_evaluated', detail: reason });
      } else {
        add({
          id: 'sizable',
          group: 'risk',
          label: 'Position can be sized',
          status: 'pass',
          detail: `At ${risk.maxRiskPerTradePct}% risk the stop is ${sized.risk.stopDistance.toFixed(inst.pricePrecision)} away from the entry.`,
        });
        for (const limit of evaluateLimits(risk, sized.risk.monetaryRisk).filter((l) => l.id !== 'per_trade')) {
          add({
            id: `limit_${limit.id}`,
            group: 'risk',
            label: `Within ${limit.label.toLowerCase()}`,
            status: limit.status === 'breach' ? 'fail' : 'pass',
            detail: limit.status === 'breach' ? `Would breach: ${limit.rule}.` : `OK: ${limit.rule}.`,
          });
        }
      }
    }
  }

  const passed = checks.filter((c) => c.status === 'pass').length;
  const failed = checks.filter((c) => c.status === 'fail').length;
  const notEvaluated = checks.filter((c) => c.status === 'not_evaluated').length;
  const coreOk = checks.filter((c) => c.group !== 'risk').every((c) => c.status === 'pass');
  const riskOk = !profile.requireRiskFit || checks.filter((c) => c.group === 'risk').every((c) => c.status !== 'fail');
  return { checks, matches: coreOk && riskOk, passed, failed, notEvaluated };
}

export function isValidSignalProfile(p: SignalProfile): boolean {
  return (
    p.symbols.length > 0 &&
    p.symbols.every((s) => INSTRUMENT_SYMBOLS.includes(s)) &&
    p.timeframes.length > 0 &&
    p.directions.length > 0 &&
    p.minProbability >= 0 &&
    p.minProbability < 1 &&
    p.minRiskReward >= 0
  );
}
