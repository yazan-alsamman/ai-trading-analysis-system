// @vitest-environment node
import { describe, expect, it } from 'vitest';
import type { Session } from '@/domain/user';
import { isApiError } from '../errors';
import type { AppConfig } from '../config';
import type { Services } from '../types';
import { createApiServices } from './index';

/**
 * LIVE service-layer integration: the real `createApiServices` against a REAL
 * running backend (no mocks, no recordings). Skipped unless LIVE_BACKEND_URL
 * is set. It registers throwaway accounts (`live-svc-…@example.com`); run it
 * only against a local or test backend. Admin credentials (LIVE_ADMIN_EMAIL /
 * LIVE_ADMIN_PASSWORD) are used to give two test accounts the analyst and
 * expert roles, which posting and selling plans require.
 *
 *   LIVE_BACKEND_URL=http://127.0.0.1:8000 LIVE_ADMIN_EMAIL=… LIVE_ADMIN_PASSWORD=… pnpm exec vitest run live.services
 */
const BACKEND = process.env.LIVE_BACKEND_URL;
const API = `${BACKEND ?? ''}/api/v1`;
const PASSWORD = 'Live-pass1234';
const run = BACKEND ? describe : describe.skip;

const cfg = (): AppConfig => ({ dataSource: 'api', apiBaseUrl: API, wsUrl: API.replace(/^http/, 'ws').replace('/api/v1', '/ws/market'), apiTimeoutMs: 20_000, pricePollMs: 15_000, staleAfterMs: 90_000, issues: [] });

interface Client {
  services: Services;
  session: () => Session;
  email: string;
}

async function newClient(label: string): Promise<Client> {
  let current: Session | null = null;
  const store = { get: () => current, set: (s: Session | null) => (current = s), readPersisted: () => current };
  const services = createApiServices(cfg(), store, () => (current = null));
  const email = `live-svc-${label}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.com`;
  current = await services.auth.register({ name: `Live ${label}`, email, password: PASSWORD });
  return { services, session: () => current as Session, email };
}

