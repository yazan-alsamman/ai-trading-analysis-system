/**
 * Membership packages — FRONTEND CONFIGURATION ONLY.
 *
 * These are PROPOSED packages for presentation and a labelled demo state.
 * There is no billing, no subscription service and no server-side
 * enforcement (docs/MEMBERSHIP_FRONTEND_SPEC.md). Prices are deliberately
 * not defined: the product owner has not set commercial terms.
 *
 * Differentiation follows stated product principles rather than arbitrary caps:
 *  - Transparency for everyone: model analytics and risk tools are in every tier.
 *  - Essential is gold-first (the platform's initial focus).
 *  - Professional adds breadth (FX majors) and personalisation.
 *  - Elite adds the assistant and research history.
 */

export const PLAN_IDS = ['essential', 'professional', 'elite'] as const;
export type PlanId = (typeof PLAN_IDS)[number];

export function isPlanId(value: unknown): value is PlanId {
  return typeof value === 'string' && (PLAN_IDS as readonly string[]).includes(value);
}

/** What the feature runs on today — independent of the plan. */
export type FeatureStatus = 'available' | 'demo' | 'backend' | 'planned';

export const STATUS_LABELS: Record<FeatureStatus, { label: string; description: string }> = {
  available: { label: 'Works now', description: 'Fully functional in the browser with your own inputs.' },
  demo: { label: 'Demo data', description: 'The interface works; it runs on simulated market data and model output.' },
  backend: { label: 'Needs backend', description: 'The interface exists; delivery or storage needs a backend service that is not connected.' },
  planned: { label: 'Planned', description: 'Not built yet. Shown so the package is complete.' },
};

export type FeatureGroup = 'Research' | 'Personalisation' | 'Risk & review' | 'Assistant & workflow';

export const FEATURE_IDS = [
  'workspace',
  'instruments',
  'timeframes',
  'ai_analysis',
  'explanations',
  'tf_alignment',
  'signal_filters',
  'watchlist',
  'risk_tools',
  'analytics',
  'alerts',
  'alert_delivery',
  'assistant',
  'research_history',
  'saved_workspaces',
] as const;
export type FeatureId = (typeof FEATURE_IDS)[number];

export interface Feature {
  id: FeatureId;
  label: string;
  group: FeatureGroup;
  status: FeatureStatus;
  /** One line on what it does. */
  detail: string;
}

export const FEATURES: readonly Feature[] = [
  { id: 'workspace', label: 'Market workspace', group: 'Research', status: 'demo', detail: 'Candles, indicators, NOW boundary and the model’s levels on one chart.' },
  { id: 'instruments', label: 'Instruments', group: 'Research', status: 'demo', detail: 'Gold (XAU/USD) and the seven FX majors supported by the model.' },
  { id: 'timeframes', label: 'Chart timeframes', group: 'Research', status: 'demo', detail: '15-minute, 1-hour and 4-hour analysis.' },
  { id: 'ai_analysis', label: 'AI analysis', group: 'Research', status: 'demo', detail: 'Direction, probability (target before stop), zones and reward : risk.' },
  { id: 'explanations', label: 'Research explanations', group: 'Research', status: 'demo', detail: 'Contributing factors, what could invalidate it, and what is missing.' },
  { id: 'tf_alignment', label: 'Multi-timeframe alignment', group: 'Research', status: 'demo', detail: '15m, 1h and 4h model outputs compared side by side.' },
  { id: 'signal_filters', label: 'Personalised signal filters', group: 'Personalisation', status: 'demo', detail: 'Your saved profile applied to every model output, with each check shown.' },
  { id: 'watchlist', label: 'Watchlist', group: 'Personalisation', status: 'demo', detail: 'Prices, intraday shape and model status per instrument.' },
  { id: 'risk_tools', label: 'Capital & risk tools', group: 'Risk & review', status: 'available', detail: 'Position size, money at risk and limit checks from your own capital.' },
  { id: 'analytics', label: 'Model analytics', group: 'Risk & review', status: 'demo', detail: 'Hit rate, Brier score and calibration, with every metric defined.' },
  { id: 'alerts', label: 'Price alerts', group: 'Risk & review', status: 'demo', detail: 'Alerts that fire in the app while it is open.' },
  { id: 'alert_delivery', label: 'Email & Telegram delivery', group: 'Risk & review', status: 'backend', detail: 'Alerts delivered when the app is closed.' },
  { id: 'assistant', label: 'AI assistant', group: 'Assistant & workflow', status: 'demo', detail: 'Ask about the analysis and your risk; answers use only the data on screen. Rule-based demo today.' },
  { id: 'research_history', label: 'Research history', group: 'Assistant & workflow', status: 'planned', detail: 'Saved analyses and conversations across devices.' },
  { id: 'saved_workspaces', label: 'Saved workspaces', group: 'Assistant & workflow', status: 'available', detail: 'Named chart layouts, stored in this browser.' },
];

/** `true` = included, `false` = not included, string = included with this scope. */
export type Access = boolean | string;

export type Price = { kind: 'tba' } | { kind: 'amount'; amount: number; currency: string; period: 'month' | 'year' };

