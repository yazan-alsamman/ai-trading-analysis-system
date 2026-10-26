/**
 * Personal API keys (docs/api-keys.md): read-only programmatic access to
 * market data, indicators, strategies, signals, backtests and news. The full
 * key is shown ONCE, at creation; the server stores only a hash.
 */

export interface ApiKey {
  id: string;
  name: string;
  /** First characters of the key, to recognise it. */
  prefix: string;
  scopes: string[];
  rateLimitPerMinute: number | null;
  expiresAt: number | null;
  lastUsedAt: number | null;
  revoked: boolean;
  createdAt: number;
}

export interface ApiKeyScope {
  scope: string;
  description: string;
  /** False for scopes reserved to admins (e.g. `news:write`). */
  grantable: boolean;
}

export interface ApiKeyInput {
  name: string;
  scopes: string[];
  expiresInDays: number | null;
  rateLimitPerMinute: number | null;
}

export interface ApiKeyUsageDay {
  date: string;
  requests: number;
  rejected: number;
}
