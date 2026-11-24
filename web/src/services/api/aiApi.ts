import { z } from 'zod';
import { AI_GRADES, SETUP_STATES, type AISetup, type AITake, type AITrade } from '@/domain/aiSetups';
import { EVENT_IMPACTS, type CalendarEvent } from '@/domain/calendar';
import type { AISetupService, CalendarService } from '../types';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';
import type { MarketSocket } from './marketSocket';

/**
 * AI setups (docs/ai-contract.md, docs/notifications.md B11) and the economic
 * calendar (docs/economic-calendar.md). Every value shown comes from the
 * backend; v1 has no model, so probability, EV and grade stay null and are
 * never filled in by the client.
 */

const opt = (signal?: AbortSignal): { signal?: AbortSignal } => (signal ? { signal } : {});
const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
};
const msReq = (iso: string) => ms(iso) ?? 0;
const num = z.number().nullable().optional().transform((v) => v ?? null);
const str = z.string().nullable().optional().transform((v) => v ?? null);
const State = z.enum(SETUP_STATES);
const Grade = z.enum(AI_GRADES).nullable().optional().catch(null).transform((v) => v ?? null);
const page = <T extends z.ZodType>(item: T) => z.object({ items: z.array(item), total: z.number().int(), limit: z.number().int(), offset: z.number().int() });

/* ------------------------------------------------------------- setups */

/** `data` of an `ai_setup` notification (alerts._base_data). */
const SetupAlertData = z.object({
  setup_id: z.string(),
  state: State,
  transition: z.object({ at: z.string() }).partial().nullable().optional(),
  direction: z.enum(['buy', 'sell']),
  instrument: z
    .object({ id: z.string(), symbol: z.string(), price_precision: z.number().int().nullable().optional() })
    .nullable()
    .optional(),
  profile: str,
  entry: num,
  sl: num,
  tp: num,
  r_multiple: num,
  probability: num,
  ev_r: num,
  grade: Grade,
  valid_until: str,
  reason: str,
  realized_r: num,
  late: z.boolean().optional().default(false),
});
const NotificationWithData = z.object({ id: z.string(), type: z.string(), created_at: z.string(), data: z.record(z.string(), z.unknown()) });

function toSetup(d: z.infer<typeof SetupAlertData>, fallbackAt: number): AISetup {
  return {
    setupId: d.setup_id,
    state: d.state,
    direction: d.direction,
    instrument: d.instrument ? { id: d.instrument.id, symbol: d.instrument.symbol, pricePrecision: d.instrument.price_precision ?? null } : null,
    profile: d.profile,
    entry: d.entry,
    sl: d.sl,
    tp: d.tp,
    rMultiple: d.r_multiple,
    probability: d.probability,
    evR: d.ev_r,
    grade: d.grade,
    validUntil: ms(d.valid_until),
    reason: d.reason,
    realizedR: d.realized_r,
    updatedAt: ms(d.transition?.at) ?? fallbackAt,
    late: d.late,
  };
}

/** ai-service's Setup object as sent in a live frame (unknown fields are ignored). */
const LiveSetup = z.object({
  setup_id: z.string(),
  state: State,
  direction: z.enum(['buy', 'sell']),
  profile: str,
  entry: num,
  sl: num,
  tp: num,
  r_multiple: num,
  probability: num,
  ev_r: num,
  grade: Grade,
  valid_until: str,
});
const LiveFrame = z.object({
  type: z.literal('ai_setup'),
  setup: LiveSetup,
  transition: z.object({ at: z.string().optional(), reason: z.string().nullable().optional(), realized_r: z.number().nullable().optional() }).optional(),
});

