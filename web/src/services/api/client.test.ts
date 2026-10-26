import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import type { Session } from '@/domain/user';
import { deriveWsUrl, loadConfig, resolveBaseUrl, type AppConfig } from '../config';
import { createDemoServices } from '../demo';
import { ApiError, userMessage } from '../errors';
import { createHttpClient } from './http';
import { createApiServices } from './index';
import { createMarketSocket } from './marketSocket';
import { createTokenManager, safeRedirect, type SessionStore } from './session';

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(body === null ? null : typeof body === 'string' ? body : JSON.stringify(body), { status, headers });

const session = (over: Partial<Session> = {}): Session => ({
  user: { id: 'u1', name: 'Sara', email: 's@example.com', role: 'trader' },
  token: 'acc-1',
  refreshToken: 'ref-1',
  expiresAt: Date.now() + 30 * 60_000,
  isDemo: false,
  ...over,
});

function memoryStore(initial: Session | null, persisted?: () => Session | null): SessionStore & { current: Session | null } {
  const s = {
    current: initial,
    get: () => s.current,
    set: (n: Session | null) => {
      s.current = n;
    },
    readPersisted: () => (persisted ? persisted() : s.current),
  };
  return s;
}

const tokens = (n: number) => ({ access_token: `acc-${n}`, refresh_token: `ref-${n}`, token_type: 'bearer', expires_in: 1800 });

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('configuration', () => {
  it('accepts a same-origin path (production behind one Nginx) and derives the WebSocket URL', () => {
    expect(resolveBaseUrl('/api/v1/')).toBe(`${window.location.origin}/api/v1`);
    expect(deriveWsUrl('https://example.org/api/v1')).toBe('wss://example.org/ws/market');
    expect(deriveWsUrl('http://localhost:8000/api/v1')).toBe('ws://localhost:8000/ws/market');
    const cfg = loadConfig({ VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: '/api/v1' });
    expect(cfg).toMatchObject({ dataSource: 'api', apiBaseUrl: `${window.location.origin}/api/v1`, staleAfterMs: 90_000 });
  });

  it('never falls back to demo data silently: an invalid configuration is a blocking issue', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const bad = loadConfig({ VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: 'javascript:alert(1)' });
    expect(bad.dataSource).toBe('api');
    expect(bad.issues.map((i) => i.variable)).toEqual(['VITE_API_BASE_URL']);
    // The Git Bash path rewrite that once switched a local run to demo data.
    expect(loadConfig({ VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: 'C:/Program Files/Git/api/v1' }).issues).toHaveLength(1);
    expect(loadConfig({ VITE_DATA_SOURCE: 'API ' }).issues[0]).toMatchObject({ variable: 'VITE_DATA_SOURCE' });
  });

  it('uses demo mode only when it is selected or left unset', () => {
    expect(loadConfig({})).toMatchObject({ dataSource: 'demo', issues: [] });
    expect(loadConfig({ VITE_DATA_SOURCE: 'demo', VITE_API_BASE_URL: 'not a url' })).toMatchObject({ dataSource: 'demo', issues: [] });
  });
});

describe('HTTP client', () => {
  const base = { baseUrl: 'http://api.test/api/v1', timeoutMs: 1000 };

  it('refreshes once on 401 and retries with the new token', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(json(401, { detail: 'expired' })).mockResolvedValueOnce(json(200, { ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const refreshToken = vi.fn().mockResolvedValue('fresh');
    const onUnauthorized = vi.fn();
    const http = createHttpClient({ ...base, getToken: () => 'old', refreshToken, onUnauthorized });
    await expect(http.request('POST', '/x', { body: { a: 1 }, schema: z.object({ ok: z.boolean() }) })).resolves.toEqual({ ok: true });
    expect(refreshToken).toHaveBeenCalledTimes(1);
    expect((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers).toMatchObject({ Authorization: 'Bearer fresh' });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('ends the session when the refresh is refused', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { detail: 'expired' })));
    const onUnauthorized = vi.fn();
    const http = createHttpClient({ ...base, getToken: () => 'old', refreshToken: async () => undefined, onUnauthorized });
    const err = await http.request('GET', '/x', { schema: z.unknown() }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('handles 204, non-JSON errors, request ids, and never shows 5xx internals', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(204, null)).mockResolvedValueOnce(json(502, '<html>Bad gateway: upstream 10.0.0.3</html>', { 'x-request-id': 'rid-7' })));
    const http = createHttpClient({ ...base, getToken: () => undefined });
    await expect(http.request('DELETE', '/a', { schema: z.unknown() })).resolves.toBeNull();
    const err = (await http.request('GET', '/b', { schema: z.unknown() }).catch((e: unknown) => e)) as ApiError;
    expect(err.kind).toBe('server');
    expect(err.requestId).toBe('rid-7');
    expect(userMessage(err)).not.toMatch(/10\.0\.0\.3|html/);
  });

  it('reports a contract mismatch instead of passing bad data on', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, { price: 'not a number' })));
    const http = createHttpClient({ ...base, getToken: () => undefined });
    await expect(http.request('GET', '/q', { schema: z.object({ price: z.number() }) })).rejects.toMatchObject({ kind: 'contract' });
  });

  it('maps network failure, timeout and cancellation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const http = createHttpClient({ ...base, getToken: () => undefined });
    await expect(http.request('GET', '/n', { schema: z.unknown() })).rejects.toMatchObject({ kind: 'network' });
    const ctrl = new AbortController();
    ctrl.abort();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')));
    await expect(http.request('GET', '/n', { schema: z.unknown(), signal: ctrl.signal })).rejects.toMatchObject({ kind: 'aborted' });
  });
});

