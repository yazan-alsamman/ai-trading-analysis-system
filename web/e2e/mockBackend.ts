import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Page, Route, WebSocketRoute } from '@playwright/test';

/**
 * A stand-in for the FastAPI backend in browser tests of VITE_DATA_SOURCE=api.
 *
 * Response bodies are the backend's RECORDED responses (docs/postman/tools/
 * examples.json); instruments are the backend's seed list
 * (backend/app/services/seed_service.py). Auth behaves like the real service:
 * only issued access tokens are accepted, refresh tokens rotate, and a used
 * refresh token is rejected. Any request the backend does not offer gets 404
 * and is recorded in `unexpected`, so the client cannot silently call
 * endpoints that do not exist.
 *
 * This is not a substitute for a run against the live stack: it verifies the
 * client against the contract, not the server's behaviour.
 */
type Recorded = Record<string, { body: string }[]>;
const examples = JSON.parse(readFileSync(resolve(process.cwd(), '../docs/postman/tools/examples.json'), 'utf8')) as Recorded;
const rec = (name: string): Record<string, unknown> => JSON.parse(examples[name]?.[0]?.body ?? '{}') as Record<string, unknown>;
/** A recorded body as-is (lists stay arrays). */
const recRaw = (name: string): unknown => JSON.parse(examples[name]?.[0]?.body ?? 'null') as unknown;
/** The recorded response with a given status code (e.g. the 409 of a stale workspace version). */
const recVariant = (name: string, code: number): Record<string, unknown> =>
  JSON.parse(examples[name]?.find((e) => (e as { code?: number }).code === code)?.body ?? '{}') as Record<string, unknown>;

const RECORDED_SIGNAL = (JSON.parse(readFileSync(resolve(process.cwd(), 'src/services/api/__fixtures__/recorded-signal.json'), 'utf8')) as { signal: Record<string, unknown> }).signal;
const BACKTEST_ID = String(rec('backtests_get').id);
export const AI_SETUP_ID = String(rec('ai_setup_size').setup_id);

/** An `ai_setup` notification as the backend builds it (app/ai/alerts.py::_base_data); v1: no probability, EV or grade. */
function aiSetupNotification(nowMs: number) {
  const at = new Date(nowMs - 10 * 60_000).toISOString();
  return {
    id: '5b0f4a43-6f3e-4a8e-9a0c-1f2e3d4c5b6a',
    type: 'ai_setup',
    title: 'BUY setup XAU/USD: entry 2,400.00',
    body: 'Entry 2,400.00 · stop 2,395.00 · target 2,410.00',
    severity: 'warning',
    created_at: at,
    read_at: null,
    data: {
      setup_id: AI_SETUP_ID,
      state: 'ARMED',
      transition: { from: 'DEVELOPING', to: 'ARMED', at, reason: 'entry conditions met', realized_r: null },
      direction: 'buy',
      instrument: { id: 'i-xau', symbol: 'XAU/USD', source: 'twelvedata', price_precision: 2, quantity_precision: 2 },
      profile: 'intraday',
      entry: 2400,
      sl: 2395,
      tp: 2410,
      r_multiple: 2,
      probability: null,
      ev_r: null,
      grade: null,
      valid_until: new Date(nowMs + 50 * 60_000).toISOString(),
      reason: 'entry conditions met',
      realized_r: null,
      late: false,
    },
  };
}
const ID = '[^/]+';
/**
 * Endpoints answered with the backend's recorded success response (method, path, recording, status).
 * 204 rows send no body, like the server.
 */
