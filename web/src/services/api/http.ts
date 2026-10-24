import type { z } from 'zod';
import { ApiError } from '../errors';

export interface HttpClientOptions {
  baseUrl: string;
  timeoutMs: number;
  /** Returns the current bearer token, if any. */
  getToken: () => string | undefined;
  /** Called once per 401 so the app can clear the session. */
  onUnauthorized?: () => void;
}

export interface RequestOptions<T> {
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  signal?: AbortSignal;
  /** Every response is validated; contract drift becomes a clear error, not a broken UI. */
  schema: z.ZodType<T>;
  /** Override the session token for this call (`null` = send none), e.g. during sign-in. */
  token?: string | null;
  /** The caller interprets 401 itself (sign-in forms) — do not end the session. */
  authFailureHandled?: boolean;
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface HttpClient {
  request<T>(method: HttpMethod, path: string, options: RequestOptions<T>): Promise<T>;
}

function buildUrl(baseUrl: string, path: string, query?: RequestOptions<unknown>['query']): string {
  // a relative base (/api/v1) resolves against the page, so it keeps the page's scheme
  const url = new URL(`${baseUrl}${path}`, globalThis.location?.origin);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined) url.searchParams.set(k, String(v));
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

function errorFromResponse(status: number, body: unknown): ApiError {
  const { message, fieldErrors } = parseErrorBody(body);

  if (status === 401) return new ApiError('unauthorized', message, { status });
  if (status === 403) return new ApiError('forbidden', message, { status });
  if (status === 404) return new ApiError('not_found', message, { status });
  if (status === 409) return new ApiError('conflict', message, { status });
  if (status === 400 || status === 422) return new ApiError('validation', message, { status, ...(fieldErrors ? { fieldErrors } : {}) });
  if (status === 429) return new ApiError('rate_limited', message, { status });
  return new ApiError('server', message || `HTTP ${status}`, { status });
}

export function createHttpClient(options: HttpClientOptions): HttpClient {
  return {
    async request<T>(method: HttpMethod, path: string, { query, body, signal, schema, token: tokenOverride, authFailureHandled }: RequestOptions<T>): Promise<T> {
      const timeout = AbortSignal.timeout(options.timeoutMs);
      const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
      const token = tokenOverride === undefined ? options.getToken() : (tokenOverride ?? undefined);

      let response: Response;
      try {
        response = await fetch(buildUrl(options.baseUrl, path, query), {
          method,
          signal: combined,
          headers: {
            Accept: 'application/json',
            ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        });
      } catch (cause) {
        if (signal?.aborted) throw new ApiError('aborted', 'Request cancelled', { cause });
        if (timeout.aborted) throw new ApiError('timeout', 'Request timed out', { cause });
        throw new ApiError('network', 'Network error', { cause });
      }

      const payload = await readBody(response);
      if (!response.ok) {
        if (response.status === 401 && !authFailureHandled) options.onUnauthorized?.();
        throw errorFromResponse(response.status, payload);
      }

      const parsed = schema.safeParse(payload);
      if (!parsed.success) {
        console.error(`Contract mismatch for ${method} ${path}`, parsed.error.issues);
        throw new ApiError('contract', 'Unexpected response format', { cause: parsed.error });
      }
      return parsed.data;
    },
  };
}
