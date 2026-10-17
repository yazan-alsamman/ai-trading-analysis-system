import type { z } from 'zod';
import { ApiError } from '../errors';

export interface HttpClientOptions {
  baseUrl: string;
  timeoutMs: number;
  /** The access token to send (may refresh it first when it is about to expire). */
  getToken: () => Promise<string | undefined> | string | undefined;
  /**
   * After a 401 on an authenticated request: obtain a new access token
   * (single-flight, see ./session.ts). Resolves undefined when the session is over.
   */
  refreshToken?: () => Promise<string | undefined>;
  /** Called when a request fails with 401 and the session could not be refreshed. */
  onUnauthorized?: () => void;
}

export interface RequestOptions<T> {
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  signal?: AbortSignal;
  /** Every response is validated; contract drift becomes a clear error, not a broken UI. */
  schema: z.ZodType<T>;
  /** Override the session token for this call (`null` = send none), e.g. during sign-in. */
  token?: string | null;
  /** The caller interprets 401 itself (sign-in forms) — no refresh, do not end the session. */
  authFailureHandled?: boolean;
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface HttpClient {
  request<T>(method: HttpMethod, path: string, options: RequestOptions<T>): Promise<T>;
}

function buildUrl(baseUrl: string, path: string, query?: RequestOptions<unknown>['query']): string {
  const url = new URL(`${baseUrl}${path}`);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  }
  return url.toString();
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Reads both error shapes the project may meet:
 *  - FastAPI (this monorepo's backend): `{ detail: "text" }`, or for 422
 *    `{ detail: [{ loc: ["body", "field"], msg: "..." }] }`
 *  - Laravel-style: `{ message, errors: { field: [msg] } }`
 * Anything else (HTML error pages from a proxy, plain text) yields no message.
 */
export function parseErrorBody(body: unknown): { message: string; fieldErrors: Record<string, string[]> | undefined } {
  if (typeof body !== 'object' || body === null) return { message: '', fieldErrors: undefined };
  const b = body as Record<string, unknown>;
  if (typeof b.detail === 'string') return { message: b.detail, fieldErrors: undefined };
  if (Array.isArray(b.detail)) {
    const fieldErrors: Record<string, string[]> = {};
    for (const item of b.detail as unknown[]) {
      if (typeof item !== 'object' || item === null) continue;
      const { loc, msg } = item as { loc?: unknown; msg?: unknown };
      const field = Array.isArray(loc) ? String(loc[loc.length - 1]) : 'form';
      if (typeof msg === 'string') (fieldErrors[field] ??= []).push(msg.replace(/^Value error, /, ''));
    }
    return { message: 'Some fields need attention.', fieldErrors };
  }
  const message = typeof b.message === 'string' ? b.message : '';
  const fieldErrors = typeof b.errors === 'object' && b.errors !== null ? (b.errors as Record<string, string[]>) : undefined;
  return { message, fieldErrors };
}

function errorFromResponse(status: number, body: unknown, requestId: string | null): ApiError {
  const { message, fieldErrors } = parseErrorBody(body);
  const extra = { status, ...(requestId ? { requestId } : {}) };
  if (status === 401) return new ApiError('unauthorized', message, extra);
  if (status === 403) return new ApiError('forbidden', message, extra);
  if (status === 404) return new ApiError('not_found', message, extra);
  if (status === 409) return new ApiError('conflict', message, extra);
  if (status === 400 || status === 422) return new ApiError('validation', message, { ...extra, ...(fieldErrors ? { fieldErrors } : {}) });
  if (status === 429) return new ApiError('rate_limited', message, extra);
  // 5xx details are internal: never shown verbatim.
  return new ApiError('server', `HTTP ${status}`, extra);
}

export function createHttpClient(options: HttpClientOptions): HttpClient {
  async function send<T>(method: HttpMethod, path: string, opts: RequestOptions<T>, token: string | undefined): Promise<{ response: Response; payload: unknown }> {
    const timeout = AbortSignal.timeout(options.timeoutMs);
    const combined = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout;
    let response: Response;
    try {
      response = await fetch(buildUrl(options.baseUrl, path, opts.query), {
        method,
        signal: combined,
        // Bearer tokens only: no cookies are needed or sent cross-origin.
        credentials: 'omit',
        headers: {
          Accept: 'application/json',
          ...(opts.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(opts.body !== undefined ? { body: JSON.stringify(opts.body) } : {}),
      });
    } catch (cause) {
      if (opts.signal?.aborted) throw new ApiError('aborted', 'Request cancelled', { cause });
      if (timeout.aborted) throw new ApiError('timeout', 'Request timed out', { cause });
      throw new ApiError('network', 'Network error', { cause });
    }
    return { response, payload: await readBody(response) };
  }

  return {
    async request<T>(method: HttpMethod, path: string, opts: RequestOptions<T>): Promise<T> {
      const token = opts.token === undefined ? await options.getToken() : (opts.token ?? undefined);
      let { response, payload } = await send(method, path, opts, token);

      // One transparent retry after refreshing an expired access token. A 401 means the
      // request was rejected before any work was done, so this is safe even for POST.
      if (response.status === 401 && token && opts.token === undefined && !opts.authFailureHandled && options.refreshToken) {
        const fresh = await options.refreshToken();
        if (fresh) ({ response, payload } = await send(method, path, opts, fresh));
      }

      if (!response.ok) {
        if (response.status === 401 && !opts.authFailureHandled) options.onUnauthorized?.();
        throw errorFromResponse(response.status, payload, response.headers.get('x-request-id'));
      }

      const parsed = opts.schema.safeParse(payload);
      if (!parsed.success) {
        console.error(`Contract mismatch for ${method} ${path}`, parsed.error.issues);
        throw new ApiError('contract', 'Unexpected response format', { cause: parsed.error });
      }
      return parsed.data;
    },
  };
}