const RECORDED_ROUTES: [string, RegExp, string, number][] = (
  [
    ['GET', '/me/price-alerts/history', 'alerts_history', 200],
    ['DELETE', `/me/notifications/${ID}`, '', 204],
    ['GET', '/me/notification-preferences', 'notif_prefs_get', 200],
    ['PUT', '/me/notification-preferences', 'notif_prefs_put', 200],
    ['GET', '/me/notifications/channels', 'notif_channels', 200],
    ['POST', '/me/notifications/test', 'notif_test', 200],
    ['POST', '/me/notifications/telegram/link', 'notif_telegram_link', 200],
    ['DELETE', '/me/notifications/telegram', '', 204],
    ['GET', '/strategies', 'strategies_catalog', 200],
    ['POST', `/strategies/${ID}/preview`, 'strategies_preview', 200],
    ['GET', '/me/strategies', 'me_strategies_list', 200],
    ['POST', '/me/strategies', 'me_strategies_create', 201],
    ['PATCH', `/me/strategies/${ID}`, 'me_strategies_update', 200],
    ['DELETE', `/me/strategies/${ID}`, '', 204],
    ['GET', '/me/signal-plans', 'risk_signal_plans', 200],
    ['GET', '/me/custom-strategies', 'custom_list', 200],
    ['POST', '/me/custom-strategies', 'custom_create', 201],
    ['POST', `/me/custom-strategies/${ID}/clone`, 'custom_clone', 201],
    ['GET', `/me/custom-strategies/${ID}`, 'custom_get', 200],
    ['PUT', `/me/custom-strategies/${ID}`, 'custom_replace', 200],
    ['PATCH', `/me/custom-strategies/${ID}`, 'custom_update', 200],
    ['DELETE', `/me/custom-strategies/${ID}`, '', 204],
    ['GET', '/custom-strategies/schema', 'custom_schema', 200],
    ['POST', '/custom-strategies/validate', 'custom_validate', 200],
    ['GET', '/custom-strategies/public', 'custom_public', 200],
    ['POST', `/custom-strategies/public/${ID}/clone`, 'custom_public_clone', 201],
    ['GET', '/backtests', 'backtests_list', 200],
    ['POST', '/backtests', 'backtests_create', 202],
    ['POST', '/backtests/compare', 'backtests_compare', 200],
    ['GET', `/backtests/${ID}/trades`, 'backtests_trades', 200],
    ['GET', `/backtests/${ID}`, 'backtests_get', 200],
    ['DELETE', `/backtests/${ID}`, '', 204],
    ['GET', '/me/workspaces', 'ws_list', 200],
    ['POST', '/me/workspaces', 'ws_create', 201],
    ['POST', `/me/workspaces/${ID}/duplicate`, 'ws_duplicate', 201],
    ['PATCH', `/me/workspaces/${ID}`, 'ws_update', 200],
    ['DELETE', `/me/workspaces/${ID}`, '', 204],
    ['POST', `/posts/${ID}/like`, 'posts_like', 200],
    ['DELETE', `/posts/${ID}/like`, 'posts_unlike', 200],
    ['PATCH', `/posts/${ID}`, 'posts_update', 200],
    ['DELETE', `/posts/${ID}`, '', 204],
    ['POST', `/posts/${ID}/comments`, 'comments_create', 201],
    ['PATCH', `/comments/${ID}`, 'comments_update', 200],
    ['DELETE', `/comments/${ID}`, '', 204],
    ['POST', '/reports', 'reports_create', 201],
    ['GET', `/users/${ID}/profile`, 'users_profile', 200],
    ['POST', `/users/${ID}/follow`, 'users_follow', 200],
    ['DELETE', `/users/${ID}/follow`, 'users_unfollow', 200],
    ['GET', '/me/following', 'me_following', 200],
    ['GET', '/me/followers', 'me_followers', 200],
    ['GET', `/experts/${ID}/signals`, 'experts_signals', 200],
    ['GET', `/experts/${ID}`, 'experts_get', 200],
    ['POST', '/subscriptions/checkout', 'subs_checkout', 201],
    ['GET', '/me/subscriptions', 'subs_mine', 200],
    ['POST', `/me/subscriptions/${ID}/cancel`, 'subs_cancel', 200],
    ['POST', `/me/subscriptions/${ID}/resume`, 'subs_resume', 200],
    ['GET', '/me/api-keys/scopes', 'keys_scopes', 200],
    ['GET', '/me/api-keys', 'keys_list', 200],
    ['POST', '/me/api-keys', 'keys_create', 201],
    ['GET', `/me/api-keys/${ID}/usage`, 'keys_usage', 200],
    ['PATCH', `/me/api-keys/${ID}`, 'keys_update', 200],
    ['DELETE', `/me/api-keys/${ID}`, '', 204],
    ['GET', '/conversations', 'chat_list', 200],
    ['GET', `/ai/setups/${ID}/size`, 'ai_setup_size', 200],
    ['GET', `/ai/setups/${ID}/explanation`, 'ai_setup_explanation', 200],
    ['POST', `/ai/setups/${ID}/take`, 'ai_setup_take', 201],
    ['DELETE', `/ai/setups/${ID}/take`, '', 204],
    ['GET', '/me/ai/trades', 'ai_trades', 200],
    ['GET', '/calendar/events', 'calendar_events', 200],
    ['GET', `/calendar/events/${ID}/history`, 'calendar_event_history', 200],
  ] as const
).map(([m, p, name, status]) => [m, new RegExp(`^${p}$`), name, status]);

