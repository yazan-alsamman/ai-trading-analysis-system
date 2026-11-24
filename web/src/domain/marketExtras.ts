/**
 * Read-only market context from the backend: news article detail, news
 * sentiment aggregates, news sources, the server's indicator catalog and
 * computation, the risk-config schema and the data-quality report.
 */

export type SentimentLabel = 'positive' | 'neutral' | 'negative';

export interface NewsArticle {
  id: string;
  source: { key: string; name: string };
  url: string;
  title: string;
  summary: string | null;
  imageUrl: string | null;
  author: string | null;
  language: string;
  publishedAt: number;
  fetchedAt: number;
  sentiment: { label: SentimentLabel; score: number | null; model: string | null } | null;
  instruments: { instrumentId: string; symbol: string; relevance: number }[];
}

export interface SentimentBucket {
  articles: number;
  scored: number;
  positive: number;
  neutral: number;
  negative: number;
  meanScore: number | null;
  weightedScore: number | null;
}

export interface SentimentAggregate {
  window: '1h' | '24h' | '7d';
  since: number;
  overall: SentimentBucket;
  instruments: (SentimentBucket & { instrumentId: string; symbol: string })[];
}

export interface IndicatorDefinition {
  name: string;
  title: string;
  category: string;
  /** `overlay` (on price) or `pane` (separate). */
  placement: string;
  params: { name: string; type: string; title: string; default: number | boolean | string | null; min: number | null; max: number | null }[];
  outputs: string[];
  levels: number[];
  lookback: number | null;
}

export interface IndicatorResult {
  name: string;
  params: Record<string, unknown>;
  placement: string;
  /** Output name → points (unix seconds; null during warm-up). */
  outputs: Record<string, { time: number; value: number | null }[]>;
}

export interface RiskSchema {
  jsonSchema: Record<string, unknown>;
  /** Normalised template configs (conservative, balanced, aggressive). */
  templates: Record<string, Record<string, unknown>>;
  defaultTemplate: string;
}

export type QualityStatus = 'ok' | 'degraded' | 'closed' | 'no_data';

export interface DataHealth {
  /** Worst instrument status; `disabled` when nothing is monitored. */
  status: QualityStatus | 'disabled';
  instruments: {
    instrument: string;
    timeframe: string;
    status: QualityStatus;
    lastClosedBar: number | null;
    lagSeconds: number | null;
    nextOpen: number | null;
    evaluatedAt: number;
    failedChecks: { name: string; ok: boolean; detail: string }[];
  }[];
}
