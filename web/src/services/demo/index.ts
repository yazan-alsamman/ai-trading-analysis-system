import { z } from 'zod';
import type { OpportunityAlertPreferences, PriceAlert } from '@/domain/alerts';
import type { ChatMessage, Comment, Post } from '@/domain/community';
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';
import { TIMEFRAMES } from '@/domain/market';
import type { Session } from '@/domain/user';
import { buildDemoComments, buildDemoConversation, buildDemoExperts, buildDemoNews, buildDemoPosts } from '@/fixtures/community';
import { buildDemoOpportunity } from '@/fixtures/opportunities';
import { buildDemoPredictionHistory } from '@/fixtures/predictions';
import { localId } from '@/lib/cn';
import { readStored, writeStored } from '@/lib/storage';
import { ApiError } from '../errors';
import { OpportunityPreferencesSchema, PriceAlertSchema } from '../schemas';
import type { AlertService, AssistantService, AuthService, CommunityService, MarketDataService, OpportunityService, PredictionService, Services } from '../types';
import { composeReply, DEMO_ASSISTANT } from './assistant';
import { DemoMarket } from './demoMarket';
import { demoList, simulateRequest } from './scenario';

const ALERTS_KEY = 'ata.demo.alerts.v1';
const OPP_PREFS_KEY = 'ata.demo.opportunityAlerts.v1';
const DEMO_USER_ID = 'demo-user';

function demoMarketService(market: DemoMarket): MarketDataService {
  return {
    async getCandles(symbol, timeframe, options) {
      await simulateRequest(options?.signal, 260);
      const all = market.candles(symbol, timeframe);
      return {
        symbol,
        timeframe,
        candles: demoList(options?.limit ? all.slice(-options.limit) : all),
        volumeKind: 'tick',
        provenance: 'demo',
        asOf: Date.now(),
      };
    },
    async getQuotes(options) {
      await simulateRequest(options?.signal, 120);
      return market.quotes();
    },
    subscribeCandles(symbol, timeframe, { onCandle, onStatus }) {
      onStatus(market.marketStatus());
      return market.subscribe(() => {
        const candle = market.latestCandle(symbol, timeframe);
        if (candle) onCandle(candle);
        onStatus(market.marketStatus());
      });
    },
    subscribeQuotes({ onQuotes, onStatus }) {
      onStatus(market.marketStatus());
      return market.subscribe(() => {
        onQuotes(market.quotes());
        onStatus(market.marketStatus());
      });
    },
  };
}

function demoOpportunityService(market: DemoMarket): OpportunityService {
  return {
    async getLatest(symbol, timeframe, options) {
      await simulateRequest(options?.signal, 380);
      return buildDemoOpportunity(symbol, timeframe, market.candles(symbol, timeframe));
    },
    async list(query, options) {
      await simulateRequest(options?.signal, 420);
      const symbols = query?.symbol ? [query.symbol] : INSTRUMENT_SYMBOLS;
      const timeframes = query?.timeframe ? [query.timeframe] : TIMEFRAMES.map((t) => t.id);
      return demoList(symbols.flatMap((s) => timeframes.map((tf) => buildDemoOpportunity(s, tf, market.candles(s, tf)))));
    },
  };
}

function demoPredictionService(): PredictionService {
  const history = buildDemoPredictionHistory(Date.now());
  return {
    async listHistory(options) {
      await simulateRequest(options?.signal, 300);
      return demoList(history);
    },
  };
}

const AlertListSchema = z.array(PriceAlertSchema);

function seedAlerts(): PriceAlert[] {
  const now = Date.now();
  return [
    {
      id: 'demo-alert-1',
      symbol: 'EURUSD',
      condition: 'crosses_above',
      price: 1.1,
      channels: ['app', 'email'],
      note: 'Example alert created by demo data',
      status: 'active',
      createdAt: now - 3 * 24 * 3600 * 1000,
    },
    {
      id: 'demo-alert-2',
      symbol: 'XAUUSD',
      condition: 'crosses_below',
      price: 2300,
      channels: ['app'],
      note: 'Example alert created by demo data',
      status: 'paused',
      createdAt: now - 26 * 3600 * 1000,
    },
  ];
}

const DEFAULT_OPP_PREFS: OpportunityAlertPreferences = {
  enabled: false,
  minProbability: 0.7,
  symbols: ['EURUSD', 'GBPUSD', 'XAUUSD'],
  timeframes: ['15m', '1h'],
  directions: ['long', 'short'],
  channels: ['app'],
};

