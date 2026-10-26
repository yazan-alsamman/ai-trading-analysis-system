import type { OpportunityAlertPreferences, PriceAlert, PriceAlertDraft } from '@/domain/alerts';
import type { AssistantContext, AssistantDescription, AssistantMessage, AssistantReply } from '@/domain/assistant';
import type { ChatMessage, Comment, Expert, NewsItem, Post } from '@/domain/community';
import type { InstrumentSymbol } from '@/domain/instruments';
import type { Candle, CandleSeries, FeedStatus, Quote, Timeframe } from '@/domain/market';
import type { Opportunity } from '@/domain/opportunity';
import type { PredictionRecord } from '@/domain/predictions';
import type { StrategySignal } from '@/domain/strategySignals';
import type { LoginInput, RegisterInput, Session, User } from '@/domain/user';
import type { AIExplanation, AIFollow, AIGrade, AISetup, AISetupEvent, AISetupInstrument, AISetupSize, AITake, AITrade } from '@/domain/aiSetups';
import type { ApiKey, ApiKeyInput, ApiKeyScope, ApiKeyUsageDay } from '@/domain/apiKeys';
import type { CalendarEvent, CalendarQuery, CalendarResult } from '@/domain/calendar';
import type { BacktestComparison, BacktestInput, BacktestProgressEvent, BacktestResult, BacktestStatus, BacktestSummary, BacktestTrade } from '@/domain/backtests';
import type { AlertTrigger, ChannelStatus, NotificationPreferences, TelegramLink, TestDelivery } from '@/domain/notificationSettings';
import type { ServerWorkspace, ServerWorkspaceSummary, WorkspaceStateDoc, WorkspaceUpdatedEvent } from '@/domain/serverWorkspaces';
import type {
  Checkout,
  Conversation,
  Earnings,
  ExpertDetail,
  ExpertPlan,
  ExpertProfile,
  ExpertSignal,
  FollowEntry,
  FollowState,
  LikeState,
  PlanInput,
  PostDirection,
  PostVisibility,
  ReportTarget,
  Subscription,
  UserProfile,
} from '@/domain/social';
import type {
  ActivationInput,
  ActivationPatch,
  BackendInstrument,
  BackendTimeframe,
  BuilderCatalog,
  CustomStrategy,
  CustomStrategyInput,
  CustomStrategyKind,
  CustomStrategySummary,
  DefinitionValidation,
  PublicStrategy,
  SignalPlan,
  StrategyActivation,
  StrategyDefinition,
  StrategyParams,
  StrategyPreview,
  StrategyVisibility,
} from '@/domain/strategies';
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
  /** Triggers of the server's price alerts, newest first (backend only). */
  history(query?: { alertId?: string; limit?: number }, options?: CallOptions): Promise<AlertTrigger[]>;
  getOpportunityPreferences(options?: CallOptions): Promise<OpportunityAlertPreferences>;
  saveOpportunityPreferences(prefs: OpportunityAlertPreferences): Promise<OpportunityAlertPreferences>;
}

export interface PostQuery {
  /** `following`: only authors the user follows (backend). */
  scope?: 'all' | 'following';
  authorId?: string;
}

export interface PostInput {
  body: string;
  symbols: InstrumentSymbol[];
  /** Backend only; derived from the first line of `body` when absent. */
  title?: string;
  direction?: PostDirection | null;
  timeframe?: Timeframe | null;
  visibility?: PostVisibility;
}

