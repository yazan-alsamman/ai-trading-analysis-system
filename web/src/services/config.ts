import { z } from 'zod';

/**
 * Runtime configuration from Vite env variables (see .env.example).
 * Invalid values fall back to the safe default: demo mode.
 *
 * Only PUBLIC values belong here: everything prefixed VITE_ is compiled into
 * the browser bundle. Server secrets (JWT keys, database URLs, provider keys)
 * must never be given a VITE_ name.
 */

/** An absolute http(s) URL, or a same-origin path such as `/api/v1` (production behind one Nginx). */
const BaseUrl = z
  .string()
  .trim()
  .refine((v) => /^https?:\/\//i.test(v) || v.startsWith('/'), 'Use an absolute http(s) URL or a path starting with "/"');

const EnvSchema = z.object({
  VITE_DATA_SOURCE: z.enum(['demo', 'api']).default('demo'),
  // Same-origin by default (production behind one Nginx); local development points it at the backend explicitly.
  VITE_API_BASE_URL: BaseUrl.default('/api/v1'),
  /** WebSocket endpoint for live market data. Default: derived from the API URL (`/ws/market` on the same host). */
  VITE_WS_URL: BaseUrl.or(z.string().regex(/^wss?:\/\//i)).optional(),
  VITE_API_TIMEOUT_MS: z.coerce.number().int().positive().default(10_000),
});

export type DataSource = 'demo' | 'api';

export interface AppConfig {
  dataSource: DataSource;
  /** Absolute REST base, e.g. https://host/api/v1 (no trailing slash). */
  apiBaseUrl: string;
  /** Absolute WebSocket URL of the market hub, e.g. wss://host/ws/market. */
  wsUrl: string;
  apiTimeoutMs: number;
  /** Polling interval of the REST fallback when the WebSocket is unavailable. */
  pricePollMs: number;
  /** A feed with no update for this long is shown as stale. */
  staleAfterMs: number;
}

function origin(): string {
  return typeof window !== 'undefined' && window.location?.origin && window.location.origin !== 'null' ? window.location.origin : 'http://localhost';
}

/** `/api/v1` → `https://current-host/api/v1`; absolute URLs pass through. */
export function resolveBaseUrl(value: string): string {
  const abs = value.startsWith('/') ? `${origin()}${value}` : value;
  return abs.replace(/\/+$/, '');
}

/** The market hub lives at `/ws/market` on the API's host (docs/websocket.md). */
export function deriveWsUrl(apiBaseUrl: string, explicit?: string): string {
  if (explicit) {
    const abs = explicit.startsWith('/') ? `${origin()}${explicit}` : explicit;
    return abs.replace(/^http/i, 'ws').replace(/\/+$/, '');
  }
  const u = new URL(apiBaseUrl);
  return `${u.protocol === 'https:' ? 'wss:' : 'ws:'}//${u.host}/ws/market`;
}

export function loadConfig(env: Record<string, unknown> = import.meta.env): AppConfig {
  const parsed = EnvSchema.safeParse(env);
  if (!parsed.success) {
    console.warn('Invalid environment configuration — falling back to demo mode.', z.prettifyError(parsed.error));
  }
  const values = parsed.success ? parsed.data : EnvSchema.parse({});
  const apiBaseUrl = resolveBaseUrl(values.VITE_API_BASE_URL);
  return {
    dataSource: values.VITE_DATA_SOURCE,
    apiBaseUrl,
    wsUrl: deriveWsUrl(apiBaseUrl, values.VITE_WS_URL),
    apiTimeoutMs: values.VITE_API_TIMEOUT_MS,
    pricePollMs: 15_000,
    // Demo ticks every second; backend 1-minute candles may legitimately go quiet for longer.
    staleAfterMs: values.VITE_DATA_SOURCE === 'api' ? 90_000 : 10_000,
  };
}

export const config: AppConfig = loadConfig();
