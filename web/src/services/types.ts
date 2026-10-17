import type { OpportunityAlertPreferences, PriceAlert, PriceAlertDraft } from '@/domain/alerts';
import type { AssistantContext, AssistantDescription, AssistantMessage, AssistantReply } from '@/domain/assistant';
import type { ChatMessage, Comment, Expert, NewsItem, Post } from '@/domain/community';
import type { InstrumentSymbol } from '@/domain/instruments';
import type { Candle, CandleSeries, FeedStatus, Quote, Timeframe } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import type { PredictionRecord } from '@/domain/predictions';
import type { StrategySignal } from '@/domain/strategySignals';
import type { LoginInput, RegisterInput, Session, User } from '@/domain/user';
import type { AppNotification } from '@/app/notifications';
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

/**
 * AI assistant boundary (provider-agnostic). The browser sends the
 * conversation and the explicit context; the backend owns the provider and its
 * credentials. Implementations must not claim data that is not in `context`.
 */
export interface AssistantService {
  describe(): AssistantDescription;
  reply(messages: readonly AssistantMessage[], context: AssistantContext, options?: CallOptions): Promise<AssistantReply>;
}

/** The signed-in account (backend: GET/PATCH /users/me, POST /users/me/password). */
export interface AccountService {
  getProfile(options?: CallOptions): Promise<User>;
  updateProfile(input: { name: string }): Promise<User>;
  changePassword(input: { currentPassword: string; newPassword: string }): Promise<void>;
}

/** Server notification inbox (backend: /me/notifications). Demo mode keeps notifications in the browser instead. */
export interface InboxService {
  list(options?: CallOptions): Promise<AppNotification[]>;
  markRead(id: string): Promise<void>;
  markAllRead(): Promise<void>;
  /** Called when the server pushes a new notification (WebSocket user topic). */
  subscribe(onPush: (notification: { title: string; body: string } | null) => void): Unsubscribe;
}

/** Rule-based strategy-engine signals (backend: GET /signals). Not the AI model's output. */
export interface StrategySignalService {
  list(query?: { symbol?: InstrumentSymbol; timeframe?: Timeframe; limit?: number }, options?: CallOptions): Promise<StrategySignal[]>;
}

/** The subset of the server risk profile the web client edits; the rest of the server config is preserved. */
export interface ServerRiskProfile {
  capital: number;
  currency: string;
  riskPerTradePct: number | null;
  dailyLossLimitPct: number | null;
  template: string | null;
  updatedAt: number;
}

/** The server's own sizing of a trade, used as a cross-check of the browser calculation. */
export interface ServerPositionPlan {
  quantity: number | null;
  notional: number | null;
  riskAmount: number | null;
  riskPct: number | null;
  riskReward: number | null;
  currency: string;
  barTime: number;
  invalidReason: string | null;
}

/** Server risk profile and position sizing (backend: /me/risk-profile, /risk/position-size). */
export interface RiskProfileService {
  get(options?: CallOptions): Promise<ServerRiskProfile>;
  save(input: { capital: number; currency: string; riskPerTradePct: number; dailyLossLimitPct: number }): Promise<ServerRiskProfile>;
  positionSize(
    input: { symbol: InstrumentSymbol; timeframe: Timeframe; side: 'buy' | 'sell'; entry: number; stop: number; capital: number; riskPct: number },
    options?: CallOptions,
  ): Promise<ServerPositionPlan>;
}

export interface Services {
  source: DataSource;
  market: MarketDataService;
  opportunities: OpportunityService;
  predictions: PredictionService;
  alerts: AlertService;
  community: CommunityService;
  auth: AuthService;
  account: AccountService;
  inbox: InboxService;
  strategySignals: StrategySignalService;
  riskProfile: RiskProfileService;
  assistant: AssistantService;
}
