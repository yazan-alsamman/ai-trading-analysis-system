import { z } from 'zod';
import type { BacktestComparison, BacktestResult, BacktestSummary, BacktestTrade } from '@/domain/backtests';
import {
  BACKEND_TIMEFRAMES,
  type BackendInstrument,
  type BuilderCatalog,
  type ChartMarker,
  type CustomStrategy,
  type CustomStrategySummary,
  type ParamSpec,
  type ParamValue,
  type StrategyActivation,
  type StrategyParams,
} from '@/domain/strategies';
import type { BacktestService, InstrumentDirectoryService, StrategyService, Unsubscribe } from '../types';
import { BackendCandleSeries, InstrumentRead, page } from './backend';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';
import { toSymbol } from './mappers';
import type { MarketSocket } from './marketSocket';

/**
 * Strategy engine, custom strategies and backtests (docs/custom-strategies.md,
 * docs/backtesting.md). Schemas validate what the client reads; objects whose
 * shape the backend owns (trade plans, metrics, configs, definitions) are kept
 * as JSON and never reinterpreted into invented fields.
 */

const Empty = z.unknown();
const Json = z.record(z.string(), z.unknown());
const Timeframe = z.enum(BACKEND_TIMEFRAMES);
const opt = (signal?: AbortSignal): { signal?: AbortSignal } => (signal ? { signal } : {});

const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
};
const msReq = (iso: string) => ms(iso) ?? 0;

/** Keep only scalar parameter values (the engine's params are numbers or booleans). */
function toParams(raw: Record<string, unknown>): StrategyParams {
  const out: StrategyParams = {};
  for (const [k, v] of Object.entries(raw)) if (typeof v === 'number' || typeof v === 'boolean' || typeof v === 'string') out[k] = v;
  return out;
}

const ParamSpecRead = z.object({
  name: z.string(),
  type: z.string(),
  title: z.string().optional(),
  default: z.union([z.number(), z.boolean(), z.string()]).nullable().optional(),
  min: z.number().nullable().optional(),
  max: z.number().nullable().optional(),
});
const toParamSpec = (p: z.infer<typeof ParamSpecRead>): ParamSpec => ({
  name: p.name,
  type: p.type,
  title: p.title ?? p.name,
  default: (p.default ?? null) as ParamValue | null,
  min: p.min ?? null,
  max: p.max ?? null,
});

const StrategyDefinitionRead = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.string(),
  params: z.array(ParamSpecRead),
  indicators: z.array(z.object({ name: z.string(), params: Json })).default([]),
  history: z.number().int(),
});

