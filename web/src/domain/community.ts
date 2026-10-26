import type { InstrumentSymbol } from './instruments';
import type { Provenance } from './market';
import type { PostDirection, PostVisibility } from './social';
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
  /** Backend only: the comment this one replies to. */
  parentId?: string | null;
  /** Backend only: the server allows the viewer to edit or delete it. */
  canEdit?: boolean;
  editedAt?: number | null;
}

export interface Post {
  id: string;
  author: Author;
  body: string;
  symbols: InstrumentSymbol[];
  createdAt: number;
  commentCount: number;
  provenance: Provenance;
  /* Backend only (absent in demo mode): */
  title?: string;
  likes?: number;
  likedByMe?: boolean;
  /** The author within 24 h of publishing, or an admin (decided by the server). */
  canEdit?: boolean;
  editedAt?: number | null;
  direction?: PostDirection | null;
  timeframe?: string | null;
  visibility?: PostVisibility;
  /** `hidden`: moderated, visible to its author only. */
  status?: 'published' | 'hidden' | 'deleted';
  /** The backend symbol when the instrument is not one the web client charts. */
  instrumentLabel?: string | null;
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
  followers?: number;
  subscribers?: number;
  provenance: Provenance;
}

export interface ChatMessage {
  id: string;
  from: 'user' | 'expert';
  body: string;
  sentAt: number;
}