export const INSTRUMENTS = [
  { symbol: 'XAU/USD', id: 'i-xau', market: 'commodity', base: 'XAU', quote: 'USD', pp: 2, price: 2400 },
  { symbol: 'EUR/USD', id: 'i-eur', market: 'forex', base: 'EUR', quote: 'USD', pp: 5, price: 1.08 },
  { symbol: 'GBP/USD', id: 'i-gbp', market: 'forex', base: 'GBP', quote: 'USD', pp: 5, price: 1.27 },
  { symbol: 'USD/JPY', id: 'i-jpy', market: 'forex', base: 'USD', quote: 'JPY', pp: 3, price: 150 },
  { symbol: 'BTC/USDT', id: 'i-btc', market: 'crypto', base: 'BTC', quote: 'USDT', pp: 2, price: 60000 },
];

const STEP: Record<string, number> = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400 };

/** Deterministic candles ending at the last closed bar before `now`. */
function candles(price: number, tf: string, limit: number, nowSec: number) {
  const step = STEP[tf] ?? 3600;
  const end = Math.floor(nowSec / step) * step;
  const out = [];
  let p = price;
  for (let i = limit - 1; i >= 0; i--) {
    const open = p;
    const close = +(open * (1 + Math.sin(i / 3) * 0.0015)).toFixed(5);
    out.push({ time: end - i * step, open, high: Math.max(open, close) * 1.0006, low: Math.min(open, close) * 0.9994, close, volume: 100 + (i % 7) });
    p = close;
  }
  return out;
}

const iso = (ms: number) => new Date(ms).toISOString();

export interface MockBackend {
  calls: { method: string; path: string; body: unknown; auth: string | null }[];
  unexpected: string[];
  refreshCount: number;
  /** Make the next authenticated request see an expired access token. */
  expireAccessToken(): void;
  /** Revoke all refresh tokens (simulates reuse detection / server-side sign-out). */
  revokeRefreshTokens(): void;
  /** WebSocket messages the client sent. */
  wsSent: Record<string, unknown>[];
  ws: WebSocketRoute | null;
  /** Simulate a save of the test workspace from another device (the next PUT with the old version gets 409). */
  bumpWorkspaceVersion(): void;
}

export const USER = { id: '2b0ff791-1d77-4e0e-9ace-eb2cdce57724', email: 'trader@example.com', full_name: 'Sara Trader', role: 'trader', is_active: true, created_at: iso(0), updated_at: iso(0) };
export const PASSWORD = 'correct-pass1';

