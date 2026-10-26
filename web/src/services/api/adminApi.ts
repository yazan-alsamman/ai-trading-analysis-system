import { z } from 'zod';
import { SETUP_STATES } from '@/domain/aiSetups';
import type { AdminAISetup, AdminInstrument, AdminReport, AdminSubscription, AdminUser, AIModel, AIOutboxRow, NewsSource } from '@/domain/admin';
import { isApiError } from '../errors';
import type { AdminService } from '../types';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';

/**
 * Administration (admin role; the server refuses everyone else with 403).
 * Typed where the backend types its responses; statistics and status blocks
 * whose shape the backend owns are passed through as JSON.
 */

const opt = (signal?: AbortSignal): { signal?: AbortSignal } => (signal ? { signal } : {});
const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
};
const msReq = (iso: string) => ms(iso) ?? 0;
const Json = z.record(z.string(), z.unknown());
const Empty = z.unknown();
const Role = z.enum(['trader', 'analyst', 'expert', 'admin']);
const State = z.enum(SETUP_STATES);
const page = <T extends z.ZodType>(item: T) => z.object({ items: z.array(item), total: z.number().int() });
const Person = z.object({ id: z.string(), display_name: z.string(), role: Role });

const UserRead = z.object({ id: z.string(), email: z.string(), full_name: z.string().nullable(), role: Role, is_active: z.boolean(), created_at: z.string() });
const toUser = (u: z.infer<typeof UserRead>): AdminUser => ({ id: u.id, email: u.email, name: u.full_name, role: u.role, isActive: u.is_active, createdAt: msReq(u.created_at) });

const ReportRead = z.object({
  id: z.string(),
  target_type: z.enum(['post', 'comment', 'message']),
  target_id: z.string(),
  reason: z.string(),
  status: z.enum(['open', 'resolved']),
  resolution: z.string().nullable(),
  created_at: z.string(),
  resolved_at: z.string().nullable(),
  reporter: Person.nullable().optional(),
  target: Json.nullable().optional(),
  open_reports_on_target: z.number().int().optional(),
});
const toReport = (r: z.infer<typeof ReportRead>): AdminReport => ({
  id: r.id,
  targetType: r.target_type,
  targetId: r.target_id,
  reason: r.reason,
  status: r.status,
  resolution: r.resolution,
  createdAt: msReq(r.created_at),
  resolvedAt: ms(r.resolved_at),
  reporter: r.reporter ? { id: r.reporter.id, name: r.reporter.display_name, role: r.reporter.role } : null,
  target: r.target ?? null,
  openReportsOnTarget: r.open_reports_on_target ?? 0,
});

const SubRead = z.object({
  id: z.string(),
  user: Person,
  expert: Person,
  plan_id: z.string(),
  status: z.string(),
  price: z.string(),
  currency: z.string(),
  interval: z.string(),
  current_period_end: z.string(),
  cancel_at_period_end: z.boolean(),
  past_due_since: z.string().nullable(),
  ended_at: z.string().nullable(),
  created_at: z.string(),
});
const toSub = (s: z.infer<typeof SubRead>): AdminSubscription => ({
  id: s.id,
  user: { id: s.user.id, name: s.user.display_name, role: s.user.role },
  expert: { id: s.expert.id, name: s.expert.display_name, role: s.expert.role },
  planId: s.plan_id,
  status: s.status,
  price: s.price,
  currency: s.currency,
  interval: s.interval,
  currentPeriodEnd: msReq(s.current_period_end),
  cancelAtPeriodEnd: s.cancel_at_period_end,
  pastDueSince: ms(s.past_due_since),
  endedAt: ms(s.ended_at),
  createdAt: msReq(s.created_at),
});

const KeyRead = z.object({
  id: z.string(),
  name: z.string(),
  prefix: z.string(),
  scopes: z.array(z.string()),
  rate_limit_per_minute: z.number().int().nullable(),
  expires_at: z.string().nullable(),
  last_used_at: z.string().nullable(),
  created_at: z.string(),
  user_id: z.string(),
  owner_email: z.string(),
  revoked: z.boolean(),
});

