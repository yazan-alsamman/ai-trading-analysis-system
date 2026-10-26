import { z } from 'zod';
import type { DataHealth, IndicatorDefinition, NewsArticle, SentimentBucket } from '@/domain/marketExtras';
import type { MarketContextService } from '../types';
import { SourceRead, toSource } from './adminApi';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';

/**
 * Read-only market context: news article detail, sentiment aggregates and
 * sources, the server's indicator catalog and computation, the risk-config
 * schema and the data-quality report.
 */

const opt = (signal?: AbortSignal): { signal?: AbortSignal } => (signal ? { signal } : {});
const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
};
const msReq = (iso: string) => ms(iso) ?? 0;
const Json = z.record(z.string(), z.unknown());

const ArticleRead = z.object({
  id: z.string(),
  source: z.object({ key: z.string(), name: z.string() }),
  url: z.string(),
  title: z.string(),
  summary: z.string().nullable(),
  image_url: z.string().nullable().optional(),
  author: z.string().nullable().optional(),
  language: z.string(),
  published_at: z.string(),
  fetched_at: z.string(),
  sentiment: z.object({ label: z.enum(['positive', 'neutral', 'negative']), score: z.number().nullable(), model: z.string().nullable().optional() }).nullable(),
  instruments: z.array(z.object({ instrument_id: z.string(), symbol: z.string(), relevance: z.number() })),
});
const Bucket = z.object({
  articles: z.number().int(),
  scored: z.number().int(),
  positive: z.number().int(),
  neutral: z.number().int(),
  negative: z.number().int(),
  mean_score: z.number().nullable(),
  weighted_score: z.number().nullable().optional(),
});
const toBucket = (b: z.infer<typeof Bucket>): SentimentBucket => ({
  articles: b.articles,
  scored: b.scored,
  positive: b.positive,
  neutral: b.neutral,
  negative: b.negative,
  meanScore: b.mean_score,
  weightedScore: b.weighted_score ?? null,
});
const ParamRead = z.object({
  name: z.string(),
  type: z.string(),
  title: z.string().optional(),
  default: z.union([z.number(), z.boolean(), z.string()]).nullable().optional(),
  min: z.number().nullable().optional(),
  max: z.number().nullable().optional(),
});
const IndicatorRead = z.object({
  name: z.string(),
  title: z.string(),
  category: z.string(),
  placement: z.string(),
  params: z.array(ParamRead),
  outputs: z.array(z.string()),
  levels: z.array(z.unknown()).optional().default([]),
  lookback: z.number().int().nullable().optional(),
});
const toIndicator = (i: z.infer<typeof IndicatorRead>): IndicatorDefinition => ({
  name: i.name,
  title: i.title,
  category: i.category,
  placement: i.placement,
  params: i.params.map((p) => ({ name: p.name, type: p.type, title: p.title ?? p.name, default: p.default ?? null, min: p.min ?? null, max: p.max ?? null })),
  outputs: i.outputs,
  levels: i.levels.filter((l): l is number => typeof l === 'number'),
  lookback: i.lookback ?? null,
});
const QualityStatus = z.enum(['ok', 'degraded', 'closed', 'no_data']);
const DataHealthRead = z.object({
  status: z.union([QualityStatus, z.literal('disabled')]).catch('degraded'),
  instruments: z.array(
    z.object({
      instrument: z.string(),
      timeframe: z.string(),
      status: QualityStatus,
      last_closed_bar: z.string().nullable(),
      lag_seconds: z.number().nullable(),
      next_open: z.string().nullable().optional(),
      evaluated_at: z.string(),
      failed_checks: z.array(z.object({ name: z.string(), ok: z.boolean(), detail: z.string() })),
    }),
  ),
});
const toHealth = (h: z.infer<typeof DataHealthRead>): DataHealth => ({
  status: h.status,
  instruments: h.instruments.map((i) => ({
    instrument: i.instrument,
    timeframe: i.timeframe,
    status: i.status,
    lastClosedBar: ms(i.last_closed_bar),
    lagSeconds: i.lag_seconds,
    nextOpen: ms(i.next_open),
    evaluatedAt: msReq(i.evaluated_at),
    failedChecks: i.failed_checks,
  })),
});

export function apiMarketContextService(http: HttpClient): MarketContextService {
  return {
    async article(id, o): Promise<NewsArticle> {
      const a = await http.request('GET', endpoints.newsExtra.article(id), { schema: ArticleRead, ...opt(o?.signal) });
      return {
        id: a.id,
        source: a.source,
        url: a.url,
        title: a.title,
        summary: a.summary,
        imageUrl: a.image_url ?? null,
        author: a.author ?? null,
        language: a.language,
        publishedAt: msReq(a.published_at),
        fetchedAt: msReq(a.fetched_at),
        sentiment: a.sentiment ? { label: a.sentiment.label, score: a.sentiment.score, model: a.sentiment.model ?? null } : null,
        instruments: a.instruments.map((t) => ({ instrumentId: t.instrument_id, symbol: t.symbol, relevance: t.relevance })),
      };
    },
    async sentiment(window, instrumentId, o) {
      const r = await http.request('GET', endpoints.newsExtra.sentiment, {
        query: { window, ...(instrumentId ? { instrument_id: instrumentId } : {}) },
        schema: z.object({ window: z.enum(['1h', '24h', '7d']), since: z.string(), overall: Bucket, instruments: z.array(Bucket.extend({ instrument_id: z.string(), symbol: z.string() })) }),
        ...opt(o?.signal),
      });
      return {
        window: r.window,
        since: msReq(r.since),
        overall: toBucket(r.overall),
        instruments: r.instruments.map((i) => ({ ...toBucket(i), instrumentId: i.instrument_id, symbol: i.symbol })),
      };
    },
    newsSources: async (o) => (await http.request('GET', endpoints.newsExtra.sources, { schema: z.array(SourceRead), ...opt(o?.signal) })).map(toSource),
    indicatorCatalog: async (o) => (await http.request('GET', endpoints.indicators.catalog, { schema: z.array(IndicatorRead), ...opt(o?.signal) })).map(toIndicator),
    async computeIndicators(instrumentId, input, o) {
      const r = await http.request('POST', endpoints.indicators.compute(instrumentId), {
        body: { timeframe: input.timeframe, limit: input.limit, indicators: input.indicators },
        schema: z.object({
          results: z.array(z.object({ name: z.string(), params: Json, placement: z.string(), outputs: z.record(z.string(), z.array(z.object({ time: z.number(), value: z.number().nullable() }))) })),
        }),
        ...opt(o?.signal),
      });
      return r.results;
    },
    async riskSchema(o) {
      const r = await http.request('GET', endpoints.riskSchema, { schema: z.object({ json_schema: Json, templates: z.record(z.string(), Json), default_template: z.string() }), ...opt(o?.signal) });
      return { jsonSchema: r.json_schema, templates: r.templates, defaultTemplate: r.default_template };
    },
    async dataHealth(o) {
      // 503 = some instrument is degraded or has no data; the body is the same report.
      return toHealth(await http.request('GET', endpoints.health.data, { schema: DataHealthRead, token: null, acceptStatus: [503], ...opt(o?.signal) }));
    },
  };
}