export async function mockBackend(page: Page, opts: { nowMs?: number } = {}): Promise<MockBackend> {
  const nowMs = opts.nowMs ?? Date.now();
  let seq = 1;
  const validAccess = new Set<string>();
  const validRefresh = new Set<string>();
  let fullName = USER.full_name;
  const issue = () => {
    const n = seq++;
    validAccess.add(`acc-${n}`);
    validRefresh.add(`ref-${n}`);
    return { access_token: `acc-${n}`, refresh_token: `ref-${n}`, token_type: 'bearer', expires_in: 1800 };
  };
  // A session already issued before the page loads (tests seed it into storage).
  validAccess.add('acc-0');
  validRefresh.add('ref-0');

  const state: MockBackend = {
    calls: [],
    unexpected: [],
    refreshCount: 0,
    wsSent: [],
    ws: null,
    bumpWorkspaceVersion: () => undefined,
    expireAccessToken: () => validAccess.clear(),
    revokeRefreshTokens: () => {
      validRefresh.clear();
      validAccess.clear();
    },
  };

  const reply = (route: Route, status: number, body?: unknown) =>
    route.fulfill({ status, contentType: 'application/json', headers: { 'x-request-id': `req-${state.calls.length}` }, body: body === undefined ? '' : JSON.stringify(body) });
  const page_ = (items: unknown[]) => ({ items, total: items.length, limit: 50, offset: 0 });
  /** The server version of the workspace edited in tests (bumped by `bumpWorkspaceVersion`, i.e. "another device"). */
  let workspaceVersion = Number(rec('ws_get').version ?? 1);
  let follows = [{ ...(recRaw('ai_follows') as Record<string, unknown>[])[0], instrument_id: 'i-xau', min_grade: null }] as Record<string, unknown>[];
  state.bumpWorkspaceVersion = () => {
    workspaceVersion += 1;
  };

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^\/api\/v1/, '');
    const method = req.method();
    let body: unknown = null;
    try {
      body = req.postDataJSON() as unknown;
    } catch {
      body = req.postData();
    }
    const authHeader = (await req.allHeaders()).authorization ?? null;
    state.calls.push({ method, path, body, auth: authHeader });
    const b = (body ?? {}) as Record<string, unknown>;

    // --- public auth endpoints
    if (method === 'POST' && path === '/auth/login') return b.email === USER.email && b.password === PASSWORD ? reply(route, 200, issue()) : reply(route, 401, { detail: 'Incorrect email or password' });
    if (method === 'POST' && path === '/auth/refresh') {
      state.refreshCount++;
      const token = String(b.refresh_token ?? '');
      if (!validRefresh.has(token)) return reply(route, 401, { detail: 'Refresh token has been revoked' });
      validRefresh.delete(token); // rotation: one use only
      return reply(route, 200, issue());
    }

    // --- everything else needs a currently valid access token
    const token = authHeader?.replace(/^Bearer /, '') ?? '';
    if (!validAccess.has(token)) return reply(route, 401, { detail: 'Could not validate credentials' });

    if (method === 'POST' && path === '/auth/logout') {
      validRefresh.delete(String(b.refresh_token ?? ''));
      return reply(route, 204);
    }
    if (method === 'GET' && path === '/users/me') return reply(route, 200, { ...USER, full_name: fullName });
    if (method === 'PATCH' && path === '/users/me') {
      fullName = String(b.full_name ?? fullName);
      return reply(route, 200, { ...USER, full_name: fullName });
    }
    if (method === 'POST' && path === '/users/me/password') return b.current_password === PASSWORD ? reply(route, 204) : reply(route, 400, { detail: 'Current password is incorrect' });

    if (method === 'GET' && path === '/market/instruments')
      return reply(
        route,
        200,
        page_(INSTRUMENTS.map((i) => ({ id: i.id, symbol: i.symbol, source: i.market === 'crypto' ? 'binance' : 'twelvedata', market: i.market, base_asset: i.base, quote_asset: i.quote, price_precision: i.pp, quantity_precision: null, is_active: true, created_at: iso(0), updated_at: iso(0) }))),
      );
    const candleMatch = /^\/market\/instruments\/([^/]+)\/candles$/.exec(path);
    if (method === 'GET' && candleMatch) {
      const inst = INSTRUMENTS.find((i) => i.id === candleMatch[1]);
      if (!inst) return reply(route, 404, { detail: 'Instrument not found' });
      const tf = url.searchParams.get('timeframe') ?? '1h';
      const limit = Math.min(Number(url.searchParams.get('limit') ?? 500), 300);
      return reply(route, 200, { instrument_id: inst.id, timeframe: tf, candles: candles(inst.price, tf, limit, Math.floor(nowMs / 1000)) });
    }

    if (method === 'GET' && path === '/signals') {
      // The current recording may hold no signal (private-signal isolation, backend B12); then use one recorded earlier.
      const current = rec('signals_list').items as Record<string, unknown>[];
      const recorded = (current.length ? current : [RECORDED_SIGNAL, { ...RECORDED_SIGNAL, id: '0a7d6c1e-3f7b-4d55-9a51-1b2c3d4e5f60' }]).slice(0, 3);
      return reply(route, 200, page_(recorded.map((s, i) => ({ ...s, instrument_id: i === 0 ? 'i-xau' : 'i-btc', price: i === 0 ? 2398.4 : s.price }))));
    }

    if (method === 'GET' && path === '/me/price-alerts') {
      const recorded = rec('alerts_list').items as Record<string, unknown>[];
      return reply(route, 200, page_(recorded.slice(0, 1).map((a) => ({ ...a, instrument: { id: 'i-xau', symbol: 'XAU/USD' }, condition: 'crosses_above', value: 2450 }))));
    }
    if (method === 'POST' && path === '/me/price-alerts') {
      const inst = INSTRUMENTS.find((i) => i.id === b.instrument_id);
      if (!inst) return reply(route, 404, { detail: 'Instrument not found' });
      return reply(route, 201, { id: 'alert-new', instrument: { id: inst.id, symbol: inst.symbol }, condition: b.condition, value: b.value, window_minutes: null, repeat: b.repeat, cooldown_minutes: null, note: b.note ?? null, is_active: true, last_triggered_at: null, trigger_count: 0, expires_at: null, created_at: iso(nowMs), updated_at: iso(nowMs), current_price: inst.price, would_trigger_now: false });
    }

    // The user's AI-setup history is their `ai_setup` notifications (none was recorded: built as alerts._base_data does).
    if (method === 'GET' && path === '/me/notifications' && url.searchParams.get('type') === 'ai_setup') return reply(route, 200, page_([aiSetupNotification(nowMs)]));
    if (method === 'GET' && path === '/me/notifications') return reply(route, 200, rec('notif_list'));
    // AI follows: the recorded responses, on the instrument the request names.
    if (method === 'GET' && path === '/me/ai/follows') return reply(route, 200, follows);
    const followMatch = /^\/me\/ai\/follows\/([^/]+)\/([^/]+)$/.exec(path);
    if (followMatch && method === 'PUT') {
      if (followMatch[2] !== 'intraday') return reply(route, 422, recVariant('ai_follow', 422));
      const f = { ...rec('ai_follow'), instrument_id: followMatch[1], profile: followMatch[2], min_grade: b.min_grade ?? null };
      follows = [f, ...follows.filter((x) => x.instrument_id !== f.instrument_id)];
      return reply(route, 200, f);
    }
    if (followMatch && method === 'DELETE') {
      follows = follows.filter((x) => x.instrument_id !== followMatch[1]);
      return reply(route, 204);
    }
    if (method === 'GET' && path === '/me/notifications/unread-count') return reply(route, 200, rec('notif_unread_count'));
    if (method === 'POST' && (path === '/me/notifications/read-all' || /^\/me\/notifications\/[^/]+\/read$/.test(path))) return reply(route, 204);

    if (method === 'GET' && path === '/news') return reply(route, 200, rec('news_list'));
    if (method === 'GET' && path === '/posts') return reply(route, 200, rec('posts_feed'));
    if (method === 'GET' && /^\/posts\/[^/]+\/comments$/.test(path)) return reply(route, 200, rec('comments_list'));
    if (method === 'GET' && path === '/experts') return reply(route, 200, rec('experts_list'));
    if (method === 'POST' && path === '/conversations') return reply(route, 200, rec('chat_open'));
    if (method === 'GET' && /^\/conversations\/[^/]+\/messages$/.test(path)) return reply(route, 200, rec('chat_history'));

    if (method === 'GET' && path === '/me/risk-profile') return reply(route, 200, rec('risk_profile_get'));
    if (method === 'PUT' && path === '/me/risk-profile') return reply(route, 200, { ...rec('risk_profile_get'), ...b });
    if (method === 'POST' && path === '/risk/position-size') return reply(route, 200, rec('risk_position_size'));

    // Workspaces: optimistic concurrency like the server (a stale version gets the recorded 409).
    if (method === 'PUT' && /^\/me\/workspaces\/[^/]+$/.test(path) && path !== '/me/workspaces/order') {
      if (b.version !== workspaceVersion) return reply(route, 409, { ...recVariant('ws_replace', 409), current_version: workspaceVersion });
      workspaceVersion += 1;
      return reply(route, 200, { ...rec('ws_replace'), version: workspaceVersion, state: b.state });
    }
    if (method === 'GET' && /^\/me\/workspaces\/[^/]+$/.test(path)) return reply(route, 200, { ...rec('ws_get'), version: workspaceVersion });
    if (method === 'GET' && path === '/backtests/' + BACKTEST_ID + '/trades.csv')
      return route.fulfill({ status: 200, contentType: 'text/csv', body: examples.backtests_trades_csv?.[0]?.body ?? '' });

    const recorded = RECORDED_ROUTES.find(([m, re]) => m === method && re.test(path));
    if (recorded) {
      const [, , name, status] = recorded;
      return status === 204 ? reply(route, 204) : reply(route, status, recRaw(name));
    }

    state.unexpected.push(`${method} ${path}`);
    return reply(route, 404, { detail: 'Not Found' });
  });

  // The market hub: a valid token is required; a subscription gets a snapshot then a live candle.
  await page.routeWebSocket('**/ws/market**', (ws) => {
    state.ws = ws;
    const token = new URL(ws.url()).searchParams.get('token') ?? '';
    if (!validAccess.has(token)) {
      void ws.close({ code: 4401, reason: 'invalid token' });
      return;
    }
    ws.onMessage((raw) => {
      const msg = JSON.parse(String(raw)) as Record<string, unknown>;
      state.wsSent.push(msg);
      if (msg.op === 'ping') ws.send(JSON.stringify({ type: 'pong' }));
      if (msg.op === 'subscribe' && msg.topic === 'ai_setups') ws.send(JSON.stringify({ type: 'subscribed', topic: `ai:setups:${String(msg.instrument_id)}` }));
      if (msg.op === 'subscribe' && msg.topic === 'candles') {
        const inst = INSTRUMENTS.find((i) => i.id === msg.instrument_id);
        const topic = `candles:${String(msg.instrument_id)}:${String(msg.timeframe)}`;
        if (!inst) return ws.send(JSON.stringify({ type: 'error', code: 'unknown_instrument', topic, message: 'instrument not found' }));
        const step = STEP[String(msg.timeframe)] ?? 60;
        const t = Math.floor(nowMs / 1000 / step) * step;
        ws.send(JSON.stringify({ type: 'subscribed', topic }));
        ws.send(JSON.stringify({ type: 'snapshot', topic, candle: { time: t, open: inst.price, high: inst.price, low: inst.price, close: inst.price, volume: 1 } }));
        ws.send(JSON.stringify({ type: 'candle', topic, instrument_id: inst.id, timeframe: msg.timeframe, candle: { time: t, open: inst.price, high: inst.price * 1.001, low: inst.price, close: inst.price * 1.0005, volume: 2 } }));
      }
    });
  });

  return state;
}

/** A session as the app stores it after sign-in (token issued by the mock as `acc-0`/`ref-0`). */
export async function seedSession(page: Page, over: { expiresInMs?: number } = {}): Promise<void> {
  const session = {
    user: { id: USER.id, name: USER.full_name, email: USER.email, role: USER.role },
    token: 'acc-0',
    refreshToken: 'ref-0',
    expiresAt: Date.now() + (over.expiresInMs ?? 30 * 60_000),
    isDemo: false,
  };
  await page.addInitScript((s) => {
    if (!sessionStorage.getItem('e2e-seeded')) {
      localStorage.setItem('ata.session.v1', JSON.stringify(s));
      sessionStorage.setItem('e2e-seeded', '1');
    }
  }, session);
}