const SourceRead = z.object({
  id: z.string(),
  key: z.string(),
  name: z.string(),
  kind: z.enum(['rss', 'api', 'manual']),
  url: z.string().nullable(),
  language: z.string(),
  is_active: z.boolean(),
  fetch_interval_minutes: z.number().int(),
  last_fetched_at: z.string().nullable(),
  last_error: z.string().nullable(),
  articles: z.number().int().nullable().optional(),
});
export const toSource = (s: z.infer<typeof SourceRead>): NewsSource => ({
  id: s.id,
  key: s.key,
  name: s.name,
  kind: s.kind,
  url: s.url,
  language: s.language,
  isActive: s.is_active,
  fetchIntervalMinutes: s.fetch_interval_minutes,
  lastFetchedAt: ms(s.last_fetched_at),
  lastError: s.last_error,
  articles: s.articles ?? null,
});
export { SourceRead };

const SPEC_KEYS = ['contract_size', 'tick_size', 'lot_step', 'min_lot', 'max_lot', 'quote_currency', 'margin_rate', 'price_basis', 'session_calendar', 'cost_per_unit', 'spec_source', 'spec_updated_at'];
const InstrumentFull = z
  .object({
    id: z.string(),
    symbol: z.string(),
    source: z.string(),
    market: z.enum(['crypto', 'forex', 'stock', 'commodity']),
    base_asset: z.string(),
    quote_asset: z.string(),
    price_precision: z.number().int().nullable(),
    quantity_precision: z.number().int().nullable(),
    is_active: z.boolean(),
  })
  .loose();
const toInstrument = (i: z.infer<typeof InstrumentFull>): AdminInstrument => {
  const raw = i as Record<string, unknown>;
  return {
    id: i.id,
    symbol: i.symbol,
    source: i.source,
    market: i.market,
    baseAsset: i.base_asset,
    quoteAsset: i.quote_asset,
    pricePrecision: i.price_precision,
    quantityPrecision: i.quantity_precision,
    isActive: i.is_active,
    specs: Object.fromEntries(SPEC_KEYS.filter((k) => k in raw).map((k) => [k, raw[k]])),
  };
};

