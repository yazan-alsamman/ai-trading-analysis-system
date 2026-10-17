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
    expireAccessToken: () => validAccess.clear(),
    revokeRefreshTokens: () => {
      validRefresh.clear();
      validAccess.clear();
    },
  };

  const reply = (route: Route, status: number, body?: unknown) =>
    route.fulfill({ status, contentType: 'application/json', headers: { 'x-request-id': `req-${state.calls.length}` }, body: body === undefined ? '' : JSON.stringify(body) });
  const page_ = (items: unknown[]) => ({ items, total: items.length, limit: 50, offset: 0 });

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
      const recorded = (rec('signals_list').items as Record<string, unknown>[]).slice(0, 3);
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

    if (method === 'GET' && path === '/me/notifications') return reply(route, 200, rec('notif_list'));
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