const SizeRead = z.object({
  setup_id: z.string(),
  lots: z.number(),
  risk_amount: z.number(),
  margin_required: z.number().nullable(),
  feasible: z.boolean(),
  warnings: z.array(z.string()),
  source: z.string(),
  computed_at: z.string(),
  inputs: z.object({
    balance: z.number(),
    currency: z.string(),
    leverage: z.number(),
    risk_per_trade_pct: z.number(),
    daily_loss_limit_pct: z.number(),
    max_drawdown_pct: z.number(),
    sources: z.record(z.string(), z.string()),
  }),
  taken: z.boolean(),
});
const ExplanationRead = z.object({ setup_id: z.string(), lang: z.enum(['ar', 'en']), explanation: z.string().nullable(), explanation_status: z.string() });
const TakeRead = z.object({
  setup_id: z.string(),
  taken_at: z.string(),
  lots: z.number().nullable(),
  risk_amount: z.number().nullable(),
  entry_price: z.number().nullable(),
  closed_at: z.string().nullable(),
  realized_r: z.number().nullable(),
  pnl: z.number().nullable(),
  close_reason: z.string().nullable(),
});
const TradeRead = TakeRead.extend({
  instrument_id: z.string(),
  profile: z.string(),
  direction: z.string(),
  state: State,
  entry: z.number().nullable(),
  sl: z.number().nullable(),
  tp: z.number().nullable(),
});
const FollowRead = z.object({ instrument_id: z.string(), profile: z.string(), min_grade: Grade, created_at: z.string() });

const toTake = (t: z.infer<typeof TakeRead>): AITake => ({
  setupId: t.setup_id,
  takenAt: msReq(t.taken_at),
  lots: t.lots,
  riskAmount: t.risk_amount,
  entryPrice: t.entry_price,
  closedAt: ms(t.closed_at),
  realizedR: t.realized_r,
  pnl: t.pnl,
  closeReason: t.close_reason,
});
const toTrade = (t: z.infer<typeof TradeRead>): AITrade => ({
  ...toTake(t),
  instrumentId: t.instrument_id,
  profile: t.profile,
  direction: t.direction,
  state: t.state,
  entry: t.entry,
  sl: t.sl,
  tp: t.tp,
});

export function apiAISetupService(http: HttpClient, socket: MarketSocket): AISetupService {
  return {
    async follows(o) {
      const list = await http.request('GET', endpoints.aiSetups.follows, { schema: z.array(FollowRead), ...opt(o?.signal) });
      return list.map((f) => ({ instrumentId: f.instrument_id, profile: f.profile, minGrade: f.min_grade, createdAt: msReq(f.created_at) }));
    },
    async follow(instrumentId, profile, minGrade) {
      const f = await http.request('PUT', endpoints.aiSetups.follow(instrumentId, profile), { body: { min_grade: minGrade }, schema: FollowRead });
      return { instrumentId: f.instrument_id, profile: f.profile, minGrade: f.min_grade, createdAt: msReq(f.created_at) };
    },
    async unfollow(instrumentId, profile) {
      await http.request('DELETE', endpoints.aiSetups.follow(instrumentId, profile), { schema: z.unknown() });
    },
    async recent(o) {
      // The setups the server told this user about (ARMED for followers, outcomes for takers),
      // newest first; the latest state of each setup wins.
      const res = await http.request('GET', endpoints.notifications.list, {
        query: { type: 'ai_setup', limit: 100 },
        schema: page(NotificationWithData),
        ...opt(o?.signal),
      });
      const latest = new Map<string, AISetup>();
      for (const n of res.items) {
        const parsed = SetupAlertData.safeParse(n.data);
        if (!parsed.success) continue; // never guess a setup from a malformed item
        const setup = toSetup(parsed.data, msReq(n.created_at));
        const cur = latest.get(setup.setupId);
        if (!cur || setup.updatedAt > cur.updatedAt) latest.set(setup.setupId, setup);
      }
      return [...latest.values()].sort((a, b) => b.updatedAt - a.updatedAt);
    },
    async size(setupId, o) {
      const s = await http.request('GET', endpoints.aiSetups.size(setupId), { schema: SizeRead, ...opt(o?.signal) });
      return {
        setupId: s.setup_id,
        lots: s.lots,
        riskAmount: s.risk_amount,
        marginRequired: s.margin_required,
        feasible: s.feasible,
        warnings: s.warnings,
        source: s.source,
        computedAt: msReq(s.computed_at),
        inputs: {
          balance: s.inputs.balance,
          currency: s.inputs.currency,
          leverage: s.inputs.leverage,
          riskPerTradePct: s.inputs.risk_per_trade_pct,
          dailyLossLimitPct: s.inputs.daily_loss_limit_pct,
          maxDrawdownPct: s.inputs.max_drawdown_pct,
          sources: s.inputs.sources,
        },
        taken: s.taken,
      };
    },
    async explanation(setupId, lang, o) {
      const e = await http.request('GET', endpoints.aiSetups.explanation(setupId), { query: { lang }, schema: ExplanationRead, ...opt(o?.signal) });
      return { setupId: e.setup_id, lang: e.lang, text: e.explanation, status: e.explanation_status };
    },
    async take(setupId, input) {
      const body: Record<string, number> = {};
      if (input.lots !== null) body.lots = input.lots;
      if (input.entryPrice !== null) body.entry_price = input.entryPrice;
      return toTake(await http.request('POST', endpoints.aiSetups.take(setupId), { body, schema: TakeRead }));
    },
    async untake(setupId) {
      await http.request('DELETE', endpoints.aiSetups.take(setupId), { schema: z.unknown() });
    },
    async trades(p, o) {
      const res = await http.request('GET', endpoints.aiSetups.trades, { query: { limit: Math.min(p.limit, 100), offset: p.offset }, schema: page(TradeRead), ...opt(o?.signal) });
      return { items: res.items.map(toTrade), total: res.total };
    },
    subscribe(instrument, onEvent) {
      return socket.subscribeTopic('ai_setups', instrument.id, `ai:setups:${instrument.id}`, (msg) => {
        const f = LiveFrame.safeParse(msg);
        if (!f.success) return;
        const s = f.data.setup;
        onEvent({
          instrumentId: instrument.id,
          setup: {
            setupId: s.setup_id,
            state: s.state,
            direction: s.direction,
            instrument: { id: instrument.id, symbol: instrument.symbol, pricePrecision: instrument.pricePrecision },
            profile: s.profile,
            entry: s.entry,
            sl: s.sl,
            tp: s.tp,
            rMultiple: s.r_multiple,
            probability: s.probability,
            evR: s.ev_r,
            grade: s.grade,
            validUntil: ms(s.valid_until),
            reason: f.data.transition?.reason ?? null,
            realizedR: f.data.transition?.realized_r ?? null,
            updatedAt: ms(f.data.transition?.at) ?? Date.now(),
            late: false,
          },
        });
      });
    },
  };
}