const UserStrategyRead = z.object({
  id: z.string(),
  strategy_key: z.string(),
  params: Json,
  instrument_id: z.string(),
  timeframe: Timeframe,
  name: z.string().nullable(),
  is_active: z.boolean(),
  notify: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
const toActivation = (s: z.infer<typeof UserStrategyRead>): StrategyActivation => ({
  id: s.id,
  strategyKey: s.strategy_key,
  params: toParams(s.params),
  instrumentId: s.instrument_id,
  timeframe: s.timeframe,
  name: s.name,
  isActive: s.is_active,
  notify: s.notify,
  createdAt: msReq(s.created_at),
  updatedAt: msReq(s.updated_at),
});

const MarkerRead = z.object({
  time: z.number(),
  position: z.enum(['aboveBar', 'belowBar', 'inBar']),
  shape: z.enum(['arrowUp', 'arrowDown', 'circle', 'square']),
  color: z.string(),
  text: z.string().default(''),
});
const toMarkers = (m: z.infer<typeof MarkerRead>[]): ChartMarker[] => m.map((x) => ({ ...x }));

const PreviewRead = z.object({
  strategy_key: z.string(),
  params: Json,
  bars: z.number().int(),
  signals: z.array(z.object({ time: z.number(), side: z.enum(['buy', 'sell']), strength: z.number(), price: z.number(), reason: z.string(), details: Json })),
  markers: z.array(MarkerRead),
  indicators: z.array(
    z.object({
      name: z.string(),
      params: Json,
      placement: z.string(),
      outputs: z.record(z.string(), z.array(z.object({ time: z.number(), value: z.number().nullable() }))),
    }),
  ),
});

const SignalPlanRead = z.object({
  id: z.string(),
  user_strategy_id: z.string().nullable(),
  plan: Json,
  created_at: z.string(),
  signal: z.object({
    id: z.string(),
    instrument_id: z.string(),
    timeframe: z.string(),
    strategy_key: z.string(),
    side: z.enum(['buy', 'sell']),
    strength: z.number(),
    price: z.number(),
    reason: z.string(),
    time: z.number().int(),
  }),
});

const Kind = z.enum(['builder', 'composite']);
const Visibility = z.enum(['private', 'public']);
const CustomSummaryRead = z.object({
  id: z.string(),
  key: z.string(),
  name: z.string(),
  description: z.string(),
  kind: Kind,
  visibility: Visibility,
  version: z.number().int(),
  cloned_from: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
const Issue = z.object({ path: z.string(), message: z.string() });
const CustomRead = CustomSummaryRead.extend({
  definition: Json,
  valid: z.boolean(),
  errors: z.array(Issue),
  history: z.number().int().nullable(),
  usage: z.object({ activations: z.number().int(), active_activations: z.number().int(), backtests: z.number().int(), composites: z.number().int() }),
});
const toSummary = (s: z.infer<typeof CustomSummaryRead>): CustomStrategySummary => ({
  id: s.id,
  key: s.key,
  name: s.name,
  description: s.description,
  kind: s.kind,
  visibility: s.visibility,
  version: s.version,
  clonedFrom: s.cloned_from,
  createdAt: msReq(s.created_at),
  updatedAt: msReq(s.updated_at),
});
const toCustom = (s: z.infer<typeof CustomRead>): CustomStrategy => ({
  ...toSummary(s),
  definition: s.definition,
  valid: s.valid,
  errors: s.errors.map((e) => ({ path: e.path, message: e.message })),
  history: s.history,
  usage: { activations: s.usage.activations, activeActivations: s.usage.active_activations, backtests: s.usage.backtests, composites: s.usage.composites },
});

const ValidateRead = z.object({ valid: z.boolean(), errors: z.array(Issue), history: z.number().int().nullable(), definition: Json.nullable() });

const PublicRead = z.object({
  id: z.string(),
  key: z.string(),
  name: z.string(),
  description: z.string(),
  kind: Kind,
  definition: Json,
  version: z.number().int(),
  author: z.object({ display_name: z.string(), role: z.string() }),
  updated_at: z.string(),
});

const Range = z.object({ min: z.number(), max: z.number() });
const SchemaRead = z.object({
  catalog: z.object({
    builder: z.object({
      indicators: z.array(
        z.object({
          name: z.string(),
          title: z.string(),
          category: z.string(),
          params: z.array(ParamSpecRead),
          outputs: z.array(z.string()),
          output_required: z.boolean(),
        }),
      ),
      price_fields: z.array(z.string()),
      ops: z.array(z.object({ op: z.string(), title: z.string(), operands: z.array(z.string()), bars: Range.optional() })),
      groups: z.array(z.string()),
      strengths: z.array(z.string()),
      categories: z.array(z.string()),
    }),
    composite: z.object({
      modes: z.array(z.string()),
      strategies: z.array(z.object({ key: z.string(), title: z.string(), params: z.array(ParamSpecRead) })),
    }),
    limits: z.object({
      max_depth: z.number(),
      max_conditions: z.number(),
      shift: Range,
      bars: Range,
      members: Range,
      window: Range,
    }),
  }),
});
const toCatalog = ({ catalog: c }: z.infer<typeof SchemaRead>): BuilderCatalog => ({
  indicators: c.builder.indicators.map((i) => ({ name: i.name, title: i.title, category: i.category, params: i.params.map(toParamSpec), outputs: i.outputs, outputRequired: i.output_required })),
  priceFields: c.builder.price_fields,
  ops: c.builder.ops.map((o) => ({ op: o.op, title: o.title, operands: o.operands, bars: o.bars ?? null })),
  groups: c.builder.groups,
  strengths: c.builder.strengths,
  categories: c.builder.categories,
  compositeModes: c.composite.modes,
  compositeStrategies: c.composite.strategies.map((s) => ({ key: s.key, title: s.title, params: s.params.map(toParamSpec) })),
  limits: {
    maxConditions: c.limits.max_conditions,
    maxDepth: c.limits.max_depth,
    shift: c.limits.shift,
    bars: c.limits.bars,
    members: c.limits.members,
    window: c.limits.window,
  },
});

/* ------------------------------------------------------------- backtests */

const Status = z.enum(['queued', 'running', 'completed', 'failed', 'cancelled']);
const InstrumentRef = z.object({ id: z.string(), symbol: z.string(), source: z.string() });
const Point = z.object({ time: z.number(), value: z.number() });
const BacktestSummaryRead = z.object({
  id: z.string(),
  status: Status,
  progress: z.number().int(),
  instrument: InstrumentRef,
  timeframe: Timeframe,
  strategy_key: z.string(),
  params: Json,
  start: z.string(),
  end: z.string(),
  bars: z.number().int().nullable(),
  error: z.string().nullable(),
  headline: Json.nullable(),
  created_at: z.string(),
  finished_at: z.string().nullable(),
});
const BacktestRead = BacktestSummaryRead.extend({
  config: Json,
  first_bar: z.string().nullable(),
  last_bar: z.string().nullable(),
  metrics: Json.nullable(),
  equity: z.array(Point),
  drawdown: z.array(Point),
  markers: z.array(MarkerRead).catch([]),
  duration_ms: z.number().int().nullable(),
});
const toBacktestSummary = (b: z.infer<typeof BacktestSummaryRead>): BacktestSummary => ({
  id: b.id,
  status: b.status,
  progress: b.progress,
  instrument: b.instrument,
  timeframe: b.timeframe,
  strategyKey: b.strategy_key,
  params: toParams(b.params),
  start: msReq(b.start),
  end: msReq(b.end),
  bars: b.bars,
  error: b.error,
  headline: b.headline,
  createdAt: msReq(b.created_at),
  finishedAt: ms(b.finished_at),
});
const toBacktest = (b: z.infer<typeof BacktestRead>): BacktestResult => ({
  ...toBacktestSummary(b),
  config: b.config,
  firstBar: ms(b.first_bar),
  lastBar: ms(b.last_bar),
  metrics: b.metrics,
  equity: b.equity,
  drawdown: b.drawdown,
  markers: toMarkers(b.markers),
  durationMs: b.duration_ms,
});

const TradeRead = z.object({
  number: z.number().int(),
  side: z.string(),
  entry_time: z.string(),
  entry_price: z.number(),
  exit_time: z.string(),
  exit_price: z.number(),
  quantity: z.number(),
  gross_pnl: z.number(),
  fees: z.number(),
  net_pnl: z.number(),
  return_pct: z.number(),
  bars_held: z.number().int(),
  entry_reason: z.string().nullable(),
  exit_reason: z.string(),
  initial_stop: z.number().nullable().optional(),
  risk_amount: z.number().nullable().optional(),
  r_multiple: z.number().nullable().optional(),
});
const toTrade = (t: z.infer<typeof TradeRead>): BacktestTrade => ({
  number: t.number,
  side: t.side,
  entryTime: msReq(t.entry_time),
  entryPrice: t.entry_price,
  exitTime: msReq(t.exit_time),
  exitPrice: t.exit_price,
  quantity: t.quantity,
  grossPnl: t.gross_pnl,
  fees: t.fees,
  netPnl: t.net_pnl,
  returnPct: t.return_pct,
  barsHeld: t.bars_held,
  entryReason: t.entry_reason,
  exitReason: t.exit_reason,
  initialStop: t.initial_stop ?? null,
  riskAmount: t.risk_amount ?? null,
  rMultiple: t.r_multiple ?? null,
});

const CompareRead = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      instrument: InstrumentRef,
      timeframe: z.string(),
      strategy_key: z.string(),
      params: Json,
      start: z.string(),
      end: z.string(),
      metrics: Json,
      equity: z.array(Point),
    }),
  ),
});

