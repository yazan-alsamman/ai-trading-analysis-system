import type { Instrument, InstrumentSymbol } from './instruments';
import { zoneMid, type Opportunity } from './opportunity';

/**
 * Capital and risk management — pure, deterministic calculations.
 *
 * Ground rules (product brief §7):
 *  - Never guess contract size, tick/pip value, leverage, currency conversion
 *    or instrument specifications. When a value is needed and not known, the
 *    affected result is withheld and the missing input is named.
 *  - Position size is computed in units of the BASE asset (ounces of gold,
 *    units of EUR…). That needs only prices and the account currency, so it is
 *    broker-independent. Lots are shown only when the user enters their
 *    broker's contract size.
 *  - Decision support only: nothing here places or sizes a real order.
 */

export const ACCOUNT_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD'] as const;
export type AccountCurrency = (typeof ACCOUNT_CURRENCIES)[number];

export interface RiskProfile {
  /** Account equity in the account currency. `null` until the user sets it. */
  capital: number | null;
  currency: AccountCurrency;
  /** Percent of capital, e.g. 1 = 1 %. */
  maxRiskPerTradePct: number;
  dailyLossLimitPct: number;
  maxOpenRiskPct: number;
  maxOpenPositions: number;
  /*
   * Current exposure, reported by the user. The platform never executes or
   * tracks trades, so it cannot know these by itself.
   */
  openRisk: number;
  realisedLossToday: number;
  openPositions: number;
  /** Units of the base asset per 1.0 lot, from the user's broker specification. */
  contractSizes: Partial<Record<InstrumentSymbol, number>>;
  /** Smallest lot increment at the user's broker (e.g. 0.01). Optional. */
  volumeStep: number | null;
}

export const DEFAULT_RISK_PROFILE: RiskProfile = {
  capital: null,
  currency: 'USD',
  maxRiskPerTradePct: 1,
  dailyLossLimitPct: 3,
  maxOpenRiskPct: 5,
  maxOpenPositions: 3,
  openRisk: 0,
  realisedLossToday: 0,
  openPositions: 0,
  contractSizes: {},
  volumeStep: null,
};

export type TradeDirection = 'long' | 'short';

export interface TradePlanInput {
  instrument: Instrument;
  entry: number | null;
  stop: number | null;
  /** Optional. Without it, reward and reward : risk are not shown. */
  target: number | null;
  /** Risk for this trade in percent of capital. */
  riskPct: number | null;
  /** Manual rate "1 unit of quote currency = X account currency", only needed when it cannot be derived. */
  quoteToAccountRate: number | null;
}

export type PlanField = 'capital' | 'entry' | 'stop' | 'target' | 'riskPct' | 'conversion';

export interface PlanIssue {
  field: PlanField;
  message: string;
}

export type ConversionMethod = 'same_currency' | 'base_is_account' | 'user_rate';

export interface Conversion {
  /** Account-currency value of 1 unit of the instrument's quote currency, at the entry price. */
  rate: number;
  method: ConversionMethod;
  /** Plain-language statement of how the rate was obtained. */
  note: string;
}

export interface TradeRisk {
  direction: TradeDirection;
  /** |entry − stop| in quote-currency price units. */
  stopDistance: number;
  targetDistance: number | null;
  riskReward: number | null;
  conversion: Conversion;
  /** capital × riskPct — the amount the user is prepared to lose. */
  riskBudget: number;
  /** Position size in units of the base asset (e.g. ounces for XAU/USD). */
  units: number;
  /** Lots — only when a contract size is known. `rounded` applies the volume step (rounded DOWN). */
  lots: { contractSize: number; exact: number; rounded: number | null; step: number | null } | null;
  /** Loss in account currency if the stop is hit, for the size actually shown (rounded lots when available). */
  monetaryRisk: number;
  /** Gain in account currency if the target is hit. */
  potentialReward: number | null;
  /** Position value at entry, in account currency. Margin is not shown: it depends on broker leverage. */
  notional: number;
  riskPctOfCapital: number;
  rewardPctOfCapital: number | null;
}

export type TradeRiskResult =
  | { kind: 'incomplete'; issues: PlanIssue[] }
  | { kind: 'invalid'; issues: PlanIssue[] }
  | { kind: 'ok'; risk: TradeRisk; notes: string[] };

const isPositive = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v) && v > 0;

/**
 * Resolve the quote → account conversion without guessing:
 *  - quote currency is the account currency → 1
 *  - base currency is the account currency → 1 / entry price (exact at entry)
 *  - otherwise the user must supply the rate.
 */
