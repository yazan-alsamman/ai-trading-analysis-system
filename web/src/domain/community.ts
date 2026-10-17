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
  impact: NewsImpact;
  commentCount: number;
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
  languages: string[];
  availability: ExpertAvailability;
  provenance: Provenance;
}

export interface ChatMessage {
  id: string;
  from: 'user' | 'expert';
  body: string;
  sentAt: number;
}