/** Alerts persist in this browser only — clearly labelled in the UI. */
function demoAlertService(): AlertService {
  let alerts = readStored(ALERTS_KEY, AlertListSchema, seedAlerts());
  const save = () => writeStored(ALERTS_KEY, alerts);
  const find = (id: string) => {
    const found = alerts.find((a) => a.id === id);
    if (!found) throw new ApiError('not_found', 'Alert not found');
    return found;
  };

  return {
    async list(options) {
      await simulateRequest(options?.signal, 200);
      return demoList([...alerts]);
    },
    async create(draft) {
      await simulateRequest(undefined, 250);
      const alert: PriceAlert = { ...draft, id: localId('alert'), status: 'active', createdAt: Date.now() };
      alerts = [alert, ...alerts];
      save();
      return alert;
    },
    async update(id, patch) {
      await simulateRequest(undefined, 200);
      const updated: PriceAlert = { ...find(id), ...patch };
      alerts = alerts.map((a) => (a.id === id ? updated : a));
      save();
      return updated;
    },
    async remove(id) {
      await simulateRequest(undefined, 200);
      find(id);
      alerts = alerts.filter((a) => a.id !== id);
      save();
    },
    async getOpportunityPreferences(options) {
      await simulateRequest(options?.signal, 150);
      return readStored(OPP_PREFS_KEY, OpportunityPreferencesSchema, DEFAULT_OPP_PREFS);
    },
    async saveOpportunityPreferences(prefs) {
      await simulateRequest(undefined, 250);
      writeStored(OPP_PREFS_KEY, prefs);
      return prefs;
    },
  };
}

function demoCommunityService(getSession: () => Session | null): CommunityService {
  const now = Date.now();
  const news = buildDemoNews(now);
  let comments: Comment[] = buildDemoComments(now);
  let posts: Post[] = buildDemoPosts(now);
  const experts = buildDemoExperts();

  const currentAuthor = () => {
    const s = getSession();
    return s ? { id: s.user.id, name: s.user.name, role: s.user.role } : { id: DEMO_USER_ID, name: 'You (demo)', role: 'trader' as const };
  };

  return {
    async listNews(options) {
      await simulateRequest(options?.signal, 280);
      return demoList(news.map((n) => ({ ...n, commentCount: comments.filter((c) => c.threadId === n.id).length })));
    },
    async listComments(threadId, options) {
      await simulateRequest(options?.signal, 180);
      return comments.filter((c) => c.threadId === threadId).sort((a, b) => a.createdAt - b.createdAt);
    },
    async addComment(threadId, body) {
      await simulateRequest(undefined, 200);
      const comment: Comment = { id: localId('comment'), threadId, author: currentAuthor(), body, createdAt: Date.now() };
      comments = [...comments, comment];
      return comment;
    },
    async listPosts(options) {
      await simulateRequest(options?.signal, 250);
      return demoList([...posts].sort((a, b) => b.createdAt - a.createdAt));
    },
    async createPost({ body, symbols }) {
      await simulateRequest(undefined, 250);
      const post: Post = { id: localId('post'), author: currentAuthor(), body, symbols, createdAt: Date.now(), commentCount: 0, provenance: 'demo' };
      posts = [post, ...posts];
      return post;
    },
    async listExperts(options) {
      await simulateRequest(options?.signal, 250);
      return demoList(experts);
    },
    async getConversation(expertId, options) {
      await simulateRequest(options?.signal, 200);
      return buildDemoConversation(expertId, now);
    },
    async sendMessage(): Promise<ChatMessage> {
      // Honest boundary: there is no simulated expert on the other end.
      throw new ApiError('not_available', 'Expert chat needs the realtime chat service, which is not connected yet.');
    },
  };
}

function demoAuthService(): AuthService {
  const sessionFor = (email: string, name?: string): Session => ({
    user: {
      id: DEMO_USER_ID,
      email,
      name: name?.trim() || email.split('@')[0] || 'Demo user',
      role: 'trader',
    },
    isDemo: true,
  });
  return {
    async login({ email }) {
      await simulateRequest(undefined, 400);
      return sessionFor(email);
    },
    async register({ email, name }) {
      await simulateRequest(undefined, 500);
      return sessionFor(email, name);
    },
    async logout() {
      await simulateRequest(undefined, 100);
    },
  };
}

function demoAssistantService(): AssistantService {
  return {
    describe: () => DEMO_ASSISTANT,
    async reply(messages, context, options) {
      await simulateRequest(options?.signal, 350);
      const question = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
      return composeReply(question, context, Date.now());
    },
  };
}

export function createDemoServices(getSession: () => Session | null): Services {
  const market = new DemoMarket();
  return {
    source: 'demo',
    market: demoMarketService(market),
    opportunities: demoOpportunityService(market),
    predictions: demoPredictionService(),
    alerts: demoAlertService(),
    community: demoCommunityService(getSession),
    auth: demoAuthService(),
    assistant: demoAssistantService(),
  };
}
