import type { SetupState } from './aiSetups';
import type { UserRole } from './user';

/**
 * Administration (backend: /admin/*, admin role only). Objects whose shape the
 * backend owns and documents only loosely (system status, hub, rate-limit,
 * notification and payment statistics, the cTrader feed) are kept as JSON
 * and shown as they are, never reinterpreted.
 */

export type JsonObject = Record<string, unknown>;

export interface Paged<T> {
  items: T[];
  total: number;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  role: UserRole;
  isActive: boolean;
  createdAt: number;
}

export type ReportStatus = 'open' | 'resolved';

export interface AdminReport {
  id: string;
  targetType: 'post' | 'comment' | 'message';
  targetId: string;
  reason: string;
  status: ReportStatus;
  resolution: string | null;
  createdAt: number;
  resolvedAt: number | null;
  reporter: { id: string; name: string; role: UserRole } | null;
  /** Excerpt of the reported content: {status, author, title?, excerpt, post_id}. */
  target: JsonObject | null;
  openReportsOnTarget: number;
}

export interface AdminSubscription {
  id: string;
  user: { id: string; name: string; role: UserRole };
  expert: { id: string; name: string; role: UserRole };
  planId: string;
  status: string;
  price: string;
  currency: string;
  interval: string;
  currentPeriodEnd: number;
  cancelAtPeriodEnd: boolean;
  pastDueSince: number | null;
  endedAt: number | null;
  createdAt: number;
}

export interface AdminInvoice {
  id: string;
  number: string;
  amount: string;
  currency: string;
  status: string;
  refundedAt: number | null;
}

export interface AdminApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  ownerEmail: string;
  userId: string;
  rateLimitPerMinute: number | null;
  expiresAt: number | null;
  lastUsedAt: number | null;
  revoked: boolean;
  createdAt: number;
}

export interface NewsSource {
  id: string;
  key: string;
  name: string;
  kind: 'rss' | 'api' | 'manual';
  url: string | null;
  language: string;
  isActive: boolean;
  fetchIntervalMinutes: number;
  lastFetchedAt: number | null;
  lastError: string | null;
  articles: number | null;
}

/** An instrument with its trading specs (as the admin endpoints return it). */
export interface AdminInstrument {
  id: string;
  symbol: string;
  source: string;
  market: 'crypto' | 'forex' | 'stock' | 'commodity';
  baseAsset: string;
  quoteAsset: string;
  pricePrecision: number | null;
  quantityPrecision: number | null;
  isActive: boolean;
  /** Spec fields (contract_size, tick_size, lot_step, min_lot, max_lot, quote_currency, margin_rate, price_basis, cost_per_unit, session_calendar…), as sent. */
  specs: JsonObject;
}

export interface AdminAISetup {
  setupId: string;
  instrumentId: string;
  profile: string;
  direction: string;
  state: SetupState;
  entry: number | null;
  sl: number | null;
  tp: number | null;
  rMultiple: number | null;
  probability: number | null;
  grade: string | null;
  realizedR: number | null;
  strategyVersion: string | null;
  modelVersion: string | null;
  createdAt: number;
  updatedAt: number;
}

export interface AdminAISetupDetail extends AdminAISetup {
  events: { from: SetupState | null; to: SetupState; at: number; reason: string | null; realizedR: number | null }[];
  sizes: { userId: string; lots: number; feasible: boolean; source: string; computedAt: number }[];
  takesCount: number;
  outbox: AIOutboxRow[];
  evidence: JsonObject;
  lastPayload: JsonObject;
}

export interface AIOutboxRow {
  id: number;
  setupId: string;
  from: SetupState | null;
  to: SetupState;
  status: string;
  attempts: number;
  lastError: string | null;
  createdAt: number;
  processedAt: number | null;
}

export interface AIModel {
  modelId: string;
  createdAt: number;
  trainingFrom: number | null;
  trainingTo: number | null;
  dataHash: string | null;
  metrics: JsonObject;
  isActive: boolean;
  notes: string | null;
}

/** A manually published article (POST /ingest/news, admin login). */
export interface ArticleInput {
  sourceKey: string;
  externalId: string;
  url: string;
  title: string;
  summary: string | null;
  publishedAt: string;
  language: string | null;
  instruments: { symbol: string; relevance: number }[];
  sentiment: { label: 'positive' | 'neutral' | 'negative'; score: number; model: string } | null;
}

export interface IngestResult {
  inserted: number;
  updated: number;
  skipped: number;
  errors: { index: number; error: string }[];
  warnings: { index: number; error: string }[];
}