export function resolveConversion(instrument: Instrument, account: AccountCurrency, entry: number, userRate: number | null): Conversion | null {
  if (instrument.quote === account) {
    return { rate: 1, method: 'same_currency', note: `Prices are quoted in ${account}, your account currency — no conversion needed.` };
  }
  if (instrument.base === account) {
    return {
      rate: 1 / entry,
      method: 'base_is_account',
      note: `${instrument.display} profit and loss is in ${instrument.quote}; it is converted to ${account} at the exit price (stop or target), which is exact for a pair whose base currency is your account currency.`,
    };
  }
  if (isPositive(userRate)) {
    return { rate: userRate, method: 'user_rate', note: `Converted with your rate: 1 ${instrument.quote} = ${userRate} ${account}.` };
  }
  return null;
}

/**
 * Account-currency value of 1 quote unit at a given price. For a pair whose
 * base is the account currency the conversion happens at the exit price,
 * e.g. USD/JPY on a USD account: P/L(USD) = P/L(JPY) / exit price.
 */
export function conversionRateAt(conversion: Conversion, price: number): number {
  return conversion.method === 'base_is_account' ? 1 / price : conversion.rate;
}

/** Round DOWN to the volume step, tolerant of binary floating point (0.1 + 0.2). */
export function floorToStep(value: number, step: number): number {
  const decimals = Math.max(0, -Math.floor(Math.log10(step)) + 2);
  const steps = Math.floor(value / step + 1e-9);
  return Number((steps * step).toFixed(decimals));
}

/** Position size and money at risk for one planned trade. */
export function computeTradeRisk(profile: RiskProfile, input: TradePlanInput): TradeRiskResult {
  const { instrument, entry, stop, target, riskPct, quoteToAccountRate } = input;
  const missing: PlanIssue[] = [];
  if (!isPositive(profile.capital)) missing.push({ field: 'capital', message: 'Enter your account capital.' });
  if (!isPositive(entry)) missing.push({ field: 'entry', message: 'Enter an entry price.' });
  if (!isPositive(stop)) missing.push({ field: 'stop', message: 'Enter a stop-loss price.' });
  if (!isPositive(riskPct)) missing.push({ field: 'riskPct', message: 'Enter the percentage of capital to risk.' });
  if (missing.length > 0 || !isPositive(profile.capital) || !isPositive(entry) || !isPositive(stop) || !isPositive(riskPct)) {
    return { kind: 'incomplete', issues: missing };
  }

  const invalid: PlanIssue[] = [];
  if (stop === entry) invalid.push({ field: 'stop', message: 'The stop-loss must differ from the entry price.' });
  if (riskPct > 100) invalid.push({ field: 'riskPct', message: 'Risk cannot exceed 100 % of capital.' });
  const direction: TradeDirection = stop < entry ? 'long' : 'short';
  if (target !== null && target !== undefined) {
    if (!isPositive(target)) invalid.push({ field: 'target', message: 'The target must be a positive price.' });
    else if (direction === 'long' && target <= entry) invalid.push({ field: 'target', message: 'For a long trade (stop below entry) the target must be above the entry.' });
    else if (direction === 'short' && target >= entry) invalid.push({ field: 'target', message: 'For a short trade (stop above entry) the target must be below the entry.' });
  }
  if (invalid.length > 0) return { kind: 'invalid', issues: invalid };

  const conversion = resolveConversion(instrument, profile.currency, entry, quoteToAccountRate);
  if (!conversion) {
    return {
      kind: 'incomplete',
      issues: [
        {
          field: 'conversion',
          message: `${instrument.display} is quoted in ${instrument.quote} and your account is in ${profile.currency}. Enter the current ${instrument.quote}→${profile.currency} rate to size the position.`,
        },
      ],
    };
  }

  const capital = profile.capital;
  const stopDistance = Math.abs(entry - stop);
  const targetDistance = isPositive(target) ? Math.abs(target - entry) : null;
  // Account currency lost per base unit if the stop is hit (converted at the stop price when relevant).
  const riskPerUnit = stopDistance * conversionRateAt(conversion, stop);
  const rewardPerUnit = targetDistance !== null && isPositive(target) ? targetDistance * conversionRateAt(conversion, target) : null;
  const riskBudget = (capital * riskPct) / 100;
  const units = riskBudget / riskPerUnit;

  const contractSize = profile.contractSizes[instrument.symbol];
  let lots: TradeRisk['lots'] = null;
  let sizedUnits = units;
  const notes: string[] = [conversion.note];
  if (isPositive(contractSize)) {
    const exact = units / contractSize;
    const step = isPositive(profile.volumeStep) ? profile.volumeStep : null;
    const rounded = step ? floorToStep(exact, step) : null;
    lots = { contractSize, exact, rounded, step };
    if (rounded !== null) {
      sizedUnits = rounded * contractSize;
      if (rounded === 0) notes.push(`The risk budget is smaller than one volume step (${step} lot) — this trade cannot be taken at this risk.`);
      else notes.push(`Lots rounded down to your volume step (${step}). Money at risk is shown for the rounded size.`);
    }
  } else {
    notes.push(`Lots are not shown: enter your broker's contract size for ${instrument.display} (units per 1.0 lot).`);
  }

  const monetaryRisk = sizedUnits * riskPerUnit;
  const potentialReward = rewardPerUnit !== null ? sizedUnits * rewardPerUnit : null;
  return {
    kind: 'ok',
    notes,
    risk: {
      direction,
      stopDistance,
      targetDistance,
      riskReward: targetDistance !== null ? targetDistance / stopDistance : null,
      conversion,
      riskBudget,
      units: sizedUnits,
      lots,
      monetaryRisk,
      potentialReward,
      notional: sizedUnits * entry * conversion.rate,
      riskPctOfCapital: (monetaryRisk / capital) * 100,
      rewardPctOfCapital: potentialReward !== null ? (potentialReward / capital) * 100 : null,
    },
  };
}