/* --------------------------------------------------------------- factories */

export function apiInstrumentDirectory(http: HttpClient): InstrumentDirectoryService {
  return {
    async list(o) {
      const p = await http.request('GET', endpoints.market.instruments, { query: { limit: 100 }, schema: page(InstrumentRead), ...opt(o?.signal) });
      return p.items.map(
        (i): BackendInstrument => ({ id: i.id, symbol: i.symbol, webSymbol: toSymbol(i.symbol), source: i.source, market: i.market, pricePrecision: i.price_precision, isActive: i.is_active }),
      );
    },
    async candles(instrumentId, timeframe, limit, o) {
      const s = await http.request('GET', endpoints.market.candles(instrumentId), { query: { timeframe, limit: Math.min(limit, 5000) }, schema: BackendCandleSeries, ...opt(o?.signal) });
      return s.candles.map((c) => ({ ...c, volume: Math.max(0, c.volume) }));
    },
  };
}

export function apiStrategyService(http: HttpClient): StrategyService {
  return {
    catalog: async (o) =>
      (await http.request('GET', endpoints.strategies.catalog, { schema: z.array(StrategyDefinitionRead), ...opt(o?.signal) })).map((s) => ({
        key: s.key,
        title: s.title,
        description: s.description,
        category: s.category,
        params: s.params.map(toParamSpec),
        indicators: s.indicators,
        history: s.history,
      })),
    listActivations: async (o) => (await http.request('GET', endpoints.strategies.mine, { schema: z.array(UserStrategyRead), ...opt(o?.signal) })).map(toActivation),
    activate: async (i) =>
      toActivation(
        await http.request('POST', endpoints.strategies.mine, {
          body: { strategy_key: i.strategyKey, instrument_id: i.instrumentId, timeframe: i.timeframe, params: i.params, name: i.name?.trim() || null, is_active: i.isActive, notify: i.notify },
          schema: UserStrategyRead,
        }),
      ),
    updateActivation: async (id, p) => {
      const body: Record<string, unknown> = {};
      if (p.name !== undefined) body.name = p.name?.trim() || null;
      if (p.params !== undefined) body.params = p.params;
      if (p.isActive !== undefined) body.is_active = p.isActive;
      if (p.notify !== undefined) body.notify = p.notify;
      return toActivation(await http.request('PATCH', endpoints.strategies.mineItem(id), { body, schema: UserStrategyRead }));
    },
    removeActivation: async (id) => {
      await http.request('DELETE', endpoints.strategies.mineItem(id), { schema: Empty });
    },
    preview: async (key, i, o) => {
      const r = await http.request('POST', endpoints.strategies.preview(key), {
        body: { instrument_id: i.instrumentId, timeframe: i.timeframe, params: i.params, limit: i.limit ?? 500 },
        schema: PreviewRead,
        ...opt(o?.signal),
      });
      return { strategyKey: r.strategy_key, params: toParams(r.params), bars: r.bars, signals: r.signals, markers: toMarkers(r.markers), indicators: r.indicators };
    },
    signalPlans: async (q, o) => {
      const p = await http.request('GET', endpoints.strategies.signalPlans, {
        query: { limit: Math.min(q?.limit ?? 50, 100), strategy_key: q?.strategyKey },
        schema: page(SignalPlanRead),
        ...opt(o?.signal),
      });
      return p.items.map((x) => ({
        id: x.id,
        activationId: x.user_strategy_id,
        plan: x.plan,
        createdAt: msReq(x.created_at),
        signal: {
          id: x.signal.id,
          instrumentId: x.signal.instrument_id,
          timeframe: x.signal.timeframe,
          strategyKey: x.signal.strategy_key,
          side: x.signal.side,
          strength: x.signal.strength,
          price: x.signal.price,
          reason: x.signal.reason,
          time: x.signal.time,
        },
      }));
    },
    listCustom: async (o) => (await http.request('GET', endpoints.customStrategies.mine, { query: { limit: 100 }, schema: page(CustomSummaryRead), ...opt(o?.signal) })).items.map(toSummary),
    getCustom: async (id, o) => toCustom(await http.request('GET', endpoints.customStrategies.item(id), { schema: CustomRead, ...opt(o?.signal) })),
    createCustom: async (i) =>
      toCustom(
        await http.request('POST', endpoints.customStrategies.mine, {
          body: { name: i.name.trim(), description: i.description.trim(), kind: i.kind, definition: i.definition, visibility: i.visibility },
          schema: CustomRead,
        }),
      ),
    replaceCustom: async (id, i) =>
      toCustom(
        await http.request('PUT', endpoints.customStrategies.item(id), {
          body: { version: i.version, definition: i.definition, ...(i.name !== undefined ? { name: i.name.trim() } : {}), ...(i.description !== undefined ? { description: i.description.trim() } : {}) },
          schema: CustomRead,
        }),
      ),
    updateCustom: async (id, p) => toCustom(await http.request('PATCH', endpoints.customStrategies.item(id), { body: p, schema: CustomRead })),
    removeCustom: async (id) => {
      await http.request('DELETE', endpoints.customStrategies.item(id), { schema: Empty });
    },
    cloneCustom: async (id) => toCustom(await http.request('POST', endpoints.customStrategies.clone(id), { schema: CustomRead })),
    builderCatalog: async (o) => toCatalog(await http.request('GET', endpoints.customStrategies.schema, { schema: SchemaRead, ...opt(o?.signal) })),
    validate: async (kind, definition, id) => {
      const r = await http.request('POST', endpoints.customStrategies.validate, { body: { kind, definition, ...(id ? { id } : {}) }, schema: ValidateRead });
      return { valid: r.valid, errors: r.errors, history: r.history, definition: r.definition };
    },
    listPublic: async (q, o) =>
      (
        await http.request('GET', endpoints.customStrategies.public, { query: { limit: 50, search: q?.search?.trim() || undefined }, schema: page(PublicRead), ...opt(o?.signal) })
      ).items.map((s) => ({
        id: s.id,
        key: s.key,
        name: s.name,
        description: s.description,
        kind: s.kind,
        definition: s.definition,
        version: s.version,
        author: { name: s.author.display_name, role: s.author.role },
        updatedAt: msReq(s.updated_at),
      })),
    clonePublic: async (id) => toCustom(await http.request('POST', endpoints.customStrategies.clonePublic(id), { schema: CustomRead })),
  };
}

