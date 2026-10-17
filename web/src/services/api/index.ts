import { z } from 'zod';
import type { Candle, FeedStatus } from '@/domain/market';
import type { Session, User } from '@/domain/user';
import type { AppConfig } from '../config';
import { ApiError, isAbort, isApiError } from '../errors';
import {
  AssistantReplySchema,
  CandleSeriesSchema,
  ChatMessageSchema,
  CommentSchema,
  ExpertSchema,
  NewsItemSchema,
  OpportunityPreferencesSchema,
  OpportunitySchema,
  PostSchema,
  PredictionRecordSchema,
  PriceAlertSchema,
  QuoteSchema,
  TokenPairSchema,
  UserReadSchema,
} from '../schemas';
import type { MarketDataService, Services } from '../types';
import { endpoints } from './endpoints';
import { createHttpClient, type HttpClient } from './http';

/**
 * Backend implementation of the service interfaces. Uses the PROPOSED
 * endpoints in ./endpoints.ts. Selected with VITE_DATA_SOURCE=api.
 */

const Empty = z.unknown();

/**
 * SF9 asks for chart updates without reloading. Until the backend confirms a
 * streaming channel (WebSocket/SSE), this polls the latest candle. One timer
 * per subscription, cancelled on unsubscribe; failures surface as status.
 */
function pollingStream(
  intervalMs: number,
  fetchOnce: (signal: AbortSignal) => Promise<void>,
  onStatus: (s: FeedStatus) => void,
): () => void {
  let stopped = false;
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  onStatus('connecting');

  const run = async () => {
    controller = new AbortController();
    try {
      await fetchOnce(controller.signal);
      if (!stopped) onStatus('live');
    } catch (error) {
      if (!stopped && !isAbort(error)) onStatus('error');
    }
    if (!stopped) timer = setTimeout(run, intervalMs);
  };
  void run();

  return () => {
    stopped = true;
    controller?.abort();
    if (timer) clearTimeout(timer);
  };
}

function apiMarketService(http: HttpClient, cfg: AppConfig): MarketDataService {
  return {
    getCandles: (symbol, timeframe, o) =>
      http.request('GET', endpoints.market.candles, {
        query: { symbol, timeframe, limit: o?.limit ?? 1500 },
        schema: CandleSeriesSchema,
        ...(o?.signal ? { signal: o.signal } : {}),
      }),
    getQuotes: (o) => http.request('GET', endpoints.market.quotes, { schema: z.array(QuoteSchema), ...o }),
    subscribeCandles(symbol, timeframe, { onCandle, onStatus }) {
      return pollingStream(
        cfg.pricePollMs,
        async (signal) => {
          const series = await http.request('GET', endpoints.market.candles, {
            query: { symbol, timeframe, limit: 2 },
            schema: CandleSeriesSchema,
            signal,
          });
          const last: Candle | undefined = series.candles[series.candles.length - 1];
          if (last) onCandle(last);
        },
        onStatus,
      );
    },
    subscribeQuotes({ onQuotes, onStatus }) {
      return pollingStream(
        cfg.pricePollMs * 2,
        async (signal) => onQuotes(await http.request('GET', endpoints.market.quotes, { schema: z.array(QuoteSchema), signal })),
        onStatus,
      );
    },
  };
}

/** FastAPI UserRead → domain user. The role is assigned by the server. */
function toUser(u: z.infer<typeof UserReadSchema>): User {
  return { id: u.id, email: u.email, name: u.full_name?.trim() || u.email.split('@')[0] || u.email, role: u.role };
}

/**
 * Auth against the FastAPI backend (backend/app/api/v1/auth.py):
 * login → TokenPair, then GET /users/me with the new access token.
 * Register returns the created user (no token), so it is followed by login.
 */
