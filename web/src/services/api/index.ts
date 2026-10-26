import { z } from 'zod';
import type { AssistantDescription } from '@/domain/assistant';
import { getInstrument, type InstrumentSymbol } from '@/domain/instruments';
import type { Quote, Timeframe } from '@/domain/market';
import type { Session } from '@/domain/user';
import { composeReply } from '../demo/assistant';
import type { AppConfig } from '../config';
import { ApiError, isApiError } from '../errors';
import { TokenPairSchema } from '../schemas';
import type { MarketDataService, Services } from '../types';
import {
  ArticleRead,
  BackendCandleSeries,
  ConversationRead,
  CommentRead,
  ExpertCard,
  InstrumentRead,
  MessagePage,
  MessageRead,
  NotificationRead,
  page,
  PositionSizeResponse,
  PostRead,
  PriceAlertRead,
  RiskProfileRead,
  SignalRead,
  ThreadRead,
  UnreadCount,
  UserRead,
} from './backend';
import { endpoints } from './endpoints';
import { createHttpClient, type HttpClient } from './http';
import { toChatMessage, toComments, toCandleSeries, toExpert, toNewsItem, toNotification, toPost, toPriceAlert, toStrategySignal, toUser, instrumentIndex } from './mappers';
import { createMarketSocket, type MarketSocket } from './marketSocket';
import { createTokenManager, type SessionStore } from './session';
import { apiAlertHistory, apiExpertStudio, apiKeyService, apiNotificationSettings, apiWorkspaceSync } from './accountApi';
import { apiBacktestService, apiInstrumentDirectory, apiStrategyService } from './labApi';
import { apiAdminService } from './adminApi';
import { apiAISetupService, apiCalendarService } from './aiApi';
import { apiMarketContextService } from './extrasApi';
import { apiSocialService } from './socialApi';

/**
 * Backend implementation of the service interfaces (VITE_DATA_SOURCE=api),
 * against the verified FastAPI contract (docs/api/openapi.json). Capabilities
 * the backend does not offer reject with `not_available` and say why; they
 * never fall back to simulated data. See docs/BACKEND_INTEGRATION_GAP_ANALYSIS.md.
 */

const Empty = z.unknown();

const missing = (message: string) => () => Promise.reject(new ApiError('not_available', message));

/** Backend instruments, fetched once per session and reused (they rarely change). */
function createInstrumentRegistry(http: HttpClient) {
  let cache: Promise<{ bySymbol: Map<InstrumentSymbol, InstrumentRead>; byId: Map<string, InstrumentRead> }> | null = null;
  const load = () => {
    if (!cache) {
      cache = http
        .request('GET', endpoints.market.instruments, { query: { limit: 100, is_active: true }, schema: page(InstrumentRead) })
        .then((p) => ({ bySymbol: instrumentIndex(p.items), byId: new Map(p.items.map((i) => [i.id, i])) }))
        .catch((e: unknown) => {
          cache = null; // retry next time
          throw e;
        });
    }
    return cache;
  };
  return {
    load,
    async require(symbol: InstrumentSymbol): Promise<InstrumentRead> {
      const inst = (await load()).bySymbol.get(symbol);
      if (!inst) throw new ApiError('not_available', `${getInstrument(symbol).display} is not available on the backend yet.`);
      return inst;
    },
    reset() {
      cache = null;
    },
  };
}
type InstrumentRegistry = ReturnType<typeof createInstrumentRegistry>;

