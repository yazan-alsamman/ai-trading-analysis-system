import type { PriceAlert } from '@/domain/alerts';
import type { ChatMessage, Comment, Expert, NewsItem, Post } from '@/domain/community';
import { INSTRUMENT_SYMBOLS, type InstrumentSymbol } from '@/domain/instruments';
import type { Candle, CandleSeries, Timeframe } from '@/domain/market';
import type { StrategySignal } from '@/domain/strategySignals';
import type { User } from '@/domain/user';
import type { AppNotification } from '@/app/notifications';
import type { ArticleRead, CommentRead, ExpertCard, InstrumentRead, MessageRead, NotificationRead, PostRead, PriceAlertRead, SignalRead } from './backend';
import type { UserRead } from './backend';
import type { z } from 'zod';

/**
 * Pure mappings from the backend's shapes to the UI's domain types.
 * Rule: never invent a value the backend did not send. Missing data stays
 * missing (optional fields), and the UI says so.
 */

const ms = (iso: string): number => {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : 0;
};

/** "EUR/USD" → "EURUSD" when the web client supports it; crypto pairs and others → null. */
export function toSymbol(backendSymbol: string): InstrumentSymbol | null {
  const s = backendSymbol.replace(/[/_\-\s]/g, '').toUpperCase();
  return (INSTRUMENT_SYMBOLS as readonly string[]).includes(s) ? (s as InstrumentSymbol) : null;
}

export function toUser(u: z.infer<typeof UserRead>): User {
  return { id: u.id, email: u.email, name: u.full_name?.trim() || u.email.split('@')[0] || u.email, role: u.role };
}

/** Backend instruments the web client can show, keyed by web symbol (the first active one wins). */
export function instrumentIndex(items: readonly InstrumentRead[]): Map<InstrumentSymbol, InstrumentRead> {
  const map = new Map<InstrumentSymbol, InstrumentRead>();
  for (const i of items) {
    const sym = toSymbol(i.symbol);
    if (sym && i.is_active && !map.has(sym)) map.set(sym, i);
  }
  return map;
}

/**
 * Backend candles. Provenance is `live` in the client's vocabulary, which the
 * UI labels "Backend feed": the API does not say whether an instrument's
 * candles come from a real collector or from seeded demo data.
 */
export function toCandleSeries(raw: { candles: readonly Candle[] }, symbol: InstrumentSymbol, timeframe: Timeframe, market: string): CandleSeries {
  return {
    symbol,
    timeframe,
    candles: raw.candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close, volume: Math.max(0, c.volume) })),
    volumeKind: market === 'crypto' ? 'real' : 'tick',
    provenance: 'live',
    asOf: Date.now(),
  };
}

export function toPriceAlert(a: PriceAlertRead): PriceAlert | null {
  const symbol = toSymbol(a.instrument.symbol);
  if (!symbol) return null;
  const triggered = a.last_triggered_at ? ms(a.last_triggered_at) : undefined;
  return {
    id: a.id,
    symbol,
    condition: a.condition,
    price: a.value,
    // Delivery is decided by the server-side notification preferences, not per alert.
    channels: ['app'],
    ...(a.note ? { note: a.note } : {}),
    status: a.is_active ? 'active' : triggered !== undefined ? 'triggered' : 'paused',
    createdAt: ms(a.created_at),
    ...(triggered !== undefined ? { triggeredAt: triggered } : {}),
  };
}

export function toNewsItem(a: ArticleRead): NewsItem {
  const symbols = [...new Set(a.instruments.map((t) => toSymbol(t.symbol)).filter((s): s is InstrumentSymbol => s !== null))];
  return {
    id: a.id,
    title: a.title,
    summary: a.summary ?? '',
    source: a.source.name,
    publishedAt: ms(a.published_at),
    symbols,
    ...(a.sentiment ? { sentiment: { label: a.sentiment.label, score: a.sentiment.score } } : {}),
    url: a.url,
    commentCount: 0,
    commentsEnabled: false,
    provenance: 'live',
  };
}

