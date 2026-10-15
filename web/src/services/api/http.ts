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
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface HttpClient {
  request<T>(method: HttpMethod, path: string, options: RequestOptions<T>): Promise<T>;
}

function buildUrl(baseUrl: string, path: string, query?: RequestOptions<unknown>['query']): string {
  const url = new URL(`${baseUrl}${path}`);
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

function errorFromResponse(status: number, body: unknown): ApiError {
  const message =
    typeof body === 'object' && body !== null && 'message' in body && typeof body.message === 'string' ? body.message : '';
  const fieldErrors =
    typeof body === 'object' && body !== null && 'errors' in body && typeof body.errors === 'object' && body.errors !== null
      ? (body.errors as Record<string, string[]>)
      : undefined;

  if (status === 401) return new ApiError('unauthorized', message, { status });
  if (status === 403) return new ApiError('forbidden', message, { status });
  if (status === 404) return new ApiError('not_found', message, { status });
  if (status === 422) return new ApiError('validation', message, { status, ...(fieldErrors ? { fieldErrors } : {}) });
  if (status === 429) return new ApiError('rate_limited', message, { status });
  return new ApiError('server', message || `HTTP ${status}`, { status });
}

export function createHttpClient(options: HttpClientOptions): HttpClient {
  return {
    async request<T>(method: HttpMethod, path: string, { query, body, signal, schema }: RequestOptions<T>): Promise<T> {
      const timeout = AbortSignal.timeout(options.timeoutMs);
      const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
      const token = options.getToken();

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
        if (response.status === 401) options.onUnauthorized?.();
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
