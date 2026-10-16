import { z } from 'zod';

/**
 * Runtime configuration from Vite env variables (see .env.example).
 * Invalid values fall back to the safe default: demo mode.
 */
const EnvSchema = z.object({
  VITE_DATA_SOURCE: z.enum(['demo', 'api']).default('demo'),
  VITE_API_BASE_URL: z.url().default('http://localhost:8000/api/v1'),
  VITE_API_TIMEOUT_MS: z.coerce.number().int().positive().default(10_000),
});

export type DataSource = 'demo' | 'api';

export interface AppConfig {
  dataSource: DataSource;
  apiBaseUrl: string;
  apiTimeoutMs: number;
  /** Polling interval used by the REST fallback for price updates (SF9). */
  pricePollMs: number;
  /** A feed with no update for this long is shown as stale. */
  staleAfterMs: number;
}

function loadConfig(): AppConfig {
  const parsed = EnvSchema.safeParse(import.meta.env);
  if (!parsed.success) {
    console.warn('Invalid environment configuration — falling back to demo mode.', z.prettifyError(parsed.error));
  }
  const env = parsed.success ? parsed.data : EnvSchema.parse({});
  return {
    dataSource: env.VITE_DATA_SOURCE,
    apiBaseUrl: env.VITE_API_BASE_URL.replace(/\/+$/, ''),
    apiTimeoutMs: env.VITE_API_TIMEOUT_MS,
    pricePollMs: 1_000,
    staleAfterMs: 10_000,
  };
}

export const config: AppConfig = loadConfig();