function apiMarketService(http: HttpClient, registry: InstrumentRegistry, socket: MarketSocket): MarketDataService {
  /** Price now and 24 hours earlier, from the last 25 hourly candles. */
  const quoteFor = async (symbol: InstrumentSymbol, signal?: AbortSignal): Promise<Quote | null> => {
    const inst = await registry.require(symbol);
    const series = await http.request('GET', endpoints.market.candles(inst.id), { query: { timeframe: '1h', limit: 25 }, schema: BackendCandleSeries, ...(signal ? { signal } : {}) });
    const last = series.candles[series.candles.length - 1];
    const first = series.candles[0];
    if (!last || !first) return null;
    return { symbol, price: last.close, reference: series.candles.length >= 25 ? first.close : first.open, time: last.time * 1000, provenance: 'live' };
  };
  const quotes = async (signal?: AbortSignal): Promise<Quote[]> => {
    const symbols = [...(await registry.load()).bySymbol.keys()];
    const settled = await Promise.allSettled(symbols.map((s) => quoteFor(s, signal)));
    return settled.flatMap((r) => (r.status === 'fulfilled' && r.value ? [r.value] : []));
  };

  return {
    async getCandles(symbol, timeframe, o) {
      const inst = await registry.require(symbol);
      const raw = await http.request('GET', endpoints.market.candles(inst.id), {
        query: { timeframe, limit: Math.min(o?.limit ?? 1500, 5000) },
        schema: BackendCandleSeries,
        ...(o?.signal ? { signal: o.signal } : {}),
      });
      return toCandleSeries(raw, symbol, timeframe, inst.market);
    },
    getQuotes: (o) => quotes(o?.signal),
    subscribeCandles(symbol, timeframe, { onCandle, onStatus }) {
      let unsubscribe: (() => void) | null = null;
      let stopped = false;
      onStatus('connecting');
      registry.require(symbol).then(
        (inst) => {
          if (!stopped) unsubscribe = socket.subscribeCandles(inst.id, timeframe, { onCandle, onStatus });
        },
        () => !stopped && onStatus('error'),
      );
      return () => {
        stopped = true;
        unsubscribe?.();
      };
    },
    subscribeQuotes({ onQuotes, onStatus }) {
      let stopped = false;
      const latest = new Map<InstrumentSymbol, Quote>();
      const unsubs: (() => void)[] = [];
      onStatus('connecting');
      quotes()
        .then(async (initial) => {
          if (stopped) return;
          initial.forEach((q) => latest.set(q.symbol, q));
          onQuotes([...latest.values()]);
          const { bySymbol } = await registry.load();
          for (const [symbol, inst] of bySymbol) {
            unsubs.push(
              socket.subscribeCandles(inst.id, '1m', {
                onStatus,
                onCandle: (c) => {
                  const prev = latest.get(symbol);
                  if (!prev) return;
                  latest.set(symbol, { ...prev, price: c.close, time: c.time * 1000 });
                  onQuotes([...latest.values()]);
                },
              }),
            );
          }
        })
        .catch(() => !stopped && onStatus('error'));
      return () => {
        stopped = true;
        unsubs.forEach((u) => u());
      };
    },
  };
}

function apiAuthService(http: HttpClient): Services['auth'] {
  const signIn = async (email: string, password: string): Promise<Session> => {
    let tokens: z.infer<typeof TokenPairSchema>;
    try {
      tokens = await http.request('POST', endpoints.auth.login, { body: { email, password }, schema: TokenPairSchema, token: null, authFailureHandled: true });
    } catch (e) {
      if (isApiError(e) && e.kind === 'unauthorized') throw new ApiError('validation', 'The email or password is incorrect.', { status: 401 });
      if (isApiError(e) && e.kind === 'forbidden') throw new ApiError('forbidden', e.message || 'This account is disabled.', { status: 403 });
      throw e;
    }
    const me = await http.request('GET', endpoints.users.me, { schema: UserRead, token: tokens.access_token, authFailureHandled: true });
    return { user: toUser(me), token: tokens.access_token, refreshToken: tokens.refresh_token, expiresAt: Date.now() + tokens.expires_in * 1000, isDemo: false };
  };

  return {
    login: ({ email, password }) => signIn(email, password),
    register: async ({ name, email, password }) => {
      try {
        await http.request('POST', endpoints.auth.register, { body: { email, password, full_name: name }, schema: UserRead, token: null, authFailureHandled: true });
      } catch (e) {
        if (isApiError(e) && e.kind === 'conflict')
          throw new ApiError('validation', 'An account with this email already exists.', {
            status: 409,
            fieldErrors: { email: ['An account with this email already exists. Sign in instead.'] },
          });
        if (isApiError(e) && e.fieldErrors.full_name)
          throw new ApiError(e.kind, e.message, { fieldErrors: { ...e.fieldErrors, name: e.fieldErrors.full_name }, ...(e.status ? { status: e.status } : {}) });
        throw e;
      }
      return signIn(email, password);
    },
    logout: async (session) => {
      if (!session.refreshToken) return;
      await http.request('POST', endpoints.auth.logout, {
        body: { refresh_token: session.refreshToken },
        schema: Empty,
        ...(session.token ? { token: session.token } : {}),
        authFailureHandled: true,
      });
    },
  };
}

