import { z } from 'zod';

/**
 * Zod schemas of the FastAPI backend's OWN response shapes (docs/api/openapi.json).
 * They validate exactly what the client reads; unknown fields are ignored so
 * additive backend changes do not break the client. Mapping to the UI's domain
 * types happens in ./mappers.ts.
 */

const Uuid = z.string().min(1);
const IsoDate = z.string().min(1);

export const page = <T extends z.ZodType>(item: T) => z.object({ items: z.array(item), total: z.number().int(), limit: z.number().int(), offset: z.number().int() });

export const Role = z.enum(['trader', 'analyst', 'expert', 'admin']);

export const UserRead = z.object({
  id: Uuid,
  email: z.string(),
  full_name: z.string().nullable(),
  role: Role,
  is_active: z.boolean(),
});

export const InstrumentRead = z.object({
  id: Uuid,
  symbol: z.string(),
  source: z.string(),
  market: z.string(),
  base_asset: z.string(),
  quote_asset: z.string(),
  price_precision: z.number().int().nullable(),
  is_active: z.boolean(),
});
export type InstrumentRead = z.infer<typeof InstrumentRead>;

export const CandleOut = z.object({ time: z.number().int(), open: z.number(), high: z.number(), low: z.number(), close: z.number(), volume: z.number() });

export const BackendCandleSeries = z.object({
  instrument_id: Uuid,
  timeframe: z.string(),
  candles: z.array(CandleOut),
});

export const SignalRead = z.object({
  id: Uuid,
  instrument_id: Uuid,
  timeframe: z.string(),
  strategy_key: z.string(),
  side: z.enum(['buy', 'sell']),
  strength: z.number(),
  price: z.number(),
  reason: z.string(),
  details: z.record(z.string(), z.unknown()),
  time: z.number().int(),
  created_at: IsoDate,
});
export type SignalRead = z.infer<typeof SignalRead>;

export const RiskProfileRead = z.object({
  account_size: z.number(),
  quote_currency: z.string(),
  config: z.record(z.string(), z.unknown()),
  template: z.string().nullable(),
  updated_at: IsoDate,
});
export type RiskProfileRead = z.infer<typeof RiskProfileRead>;

export const PositionSizeResponse = z.object({
  instrument_id: Uuid,
  timeframe: z.string(),
  bar_time: IsoDate,
  account_size: z.number(),
  quote_currency: z.string(),
  plan: z.object({
    side: z.string(),
    entry_ref: z.number().nullable(),
    stop: z.number().nullable(),
    quantity: z.number().nullable(),
    notional: z.number().nullable(),
    risk_amount: z.number().nullable(),
    risk_pct: z.number().nullable(),
    rr: z.number().nullable().optional(),
    invalid_reason: z.string().nullable(),
  }),
});
export type PositionSizeResponse = z.infer<typeof PositionSizeResponse>;

export const PriceAlertRead = z.object({
  id: Uuid,
  instrument: z.object({ id: Uuid, symbol: z.string() }),
  condition: z.enum(['above', 'below', 'crosses_above', 'crosses_below', 'change_pct']),
  value: z.number(),
  repeat: z.enum(['once', 'every']),
  note: z.string().nullable(),
  is_active: z.boolean(),
  last_triggered_at: IsoDate.nullable(),
  trigger_count: z.number().int(),
  created_at: IsoDate,
});
export type PriceAlertRead = z.infer<typeof PriceAlertRead>;

export const NotificationRead = z.object({
  id: Uuid,
  type: z.string(),
  title: z.string(),
  body: z.string(),
  severity: z.enum(['info', 'success', 'warning', 'critical']),
  created_at: IsoDate,
  read_at: IsoDate.nullable(),
});
export type NotificationRead = z.infer<typeof NotificationRead>;

export const UnreadCount = z.object({ count: z.number().int().nonnegative() });

export const ArticleRead = z.object({
  id: Uuid,
  source: z.object({ key: z.string(), name: z.string() }),
  url: z.string(),
  title: z.string(),
  summary: z.string().nullable(),
  published_at: IsoDate,
  sentiment: z.object({ label: z.string(), score: z.number().nullable() }).nullable(),
  instruments: z.array(z.object({ instrument_id: Uuid, symbol: z.string(), relevance: z.number() })),
});
export type ArticleRead = z.infer<typeof ArticleRead>;

const AuthorRead = z.object({ id: Uuid, display_name: z.string(), role: Role });

export const PostRead = z.object({
  id: Uuid,
  author: AuthorRead,
  title: z.string(),
  body: z.string(),
  instrument: z.object({ id: Uuid, symbol: z.string() }).nullable(),
  comments_count: z.number().int().nonnegative(),
  created_at: IsoDate,
  // Optional so older recordings still parse; the live backend always sends them.
  likes_count: z.number().int().nonnegative().optional(),
  liked_by_me: z.boolean().optional(),
  can_edit: z.boolean().optional(),
  edited_at: IsoDate.nullable().optional(),
  timeframe: z.string().nullable().optional(),
  direction: z.enum(['bullish', 'bearish', 'neutral']).nullable().optional(),
  visibility: z.enum(['public', 'followers', 'subscribers']).optional(),
  status: z.enum(['published', 'hidden', 'deleted']).optional(),
});
export type PostRead = z.infer<typeof PostRead>;

export const CommentRead = z.object({
  id: Uuid,
  post_id: Uuid,
  parent_id: Uuid.nullable(),
  author: AuthorRead.nullable(),
  body: z.string().nullable(),
  status: z.string(),
  created_at: IsoDate,
  can_edit: z.boolean().optional(),
  edited_at: IsoDate.nullable().optional(),
});
export type CommentRead = z.infer<typeof CommentRead>;

/** Top-level comments come back as threads with their first replies. */
export const ThreadRead = CommentRead.extend({ replies: z.array(CommentRead).default([]) });

export const ExpertCard = z.object({
  id: Uuid,
  display_name: z.string(),
  headline: z.string(),
  markets: z.array(z.string()),
  languages: z.array(z.string()),
  chat_enabled: z.boolean(),
  response_time_hint: z.string().nullable(),
  cheapest_plan: z.object({ name: z.string(), price: z.string(), currency: z.string(), interval: z.string(), trial_days: z.number().int() }).nullable(),
  is_subscribed: z.boolean(),
  followers_count: z.number().int().optional(),
  subscribers_count: z.number().int().optional(),
});
export type ExpertCard = z.infer<typeof ExpertCard>;

export const ConversationRead = z.object({
  id: Uuid,
  expert_id: Uuid,
  user_id: Uuid,
  can_send: z.boolean(),
  read_only_reason: z.string().nullable(),
});

export const MessageRead = z.object({
  id: Uuid,
  conversation_id: Uuid,
  sender_id: Uuid,
  body: z.string().nullable(),
  deleted: z.boolean(),
  created_at: IsoDate,
});
export type MessageRead = z.infer<typeof MessageRead>;

export const MessagePage = z.object({ items: z.array(MessageRead), next_before: z.string().nullable() });
