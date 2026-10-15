import type { OpportunityAlertPreferences, PriceAlert, PriceAlertDraft } from '@/domain/alerts';
import type { ChatMessage, Comment, Expert, NewsItem, Post } from '@/domain/community';
import type { InstrumentSymbol } from '@/domain/instruments';
import type { Candle, CandleSeries, FeedStatus, Quote, Timeframe } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import type { PredictionRecord } from '@/domain/predictions';
import type { LoginInput, RegisterInput, Session } from '@/domain/user';
import type { DataSource } from './config';

/**
 * Service interfaces — the boundary between UI and data.
 * Two implementations exist: `services/demo/*` (simulated fixtures) and
 * `services/api/*` (backend). UI code depends only on these interfaces.
 */

export interface CallOptions {
  signal?: AbortSignal;
}

export type Unsubscribe = () => void;

export interface CandleStreamHandlers {
  /** Called with the latest (possibly still-forming) candle. */
  onCandle: (candle: Candle) => void;
  onStatus: (status: FeedStatus) => void;
}

export interface QuoteStreamHandlers {
  onQuotes: (quotes: Quote[]) => void;
  onStatus: (status: FeedStatus) => void;
}

export interface MarketDataService {
  /** `limit` = most recent N candles (default: full history the source provides). */
  getCandles(symbol: InstrumentSymbol, timeframe: Timeframe, options?: CallOptions & { limit?: number }): Promise<CandleSeries>;
  getQuotes(options?: CallOptions): Promise<Quote[]>;
  subscribeCandles(symbol: InstrumentSymbol, timeframe: Timeframe, handlers: CandleStreamHandlers): Unsubscribe;
  subscribeQuotes(handlers: QuoteStreamHandlers): Unsubscribe;
}

export interface OpportunityQuery {
  symbol?: InstrumentSymbol;
  timeframe?: Timeframe;
}

export interface OpportunityService {
  /** Latest analysis for one instrument/timeframe (status may be `not_detected`). */
  getLatest(symbol: InstrumentSymbol, timeframe: Timeframe, options?: CallOptions): Promise<Opportunity>;
  list(query?: OpportunityQuery, options?: CallOptions): Promise<Opportunity[]>;
}

export interface PredictionService {
  listHistory(options?: CallOptions): Promise<PredictionRecord[]>;
}

export interface AlertService {
  list(options?: CallOptions): Promise<PriceAlert[]>;
  create(draft: PriceAlertDraft): Promise<PriceAlert>;
  update(id: string, patch: Partial<PriceAlertDraft> & { status?: PriceAlert['status']; triggeredAt?: number }): Promise<PriceAlert>;
  remove(id: string): Promise<void>;
  getOpportunityPreferences(options?: CallOptions): Promise<OpportunityAlertPreferences>;
  saveOpportunityPreferences(prefs: OpportunityAlertPreferences): Promise<OpportunityAlertPreferences>;
}

export interface CommunityService {
  listNews(options?: CallOptions): Promise<NewsItem[]>;
  listComments(threadId: string, options?: CallOptions): Promise<Comment[]>;
  addComment(threadId: string, body: string): Promise<Comment>;
  listPosts(options?: CallOptions): Promise<Post[]>;
  createPost(input: { body: string; symbols: InstrumentSymbol[] }): Promise<Post>;
  listExperts(options?: CallOptions): Promise<Expert[]>;
  getConversation(expertId: string, options?: CallOptions): Promise<ChatMessage[]>;
  /** Expert chat (SF13) needs a realtime backend; implementations may reject with `not_available`. */
  sendMessage(expertId: string, body: string): Promise<ChatMessage>;
}

export interface AuthService {
  login(input: LoginInput): Promise<Session>;
  register(input: RegisterInput): Promise<Session>;
  logout(session: Session): Promise<void>;
}

export interface Services {
  source: DataSource;
  market: MarketDataService;
  opportunities: OpportunityService;
  predictions: PredictionService;
  alerts: AlertService;
  community: CommunityService;
  auth: AuthService;
}
