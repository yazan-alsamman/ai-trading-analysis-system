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

const DataSourceSchema = z.enum(['demo', 'api']);
const WsUrl = BaseUrl.or(z.string().regex(/^wss?:\/\//i));
const Timeout = z.coerce.number().int().positive();

export type DataSource = 'demo' | 'api';

/** A configuration value the app refuses to guess about. The app shows these instead of starting. */
export interface ConfigIssue {
  variable: string;
  /** The public value received (VITE_ variables are compiled into the bundle; never secrets). */
  value: string;
  message: string;
}

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
  /**
   * Blocking problems. Demo mode is only ever used when VITE_DATA_SOURCE is
   * unset or `demo`: a malformed value never silently swaps real data for
   * simulated data.
   */
  issues: ConfigIssue[];
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

const present = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';

export function loadConfig(env: Record<string, unknown> = import.meta.env): AppConfig {
  const issues: ConfigIssue[] = [];
  const issue = (variable: string, value: unknown, message: string) => issues.push({ variable, value: String(value), message });

  // Unset = demo (the documented default). Anything else must be exactly `demo` or `api`.
  const rawSource = env.VITE_DATA_SOURCE;
  let dataSource: DataSource = 'demo';
  if (present(rawSource)) {
    const parsed = DataSourceSchema.safeParse(rawSource.trim());
    if (parsed.success) dataSource = parsed.data;
    else issue('VITE_DATA_SOURCE', rawSource, 'Must be "demo" or "api".');
  }

  let apiBase = '/api/v1';
  if (present(env.VITE_API_BASE_URL)) {
    const parsed = BaseUrl.safeParse(env.VITE_API_BASE_URL);
    if (parsed.success) apiBase = parsed.data;
    // In demo mode the API URL is unused; in API mode a wrong URL would talk to the wrong server.
    else if (dataSource === 'api')
      issue(
        'VITE_API_BASE_URL',
        env.VITE_API_BASE_URL,
        'Use an absolute http(s) URL or a path starting with "/". (Git Bash on Windows rewrites "/api/v1" into a Windows path: leave it unset or put it in .env.local.)',
      );
  }

  let wsExplicit: string | undefined;
  if (present(env.VITE_WS_URL)) {
    const parsed = WsUrl.safeParse(env.VITE_WS_URL);
    if (parsed.success) wsExplicit = parsed.data;
    else if (dataSource === 'api') issue('VITE_WS_URL', env.VITE_WS_URL, 'Use a ws(s):// or http(s):// URL, a path starting with "/", or leave it empty.');
  }

  let apiTimeoutMs = 10_000;
  if (env.VITE_API_TIMEOUT_MS !== undefined && env.VITE_API_TIMEOUT_MS !== '') {
    const parsed = Timeout.safeParse(env.VITE_API_TIMEOUT_MS);
    if (parsed.success) apiTimeoutMs = parsed.data;
    else console.warn(`VITE_API_TIMEOUT_MS=${String(env.VITE_API_TIMEOUT_MS)} is not a positive integer; using 10000.`);
  }

  if (issues.length) console.error('Invalid configuration:', issues);
  const apiBaseUrl = resolveBaseUrl(apiBase);
  return {
    dataSource,
    apiBaseUrl,
    wsUrl: deriveWsUrl(apiBaseUrl, wsExplicit),
    apiTimeoutMs,
    pricePollMs: 15_000,
    // Demo ticks every second; backend 1-minute candles may legitimately go quiet for longer.
    staleAfterMs: dataSource === 'api' ? 90_000 : 10_000,
    issues,
  };
}

export const config: AppConfig = loadConfig();
