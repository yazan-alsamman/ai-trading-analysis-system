import { z } from 'zod';
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';

/**
 * Runtime schemas for every payload crossing the client boundary
 * (backend responses and localStorage). They mirror src/domain types and are
 * the executable version of docs/API_INTEGRATION.md.
 */

export const SymbolSchema = z.enum(INSTRUMENT_SYMBOLS);
export const TimeframeSchema = z.enum(['15m', '1h', '4h']);
export const ProvenanceSchema = z.enum(['demo', 'live']);
export const ChannelSchema = z.enum(['app', 'email', 'telegram']);
const Epoch = z.number().int().nonnegative();

export const CandleSchema = z.object({
  time: Epoch,
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number().nonnegative(),
});

export const CandleSeriesSchema = z.object({
  symbol: SymbolSchema,
  timeframe: TimeframeSchema,
  candles: z.array(CandleSchema),
  volumeKind: z.enum(['tick', 'real']),
  provenance: ProvenanceSchema,
  asOf: Epoch,
});

export const QuoteSchema = z.object({
  symbol: SymbolSchema,
  price: z.number(),
  reference: z.number(),
  time: Epoch,
  provenance: ProvenanceSchema,
});

const ZoneSchema = z.object({ low: z.number(), high: z.number() });

export const OpportunitySchema = z.object({
  id: z.string(),
  symbol: SymbolSchema,
  timeframe: TimeframeSchema,
  status: z.enum(['detected', 'not_detected']),
  direction: z.enum(['long', 'short', 'neutral']),
  setupType: z.enum(['trend_following', 'mean_reversion', 'breakout', 'scalping']),
  riskLevel: z.enum(['low', 'medium', 'high']),
  probability: z.number().min(0).max(1),
  confidenceBand: z.object({ low: z.number().min(0).max(1), high: z.number().min(0).max(1) }).optional(),
  entryZone: ZoneSchema,
  stopLossZone: ZoneSchema,
  takeProfitZone: ZoneSchema,
  riskReward: z.number().positive(),
  expectedValueR: z.number().optional(),
  factors: z.array(z.object({ id: z.string(), label: z.string(), detail: z.string(), contribution: z.number() })),
  forecast: z.array(z.object({ time: Epoch, value: z.number() })).optional(),
  horizonCandles: z.number().int().positive(),
  signalCandleTime: Epoch,
  generatedAt: Epoch,
  validUntil: Epoch,
  modelVersion: z.string(),
  provenance: ProvenanceSchema,
});

export const PredictionRecordSchema = z.object({
  id: z.string(),
  symbol: SymbolSchema,
  timeframe: TimeframeSchema,
  direction: z.enum(['long', 'short']),
  probability: z.number().min(0).max(1),
  riskReward: z.number().positive(),
  generatedAt: Epoch,
  resolvedAt: Epoch.optional(),
  outcome: z.enum(['tp_hit', 'sl_hit', 'expired', 'open']),
  realizedR: z.number().optional(),
  requestedByUser: z.boolean(),
  modelVersion: z.string(),
  provenance: ProvenanceSchema,
});

export const PriceAlertSchema = z.object({
  id: z.string(),
  symbol: SymbolSchema,
  condition: z.enum(['crosses_above', 'crosses_below']),
  price: z.number().positive(),
  channels: z.array(ChannelSchema),
  note: z.string().optional(),
  status: z.enum(['active', 'paused', 'triggered']),
  createdAt: Epoch,
  triggeredAt: Epoch.optional(),
});

export const OpportunityPreferencesSchema = z.object({
  enabled: z.boolean(),
  minProbability: z.number().min(0).max(1),
  symbols: z.array(SymbolSchema),
  timeframes: z.array(TimeframeSchema),
  directions: z.array(z.enum(['long', 'short'])),
  channels: z.array(ChannelSchema),
});

const RoleSchema = z.enum(['trader', 'analyst', 'expert', 'admin']);
const AuthorSchema = z.object({ id: z.string(), name: z.string(), role: RoleSchema });

export const NewsItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  source: z.string(),
  publishedAt: Epoch,
  symbols: z.array(SymbolSchema),
  impact: z.enum(['low', 'medium', 'high']),
  commentCount: z.number().int().nonnegative(),
  provenance: ProvenanceSchema,
});

export const CommentSchema = z.object({
  id: z.string(),
  threadId: z.string(),
  author: AuthorSchema,
  body: z.string(),
  createdAt: Epoch,
});

export const PostSchema = z.object({
  id: z.string(),
  author: AuthorSchema,
  body: z.string(),
  symbols: z.array(SymbolSchema),
  createdAt: Epoch,
  commentCount: z.number().int().nonnegative(),
  provenance: ProvenanceSchema,
});

export const ExpertSchema = z.object({
  id: z.string(),
  name: z.string(),
  headline: z.string(),
  specialties: z.array(z.string()),
  markets: z.array(SymbolSchema),
  languages: z.array(z.string()),
  availability: z.enum(['available', 'busy', 'offline']),
  provenance: ProvenanceSchema,
});

export const ChatMessageSchema = z.object({
  id: z.string(),
  from: z.enum(['user', 'expert']),
  body: z.string(),
  sentAt: Epoch,
});

export const SessionSchema = z.object({
  user: z.object({ id: z.string(), name: z.string(), email: z.string(), role: RoleSchema }),
  token: z.string().optional(),
  refreshToken: z.string().optional(),
  /** Access-token expiry (epoch ms). */
  expiresAt: z.number().optional(),
  isDemo: z.boolean(),
});

/** FastAPI `POST /api/v1/auth/login` → TokenPair (backend/app/schemas/auth.py). */
export const TokenPairSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  token_type: z.literal('bearer'),
  expires_in: z.number().int().positive(),
});

/** FastAPI `UserRead` (backend/app/schemas/user.py). */
export const UserReadSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string().nullable(),
  role: RoleSchema,
  is_active: z.boolean(),
});

export const AssistantReplySchema = z.object({
  id: z.string(),
  content: z.string(),
  createdAt: z.number(),
  provider: z.literal('remote').default('remote'),
  contextUsed: z.array(z.string()).default([]),
});
