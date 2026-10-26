import type { InstrumentSymbol } from './instruments';

/**
 * The backend's strategy engine (libs/strategies + /api/v1 strategies,
 * custom strategies and signal plans). Everything here is rule-based: a
 * strategy fires on a closed bar when its conditions hold. Nothing here is
 * the AI model's output.
 */

/** Every timeframe the backend accepts (the chart UI uses 15m/1h/4h only). */
export const BACKEND_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'] as const;
export type BackendTimeframe = (typeof BACKEND_TIMEFRAMES)[number];

export function isBackendTimeframe(v: string): v is BackendTimeframe {
  return (BACKEND_TIMEFRAMES as readonly string[]).includes(v);
}

/** A backend instrument, including the ones the chart UI does not support (e.g. crypto). */
export interface BackendInstrument {
  id: string;
  /** Backend symbol, e.g. "XAU/USD" or "BTC/USDT". */
  symbol: string;
  /** Web-client symbol when the chart UI supports the instrument. */
  webSymbol: InstrumentSymbol | null;
  source: string;
  market: string;
  pricePrecision: number | null;
  isActive: boolean;
}

export type ParamValue = number | boolean | string;
export type StrategyParams = Record<string, ParamValue>;

export interface ParamSpec {
  name: string;
  /** `int`, `float` (and `bool` where a strategy defines one). */
  type: string;
  title: string;
  default: ParamValue | null;
  min: number | null;
  max: number | null;
}

/** A global strategy from GET /strategies. */
export interface StrategyDefinition {
  key: string;
  title: string;
  description: string;
  category: string;
  params: ParamSpec[];
  /** Indicator lines drawn with the strategy. */
  indicators: { name: string; params: Record<string, unknown> }[];
  /** Bars of history needed before the first reliable signal. */
  history: number;
}

/** One of the user's activations (GET /me/strategies): the live engine evaluates it on every closed bar. */
export interface StrategyActivation {
  id: string;
  /** A global key or `custom:<uuid>`. */
  strategyKey: string;
  params: StrategyParams;
  instrumentId: string;
  timeframe: BackendTimeframe;
  name: string | null;
  isActive: boolean;
  /** Whether a signal produces a notification. */
  notify: boolean;
  createdAt: number;
  updatedAt: number;
}

export interface ActivationInput {
  strategyKey: string;
  instrumentId: string;
  timeframe: BackendTimeframe;
  params: StrategyParams;
  name: string | null;
  isActive: boolean;
  notify: boolean;
}

export interface ActivationPatch {
  name?: string | null;
  params?: StrategyParams;
  isActive?: boolean;
  notify?: boolean;
}

/** A Lightweight Charts marker as the backend sends it. */
export interface ChartMarker {
  time: number;
  position: 'aboveBar' | 'belowBar' | 'inBar';
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  color: string;
  text: string;
}

export interface LinePoint {
  time: number;
  value: number | null;
}

export interface PreviewSignal {
  time: number;
  side: 'buy' | 'sell';
  strength: number;
  price: number;
  reason: string;
  details: Record<string, unknown>;
}

/** POST /strategies/{key}/preview: the strategy run over a candle window. */
export interface StrategyPreview {
  strategyKey: string;
  params: StrategyParams;
  bars: number;
  signals: PreviewSignal[];
  markers: ChartMarker[];
  indicators: { name: string; params: Record<string, unknown>; placement: string; outputs: Record<string, LinePoint[]> }[];
}

/** GET /me/signal-plans: the user's trade plan for a live signal of one of their activations. */
export interface SignalPlan {
  id: string;
  activationId: string | null;
  signal: {
    id: string;
    instrumentId: string;
    timeframe: string;
    strategyKey: string;
    side: 'buy' | 'sell';
    strength: number;
    price: number;
    reason: string;
    time: number;
  };
  /** The server's plan (entry, stop, targets, size, risk); shape owned by the backend risk engine. */
  plan: Record<string, unknown>;
  createdAt: number;
}

/* ------------------------------------------------------- custom strategies */

export type CustomStrategyKind = 'builder' | 'composite';
export type StrategyVisibility = 'private' | 'public';

export interface CustomStrategySummary {
  id: string;
  /** `custom:<uuid>`: usable wherever a global key is. */
  key: string;
  name: string;
  description: string;
  kind: CustomStrategyKind;
  visibility: StrategyVisibility;
  /** Optimistic-concurrency version of the definition. */
  version: number;
  clonedFrom: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface DefinitionIssue {
  /** JSON path of the problem, e.g. `buy.all[2].right.params.length`. */
  path: string;
  message: string;
}

export interface CustomStrategy extends CustomStrategySummary {
  definition: Record<string, unknown>;
  /** Whether it can still run (e.g. a referenced strategy was deleted). */
  valid: boolean;
  errors: DefinitionIssue[];
  history: number | null;
  usage: { activations: number; activeActivations: number; backtests: number; composites: number };
}

export interface CustomStrategyInput {
  name: string;
  description: string;
  kind: CustomStrategyKind;
  definition: Record<string, unknown>;
  visibility: StrategyVisibility;
}

export interface DefinitionValidation {
  valid: boolean;
  errors: DefinitionIssue[];
  history: number | null;
  /** The normalised definition the server would store. */
  definition: Record<string, unknown> | null;
}

export interface PublicStrategy {
  id: string;
  key: string;
  name: string;
  description: string;
  kind: CustomStrategyKind;
  definition: Record<string, unknown>;
  version: number;
  author: { name: string; role: string };
  updatedAt: number;
}

/** The editor catalog from GET /custom-strategies/schema. */
export interface BuilderCatalog {
  indicators: {
    name: string;
    title: string;
    category: string;
    params: ParamSpec[];
    outputs: string[];
    outputRequired: boolean;
  }[];
  priceFields: string[];
  ops: { op: string; title: string; operands: string[]; bars: { min: number; max: number } | null }[];
  groups: string[];
  strengths: string[];
  categories: string[];
  compositeModes: string[];
  compositeStrategies: { key: string; title: string; params: ParamSpec[] }[];
  limits: {
    maxConditions: number;
    maxDepth: number;
    shift: { min: number; max: number };
    bars: { min: number; max: number };
    members: { min: number; max: number };
    window: { min: number; max: number };
  };
}

/** Human title for a strategy key (global or custom). */
export function strategyLabel(key: string, catalog: readonly { key: string; title: string }[], custom: readonly { key: string; name: string }[] = []): string {
  return catalog.find((s) => s.key === key)?.title ?? custom.find((s) => s.key === key)?.name ?? (key.startsWith('custom:') ? 'Custom strategy' : key);
}

/** Default params for a strategy, from its catalog entry. */
export function defaultParams(def: Pick<StrategyDefinition, 'params'>): StrategyParams {
  const out: StrategyParams = {};
  for (const p of def.params) if (p.default !== null) out[p.name] = p.default;
  return out;
}