function apiAuthService(http: HttpClient): Services['auth'] {
  const signIn = async (email: string, password: string): Promise<Session> => {
    let tokens: z.infer<typeof TokenPairSchema>;
    try {
      tokens = await http.request('POST', endpoints.auth.login, { body: { email, password }, schema: TokenPairSchema, token: null, authFailureHandled: true });
    } catch (e) {
      if (isApiError(e) && e.kind === 'unauthorized') throw new ApiError('validation', 'The email or password is incorrect.', { status: 401 });
      throw e;
    }
    const me = await http.request('GET', endpoints.auth.me, { schema: UserReadSchema, token: tokens.access_token, authFailureHandled: true });
    return { user: toUser(me), token: tokens.access_token, refreshToken: tokens.refresh_token, expiresAt: Date.now() + tokens.expires_in * 1000, isDemo: false };
  };

  return {
    login: ({ email, password }) => signIn(email, password),
    register: async ({ name, email, password }) => {
      try {
        await http.request('POST', endpoints.auth.register, { body: { email, password, full_name: name }, schema: UserReadSchema, token: null, authFailureHandled: true });
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

export function createApiServices(cfg: AppConfig, getSession: () => Session | null, onUnauthorized: () => void): Services {
  const http = createHttpClient({
    baseUrl: cfg.apiBaseUrl,
    timeoutMs: cfg.apiTimeoutMs,
    getToken: () => getSession()?.token,
    onUnauthorized,
  });

  return {
    source: 'api',
    market: apiMarketService(http, cfg),
    opportunities: {
      getLatest: (symbol, timeframe, o) =>
        http.request('GET', endpoints.opportunities.latest, { query: { symbol, timeframe }, schema: OpportunitySchema, ...o }),
      list: (q, o) =>
        http.request('GET', endpoints.opportunities.list, {
          query: { symbol: q?.symbol, timeframe: q?.timeframe },
          schema: z.array(OpportunitySchema),
          ...o,
        }),
    },
    predictions: {
      listHistory: (o) => http.request('GET', endpoints.predictions.history, { schema: z.array(PredictionRecordSchema), ...o }),
    },
    alerts: {
      list: (o) => http.request('GET', endpoints.alerts.list, { schema: z.array(PriceAlertSchema), ...o }),
      create: (draft) => http.request('POST', endpoints.alerts.list, { body: draft, schema: PriceAlertSchema }),
      update: (id, patch) => http.request('PATCH', endpoints.alerts.item(id), { body: patch, schema: PriceAlertSchema }),
      remove: async (id) => {
        await http.request('DELETE', endpoints.alerts.item(id), { schema: Empty });
      },
      getOpportunityPreferences: (o) =>
        http.request('GET', endpoints.alerts.opportunityPreferences, { schema: OpportunityPreferencesSchema, ...o }),
      saveOpportunityPreferences: (prefs) =>
        http.request('PUT', endpoints.alerts.opportunityPreferences, { body: prefs, schema: OpportunityPreferencesSchema }),
    },
    assistant: {
      describe: () => ({
        provider: 'remote',
        label: 'Backend assistant',
        description: 'Answers come from the AI service configured on the backend. It receives only the context listed here.',
      }),
      reply: (messages, context, o) =>
        http.request('POST', endpoints.assistant.reply, {
          body: { messages: messages.map(({ role, content }) => ({ role, content })), context },
          schema: AssistantReplySchema,
          ...o,
        }),
    },
    community: {
      listNews: (o) => http.request('GET', endpoints.community.news, { schema: z.array(NewsItemSchema), ...o }),
      listComments: (id, o) => http.request('GET', endpoints.community.newsComments(id), { schema: z.array(CommentSchema), ...o }),
      addComment: (id, body) => http.request('POST', endpoints.community.newsComments(id), { body: { body }, schema: CommentSchema }),
      listPosts: (o) => http.request('GET', endpoints.community.posts, { schema: z.array(PostSchema), ...o }),
      createPost: (input) => http.request('POST', endpoints.community.posts, { body: input, schema: PostSchema }),
      listExperts: (o) => http.request('GET', endpoints.community.experts, { schema: z.array(ExpertSchema), ...o }),
      getConversation: (id, o) => http.request('GET', endpoints.community.conversation(id), { schema: z.array(ChatMessageSchema), ...o }),
      sendMessage: (id, body) => http.request('POST', endpoints.community.conversation(id), { body: { body }, schema: ChatMessageSchema }),
    },
    auth: apiAuthService(http),
  };
}