export function toPost(p: PostRead): Post {
  const body = p.body.startsWith(p.title) ? p.body : `${p.title}\n\n${p.body}`;
  const sym = p.instrument ? toSymbol(p.instrument.symbol) : null;
  return {
    id: p.id,
    author: { id: p.author.id, name: p.author.display_name, role: p.author.role },
    body,
    symbols: sym ? [sym] : [],
    createdAt: ms(p.created_at),
    commentCount: p.comments_count,
    provenance: 'live',
    title: p.title,
    instrumentLabel: p.instrument?.symbol ?? null,
    ...(p.likes_count !== undefined ? { likes: p.likes_count } : {}),
    ...(p.liked_by_me !== undefined ? { likedByMe: p.liked_by_me } : {}),
    ...(p.can_edit !== undefined ? { canEdit: p.can_edit } : {}),
    ...(p.edited_at !== undefined ? { editedAt: p.edited_at ? ms(p.edited_at) : null } : {}),
    ...(p.direction !== undefined ? { direction: p.direction } : {}),
    ...(p.timeframe !== undefined ? { timeframe: p.timeframe } : {}),
    ...(p.visibility !== undefined ? { visibility: p.visibility } : {}),
    ...(p.status !== undefined ? { status: p.status } : {}),
  };
}

/** Threads (top-level + their replies) flattened in reading order. Removed comments are skipped. */
export function toComments(threads: readonly (CommentRead & { replies?: readonly CommentRead[] })[], threadId: string): Comment[] {
  const out: Comment[] = [];
  const add = (c: CommentRead) => {
    if (c.body === null || c.status !== 'published') return;
    out.push({
      id: c.id,
      threadId,
      author: c.author ? { id: c.author.id, name: c.author.display_name, role: c.author.role } : { id: 'deleted', name: 'Deleted account', role: 'trader' },
      body: c.body,
      createdAt: ms(c.created_at),
      parentId: c.parent_id,
      ...(c.can_edit !== undefined ? { canEdit: c.can_edit } : {}),
      ...(c.edited_at !== undefined ? { editedAt: c.edited_at ? ms(c.edited_at) : null } : {}),
    });
  };
  for (const t of threads) {
    add(t);
    for (const r of t.replies ?? []) add(r);
  }
  return out;
}

export function toExpert(e: ExpertCard): Expert {
  return {
    id: e.id,
    name: e.display_name,
    headline: e.headline,
    specialties: [],
    markets: [],
    marketCategories: e.markets,
    languages: e.languages,
    chatEnabled: e.chat_enabled,
    responseTimeHint: e.response_time_hint,
    cheapestPlan: e.cheapest_plan
      ? { name: e.cheapest_plan.name, price: e.cheapest_plan.price, currency: e.cheapest_plan.currency, interval: e.cheapest_plan.interval, trialDays: e.cheapest_plan.trial_days }
      : null,
    isSubscribed: e.is_subscribed,
    ...(e.followers_count !== undefined ? { followers: e.followers_count } : {}),
    ...(e.subscribers_count !== undefined ? { subscribers: e.subscribers_count } : {}),
    provenance: 'live',
  };
}

export function toChatMessage(m: MessageRead, myUserId: string): ChatMessage | null {
  if (m.deleted || m.body === null) return null;
  return { id: m.id, from: m.sender_id === myUserId ? 'user' : 'expert', body: m.body, sentAt: ms(m.created_at) };
}

export function toNotification(n: NotificationRead): AppNotification {
  return {
    id: n.id,
    kind: n.type === 'price_alert' ? 'price_alert' : n.type === 'signal' ? 'signal' : 'system',
    title: n.title,
    body: n.body,
    createdAt: ms(n.created_at),
    read: n.read_at !== null,
    provenance: 'live',
    remote: true,
  };
}

export function toStrategySignal(s: SignalRead, instrumentsById: ReadonlyMap<string, InstrumentRead>): StrategySignal {
  const inst = instrumentsById.get(s.instrument_id);
  return {
    id: s.id,
    symbol: inst ? toSymbol(inst.symbol) : null,
    instrumentLabel: inst?.symbol ?? 'Unknown instrument',
    timeframe: s.timeframe,
    strategyKey: s.strategy_key,
    side: s.side,
    strength: s.strength,
    price: s.price,
    reason: s.reason,
    details: s.details,
    time: s.time,
    createdAt: ms(s.created_at),
  };
}
