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