const SetupRead = z.object({
  setup_id: z.string(),
  instrument_id: z.string(),
  profile: z.string(),
  direction: z.string(),
  state: State,
  entry: z.number().nullable(),
  sl: z.number().nullable(),
  tp: z.number().nullable(),
  r_multiple: z.number().nullable(),
  probability: z.number().nullable(),
  grade: z.string().nullable(),
  realized_r: z.number().nullable(),
  strategy_version: z.string().nullable(),
  model_version: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
const toSetup = (s: z.infer<typeof SetupRead>): AdminAISetup => ({
  setupId: s.setup_id,
  instrumentId: s.instrument_id,
  profile: s.profile,
  direction: s.direction,
  state: s.state,
  entry: s.entry,
  sl: s.sl,
  tp: s.tp,
  rMultiple: s.r_multiple,
  probability: s.probability,
  grade: s.grade,
  realizedR: s.realized_r,
  strategyVersion: s.strategy_version,
  modelVersion: s.model_version,
  createdAt: msReq(s.created_at),
  updatedAt: msReq(s.updated_at),
});
const OutboxRead = z.object({
  id: z.number().int(),
  setup_id: z.string(),
  from_state: State.nullable(),
  to_state: State,
  status: z.string(),
  attempts: z.number().int(),
  last_error: z.string().nullable(),
  created_at: z.string(),
  processed_at: z.string().nullable(),
});
const toOutbox = (o: z.infer<typeof OutboxRead>): AIOutboxRow => ({
  id: o.id,
  setupId: o.setup_id,
  from: o.from_state,
  to: o.to_state,
  status: o.status,
  attempts: o.attempts,
  lastError: o.last_error,
  createdAt: msReq(o.created_at),
  processedAt: ms(o.processed_at),
});
const SetupDetailRead = SetupRead.extend({
  evidence: Json,
  last_payload: Json,
  events: z.array(z.object({ from_state: State.nullable(), to_state: State, at: z.string(), reason: z.string().nullable(), realized_r: z.number().nullable() })),
  sizes: z.array(z.object({ user_id: z.string(), lots: z.number(), feasible: z.boolean(), source: z.string(), computed_at: z.string() })),
  takes_count: z.number().int(),
  outbox: z.array(OutboxRead),
});
const ModelRead = z.object({
  model_id: z.string(),
  created_at: z.string(),
  training_from: z.string().nullable(),
  training_to: z.string().nullable(),
  data_hash: z.string().nullable(),
  metrics: Json,
  is_active: z.boolean(),
  notes: z.string().nullable(),
});
const toModel = (m: z.infer<typeof ModelRead>): AIModel => ({
  modelId: m.model_id,
  createdAt: msReq(m.created_at),
  trainingFrom: ms(m.training_from),
  trainingTo: ms(m.training_to),
  dataHash: m.data_hash,
  metrics: m.metrics,
  isActive: m.is_active,
  notes: m.notes,
});

const nonNull = <T extends Record<string, unknown>>(o: T) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>;
const json = (http: HttpClient, path: string, signal?: AbortSignal) => http.request('GET', path, { schema: Json, ...opt(signal) });

export function apiAdminService(http: HttpClient): AdminService {
  const a = endpoints.admin;
  return {
    /* system */
    systemStatus: (o) => json(http, a.systemStatus, o?.signal),
    realtimeStats: (o) => json(http, a.realtimeStats, o?.signal),
    rateLimitStats: (o) => json(http, a.rateLimitStats, o?.signal),
    notificationStats: (o) => json(http, a.notificationStats, o?.signal),
    paymentStats: (o) => json(http, a.paymentStats, o?.signal),
    readiness: async (o) => {
      // 503 with a body while a dependency is down: report it instead of failing.
      try {
        return await http.request('GET', endpoints.health.ready, { schema: Json, ...opt(o?.signal) });
      } catch (e) {
        // The server answers 503 while a dependency is down (its body is not kept for 5xx).
        if (isApiError(e) && e.status === 503) return { status: 'not_ready' };
        throw e;
      }
    },
    /* users */
    async users(q, o) {
      const res = await http.request('GET', a.users, {
        query: { limit: q.limit, offset: q.offset, ...(q.role ? { role: q.role } : {}), ...(q.isActive !== undefined ? { is_active: q.isActive } : {}), ...(q.search ? { q: q.search } : {}) },
        schema: page(UserRead),
        ...opt(o?.signal),
      });
      return { items: res.items.map(toUser), total: res.total };
    },
    setRole: async (id, role) => toUser(await http.request('PATCH', a.userRole(id), { body: { role }, schema: UserRead })),
    setActive: async (id, isActive) => toUser(await http.request('PATCH', a.userStatus(id), { body: { is_active: isActive }, schema: UserRead })),
    /* moderation */
    async reports(q, o) {
      const res = await http.request('GET', a.reports, { query: { status: q.status, limit: q.limit, offset: q.offset }, schema: page(ReportRead), ...opt(o?.signal) });
      return { items: res.items.map(toReport), total: res.total };
    },
    resolveReport: async (id, action, note) => toReport(await http.request('POST', a.resolveReport(id), { body: { action, note: note || null }, schema: ReportRead })),
    async conversations(q, o) {
      const res = await http.request('GET', a.conversations, { query: { ...(q.status ? { status: q.status } : {}), limit: q.limit, offset: q.offset }, schema: page(Json), ...opt(o?.signal) });
      return { items: res.items, total: res.total };
    },
    /* payments */
    async subscriptions(q, o) {
      const res = await http.request('GET', a.subscriptions, { query: { ...(q.status ? { status: q.status } : {}), limit: q.limit, offset: q.offset }, schema: page(SubRead), ...opt(o?.signal) });
      return { items: res.items.map(toSub), total: res.total };
    },
    async refundInvoice(invoiceId) {
      const r = await http.request('POST', a.refund(invoiceId), {
        schema: z.object({ id: z.string(), number: z.string(), amount: z.string(), currency: z.string(), status: z.string(), refunded_at: z.string().nullable() }),
      });
      return { id: r.id, number: r.number, amount: r.amount, currency: r.currency, status: r.status, refundedAt: ms(r.refunded_at) };
    },
    async fastForward(subId, to) {
      const r = await http.request('POST', a.fastForward(subId), { body: { to }, schema: z.object({ outcome: z.string(), subscription: SubRead }) });
      return { outcome: r.outcome, subscription: toSub(r.subscription) };
    },
    /* API keys */
    async apiKeys(q, o) {
      const res = await http.request('GET', a.apiKeys, { query: { limit: q.limit, offset: q.offset, ...(q.revoked !== undefined ? { revoked: q.revoked } : {}) }, schema: page(KeyRead), ...opt(o?.signal) });
      return {
        total: res.total,
        items: res.items.map((k) => ({
          id: k.id,
          name: k.name,
          prefix: k.prefix,
          scopes: k.scopes,
          ownerEmail: k.owner_email,
          userId: k.user_id,
          rateLimitPerMinute: k.rate_limit_per_minute,
          expiresAt: ms(k.expires_at),
          lastUsedAt: ms(k.last_used_at),
          revoked: k.revoked,
          createdAt: msReq(k.created_at),
        })),
      };
    },
    revokeApiKey: async (id) => {
      await http.request('DELETE', a.apiKey(id), { schema: Empty });
    },
    /* notifications */
    async broadcast(input) {
      const r = await http.request('POST', a.broadcast, { body: { title: input.title, body: input.body, severity: input.severity, roles: input.roles }, schema: z.object({ broadcast_id: z.string(), recipients: z.number().int() }) });
      return { broadcastId: r.broadcast_id, recipients: r.recipients };
    },
    /* news */
    newsSources: async (o) => (await http.request('GET', endpoints.newsExtra.sources, { schema: z.array(SourceRead), ...opt(o?.signal) })).map(toSource),
    updateNewsSource: async (id, patch) => toSource(await http.request('PATCH', a.newsSource(id), { body: nonNull({ is_active: patch.isActive, fetch_interval_minutes: patch.fetchIntervalMinutes }), schema: SourceRead })),
    async publishArticle(input) {
      const article = {
        source_key: input.sourceKey,
        external_id: input.externalId,
        url: input.url,
        title: input.title,
        summary: input.summary,
        published_at: input.publishedAt,
        language: input.language,
        ...(input.instruments.length ? { instruments: input.instruments } : {}),
        ...(input.sentiment ? { sentiment: input.sentiment } : {}),
      };
      const IssueList = z.array(z.object({ index: z.number().int(), error: z.string() }).loose());
      const r = await http.request('POST', endpoints.ingest.news, {
        body: { articles: [article] },
        schema: z.object({ inserted: z.number().int(), updated: z.number().int(), skipped: z.number().int(), errors: IssueList, warnings: IssueList.optional().default([]) }),
      });
      return { inserted: r.inserted, updated: r.updated, skipped: r.skipped, errors: r.errors.map((e) => ({ index: e.index, error: e.error })), warnings: r.warnings.map((e) => ({ index: e.index, error: e.error })) };
    },
    async setSentiment(articleId, sentiment) {
      const r = await http.request('POST', endpoints.ingest.sentiment, {
        body: { items: [{ article_id: articleId, ...sentiment }] },
        schema: z.object({ updated: z.number().int(), errors: z.array(z.object({ error: z.string() }).loose()) }),
      });
      return { updated: r.updated, errors: r.errors.map((e) => e.error) };
    },
    /* calendar */
    refreshCalendar: () => http.request('POST', a.calendarRefresh, { schema: Json }),
    importCalendar(file, q) {
      const form = new FormData();
      form.append('file', file);
      return http.request('POST', a.calendarImport, {
        formData: form,
        query: { dry_run: q.dryRun, source: q.source, ...(q.tz ? { tz: q.tz } : {}), ...(q.from ? { from: q.from } : {}) },
        schema: Json,
      });
    },
    /* instruments */
    instruments: async (o) =>
      (await http.request('GET', endpoints.market.instruments, { query: { limit: 100 }, schema: page(InstrumentFull), ...opt(o?.signal) })).items.map(toInstrument),
    createInstrument: async (input) => toInstrument(await http.request('POST', a.instruments, { body: input, schema: InstrumentFull })),
    updateInstrument: async (id, patch) => toInstrument(await http.request('PATCH', a.instrument(id), { body: patch, schema: InstrumentFull })),
    async uploadCandles(id, candles) {
      const r = await http.request('POST', a.instrumentCandles(id), { body: { candles }, schema: z.object({ written: z.number().int() }) });
      return r.written;
    },
    /* cTrader feed */
    ctraderStatus: (o) => json(http, a.ctrader, o?.signal),
    ctraderConnect: () => http.request('GET', a.ctraderConnect, { schema: Json }),
    ctraderCode: (code, state) => http.request('POST', a.ctraderCode, { body: { code, state }, schema: Json }),
    ctraderAccount: (accountId) => http.request('PATCH', a.ctrader, { body: { account_id: accountId }, schema: Json }),
    ctraderBackfill: (from, to) => http.request('POST', a.ctraderBackfill, { body: { from, to }, schema: Json }),
    /* AI engine */
    async aiSetups(q, o) {
      const res = await http.request('GET', a.aiSetups, { query: { limit: q.limit, ...(q.state ? { state: q.state } : {}), ...(q.instrumentId ? { instrument_id: q.instrumentId } : {}) }, schema: z.array(SetupRead), ...opt(o?.signal) });
      return res.map(toSetup);
    },
    async aiSetup(id, o) {
      const d = await http.request('GET', a.aiSetup(id), { schema: SetupDetailRead, ...opt(o?.signal) });
      return {
        ...toSetup(d),
        events: d.events.map((e) => ({ from: e.from_state, to: e.to_state, at: msReq(e.at), reason: e.reason, realizedR: e.realized_r })),
        sizes: d.sizes.map((s) => ({ userId: s.user_id, lots: s.lots, feasible: s.feasible, source: s.source, computedAt: msReq(s.computed_at) })),
        takesCount: d.takes_count,
        outbox: d.outbox.map(toOutbox),
        evidence: d.evidence,
        lastPayload: d.last_payload,
      };
    },
    async aiOutbox(q, o) {
      const res = await http.request('GET', a.aiOutbox, { query: { limit: q.limit, offset: q.offset, ...(q.status ? { status: q.status } : {}) }, schema: page(OutboxRead), ...opt(o?.signal) });
      return { items: res.items.map(toOutbox), total: res.total };
    },
    retryOutbox: async (id) => toOutbox(await http.request('POST', a.aiOutboxRetry(id), { schema: OutboxRead })),
    aiModels: async (o) => (await http.request('GET', a.aiModels, { schema: z.array(ModelRead), ...opt(o?.signal) })).map(toModel),
    registerModel: async (input) =>
      toModel(
        await http.request('POST', a.aiModels, {
          body: { model_id: input.modelId, training_from: input.trainingFrom, training_to: input.trainingTo, data_hash: input.dataHash, metrics: input.metrics, notes: input.notes },
          schema: ModelRead,
        }),
      ),
    activateModel: async (id) => toModel(await http.request('POST', a.aiModelActivate(id), { schema: ModelRead })),
  };
}