/* ----------------------------------------------------------- calendar */

const EventRead = z.object({
  event_key: z.string(),
  scheduled_at: z.string().nullable(),
  scheduled_date: z.string(),
  time_label: z.string().nullable(),
  currency: z.string(),
  impact: z.enum(EVENT_IMPACTS),
  title: z.string(),
  actual: z.string().nullable(),
  forecast: z.string().nullable(),
  previous: z.string().nullable(),
  fetched_at: z.string(),
  source: z.string(),
});
const toEvent = (e: z.infer<typeof EventRead>): CalendarEvent => ({
  key: e.event_key,
  scheduledAt: ms(e.scheduled_at),
  scheduledDate: e.scheduled_date,
  timeLabel: e.time_label,
  currency: e.currency,
  impact: e.impact,
  title: e.title,
  actual: e.actual,
  forecast: e.forecast,
  previous: e.previous,
  fetchedAt: msReq(e.fetched_at),
  source: e.source,
});

export function apiCalendarService(http: HttpClient): CalendarService {
  return {
    async events(q, o) {
      const res = await http.request('GET', endpoints.calendar.events, {
        query: {
          start: new Date(q.start).toISOString(),
          end: new Date(q.end).toISOString(),
          ...(q.currencies?.length ? { currencies: q.currencies.join(',') } : {}),
          ...(q.minImpact ? { min_impact: q.minImpact } : {}),
        },
        schema: z.object({ as_of: z.string(), events: z.array(EventRead) }),
        ...opt(o?.signal),
      });
      return { asOf: msReq(res.as_of), events: res.events.map(toEvent) };
    },
    async history(key, o) {
      const res = await http.request('GET', endpoints.calendar.history(key), { schema: z.object({ versions: z.array(EventRead) }), ...opt(o?.signal) });
      return res.versions.map(toEvent);
    },
  };
}