/* ------------------------------------------------------------- limits */

export type LimitId = 'per_trade' | 'daily_loss' | 'open_risk' | 'positions';
export type LimitStatus = 'ok' | 'caution' | 'breach';

export interface LimitCheck {
  id: LimitId;
  label: string;
  /** How the check is computed, in plain language. */
  rule: string;
  unit: 'money' | 'count';
  /** Usage before this trade. */
  used: number;
  /** Usage if this trade is added (worst case: it hits its stop). */
  after: number;
  limit: number;
  remaining: number;
  status: LimitStatus;
}

/** A limit at or above this share of its allowance is flagged as caution. */
export const CAUTION_SHARE = 0.8;

function statusOf(after: number, limit: number, caution = true): LimitStatus {
  // Small epsilon so a trade sized exactly at the limit is not a breach.
  if (after > limit + 1e-9) return 'breach';
  if (caution && limit > 0 && after >= limit * CAUTION_SHARE) return 'caution';
  return 'ok';
}

/**
 * Check a proposed trade (its money at risk) against the user's limits.
 * `tradeRisk` may be null to show current utilisation only.
 */
export function evaluateLimits(profile: RiskProfile, tradeRisk: number | null): LimitCheck[] {
  const capital = profile.capital ?? 0;
  const add = tradeRisk ?? 0;
  const pct = (p: number) => (capital * p) / 100;

  const perTradeLimit = pct(profile.maxRiskPerTradePct);
  const dailyLimit = pct(profile.dailyLossLimitPct);
  const openLimit = pct(profile.maxOpenRiskPct);
  const dailyUsed = profile.realisedLossToday + profile.openRisk;

  const money = (id: LimitId, label: string, rule: string, used: number, after: number, limit: number): LimitCheck => ({
    id,
    label,
    rule,
    unit: 'money',
    used,
    after,
    limit,
    remaining: Math.max(0, limit - after),
    // Sizing a trade at exactly the per-trade maximum is the intended use, not a warning.
    status: statusOf(after, limit, id !== 'per_trade'),
  });

  const positionsAfter = profile.openPositions + (tradeRisk !== null ? 1 : 0);
  return [
    money('per_trade', 'Risk per trade', `This trade's loss at the stop ≤ ${profile.maxRiskPerTradePct}% of capital`, 0, add, perTradeLimit),
    money(
      'daily_loss',
      'Daily loss limit',
      `Loss realised today + all open risk + this trade ≤ ${profile.dailyLossLimitPct}% of capital (worst case: every stop is hit today)`,
      dailyUsed,
      dailyUsed + add,
      dailyLimit,
    ),
    money('open_risk', 'Aggregate open risk', `Open risk + this trade ≤ ${profile.maxOpenRiskPct}% of capital`, profile.openRisk, profile.openRisk + add, openLimit),
    {
      id: 'positions',
      label: 'Concurrent positions',
      rule: `Open positions${tradeRisk !== null ? ' + this trade' : ''} ≤ ${profile.maxOpenPositions}`,
      unit: 'count',
      used: profile.openPositions,
      after: positionsAfter,
      limit: profile.maxOpenPositions,
      remaining: Math.max(0, profile.maxOpenPositions - positionsAfter),
      status: positionsAfter > profile.maxOpenPositions ? 'breach' : positionsAfter === profile.maxOpenPositions && profile.maxOpenPositions > 0 ? 'caution' : 'ok',
    },
  ];
}