describe('token manager (rotating refresh tokens with reuse detection)', () => {
  const bare = () => createHttpClient({ baseUrl: 'http://api.test/api/v1', timeoutMs: 1000, getToken: () => undefined });

  it('is single-flight: concurrent 401s cause exactly one refresh', async () => {
    const fetchMock = vi.fn().mockImplementation(() => new Promise((r) => setTimeout(() => r(json(200, tokens(2))), 5)));
    vi.stubGlobal('fetch', fetchMock);
    const store = memoryStore(session());
    const tm = createTokenManager(bare(), store);
    const [a, b, c] = await Promise.all([tm.refresh(), tm.refresh(), tm.refresh()]);
    expect([a, b, c]).toEqual(['acc-2', 'acc-2', 'acc-2']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body))).toEqual({ refresh_token: 'ref-1' });
    expect(store.current).toMatchObject({ token: 'acc-2', refreshToken: 'ref-2' });
  });

  it('adopts a token another tab already rotated instead of reusing the old one', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const rotatedElsewhere = session({ token: 'acc-9', refreshToken: 'ref-9' });
    const store = memoryStore(session(), () => rotatedElsewhere);
    await expect(createTokenManager(bare(), store).refresh()).resolves.toBe('acc-9');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('a refused refresh ends the session; a network failure does not', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { detail: 'Refresh token has been revoked' })));
    const ended = memoryStore(session());
    await expect(createTokenManager(bare(), ended).refresh()).resolves.toBeUndefined();
    expect(ended.current).toBeNull();

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const kept = memoryStore(session());
    await expect(createTokenManager(bare(), kept).refresh()).rejects.toMatchObject({ kind: 'network' });
    expect(kept.current).not.toBeNull();
  });

  it('refreshes proactively shortly before the access token expires', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(200, tokens(3))));
    const store = memoryStore(session({ expiresAt: Date.now() + 10_000 }));
    await expect(createTokenManager(bare(), store).getToken()).resolves.toBe('acc-3');
    const fresh = memoryStore(session());
    await expect(createTokenManager(bare(), fresh).getToken()).resolves.toBe('acc-1');
  });
});

describe('post-sign-in redirects', () => {
  it('accepts only in-app paths', () => {
    expect(safeRedirect('/signals?tf=1h')).toBe('/signals?tf=1h');
    for (const bad of ['https://evil.example', '//evil.example', '/\\evil.example', 'javascript:alert(1)', '/login', 42, undefined]) expect(safeRedirect(bad)).toBe('/overview');
  });
});

