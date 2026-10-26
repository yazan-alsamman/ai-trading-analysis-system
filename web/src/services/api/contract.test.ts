import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { TokenPairSchema } from '../schemas';
import {
  ArticleRead,
  BackendCandleSeries,
  ConversationRead,
  ExpertCard,
  InstrumentRead,
  MessagePage,
  NotificationRead,
  page,
  PositionSizeResponse,
  PostRead,
  PriceAlertRead,
  RiskProfileRead,
  SignalRead,
  ThreadRead,
  UnreadCount,
  UserRead,
} from './backend';
import { toChatMessage, toComments, toExpert, toNewsItem, toNotification, toPost, toPriceAlert, toStrategySignal, toSymbol, toUser } from './mappers';

/**
 * Contract tests against RECORDED responses of the real backend
 * (docs/postman/tools/examples.json, captured from the running FastAPI stack and
 * kept in sync with the OpenAPI document by the backend team). If the backend
 * changes a shape the web client reads, these tests fail.
 */
type Recorded = Record<string, { code: number; body: string }[]>;
// Tests run from web/ (package root); the recordings live in the monorepo's docs/.
const examples = JSON.parse(readFileSync(resolve(process.cwd(), '../docs/postman/tools/examples.json'), 'utf8')) as Recorded;
const body = (name: string): unknown => {
  const e = examples[name]?.[0];
  if (!e) throw new Error(`No recorded example "${name}"`);
  return JSON.parse(e.body);
};

describe('recorded backend responses parse with the client schemas', () => {
  it.each([
    ['auth_login', TokenPairSchema],
    ['auth_refresh', TokenPairSchema],
    ['users_me', UserRead],
    ['users_me_update', UserRead],
    ['market_instruments', page(InstrumentRead)],
    ['market_candles', BackendCandleSeries],
    ['signals_list', page(SignalRead)],
    ['risk_profile_get', RiskProfileRead],
    ['risk_profile_put', RiskProfileRead],
    ['risk_position_size', PositionSizeResponse],
    ['alerts_list', page(PriceAlertRead)],
    ['alerts_create', PriceAlertRead],
    ['alerts_update', PriceAlertRead],
    ['notif_list', page(NotificationRead)],
    ['notif_unread_count', UnreadCount],
    ['news_list', page(ArticleRead)],
    ['posts_feed', page(PostRead)],
    ['posts_create', PostRead],
    ['comments_list', page(ThreadRead)],
    ['experts_list', page(ExpertCard)],
    ['chat_open', ConversationRead],
    ['chat_history', MessagePage],
  ] as const)('%s', (name, schema) => {
    const r = schema.safeParse(body(name));
    expect(r.success, r.success ? '' : JSON.stringify(r.error.issues.slice(0, 3))).toBe(true);
  });
});

describe('mapping recorded responses to the UI domain', () => {
  it('user and symbols', () => {
    const u = toUser(UserRead.parse(body('users_me')));
    expect(u).toMatchObject({ email: 'trader@example.com', name: 'Sara Trader', role: 'expert' });
    expect(toSymbol('XAU/USD')).toBe('XAUUSD');
    expect(toSymbol('EUR/USD')).toBe('EURUSD');
    expect(toSymbol('BTC/USDT')).toBeNull(); // crypto is not a web-client instrument
  });

  it('strategy signals keep what the backend says and nothing more', () => {
    const instruments = page(InstrumentRead).parse(body('market_instruments')).items;
    const s = page(SignalRead).parse(body('signals_list')).items[0];
    if (!s) throw new Error('no signal');
    const byId = new Map(instruments.map((i) => [i.id, i]));
    const mapped = toStrategySignal(s, byId);
    // Compared with the recording itself, so a re-recorded example (different strategy) stays valid.
    expect(mapped).toMatchObject({ strategyKey: s.strategy_key, side: s.side, reason: s.reason, instrumentLabel: byId.get(s.instrument_id)?.symbol });
    expect(mapped.symbol).toBe(toSymbol(byId.get(s.instrument_id)?.symbol ?? ''));
    expect(mapped).not.toHaveProperty('probability');
  });

  it('price alerts: crypto alerts are skipped, others mapped with server delivery', () => {
    const alerts = page(PriceAlertRead).parse(body('alerts_list')).items;
    const fx = alerts.map((a) => ({ ...a, instrument: { ...a.instrument, symbol: 'XAU/USD' } }));
    for (const a of alerts) expect(toPriceAlert(a)).toBeNull(); // recorded alerts are on BTC/USDT
    const mapped = fx.map(toPriceAlert);
    expect(mapped[0]).toMatchObject({ symbol: 'XAUUSD', channels: ['app'] });
    expect(['active', 'paused', 'triggered']).toContain(mapped[0]?.status);
  });

  it('news: no invented impact; sentiment and source link kept; comments disabled', () => {
    const items = page(ArticleRead).parse(body('news_list')).items.map(toNewsItem);
    const first = items[0];
    expect(first).toBeDefined();
    expect(first?.impact).toBeUndefined();
    expect(first?.commentsEnabled).toBe(false);
    expect(first?.url).toMatch(/^https:\/\//);
    expect(items.some((n) => n.sentiment?.label === 'positive')).toBe(true);
  });

  it('posts, comment threads, experts and chat', () => {
    const post = toPost(page(PostRead).parse(body('posts_feed')).items[0] ?? PostRead.parse(body('posts_create')));
    expect(post.body.length).toBeGreaterThan(0);
    expect(post.provenance).toBe('live');
    const threads = page(ThreadRead).parse(body('comments_list')).items;
    const comments = toComments(threads, 'p1');
    expect(comments.length).toBeGreaterThan(0);
    expect(comments.every((c) => c.threadId === 'p1' && c.body.length > 0)).toBe(true);
    const expert = toExpert(page(ExpertCard).parse(body('experts_list')).items[0] ?? ExpertCard.parse({}));
    expect(expert).toMatchObject({ name: 'Sami Expert', marketCategories: ['forex', 'gold'], chatEnabled: true });
    expect(expert.availability).toBeUndefined(); // no presence is invented
    expect(expert.cheapestPlan).toMatchObject({ price: '19.00', currency: 'USD', interval: 'month' });
    const conv = ConversationRead.parse(body('chat_open'));
    const msgs = MessagePage.parse(body('chat_history')).items.flatMap((m) => toChatMessage(m, conv.user_id) ?? []);
    expect(msgs.length).toBeGreaterThan(0);
    expect(new Set(msgs.map((m) => m.from)).size).toBeGreaterThan(0);
  });

  it('server notifications become remote, read-tracked items', () => {
    const n = toNotification(page(NotificationRead).parse(body('notif_list')).items[0] ?? NotificationRead.parse({}));
    expect(n).toMatchObject({ remote: true, provenance: 'live' });
    expect(typeof n.read).toBe('boolean');
  });
});
