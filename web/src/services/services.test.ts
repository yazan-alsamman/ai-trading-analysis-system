import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { effectiveFeedStatus } from '@/hooks/useMarketData';
import { createHttpClient } from './api/http';
import { ApiError, userMessage } from './errors';

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));
}

describe('HTTP client', () => {
  afterEach(() => vi.unstubAllGlobals());
  const client = (onUnauthorized = vi.fn()) =>
    createHttpClient({ baseUrl: 'http://api.test', timeoutMs: 1000, getToken: () => 'tok', onUnauthorized });

  it('sends the bearer token and validates the response schema', async () => {
    const fetchMock = mockFetch(200, { value: 1 });
    vi.stubGlobal('fetch', fetchMock);
    await expect(client().request('GET', '/x', { query: { a: 1, b: undefined }, schema: z.object({ value: z.number() }) })).resolves.toEqual({ value: 1 });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://api.test/x?a=1');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('resolves a relative base (/api/v1) on the page origin, so https pages call https', async () => {
    const fetchMock = mockFetch(200, { value: 1 });
    vi.stubGlobal('fetch', fetchMock);
    const relative = createHttpClient({ baseUrl: '/api/v1', timeoutMs: 1000, getToken: () => undefined, onUnauthorized: vi.fn() });
    await relative.request('GET', '/x', { schema: z.object({ value: z.number() }) });
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${window.location.origin}/api/v1/x`);
    expect(new URL(url).protocol).toBe(window.location.protocol);
  });

  it('turns a schema mismatch into a contract error instead of bad data', async () => {
    vi.stubGlobal('fetch', mockFetch(200, { value: 'one' }));
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    await expect(client().request('GET', '/x', { schema: z.object({ value: z.number() }) })).rejects.toMatchObject({ kind: 'contract' });
  });

  it('maps Laravel 422 field errors', async () => {
    vi.stubGlobal('fetch', mockFetch(422, { message: 'Invalid', errors: { email: ['Taken'] } }));
    const error = await client().request('POST', '/x', { schema: z.unknown() }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: 'validation', fieldErrors: { email: ['Taken'] } });
  });

  it('notifies on 401 so the session can be cleared', async () => {
    vi.stubGlobal('fetch', mockFetch(401, { message: 'Unauthenticated' }));
    const onUnauthorized = vi.fn();
    await expect(client(onUnauthorized).request('GET', '/x', { schema: z.unknown() })).rejects.toMatchObject({ kind: 'unauthorized' });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it('reports network failures as network errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(client().request('GET', '/x', { schema: z.unknown() })).rejects.toMatchObject({ kind: 'network' });
  });
});

describe('error messages', () => {
  it('are plain language and never expose internals', () => {
    expect(userMessage(new ApiError('server', 'SQLSTATE[42S02] stack…', { status: 500 }))).toBe('The server encountered an error. Please try again shortly.');
    expect(userMessage(new Error('boom'))).toBe('Something went wrong. Please try again.');
  });
});

describe('feed status', () => {
  it('prioritises offline, then explicit states, then staleness', () => {
    const now = 100_000;
    expect(effectiveFeedStatus('demo', false, now, now)).toBe('offline');
    expect(effectiveFeedStatus('closed', true, 0, now)).toBe('closed');
    expect(effectiveFeedStatus('demo', true, now - 15_000, now)).toBe('stale');
    expect(effectiveFeedStatus('live', true, now - 2_000, now)).toBe('live');
  });
});

describe('API auth against the FastAPI backend contract (round 3)', () => {
  afterEach(() => vi.unstubAllGlobals());

  const cfg = { dataSource: 'api' as const, apiBaseUrl: 'http://api.test/api/v1', wsUrl: 'ws://api.test/ws/market', apiTimeoutMs: 1000, pricePollMs: 1000, staleAfterMs: 10_000, issues: [] };
  const store = () => ({ get: () => null, set: () => undefined, readPersisted: () => null });
  const json = (status: number, body: unknown) => new Response(body === null ? null : JSON.stringify(body), { status });
  const user = { id: 'u1', email: 'sara@example.com', full_name: 'Sara K', role: 'trader', is_active: true, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' };
  const tokens = { access_token: 'acc', refresh_token: 'ref', token_type: 'bearer', expires_in: 1800 };

  it('signs in with TokenPair, then loads /users/me with the new access token', async () => {
    const { createApiServices } = await import('./api');
    const fetchMock = vi.fn().mockResolvedValueOnce(json(200, tokens)).mockResolvedValueOnce(json(200, user));
    vi.stubGlobal('fetch', fetchMock);
    const session = await createApiServices(cfg, store(), vi.fn()).auth.login({ email: 'sara@example.com', password: 'secret123' });
    expect(session).toMatchObject({ user: { id: 'u1', name: 'Sara K', email: 'sara@example.com', role: 'trader' }, token: 'acc', refreshToken: 'ref', isDemo: false });
    const [loginUrl, loginInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(loginUrl).toBe('http://api.test/api/v1/auth/login');
    expect((loginInit.headers as Record<string, string>).Authorization).toBeUndefined();
    const [meUrl, meInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(meUrl).toBe('http://api.test/api/v1/users/me');
    expect((meInit.headers as Record<string, string>).Authorization).toBe('Bearer acc');
  });

  it('reports wrong credentials as such — not as an expired session — and keeps the session handler idle', async () => {
    const { createApiServices } = await import('./api');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(401, { detail: 'Invalid credentials' })));
    const onUnauthorized = vi.fn();
    const err = await createApiServices(cfg, store(), onUnauthorized).auth.login({ email: 'a@b.co', password: 'wrongpass1' }).catch((e: unknown) => e);
    expect(userMessage(err)).toBe('The email or password is incorrect.');
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('maps 409 on register to an email field error, and FastAPI 422 details to fields', async () => {
    const { createApiServices } = await import('./api');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(409, { detail: 'Email already registered' })));
    const conflict = await createApiServices(cfg, store(), vi.fn()).auth.register({ name: 'Sara', email: 'sara@example.com', password: 'secret123' }).catch((e: unknown) => e);
    expect(conflict).toMatchObject({ kind: 'validation', fieldErrors: { email: ['An account with this email already exists. Sign in instead.'] } });

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json(422, { detail: [{ loc: ['body', 'password'], msg: 'Value error, Password must contain at least one letter and one digit', type: 'value_error' }] })));
    const invalid = await createApiServices(cfg, store(), vi.fn()).auth.register({ name: 'Sara', email: 'sara@example.com', password: 'abcdefgh' }).catch((e: unknown) => e);
    expect(invalid).toMatchObject({ kind: 'validation', fieldErrors: { password: ['Password must contain at least one letter and one digit'] } });
  });

  it('registers then signs in, and revokes the refresh token on logout', async () => {
    const { createApiServices } = await import('./api');
    const fetchMock = vi.fn().mockResolvedValueOnce(json(201, user)).mockResolvedValueOnce(json(200, tokens)).mockResolvedValueOnce(json(200, user)).mockResolvedValueOnce(json(204, null));
    vi.stubGlobal('fetch', fetchMock);
    const services = createApiServices(cfg, store(), vi.fn());
    const session = await services.auth.register({ name: 'Sara K', email: 'sara@example.com', password: 'secret123' });
    expect(JSON.parse(String((fetchMock.mock.calls[0] as [string, RequestInit])[1].body))).toEqual({ email: 'sara@example.com', password: 'secret123', full_name: 'Sara K' });
    await services.auth.logout(session);
    const [logoutUrl, logoutInit] = fetchMock.mock.calls[3] as [string, RequestInit];
    expect(logoutUrl).toBe('http://api.test/api/v1/auth/logout');
    expect(JSON.parse(String(logoutInit.body))).toEqual({ refresh_token: 'ref' });
    expect((logoutInit.headers as Record<string, string>).Authorization).toBe('Bearer acc');
  });
});