export interface CommunityService {
  listNews(options?: CallOptions): Promise<NewsItem[]>;
  listComments(threadId: string, options?: CallOptions): Promise<Comment[]>;
  /** `parentId`: reply to a comment (backend). */
  addComment(threadId: string, body: string, parentId?: string | null): Promise<Comment>;
  listPosts(options?: CallOptions & PostQuery): Promise<Post[]>;
  createPost(input: PostInput): Promise<Post>;
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
  remove(id: string): Promise<void>;
  unreadCount(options?: CallOptions): Promise<number>;
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

/* ---------------------------------------------------------------------------
 * Backend capabilities added with the full integration. Demo mode implements
 * every method by rejecting with `not_available` (no simulated stand-ins).
 * ------------------------------------------------------------------------- */

/** Every backend instrument, including the ones the chart UI does not chart (crypto). */
export interface InstrumentDirectoryService {
  list(options?: CallOptions): Promise<BackendInstrument[]>;
  /** Raw candles of any backend instrument and timeframe. */
  candles(instrumentId: string, timeframe: BackendTimeframe, limit: number, options?: CallOptions): Promise<Candle[]>;
}

/** Strategy engine: catalog, activations, preview, signal plans, custom strategies (/strategies, /me/strategies, /me/custom-strategies). */
export interface StrategyService {
  catalog(options?: CallOptions): Promise<StrategyDefinition[]>;
  listActivations(options?: CallOptions): Promise<StrategyActivation[]>;
  activate(input: ActivationInput): Promise<StrategyActivation>;
  updateActivation(id: string, patch: ActivationPatch): Promise<StrategyActivation>;
  removeActivation(id: string): Promise<void>;
  preview(key: string, input: { instrumentId: string; timeframe: BackendTimeframe; params: StrategyParams; limit?: number }, options?: CallOptions): Promise<StrategyPreview>;
  signalPlans(query?: { limit?: number; strategyKey?: string }, options?: CallOptions): Promise<SignalPlan[]>;
  listCustom(options?: CallOptions): Promise<CustomStrategySummary[]>;
  getCustom(id: string, options?: CallOptions): Promise<CustomStrategy>;
  createCustom(input: CustomStrategyInput): Promise<CustomStrategy>;
  /** `version` = the version that was edited; a stale one rejects with `conflict`. */
  replaceCustom(id: string, input: { version: number; definition: Record<string, unknown>; name?: string; description?: string }): Promise<CustomStrategy>;
  updateCustom(id: string, patch: { name?: string; description?: string; visibility?: StrategyVisibility }): Promise<CustomStrategy>;
  removeCustom(id: string): Promise<void>;
  cloneCustom(id: string): Promise<CustomStrategy>;
  builderCatalog(options?: CallOptions): Promise<BuilderCatalog>;
  validate(kind: CustomStrategyKind, definition: Record<string, unknown>, id?: string): Promise<DefinitionValidation>;
  listPublic(query?: { search?: string }, options?: CallOptions): Promise<PublicStrategy[]>;
  clonePublic(id: string): Promise<CustomStrategy>;
}

/** Backtests on historical candles (/backtests). */
export interface BacktestService {
  create(input: BacktestInput): Promise<{ id: string; status: BacktestStatus }>;
  list(query?: { limit?: number; offset?: number }, options?: CallOptions): Promise<{ items: BacktestSummary[]; total: number }>;
  get(id: string, options?: CallOptions): Promise<BacktestResult>;
  /** Cancels a queued/running backtest, otherwise deletes it with its trades. */
  remove(id: string): Promise<void>;
  trades(id: string, page: { limit: number; offset: number }, options?: CallOptions): Promise<{ items: BacktestTrade[]; total: number }>;
  /** All trades as CSV text (ISO 8601 UTC times). */
  exportTradesCsv(id: string): Promise<string>;
  compare(ids: string[]): Promise<BacktestComparison>;
  /** Progress pushed on the user's WebSocket topic. */
  subscribe(onEvent: (event: BacktestProgressEvent) => void): Unsubscribe;
}

/** Server-saved workspaces with optimistic concurrency (/me/workspaces). */
export interface WorkspaceSyncService {
  list(options?: CallOptions): Promise<ServerWorkspaceSummary[]>;
  get(id: string, options?: CallOptions): Promise<ServerWorkspace>;
  create(input: { name: string; state?: WorkspaceStateDoc }): Promise<ServerWorkspace>;
  /** Rejects with ApiError `conflict` (409, `data.current_version`) when `version` is stale. */
  replaceState(id: string, state: WorkspaceStateDoc, version: number): Promise<ServerWorkspace>;
  update(id: string, patch: { name?: string; isDefault?: true }): Promise<ServerWorkspace>;
  remove(id: string): Promise<void>;
  duplicate(id: string): Promise<ServerWorkspace>;
  subscribe(onEvent: (event: WorkspaceUpdatedEvent) => void): Unsubscribe;
}

/** Delivery preferences, channel status, Telegram linking (/me/notification-preferences, /me/notifications/*). */
export interface NotificationSettingsService {
  getPreferences(options?: CallOptions): Promise<NotificationPreferences>;
  savePreferences(prefs: Omit<NotificationPreferences, 'updatedAt'>): Promise<NotificationPreferences>;
  channels(options?: CallOptions): Promise<ChannelStatus>;
  sendTest(channel: 'in_app' | 'telegram' | 'email' | 'push'): Promise<TestDelivery[]>;
  linkTelegram(): Promise<TelegramLink>;
  unlinkTelegram(): Promise<void>;
}

/** Likes, follows, profiles, editing, reports, expert detail, demo-payment subscriptions and conversations. */
export interface SocialService {
  likePost(postId: string): Promise<LikeState>;
  unlikePost(postId: string): Promise<LikeState>;
  updatePost(postId: string, patch: { title?: string; body?: string; direction?: PostDirection | null; visibility?: PostVisibility }): Promise<Post>;
  deletePost(postId: string): Promise<void>;
  updateComment(commentId: string, body: string): Promise<void>;
  deleteComment(commentId: string): Promise<void>;
  report(target: ReportTarget, targetId: string, reason: string): Promise<void>;
  profile(userId: string, options?: CallOptions): Promise<UserProfile>;
  follow(userId: string): Promise<FollowState>;
  unfollow(userId: string): Promise<FollowState>;
  following(options?: CallOptions): Promise<FollowEntry[]>;
  followers(options?: CallOptions): Promise<FollowEntry[]>;
  expert(expertId: string, options?: CallOptions): Promise<ExpertDetail>;
  /** Needs a subscription with the `signals_feed` perk (403 otherwise). */
  expertSignals(expertId: string, options?: CallOptions): Promise<ExpertSignal[]>;
  /** Opens the backend's DEMO checkout (no real money). */
  checkout(planId: string, returnUrl: string | null): Promise<Checkout>;
  subscriptions(options?: CallOptions): Promise<Subscription[]>;
  cancelSubscription(id: string): Promise<Subscription>;
  resumeSubscription(id: string): Promise<Subscription>;
  conversations(options?: CallOptions): Promise<Conversation[]>;
  markConversationRead(conversationId: string): Promise<void>;
}

/** An expert's own profile, plans and earnings (/me/expert-profile, /me/plans, /me/earnings). */
export interface ExpertStudioService {
  /** `null` until the expert creates a profile. */
  getProfile(options?: CallOptions): Promise<ExpertProfile | null>;
  saveProfile(profile: ExpertProfile): Promise<ExpertProfile>;
  listPlans(options?: CallOptions): Promise<ExpertPlan[]>;
  createPlan(input: PlanInput): Promise<ExpertPlan>;
  updatePlan(id: string, patch: Partial<Omit<PlanInput, 'currency' | 'interval'>>): Promise<ExpertPlan>;
  deactivatePlan(id: string): Promise<void>;
  earnings(options?: CallOptions): Promise<Earnings>;
}

/** Personal API keys (/me/api-keys). */
export interface ApiKeyService {
  list(options?: CallOptions): Promise<ApiKey[]>;
  scopes(options?: CallOptions): Promise<ApiKeyScope[]>;
  /** The full key is returned once, here. */
  create(input: ApiKeyInput): Promise<{ apiKey: ApiKey; secret: string }>;
  update(id: string, patch: { name?: string; scopes?: string[]; rateLimitPerMinute?: number | null }): Promise<ApiKey>;
  revoke(id: string): Promise<void>;
  usage(id: string, options?: CallOptions): Promise<ApiKeyUsageDay[]>;
}

/**
 * AI setups (docs/ai-contract.md): follows, the setups the server told the user
 * about, live state changes, sizing, explanation and the user's own "taken"
 * record. v1 is rules-only: probability, EV and grade are null.
 */
export interface AISetupService {
  follows(options?: CallOptions): Promise<AIFollow[]>;
  follow(instrumentId: string, profile: string, minGrade: AIGrade | null): Promise<AIFollow>;
  unfollow(instrumentId: string, profile: string): Promise<void>;
  /** Latest state of every setup in the user's `ai_setup` notifications, newest first. */
  recent(options?: CallOptions): Promise<AISetup[]>;
  size(setupId: string, options?: CallOptions): Promise<AISetupSize>;
  explanation(setupId: string, lang: 'ar' | 'en', options?: CallOptions): Promise<AIExplanation>;
  /** Records that the user took the setup (nothing is executed). Null fields take the server defaults. */
  take(setupId: string, input: { lots: number | null; entryPrice: number | null }): Promise<AITake>;
  untake(setupId: string): Promise<void>;
  trades(page: { limit: number; offset: number }, options?: CallOptions): Promise<{ items: AITrade[]; total: number }>;
  /** State changes pushed on `ai:setups:{instrument_id}` (no snapshot: past setups come from `recent`). */
  subscribe(instrument: AISetupInstrument, onEvent: (event: AISetupEvent) => void): Unsubscribe;
}

/** Economic calendar (docs/economic-calendar.md). */
export interface CalendarService {
  events(query: CalendarQuery, options?: CallOptions): Promise<CalendarResult>;
  /** Every version of one event, oldest first. */
  history(eventKey: string, options?: CallOptions): Promise<CalendarEvent[]>;
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
  instruments: InstrumentDirectoryService;
  strategies: StrategyService;
  backtests: BacktestService;
  workspacesSync: WorkspaceSyncService;
  notificationSettings: NotificationSettingsService;
  social: SocialService;
  expertStudio: ExpertStudioService;
  apiKeys: ApiKeyService;
  aiSetups: AISetupService;
  calendar: CalendarService;
}