export function apiBacktestService(http: HttpClient, socket: MarketSocket): BacktestService {
  return {
    create: async (i) =>
      http.request('POST', endpoints.backtests.list, {
        body: { instrument_id: i.instrumentId, timeframe: i.timeframe, strategy_key: i.strategyKey, params: i.params, start: i.start, end: i.end, ...(i.config ? { config: i.config } : {}) },
        schema: z.object({ id: z.string(), status: Status }),
      }),
    list: async (q, o) => {
      const p = await http.request('GET', endpoints.backtests.list, { query: { limit: q?.limit ?? 50, offset: q?.offset ?? 0 }, schema: page(BacktestSummaryRead), ...opt(o?.signal) });
      return { items: p.items.map(toBacktestSummary), total: p.total };
    },
    get: async (id, o) => toBacktest(await http.request('GET', endpoints.backtests.item(id), { schema: BacktestRead, ...opt(o?.signal) })),
    remove: async (id) => {
      await http.request('DELETE', endpoints.backtests.item(id), { schema: Empty });
    },
    trades: async (id, pg, o) => {
      const p = await http.request('GET', endpoints.backtests.trades(id), { query: { limit: Math.min(pg.limit, 500), offset: pg.offset }, schema: page(TradeRead), ...opt(o?.signal) });
      return { items: p.items.map(toTrade), total: p.total };
    },
    exportTradesCsv: (id) => http.request('GET', endpoints.backtests.tradesCsv(id), { schema: z.string(), responseType: 'text' }),
    compare: async (ids): Promise<BacktestComparison> => {
      const r = await http.request('POST', endpoints.backtests.compare, { body: { ids }, schema: CompareRead });
      return {
        items: r.items.map((x) => ({
          id: x.id,
          instrument: x.instrument,
          timeframe: x.timeframe,
          strategyKey: x.strategy_key,
          params: toParams(x.params),
          start: msReq(x.start),
          end: msReq(x.end),
          metrics: x.metrics,
          equity: x.equity,
        })),
      };
    },
    subscribe(onEvent): Unsubscribe {
      // docs/backtesting.md: backtest_progress / backtest_completed / backtest_failed on the user's topic.
      const handler = (msg: Record<string, unknown>) => {
        const parsed = Status.safeParse(msg.status);
        if (typeof msg.backtest_id !== 'string' || !parsed.success) return;
        onEvent({
          backtestId: msg.backtest_id,
          status: parsed.data,
          progress: typeof msg.progress === 'number' ? msg.progress : 0,
          error: typeof msg.error === 'string' ? msg.error : null,
        });
      };
      const offs = ['backtest_progress', 'backtest_completed', 'backtest_failed'].map((t) => socket.onUserEvent(t, handler));
      return () => offs.forEach((off) => off());
    },
  };
}