export interface Plan {
  id: PlanId;
  name: string;
  tagline: string;
  audience: string;
  /** Short list shown on the card. */
  highlights: string[];
  access: Record<FeatureId, Access>;
  price: Price;
  cta: string;
  /** Can this plan be activated today? Always false until billing exists. */
  activation: 'unavailable';
}

const GOLD = 'Gold (XAU/USD)';
const ALL_INSTRUMENTS = 'Gold + 7 FX majors';

export const PLANS: readonly Plan[] = [
  {
    id: 'essential',
    name: 'Essential',
    tagline: 'Gold research, done properly.',
    audience: 'Traders focused on gold who want structured analysis and disciplined position sizing.',
    highlights: ['Gold workspace with the model’s levels', 'Evidence, invalidation and missing data', 'Capital & risk tools', 'Model analytics for full transparency'],
    access: {
      workspace: true,
      instruments: GOLD,
      timeframes: '15m · 1h · 4h',
      ai_analysis: true,
      explanations: true,
      tf_alignment: false,
      signal_filters: false,
      watchlist: GOLD,
      risk_tools: true,
      analytics: true,
      alerts: true,
      alert_delivery: false,
      assistant: false,
      research_history: false,
      saved_workspaces: 'One workspace',
    },
    price: { kind: 'tba' },
    cta: 'Choose Essential',
    activation: 'unavailable',
  },
  {
    id: 'professional',
    name: 'Professional',
    tagline: 'Personalised research across gold and FX.',
    audience: 'Active traders who follow several instruments and want setups filtered by their own rules.',
    highlights: ['Gold and the seven FX majors', 'Personalised signals with every check shown', 'Multi-timeframe alignment', 'Alert delivery by email & Telegram'],
    access: {
      workspace: true,
      instruments: ALL_INSTRUMENTS,
      timeframes: '15m · 1h · 4h',
      ai_analysis: true,
      explanations: true,
      tf_alignment: true,
      signal_filters: true,
      watchlist: ALL_INSTRUMENTS,
      risk_tools: true,
      analytics: true,
      alerts: true,
      alert_delivery: true,
      assistant: false,
      research_history: false,
      saved_workspaces: 'Multiple workspaces',
    },
    price: { kind: 'tba' },
    cta: 'Choose Professional',
    activation: 'unavailable',
  },
  {
    id: 'elite',
    name: 'Elite',
    tagline: 'The complete research desk.',
    audience: 'Traders who want every module, including the assistant to question the evidence.',
    highlights: ['Everything in Professional', 'AI assistant in every module', 'Research history (planned)', 'Every future research view'],
    access: {
      workspace: true,
      instruments: ALL_INSTRUMENTS,
      timeframes: '15m · 1h · 4h',
      ai_analysis: true,
      explanations: true,
      tf_alignment: true,
      signal_filters: true,
      watchlist: ALL_INSTRUMENTS,
      risk_tools: true,
      analytics: true,
      alerts: true,
      alert_delivery: true,
      assistant: true,
      research_history: true,
      saved_workspaces: 'Multiple workspaces',
    },
    price: { kind: 'tba' },
    cta: 'Choose Elite',
    activation: 'unavailable',
  },
];

export function getPlan(id: PlanId): Plan {
  const plan = PLANS.find((p) => p.id === id);
  if (!plan) throw new Error(`Unknown plan: ${id}`);
  return plan;
}

export function getFeature(id: FeatureId): Feature {
  const f = FEATURES.find((x) => x.id === id);
  if (!f) throw new Error(`Unknown feature: ${id}`);
  return f;
}

export function planIncludes(plan: PlanId, feature: FeatureId): boolean {
  return getPlan(plan).access[feature] !== false;
}

/** Lowest plan that includes a feature — for "available in …" messages. */
export function lowestPlanWith(feature: FeatureId): Plan | null {
  return PLANS.find((p) => p.access[feature] !== false) ?? null;
}

/** Features a plan gains over the previous tier (for "Everything in X, plus…"). */
export function addedOver(previous: PlanId, plan: PlanId): FeatureId[] {
  return FEATURE_IDS.filter((f) => getPlan(plan).access[f] !== getPlan(previous).access[f] && getPlan(plan).access[f] !== false);
}

export function formatPrice(price: Price): string {
  if (price.kind === 'tba') return 'Pricing to be announced';
  return `${new Intl.NumberFormat('en-US', { style: 'currency', currency: price.currency }).format(price.amount)} / ${price.period}`;
}

/* ------------------------------------------------- plan-fit questions */

export interface FitAnswers {
  instruments: 'gold' | 'gold_fx';
  personalise: boolean;
  assistant: boolean;
}

/**
 * Suggest the smallest plan that covers the visitor's stated needs.
 * A recommendation derived from their answers — never a default "popular" badge.
 */
export function suggestPlan(a: FitAnswers): PlanId {
  if (a.assistant) return 'elite';
  if (a.instruments === 'gold_fx' || a.personalise) return 'professional';
  return 'essential';
}

/* ------------------------------------------------- frontend gating (demo) */

/** App routes that map to a gated feature in the DEMO membership state. */
export const ROUTE_FEATURES: Partial<Record<string, FeatureId>> = {
  '/assistant': 'assistant',
};