async function adminSetRole(userId: string, role: 'analyst' | 'expert') {
  const email = process.env.LIVE_ADMIN_EMAIL;
  const password = process.env.LIVE_ADMIN_PASSWORD;
  if (!email || !password) throw new Error('LIVE_ADMIN_EMAIL / LIVE_ADMIN_PASSWORD are required for role-dependent checks');
  const login = await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
  const { access_token } = (await login.json()) as { access_token: string };
  const r = await fetch(`${API}/admin/users/${userId}/role`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${access_token}` }, body: JSON.stringify({ role }) });
  expect(r.status).toBe(200);
}

/** Expect an ApiError of this kind (the server's refusal, mapped). */
async function rejectsWith(p: Promise<unknown>, kind: string) {
  const e = await p.then(
    () => null,
    (err: unknown) => err,
  );
  expect(isApiError(e) ? e.kind : e).toBe(kind);
  return e;
}

const until = async <T>(fn: () => Promise<T>, done: (v: T) => boolean, ms = 90_000): Promise<T> => {
  const end = Date.now() + ms;
  for (;;) {
    const v = await fn();
    if (done(v) || Date.now() > end) return v;
    await new Promise((r) => setTimeout(r, 1500));
  }
};

run('live backend: full service layer', () => {
  let a: Client;
  let b: Client;
  let eurusd: string;

  it('registers two independent accounts and resolves instruments', async () => {
    a = await newClient('a');
    b = await newClient('b');
    expect(a.session().user.id).not.toBe(b.session().user.id);
    const instruments = await a.services.instruments.list();
    const eur = instruments.find((i) => i.symbol === 'EUR/USD');
    expect(eur?.webSymbol).toBe('EURUSD');
    eurusd = eur?.id ?? '';
    const candles = await a.services.instruments.candles(eurusd, '1h', 50);
    expect(candles.length).toBeGreaterThan(0);
  }, 60_000);

  it('strategies: catalog, activation lifecycle, preview, signal plans, isolation', async () => {
    const catalog = await a.services.strategies.catalog();
    expect(catalog.map((s) => s.key)).toEqual(expect.arrayContaining(['ma_crossover', 'rsi_reversal', 'macd_cross']));
    const act = await a.services.strategies.activate({ strategyKey: 'ma_crossover', instrumentId: eurusd, timeframe: '1h', params: { fast: 9, slow: 21 }, name: 'Live EMA', isActive: true, notify: true });
    expect(act).toMatchObject({ strategyKey: 'ma_crossover', isActive: true, name: 'Live EMA' });
    expect((await a.services.strategies.listActivations()).map((x) => x.id)).toContain(act.id);
    const paused = await a.services.strategies.updateActivation(act.id, { isActive: false, notify: false, params: { fast: 5, slow: 20 } });
    expect(paused).toMatchObject({ isActive: false, notify: false });
    expect(paused.params.fast).toBe(5);
    // Another user cannot see or change it (404, never 403).
    expect(await b.services.strategies.listActivations()).toEqual([]);
    await rejectsWith(b.services.strategies.updateActivation(act.id, { isActive: true }), 'not_found');
    const preview = await a.services.strategies.preview('ma_crossover', { instrumentId: eurusd, timeframe: '1h', params: { fast: 9, slow: 21 }, limit: 200 });
    expect(preview.bars).toBeGreaterThan(0);
    expect(preview.indicators.length).toBe(2);
    expect(Array.isArray(await a.services.strategies.signalPlans())).toBe(true);
    await a.services.strategies.removeActivation(act.id);
    expect(await a.services.strategies.listActivations()).toEqual([]);
  }, 60_000);

  it('custom strategies: validate, create, optimistic versioning, clone, isolation, delete', async () => {
    const cat = await a.services.strategies.builderCatalog();
    expect(cat.indicators.some((i) => i.name === 'ema')).toBe(true);
    expect(cat.ops.map((o) => o.op)).toContain('crosses_above');
    const ema = (length: number) => ({ type: 'indicator', name: 'ema', params: { length } });
    const definition = {
      schema_version: 1,
      category: 'trend',
      buy: { all: [{ left: ema(9), op: 'crosses_above', right: ema(21) }] },
      sell: { all: [{ left: ema(9), op: 'crosses_below', right: ema(21) }] },
    };
    const bad = await a.services.strategies.validate('builder', { ...definition, category: 'nonsense' });
    expect(bad.valid).toBe(false);
    expect(bad.errors.length).toBeGreaterThan(0);
    const ok = await a.services.strategies.validate('builder', definition);
    expect(ok).toMatchObject({ valid: true });
    const created = await a.services.strategies.createCustom({ name: `Live builder ${Date.now()}`, description: 'EMA replica', kind: 'builder', definition, visibility: 'private' });
    expect(created).toMatchObject({ valid: true, kind: 'builder', version: 1 });
    expect(created.key).toBe(`custom:${created.id}`);
    const v2 = await a.services.strategies.replaceCustom(created.id, { version: 1, definition: { ...definition, strength: 'rule_ratio' } });
    expect(v2.version).toBe(2);
    const stale = await rejectsWith(a.services.strategies.replaceCustom(created.id, { version: 1, definition }), 'conflict');
    expect(isApiError(stale) && stale.status).toBe(409);
    const renamed = await a.services.strategies.updateCustom(created.id, { name: `${created.name} renamed` });
    expect(renamed.name).toMatch(/renamed$/);
    await rejectsWith(b.services.strategies.getCustom(created.id), 'not_found');
    const copy = await a.services.strategies.cloneCustom(created.id);
    expect(copy.clonedFrom).toBe(created.id);
    expect((await a.services.strategies.listCustom()).length).toBe(2);
    // A custom strategy previews like a global one.
    const pv = await a.services.strategies.preview(created.key, { instrumentId: eurusd, timeframe: '1h', params: {}, limit: 200 });
    expect(pv.bars).toBeGreaterThan(0);
    await a.services.strategies.removeCustom(copy.id);
    await a.services.strategies.removeCustom(created.id);
    expect(await a.services.strategies.listCustom()).toEqual([]);
    expect(Array.isArray(await a.services.strategies.listPublic())).toBe(true);
  }, 60_000);

  it('backtests: queue → worker → results, trades, CSV, compare, isolation, delete', async () => {
    const end = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    const start = new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString();
    const input = { instrumentId: eurusd, timeframe: '15m' as const, strategyKey: 'ma_crossover', params: { fast: 5, slow: 20 }, start, end, config: { initial_capital: 10_000 } };
    const one = await a.services.backtests.create(input);
    const two = await a.services.backtests.create({ ...input, params: { fast: 9, slow: 30 } });
    expect(one.status).toBe('queued');
    const done = async (id: string) => until(() => a.services.backtests.get(id), (r) => r.status === 'completed' || r.status === 'failed');
    const r1 = await done(one.id);
    const r2 = await done(two.id);
    expect(r1.status, r1.error ?? '').toBe('completed');
    expect(r2.status).toBe('completed');
    expect(r1.progress).toBe(100);
    expect(r1.equity.length).toBeGreaterThan(0);
    expect(typeof r1.metrics?.total_return_pct).toBe('number');
    const trades = await a.services.backtests.trades(one.id, { limit: 50, offset: 0 });
    expect(trades.total).toBe(r1.metrics?.trades);
    const csv = await a.services.backtests.exportTradesCsv(one.id);
    expect(csv.split('\n')[0]).toMatch(/number/);
    const cmp = await a.services.backtests.compare([one.id, two.id]);
    expect(cmp.items).toHaveLength(2);
    expect(cmp.items[0]?.equity[0]?.value).toBeCloseTo(100, 5);
    expect((await a.services.backtests.list()).total).toBe(2);
    await rejectsWith(b.services.backtests.get(one.id), 'not_found');
    expect((await b.services.backtests.list()).total).toBe(0);
    await a.services.backtests.remove(one.id);
    await a.services.backtests.remove(two.id);
    expect((await a.services.backtests.list()).total).toBe(0);
  }, 240_000);

  it('workspaces: default created, versioned save, 409 on a stale version, isolation', async () => {
    const list = await a.services.workspacesSync.list();
    expect(list.length).toBeGreaterThan(0);
    const ws = await a.services.workspacesSync.get(list[0]?.id ?? '');
    const state = {
      layout: { type: '1x1' },
      panels: [{ id: 'p1', instrument_id: eurusd, timeframe: '1h', chart_type: 'candles', indicators: [{ id: 'i1', name: 'ema', params: { length: 50 } }], strategies: [], drawings: [] }],
      watchlist: [eurusd],
      active_panel: 'p1',
    };
    const saved = await a.services.workspacesSync.replaceState(ws.id, state, ws.version);
    expect(saved.version).toBe(ws.version + 1);
    const conflict = await rejectsWith(a.services.workspacesSync.replaceState(ws.id, state, ws.version), 'conflict');
    expect(isApiError(conflict) && conflict.data?.current_version).toBe(saved.version);
    await rejectsWith(b.services.workspacesSync.get(ws.id), 'not_found');
    await rejectsWith(b.services.workspacesSync.replaceState(ws.id, state, saved.version), 'not_found');
    const created = await a.services.workspacesSync.create({ name: `Live ${Date.now()}`, state });
    const renamed = await a.services.workspacesSync.update(created.id, { name: `${created.name} (r)` });
    expect(renamed.name).toMatch(/\(r\)$/);
    const dup = await a.services.workspacesSync.duplicate(created.id);
    expect(dup.name).toMatch(/copy/);
    await a.services.workspacesSync.remove(dup.id);
    await a.services.workspacesSync.remove(created.id);
  }, 60_000);

  it('notifications: preferences, channels, test delivery, inbox count and delete, alert history', async () => {
    const prefs = await a.services.notificationSettings.getPreferences();
    expect(prefs.matrix.signal).toBeDefined();
    const saved = await a.services.notificationSettings.savePreferences({ ...prefs, language: 'en', minSignalStrength: 0.25, quietHours: { start: '23:00', end: '07:00', tz: 'Asia/Damascus' } });
    expect(saved).toMatchObject({ language: 'en', minSignalStrength: 0.25, quietHours: { start: '23:00', end: '07:00' } });
    const channels = await a.services.notificationSettings.channels();
    expect(channels.in_app.enabledOnServer).toBe(true);
    const deliveries = await a.services.notificationSettings.sendTest('in_app');
    expect(Array.isArray(deliveries)).toBe(true);
    const count = await a.services.inbox.unreadCount();
    expect(count).toBeGreaterThan(0);
    const inbox = await a.services.inbox.list();
    await a.services.inbox.remove(inbox[0]?.id ?? '');
    expect((await a.services.inbox.list()).length).toBe(inbox.length - 1);
    // B cannot touch A's notification.
    const other = await a.services.inbox.list();
    if (other[0]) await rejectsWith(b.services.inbox.markRead(other[0].id), 'not_found');
    expect(await a.services.alerts.history()).toEqual([]);
    // Telegram linking needs a bot configured on the server; without one the server refuses clearly.
    if (!channels.telegram.enabledOnServer) await expect(a.services.notificationSettings.linkTelegram()).rejects.toBeTruthy();
    else expect((await a.services.notificationSettings.linkTelegram()).code.length).toBeGreaterThan(0);
  }, 60_000);

  it('community: likes, follows, profile, replies, edit rights, report, delete', async () => {
    await adminSetRole(a.session().user.id, 'analyst');
    const post = await a.services.community.createPost({ body: 'Live post body\n\nMore text', symbols: ['EURUSD'], title: 'Live analyst post', direction: 'bullish', timeframe: '1h' });
    expect(post).toMatchObject({ title: 'Live analyst post', direction: 'bullish', canEdit: true, likes: 0 });
    const liked = await b.services.social.likePost(post.id);
    expect(liked).toEqual({ liked: true, likes: 1 });
    expect(await b.services.social.likePost(post.id)).toEqual({ liked: true, likes: 1 }); // idempotent
    expect(await b.services.social.unlikePost(post.id)).toEqual({ liked: false, likes: 0 });
    const followed = await b.services.social.follow(a.session().user.id);
    expect(followed.following).toBe(true);
    expect((await b.services.social.following()).map((f) => f.user.id)).toContain(a.session().user.id);
    expect((await a.services.social.followers()).map((f) => f.user.id)).toContain(b.session().user.id);
    const profile = await b.services.social.profile(a.session().user.id);
    expect(profile).toMatchObject({ followable: true, isFollowing: true, role: 'analyst' });
    expect((await b.services.community.listPosts({ scope: 'following' })).map((p) => p.id)).toContain(post.id);
    const comment = await b.services.community.addComment(post.id, 'A question from B');
    const reply = await a.services.community.addComment(post.id, 'An answer from A', comment.id);
    expect(reply.parentId).toBe(comment.id);
    await b.services.social.updateComment(comment.id, 'An edited question from B');
    const thread = await b.services.community.listComments(post.id);
    expect(thread.find((c) => c.id === comment.id)).toMatchObject({ body: 'An edited question from B', canEdit: true });
    expect(thread.find((c) => c.id === reply.id)?.canEdit).toBe(false);
    await rejectsWith(b.services.social.updatePost(post.id, { title: 'hijack' }), 'forbidden');
    await b.services.social.report('post', post.id, 'Live test report');
    expect(await b.services.social.unfollow(a.session().user.id)).toMatchObject({ following: false });
    await a.services.social.deletePost(post.id);
  }, 60_000);

  it('experts: profile and plan, detail, DEMO checkout paid with a test card, cancel and resume', async () => {
    const expert = await newClient('expert');
    await adminSetRole(expert.session().user.id, 'expert');
    expect(await expert.services.expertStudio.getProfile()).toBeNull();
    await expert.services.expertStudio.saveProfile({ headline: 'Live gold expert', bio: 'Test bio', markets: ['gold', 'forex'], languages: ['en'], chatEnabled: true, responseTimeHint: 'within a day', isListed: true });
    const plan = await expert.services.expertStudio.createPlan({ name: 'Live plan', description: '', price: '9.00', currency: 'USD', interval: 'month', trialDays: 0, perks: { premiumPosts: true, chat: true, signalsFeed: false }, isActive: true });
    expect(plan).toMatchObject({ price: '9.00', perks: { chat: true, signalsFeed: false } });
    const detail = await b.services.social.expert(expert.session().user.id);
    expect(detail.plans.map((p) => p.id)).toContain(plan.id);
    await rejectsWith(b.services.social.expertSignals(expert.session().user.id), 'forbidden');
    const checkout = await b.services.social.checkout(plan.id, null);
    expect(checkout.checkoutUrl).toMatch(/\/pay\/demo\//);
    // Pay on the backend's demo page with the documented test card (no real money).
    const form = new URLSearchParams({ card_number: '4242 4242 4242 4242', expiry: '12/30', cvc: '123', name: 'Live Tester' });
    const paid = await fetch(`${API}/pay/demo/${checkout.checkoutId}/confirm`, { method: 'POST', body: form, redirect: 'manual' });
    expect([200, 303]).toContain(paid.status);
    const subs = await until(() => b.services.social.subscriptions(), (s) => s.some((x) => x.status === 'active'), 20_000);
    const sub = subs.find((s) => s.expert.id === expert.session().user.id);
    expect(sub).toMatchObject({ status: 'active', price: '9.00', cancelAtPeriodEnd: false });
    expect(sub?.paymentMethod?.last4).toBe('4242');
    expect((await b.services.social.cancelSubscription(sub?.id ?? '')).cancelAtPeriodEnd).toBe(true);
    expect((await b.services.social.resumeSubscription(sub?.id ?? '')).cancelAtPeriodEnd).toBe(false);
    const msgs = await b.services.community.getConversation(expert.session().user.id);
    expect(Array.isArray(msgs)).toBe(true);
    expect((await b.services.social.conversations()).length).toBe(1);
    const earnings = await expert.services.expertStudio.earnings();
    expect(earnings.activeSubscribers).toBe(1);
  }, 90_000);

  it('API keys: scopes, create (secret shown once), update, usage, revoke', async () => {
    const scopes = await a.services.apiKeys.scopes();
    expect(scopes.find((s) => s.scope === 'news:write')?.grantable).toBe(false);
    const { apiKey, secret } = await a.services.apiKeys.create({ name: 'Live key', scopes: ['market:read', 'signals:read'], expiresInDays: 30, rateLimitPerMinute: null });
    expect(secret).toContain(apiKey.prefix); // the key reads `tk_<prefix>_…`
    expect(JSON.stringify(await a.services.apiKeys.list())).not.toContain(secret);
    const updated = await a.services.apiKeys.update(apiKey.id, { name: 'Live key 2', scopes: ['market:read'] });
    expect(updated).toMatchObject({ name: 'Live key 2', scopes: ['market:read'] });
    expect(Array.isArray(await a.services.apiKeys.usage(apiKey.id))).toBe(true);
    await rejectsWith(b.services.apiKeys.revoke(apiKey.id), 'not_found');
    await a.services.apiKeys.revoke(apiKey.id);
    expect((await a.services.apiKeys.list()).find((k) => k.id === apiKey.id)?.revoked).toBe(true);
  }, 30_000);

  it('AI setups: follow (idempotent, per user), unknown profile refused, history and trades readable, unknown setup 404', async () => {
    const f = await a.services.aiSetups.follow(eurusd, 'intraday', null);
    expect(f).toMatchObject({ instrumentId: eurusd, profile: 'intraday', minGrade: null });
    await a.services.aiSetups.follow(eurusd, 'intraday', 'B'); // upsert
    expect((await a.services.aiSetups.follows()).filter((x) => x.instrumentId === eurusd)).toHaveLength(1);
    expect(await b.services.aiSetups.follows()).toEqual([]);
    await rejectsWith(a.services.aiSetups.follow(eurusd, 'scalping', null), 'validation');
    expect(Array.isArray(await a.services.aiSetups.recent())).toBe(true);
    expect((await a.services.aiSetups.trades({ limit: 10, offset: 0 })).items).toEqual([]);
    await rejectsWith(a.services.aiSetups.size('no-such-setup'), 'not_found');
    await a.services.aiSetups.unfollow(eurusd, 'intraday');
    expect(await a.services.aiSetups.follows()).toEqual([]);
  }, 30_000);

  it('economic calendar: a week of events; windows over 31 days are refused', async () => {
    const start = Date.now() - 3 * 86_400_000;
    const res = await a.services.calendar.events({ start, end: start + 7 * 86_400_000, minImpact: 'low' });
    expect(res.asOf).toBeGreaterThan(0);
    for (const e of res.events) expect(['holiday', 'low', 'medium', 'high']).toContain(e.impact);
    if (res.events[0]) expect((await a.services.calendar.history(res.events[0].key)).length).toBeGreaterThan(0);
    await rejectsWith(a.services.calendar.events({ start, end: start + 40 * 86_400_000 }), 'validation');
  }, 30_000);
});