class FakeSocket {
  static all: FakeSocket[] = [];
  readyState = 0;
  sent: Record<string, unknown>[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeSocket.all.push(this);
  }
  send(data: string) {
    this.sent.push(JSON.parse(data) as Record<string, unknown>);
  }
  close() {
    this.readyState = 3;
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  push(msg: object) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
}

describe('market WebSocket', () => {
  it('subscribes after open, delivers candles, re-subscribes with a fresh token after 4401, and unsubscribes', async () => {
    FakeSocket.all = [];
    let token = 'acc-1';
    const refreshToken = vi.fn(async () => (token = 'acc-2'));
    const ws = createMarketSocket({ url: 'ws://h/ws/market', getToken: async () => token, refreshToken, WebSocketImpl: FakeSocket as unknown as new (url: string) => WebSocket, idleCloseMs: 0 });
    const candles: number[] = [];
    const statuses: string[] = [];
    const off = ws.subscribeCandles('inst-1', '1m', { onCandle: (c) => candles.push(c.close), onStatus: (s) => statuses.push(s) });
    await vi.waitFor(() => expect(FakeSocket.all).toHaveLength(1));
    const first = FakeSocket.all[0]!;
    expect(first.url).toBe('ws://h/ws/market?token=acc-1');
    first.open();
    expect(first.sent[0]).toEqual({ op: 'subscribe', topic: 'candles', instrument_id: 'inst-1', timeframe: '1m' });
    first.push({ type: 'snapshot', topic: 'candles:inst-1:1m', candle: { time: 60, open: 1, high: 1, low: 1, close: 1.5, volume: 0 } });
    first.push({ type: 'candle', topic: 'candles:inst-1:1m', candle: { time: 120, open: 1, high: 2, low: 1, close: 1.7, volume: 0 } });
    expect(candles).toEqual([1.5, 1.7]);
    expect(statuses).toContain('live');

    first.onclose?.({ code: 4401 });
    await vi.waitFor(() => expect(FakeSocket.all).toHaveLength(2));
    expect(refreshToken).toHaveBeenCalledTimes(1);
    const second = FakeSocket.all[1]!;
    expect(second.url).toBe('ws://h/ws/market?token=acc-2');
    second.open();
    expect(second.sent[0]).toMatchObject({ op: 'subscribe', instrument_id: 'inst-1' });

    off();
    expect(second.sent.at(-1)).toEqual({ op: 'unsubscribe', topic: 'candles', instrument_id: 'inst-1', timeframe: '1m' });
    expect(ws.topicCount()).toBe(0);
  });
});

describe('API adapter request shapes (verified contract)', () => {
  const cfg: AppConfig = { dataSource: 'api', apiBaseUrl: 'http://api.test/api/v1', wsUrl: 'ws://api.test/ws/market', apiTimeoutMs: 1000, pricePollMs: 1000, staleAfterMs: 90_000, issues: [] };
  const instruments = {
    items: [
      { id: 'i-xau', symbol: 'XAU/USD', source: 'twelvedata', market: 'commodity', base_asset: 'XAU', quote_asset: 'USD', price_precision: 2, is_active: true },
      { id: 'i-btc', symbol: 'BTC/USDT', source: 'binance', market: 'crypto', base_asset: 'BTC', quote_asset: 'USDT', price_precision: 2, is_active: true },
    ],
    total: 2,
    limit: 100,
    offset: 0,
  };
  const route = (handlers: Record<string, (init: RequestInit) => Response>) =>
    vi.fn(async (url: string, init: RequestInit) => {
      const u = new URL(url);
      const key = `${init.method} ${u.pathname}`;
      const h = handlers[key];
      if (!h) throw new Error(`unexpected ${key}`);
      return h(init);
    });
  const services = () => createApiServices(cfg, memoryStore(session()), vi.fn());

  it('candles go to /market/instruments/{id}/candles; unsupported symbols are reported, not faked', async () => {
    const fetchMock = route({
      'GET /api/v1/market/instruments': () => json(200, instruments),
      'GET /api/v1/market/instruments/i-xau/candles': () => json(200, { instrument_id: 'i-xau', timeframe: '1h', candles: [{ time: 3600, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }] }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const s = services();
    const series = await s.market.getCandles('XAUUSD', '1h');
    expect(series).toMatchObject({ symbol: 'XAUUSD', provenance: 'live', volumeKind: 'tick', candles: [{ close: 1.5 }] });
    const url = new URL(String(fetchMock.mock.calls[1]?.[0]));
    expect(url.searchParams.get('timeframe')).toBe('1h');
    await expect(s.market.getCandles('AUDUSD', '1h')).rejects.toMatchObject({ kind: 'not_available' });
  });

  it('price alert creation sends the backend body; posts derive the required title from the first line', async () => {
    const created = { id: 'a1', instrument: { id: 'i-xau', symbol: 'XAU/USD' }, condition: 'crosses_above', value: 2450, window_minutes: null, repeat: 'once', cooldown_minutes: null, note: null, is_active: true, last_triggered_at: null, trigger_count: 0, expires_at: null, created_at: '2026-10-18T10:00:00Z', updated_at: '2026-10-18T10:00:00Z' };
    const post = { id: 'p1', author: { id: 'u1', display_name: 'Sara', role: 'trader' }, title: 'Gold above the range', body: 'Gold above the range\nWatching 2,450.', instrument: { id: 'i-xau', symbol: 'XAU/USD' }, comments_count: 0, created_at: '2026-10-18T10:00:00Z' };
    const fetchMock = route({
      'GET /api/v1/market/instruments': () => json(200, instruments),
      'POST /api/v1/me/price-alerts': () => json(201, created),
      'POST /api/v1/posts': () => json(201, post),
    });
    vi.stubGlobal('fetch', fetchMock);
    const s = services();
    const alert = await s.alerts.create({ symbol: 'XAUUSD', condition: 'crosses_above', price: 2450, channels: ['app'] });
    expect(alert).toMatchObject({ id: 'a1', symbol: 'XAUUSD', status: 'active' });
    const alertBody = JSON.parse(String((fetchMock.mock.calls.find(([u, i]) => String(u).endsWith('/me/price-alerts') && (i as RequestInit).method === 'POST') as [string, RequestInit])[1].body));
    expect(alertBody).toEqual({ instrument_id: 'i-xau', condition: 'crosses_above', value: 2450, repeat: 'once', note: null });
    await s.community.createPost({ body: 'Gold above the range\nWatching 2,450.', symbols: ['XAUUSD'] });
    const postBody = JSON.parse(String((fetchMock.mock.calls.at(-1) as [string, RequestInit])[1].body));
    expect(postBody).toEqual({ title: 'Gold above the range', body: 'Gold above the range\nWatching 2,450.', instrument_id: 'i-xau' });
  });

  it('saving the risk profile preserves the rest of the server config', async () => {
    const current = { account_size: 10000, quote_currency: 'USD', config: { stop: { type: 'atr' }, fee_bps: 10, sizing: { mode: 'risk', risk_pct: 1, max_position_pct: 100 }, guards: { cooldown_bars: 0, max_daily_loss_pct: null } }, template: 'balanced', updated_at: '2026-10-18T10:00:00Z' };
    const fetchMock = route({
      'GET /api/v1/me/risk-profile': () => json(200, current),
      'PUT /api/v1/me/risk-profile': (init) => json(200, { ...current, ...(JSON.parse(String(init.body)) as object), template: null }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const saved = await services().riskProfile.save({ capital: 25000, currency: 'USD', riskPerTradePct: 0.5, dailyLossLimitPct: 3 });
    const put = JSON.parse(String((fetchMock.mock.calls[1] as [string, RequestInit])[1].body)) as { config: Record<string, unknown> };
    expect(put.config).toEqual({ stop: { type: 'atr' }, fee_bps: 10, sizing: { mode: 'risk', risk_pct: 0.5, max_position_pct: 100 }, guards: { cooldown_bars: 0, max_daily_loss_pct: 3 } });
    expect(saved).toMatchObject({ capital: 25000, riskPerTradePct: 0.5, dailyLossLimitPct: 3 });
  });

  it('password change uses the backend field names; the AI model output is reported as not available', async () => {
    const fetchMock = route({ 'POST /api/v1/users/me/password': () => json(204, null) });
    vi.stubGlobal('fetch', fetchMock);
    const s = services();
    await s.account.changePassword({ currentPassword: 'old-pass1', newPassword: 'new-pass2' });
    expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body))).toEqual({ current_password: 'old-pass1', new_password: 'new-pass2' });
    await expect(s.opportunities.list()).rejects.toMatchObject({ kind: 'not_available' });
    await expect(s.predictions.listHistory()).rejects.toMatchObject({ kind: 'not_available' });
    expect(s.assistant.describe()).toMatchObject({ provider: 'demo-rules', label: 'Rule-based' });
  });
});

describe('demo mode stays honest about backend-only features', () => {
  it('reports them as not available instead of simulating them', async () => {
    const s = createDemoServices(() => null);
    await expect(s.strategySignals.list()).rejects.toMatchObject({ kind: 'not_available' });
    await expect(s.riskProfile.get()).rejects.toMatchObject({ kind: 'not_available' });
    await expect(s.account.changePassword({ currentPassword: 'a', newPassword: 'b' })).rejects.toMatchObject({ kind: 'not_available' });
  });
});
