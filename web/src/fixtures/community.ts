/**
 * SAMPLE community content for demo mode. Headlines are generic placeholders
 * describing typical scheduled events — not real news. People are fictional.
 */
import type { ChatMessage, Comment, Expert, NewsItem, Post } from '@/domain/community';

const HOUR = 3600 * 1000;
export const DEMO_SOURCE = 'Sample feed (demo)';

export function buildDemoNews(nowMs: number): NewsItem[] {
  const item = (id: string, hoursAgo: number, n: Omit<NewsItem, 'id' | 'publishedAt' | 'provenance' | 'source'>): NewsItem => ({
    id,
    publishedAt: nowMs - hoursAgo * HOUR,
    source: DEMO_SOURCE,
    provenance: 'demo',
    ...n,
  });
  return [
    item('news-1', 0.6, {
      title: 'Sample: US employment report scheduled — high-impact event for USD pairs',
      summary:
        'Placeholder item illustrating how a scheduled high-impact release is shown. When connected, this feed lists real items from the backend news service with sentiment from the NLP model.',
      symbols: ['EURUSD', 'USDJPY', 'XAUUSD'],
      impact: 'high',
      commentCount: 2,
    }),
    item('news-2', 2.5, {
      title: 'Sample: Euro-area inflation flash estimate due this week',
      summary: 'Placeholder for a medium-impact release affecting EUR crosses.',
      symbols: ['EURUSD'],
      impact: 'medium',
      commentCount: 1,
    }),
    item('news-3', 5, {
      title: 'Sample: Central bank minutes — commentary on policy path',
      summary: 'Placeholder for a policy-communication item. Impact is classified by the backend, not by the client.',
      symbols: ['GBPUSD'],
      impact: 'medium',
      commentCount: 0,
    }),
    item('news-4', 9, {
      title: 'Sample: Commodity-currency sentiment shifts with risk appetite',
      summary: 'Placeholder for a low-impact market-colour item.',
      symbols: ['AUDUSD', 'NZDUSD', 'USDCAD'],
      impact: 'low',
      commentCount: 0,
    }),
    item('news-5', 20, {
      title: 'Sample: Safe-haven demand discussion for gold and CHF',
      summary: 'Placeholder for a cross-asset item.',
      symbols: ['XAUUSD', 'USDCHF'],
      impact: 'low',
      commentCount: 0,
    }),
  ];
}

const author = (id: string, name: string, role: 'trader' | 'analyst' | 'expert') => ({ id, name, role });
const SAMPLE_ANALYST = author('u-sample-1', 'Sample Analyst', 'analyst');
const SAMPLE_TRADER = author('u-sample-2', 'Sample Trader', 'trader');

export function buildDemoComments(nowMs: number): Comment[] {
  return [
    { id: 'c-1', threadId: 'news-1', author: SAMPLE_ANALYST, body: 'Sample comment: spreads usually widen around this release.', createdAt: nowMs - 0.4 * HOUR },
    { id: 'c-2', threadId: 'news-1', author: SAMPLE_TRADER, body: 'Sample comment: waiting for the release before acting.', createdAt: nowMs - 0.3 * HOUR },
    { id: 'c-3', threadId: 'news-2', author: SAMPLE_TRADER, body: 'Sample comment: watching EUR/USD reaction on 15m.', createdAt: nowMs - 2 * HOUR },
  ];
}

export function buildDemoPosts(nowMs: number): Post[] {
  return [
    {
      id: 'post-1',
      author: SAMPLE_ANALYST,
      body: 'Sample post: comparing 15m signals with the 4h regime before acting has reduced false starts in my reviews.',
      symbols: ['EURUSD'],
      createdAt: nowMs - 1.2 * HOUR,
      commentCount: 0,
      provenance: 'demo',
    },
    {
      id: 'post-2',
      author: SAMPLE_TRADER,
      body: 'Sample post: how are others using the probability band when sizing risk?',
      symbols: [],
      createdAt: nowMs - 6 * HOUR,
      commentCount: 0,
      provenance: 'demo',
    },
  ];
}

export function buildDemoExperts(): Expert[] {
  return [
    {
      id: 'exp-1',
      name: 'Sample Expert A',
      headline: 'Macro & major FX pairs',
      specialties: ['Macro events', 'Risk management'],
      markets: ['EURUSD', 'GBPUSD', 'USDJPY'],
      languages: ['English', 'Arabic'],
      availability: 'available',
      provenance: 'demo',
    },
    {
      id: 'exp-2',
      name: 'Sample Expert B',
      headline: 'Gold & commodity currencies',
      specialties: ['Gold', 'Intermarket analysis'],
      markets: ['XAUUSD', 'AUDUSD', 'USDCAD'],
      languages: ['English'],
      availability: 'busy',
      provenance: 'demo',
    },
    {
      id: 'exp-3',
      name: 'Sample Expert C',
      headline: 'Price action & technical patterns',
      specialties: ['Candlestick patterns', 'Multi-timeframe analysis'],
      markets: ['EURUSD', 'NZDUSD', 'USDCHF'],
      languages: ['Arabic'],
      availability: 'offline',
      provenance: 'demo',
    },
  ];
}

export function buildDemoConversation(expertId: string, nowMs: number): ChatMessage[] {
  if (expertId !== 'exp-1') return [];
  return [
    { id: 'm-1', from: 'user', body: 'Sample message: how do you treat a signal right before a high-impact release?', sentAt: nowMs - 26 * HOUR },
    { id: 'm-2', from: 'expert', body: 'Sample reply: I usually wait for the release and re-check the 15m structure afterwards.', sentAt: nowMs - 25.5 * HOUR },
  ];
}