/** The assistant has no backend provider yet: the rule-based composer runs locally on the context shown. */
const RULES_ASSISTANT: AssistantDescription = {
  provider: 'demo-rules',
  label: 'Rule-based',
  description: 'No AI provider is connected to the backend yet. Answers are assembled with fixed rules from the data listed under “Context”, in your browser.',
};

/** risk config paths the web client edits; everything else in the server config is preserved. */
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const obj = (v: unknown): Record<string, unknown> => (typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : {});

export function createApiServices(cfg: AppConfig, store: SessionStore, onUnauthorized: () => void): Services {
  // Unauthenticated transport for token refresh (it must never trigger itself).
  const bare = createHttpClient({ baseUrl: cfg.apiBaseUrl, timeoutMs: cfg.apiTimeoutMs, getToken: () => undefined });
  const tokens = createTokenManager(bare, store);
  const http = createHttpClient({
    baseUrl: cfg.apiBaseUrl,
    timeoutMs: cfg.apiTimeoutMs,
    getToken: () => tokens.getToken(),
    refreshToken: () => tokens.refresh(),
    onUnauthorized,
  });
  const registry = createInstrumentRegistry(http);
  const socket = createMarketSocket({ url: cfg.wsUrl, getToken: () => tokens.getToken(), refreshToken: () => tokens.refresh() });
  const userId = () => store.get()?.user.id ?? '';
  const conversations = new Map<string, string>(); // expert id → conversation id

  const openConversation = async (expertId: string, signal?: AbortSignal) => {
    const known = conversations.get(expertId);
    if (known) return known;
    const conv = await http.request('POST', endpoints.chat.open, { body: { expert_id: expertId }, schema: ConversationRead, ...(signal ? { signal } : {}) });
    conversations.set(expertId, conv.id);
    return conv.id;
  };

  const rawRiskProfile = (signal?: AbortSignal) => http.request('GET', endpoints.risk.profile, { schema: RiskProfileRead, ...(signal ? { signal } : {}) });
  const toServerRisk = (r: z.infer<typeof RiskProfileRead>) => ({
    capital: r.account_size,
    currency: r.quote_currency,
    riskPerTradePct: num(obj(r.config.sizing).risk_pct),
    dailyLossLimitPct: num(obj(r.config.guards).max_daily_loss_pct),
    template: r.template,
    updatedAt: Date.parse(r.updated_at) || 0,
  });

  return {
    source: 'api',
    market: apiMarketService(http, registry, socket),
    opportunities: {
      getLatest: missing('The AI model’s analysis (probability, zones, evidence) is not exposed by the backend yet.'),
      list: missing('The AI model’s signals are not exposed by the backend yet. Strategy-engine signals are listed instead.'),
    },
    predictions: {
      listHistory: missing('Prediction history and model analytics are not available from the backend yet.'),
    },
    alerts: {
      list: async (o) => {
        const p = await http.request('GET', endpoints.alerts.list, { query: { limit: 100 }, schema: page(PriceAlertRead), ...(o?.signal ? { signal: o.signal } : {}) });
        return p.items.flatMap((a) => toPriceAlert(a) ?? []);
      },
      create: async (draft) => {
        const inst = await registry.require(draft.symbol);
        const created = await http.request('POST', endpoints.alerts.list, {
          body: { instrument_id: inst.id, condition: draft.condition, value: draft.price, repeat: 'once', note: draft.note?.trim() || null },
          schema: PriceAlertRead,
        });
        const mapped = toPriceAlert(created);
        if (!mapped) throw new ApiError('contract', 'The created alert refers to an unknown instrument');
        return mapped;
      },
      update: async (id, patch) => {
        const body: Record<string, unknown> = {};
        if (patch.condition) body.condition = patch.condition;
        if (patch.price !== undefined) body.value = patch.price;
        if (patch.note !== undefined) body.note = patch.note?.trim() || null;
        if (patch.status) body.is_active = patch.status === 'active';
        const updated = await http.request('PATCH', endpoints.alerts.item(id), { body, schema: PriceAlertRead });
        const mapped = toPriceAlert(updated);
        if (!mapped) throw new ApiError('contract', 'The updated alert refers to an unknown instrument');
        return mapped;
      },
      remove: async (id) => {
        await http.request('DELETE', endpoints.alerts.item(id), { schema: Empty });
      },
      history: apiAlertHistory(http),
      getOpportunityPreferences: missing('Alerts on AI opportunities need the model’s output, which the backend does not expose yet.'),
      saveOpportunityPreferences: missing('Alerts on AI opportunities need the model’s output, which the backend does not expose yet.'),
    },
    community: {
      listNews: async (o) => {
        const p = await http.request('GET', endpoints.news.list, { query: { limit: 50 }, schema: page(ArticleRead), ...(o?.signal ? { signal: o.signal } : {}) });
        return p.items.map(toNewsItem);
      },
      listComments: async (postId, o) => {
        const p = await http.request('GET', endpoints.posts.comments(postId), { query: { limit: 100 }, schema: page(ThreadRead), ...(o?.signal ? { signal: o.signal } : {}) });
        return toComments(p.items, postId);
      },
      addComment: async (postId, body, parentId) => {
        const c = await http.request('POST', endpoints.posts.comments(postId), { body: { body: body.trim(), ...(parentId ? { parent_id: parentId } : {}) }, schema: CommentRead });
        const [mapped] = toComments([c], postId);
        if (!mapped) throw new ApiError('contract', 'The new comment was not returned');
        return mapped;
      },
      listPosts: async (o) => {
        const p = await http.request('GET', endpoints.posts.list, {
          query: { limit: 50, scope: o?.scope === 'following' ? 'following' : undefined, author_id: o?.authorId },
          schema: page(PostRead),
          ...(o?.signal ? { signal: o.signal } : {}),
        });
        return p.items.map(toPost);
      },
      createPost: async ({ body, symbols, title: explicitTitle, direction, timeframe, visibility }) => {
        const text = body.trim();
        // The backend requires a title (≤ 140): the user's own, or the first line of what they wrote.
        const firstLine = text.split('\n')[0]?.trim() ?? '';
        const derived = firstLine.length > 140 ? `${firstLine.slice(0, 139)}…` : firstLine || text.slice(0, 140);
        const title = explicitTitle?.trim() || derived;
        const first = symbols[0];
        const instrumentId = first ? (await registry.require(first)).id : null;
        const created = await http.request('POST', endpoints.posts.list, {
          body: {
            title,
            body: text,
            instrument_id: instrumentId,
            ...(direction !== undefined ? { direction } : {}),
            ...(timeframe ? { timeframe } : {}),
            ...(visibility ? { visibility } : {}),
          },
          schema: PostRead,
        });
        return toPost(created);
      },
      listExperts: async (o) => {
        const p = await http.request('GET', endpoints.experts.list, { query: { limit: 50 }, schema: page(ExpertCard), ...(o?.signal ? { signal: o.signal } : {}) });
        return p.items.map(toExpert);
      },
      getConversation: async (expertId, o) => {
        const id = await openConversation(expertId, o?.signal);
        const p = await http.request('GET', endpoints.chat.messages(id), { query: { limit: 50 }, schema: MessagePage, ...(o?.signal ? { signal: o.signal } : {}) });
        const me = userId();
        return p.items
          .flatMap((m) => toChatMessage(m, me) ?? [])
          .sort((a, b) => a.sentAt - b.sentAt);
      },
      sendMessage: async (expertId, body) => {
        const id = await openConversation(expertId);
        const sent = await http.request('POST', endpoints.chat.messages(id), { body: { body: body.trim(), client_id: crypto.randomUUID() }, schema: MessageRead });
        const mapped = toChatMessage(sent, userId());
        if (!mapped) throw new ApiError('contract', 'The sent message was not returned');
        return mapped;
      },
    },
    auth: apiAuthService(http),
    account: {
      getProfile: async (o) => toUser(await http.request('GET', endpoints.users.me, { schema: UserRead, ...(o?.signal ? { signal: o.signal } : {}) })),
      updateProfile: async ({ name }) => toUser(await http.request('PATCH', endpoints.users.me, { body: { full_name: name.trim() }, schema: UserRead })),
      changePassword: async ({ currentPassword, newPassword }) => {
        await http.request('POST', endpoints.users.password, { body: { current_password: currentPassword, new_password: newPassword }, schema: Empty });
      },
    },
    inbox: {
      list: async (o) => {
        const p = await http.request('GET', endpoints.notifications.list, { query: { limit: 50 }, schema: page(NotificationRead), ...(o?.signal ? { signal: o.signal } : {}) });
        return p.items.map(toNotification);
      },
      markRead: async (id) => {
        await http.request('POST', endpoints.notifications.read(id), { schema: Empty });
      },
      markAllRead: async () => {
        await http.request('POST', endpoints.notifications.readAll, { schema: Empty });
      },
      remove: async (id) => {
        await http.request('DELETE', endpoints.notificationSettings.item(id), { schema: Empty });
      },
      unreadCount: async (o) => (await http.request('GET', endpoints.notificationSettings.unreadCount, { schema: UnreadCount, ...(o?.signal ? { signal: o.signal } : {}) })).count,
      subscribe(onPush) {
        // docs/websocket.md: `notification` carries {notification: {title, body, …}}; `price_alert` follows a fired alert.
        const read = (msg: Record<string, unknown>) => {
          const n = msg.notification as { title?: unknown; body?: unknown } | undefined;
          onPush(n && typeof n.title === 'string' ? { title: n.title, body: typeof n.body === 'string' ? n.body : '' } : null);
        };
        const offA = socket.onUserEvent('notification', read);
        const offB = socket.onUserEvent('price_alert', () => onPush(null));
        return () => {
          offA();
          offB();
        };
      },
    },
    strategySignals: {
      list: async (q, o) => {
        const { byId } = await registry.load();
        const instrumentId = q?.symbol ? (await registry.require(q.symbol)).id : undefined;
        const p = await http.request('GET', endpoints.signals.list, {
          query: { limit: Math.min(q?.limit ?? 50, 100), instrument_id: instrumentId, timeframe: q?.timeframe },
          schema: page(SignalRead),
          ...(o?.signal ? { signal: o.signal } : {}),
        });
        return p.items.map((s) => toStrategySignal(s, byId));
      },
    },
    riskProfile: {
      get: async (o) => toServerRisk(await rawRiskProfile(o?.signal)),
      save: async ({ capital, currency, riskPerTradePct, dailyLossLimitPct }) => {
        const current = await rawRiskProfile();
        const config = {
          ...current.config,
          sizing: { ...obj(current.config.sizing), risk_pct: riskPerTradePct },
          guards: { ...obj(current.config.guards), max_daily_loss_pct: dailyLossLimitPct },
        };
        return toServerRisk(await http.request('PUT', endpoints.risk.profile, { body: { account_size: capital, quote_currency: currency, config }, schema: RiskProfileRead }));
      },
      positionSize: async ({ symbol, timeframe, side, entry, stop, capital, riskPct }: { symbol: InstrumentSymbol; timeframe: Timeframe; side: 'buy' | 'sell'; entry: number; stop: number; capital: number; riskPct: number }, o) => {
        const inst = await registry.require(symbol);
        const profile = await rawRiskProfile(o?.signal);
        const config = { ...profile.config, sizing: { ...obj(profile.config.sizing), risk_pct: riskPct } };
        const r = await http.request('POST', endpoints.risk.positionSize, {
          body: { instrument_id: inst.id, timeframe, side, entry, stop, account_size: capital, config },
          schema: PositionSizeResponse,
          ...(o?.signal ? { signal: o.signal } : {}),
        });
        return {
          quantity: r.plan.quantity,
          notional: r.plan.notional,
          riskAmount: r.plan.risk_amount,
          riskPct: r.plan.risk_pct,
          riskReward: r.plan.rr ?? null,
          currency: r.quote_currency,
          barTime: Date.parse(r.bar_time) || 0,
          invalidReason: r.plan.invalid_reason,
        };
      },
    },
    assistant: {
      describe: () => RULES_ASSISTANT,
      async reply(messages, context) {
        const question = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
        return composeReply(question, context, Date.now());
      },
    },
    instruments: apiInstrumentDirectory(http),
    strategies: apiStrategyService(http),
    backtests: apiBacktestService(http, socket),
    aiSetups: apiAISetupService(http, socket),
    calendar: apiCalendarService(http),
    marketContext: apiMarketContextService(http),
    admin: apiAdminService(http),
    workspacesSync: apiWorkspaceSync(http, socket),
    notificationSettings: apiNotificationSettings(http),
    social: apiSocialService(http),
    expertStudio: apiExpertStudio(http),
    apiKeys: apiKeyService(http),
  };
}

/** Exposed for the server inbox sync (WebSocket push on the user's topic). */
export type { MarketSocket };