export interface RiskCapacity {
  /** Largest loss-at-stop the next trade may have without breaching any limit. */
  money: number;
  pctOfCapital: number;
  /** The limit that currently binds. */
  binding: LimitId;
}

/** Remaining permitted risk for the next trade, or null without capital. */
export function remainingRiskCapacity(profile: RiskProfile): RiskCapacity | null {
  if (!isPositive(profile.capital)) return null;
  const capital = profile.capital;
  const pct = (p: number) => (capital * p) / 100;
  if (profile.openPositions >= profile.maxOpenPositions) return { money: 0, pctOfCapital: 0, binding: 'positions' };
  const candidates: [LimitId, number][] = [
    ['per_trade', pct(profile.maxRiskPerTradePct)],
    ['daily_loss', pct(profile.dailyLossLimitPct) - profile.realisedLossToday - profile.openRisk],
    ['open_risk', pct(profile.maxOpenRiskPct) - profile.openRisk],
  ];
  const [binding, raw] = candidates.reduce((min, c) => (c[1] < min[1] ? c : min));
  const money = Math.max(0, raw);
  return { money, pctOfCapital: (money / capital) * 100, binding };
}

/** Overall status for a set of checks: the worst one wins. */
export function worstStatus(checks: readonly LimitCheck[]): LimitStatus {
  if (checks.some((c) => c.status === 'breach')) return 'breach';
  if (checks.some((c) => c.status === 'caution')) return 'caution';
  return 'ok';
}

/** Validate a risk profile before saving; returns field → message. */
export function validateRiskProfile(p: RiskProfile): Partial<Record<keyof RiskProfile, string>> {
  const errors: Partial<Record<keyof RiskProfile, string>> = {};
  const pctOk = (v: number) => Number.isFinite(v) && v > 0 && v <= 100;
  if (p.capital !== null && !(Number.isFinite(p.capital) && p.capital > 0)) errors.capital = 'Capital must be a positive amount.';
  if (!pctOk(p.maxRiskPerTradePct)) errors.maxRiskPerTradePct = 'Use a percentage between 0 and 100.';
  if (!pctOk(p.dailyLossLimitPct)) errors.dailyLossLimitPct = 'Use a percentage between 0 and 100.';
  if (!pctOk(p.maxOpenRiskPct)) errors.maxOpenRiskPct = 'Use a percentage between 0 and 100.';
  if (pctOk(p.maxRiskPerTradePct) && pctOk(p.maxOpenRiskPct) && p.maxRiskPerTradePct > p.maxOpenRiskPct)
    errors.maxRiskPerTradePct = 'Risk per trade cannot exceed the aggregate open-risk limit.';
  if (!Number.isInteger(p.maxOpenPositions) || p.maxOpenPositions < 1 || p.maxOpenPositions > 50) errors.maxOpenPositions = 'Use a whole number from 1 to 50.';
  if (!(Number.isFinite(p.openRisk) && p.openRisk >= 0)) errors.openRisk = 'Open risk cannot be negative.';
  if (!(Number.isFinite(p.realisedLossToday) && p.realisedLossToday >= 0)) errors.realisedLossToday = 'Enter today’s loss as a positive amount (0 if none).';
  if (!Number.isInteger(p.openPositions) || p.openPositions < 0) errors.openPositions = 'Use a whole number (0 or more).';
  if (p.volumeStep !== null && !(Number.isFinite(p.volumeStep) && p.volumeStep > 0)) errors.volumeStep = 'The volume step must be a positive number.';
  return errors;
}

/**
 * Plan levels from a model output: midpoints of its entry, stop-loss and
 * take-profit zones (the same convention the model's reward : risk uses).
 */
export function planFromOpportunity(opportunity: Opportunity): { entry: number; stop: number; target: number } | null {
  if (opportunity.status !== 'detected' || opportunity.direction === 'neutral') return null;
  return { entry: zoneMid(opportunity.entryZone), stop: zoneMid(opportunity.stopLossZone), target: zoneMid(opportunity.takeProfitZone) };
}
