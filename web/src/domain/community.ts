import type { InstrumentSymbol } from './instruments';
import type { Provenance } from './market';
import type { UserRole } from './user';

/** SF11 news + comments, SF12 posts, SF13 expert chat. */

export type NewsImpact = 'low' | 'medium' | 'high';

export interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  publishedAt: number;
  symbols: InstrumentSymbol[];
  /** Editorial impact rating. The backend news service does not provide one, so it may be absent. */
  impact?: NewsImpact;
  /** Sentiment from the backend's NLP model (FinBERT), when it has scored the article. */
  sentiment?: { label: string; score: number | null };
  /** Link to the original article (backend news only). */
  url?: string;
  commentCount: number;
  /** False when the source does not support comments (backend news has none). Default: true. */
  commentsEnabled?: boolean;
  provenance: Provenance;
}

export interface Author {
  id: string;
  name: string;
  role: UserRole;
}

export interface Comment {
  id: string;
  threadId: string;
  author: Author;
  body: string;
  createdAt: number;
}

export interface Post {
  id: string;
  author: Author;
  body: string;
  symbols: InstrumentSymbol[];
  createdAt: number;
  commentCount: number;
  provenance: Provenance;
}

export type ExpertAvailability = 'available' | 'busy' | 'offline';

export interface Expert {
  id: string;
  name: string;
  headline: string;
  specialties: string[];
  markets: InstrumentSymbol[];
  /** Market categories the expert covers (backend: crypto, forex, gold…). */
  marketCategories?: string[];
  languages: string[];
  /** Presence (demo only). The backend reports chat availability instead. */
  availability?: ExpertAvailability;
  /** Backend: whether the expert accepts chat, and how fast they usually answer. */
  chatEnabled?: boolean;
  responseTimeHint?: string | null;
  /** Backend: the expert's cheapest subscription plan (set by the expert), and whether you subscribe. */
  cheapestPlan?: { name: string; price: string; currency: string; interval: string; trialDays: number } | null;
  isSubscribed?: boolean;
  provenance: Provenance;
}

export interface ChatMessage {
  id: string;
  from: 'user' | 'expert';
  body: string;
  sentAt: number;
}
