import type { Author } from './community';
import type { UserRole } from './user';

/**
 * Community interactions of the backend (docs/news-posts.md, docs/subscriptions.md,
 * docs/chat.md): likes, follows, profiles, editing and moderation reports,
 * expert profiles, plans and subscriptions. Payments are DEMO ONLY on this
 * backend: no real money moves.
 */

export type PostDirection = 'bullish' | 'bearish' | 'neutral';
export type PostVisibility = 'public' | 'followers' | 'subscribers';

export interface LikeState {
  liked: boolean;
  likes: number;
}

export interface FollowState {
  following: boolean;
  followers: number;
}

export interface UserProfile {
  id: string;
  name: string;
  role: UserRole;
  memberSince: number;
  posts: number;
  followers: number;
  following: number;
  /** Only analysts and experts can be followed. */
  followable: boolean;
  isFollowing: boolean;
  recentPosts: { id: string; title: string; createdAt: number }[];
  publicStrategies: { id: string; name: string; description: string; kind: string }[];
}

export interface FollowEntry {
  user: Author;
  since: number;
}

export type ReportTarget = 'post' | 'comment' | 'message';

/* --------------------------------------------------------------- experts */

export type PlanInterval = 'month' | 'year';

export interface PlanPerks {
  premiumPosts: boolean;
  chat: boolean;
  signalsFeed: boolean;
}

export interface ExpertPlan {
  id: string;
  expertId: string;
  name: string;
  description: string;
  /** Decimal string as the server sends it (e.g. "19.00"); never rounded through floats. */
  price: string;
  currency: string;
  interval: PlanInterval;
  trialDays: number;
  perks: PlanPerks;
  isActive: boolean;
}

export interface ExpertDetail {
  id: string;
  name: string;
  headline: string;
  bio: string;
  markets: string[];
  languages: string[];
  chatEnabled: boolean;
  responseTimeHint: string | null;
  followers: number;
  subscribers: number;
  memberSince: number;
  isSubscribed: boolean;
  plans: ExpertPlan[];
  /** What the viewer's subscription grants, as the server reports it. */
  entitlements: Record<string, unknown>;
}

export interface Checkout {
  checkoutId: string;
  /** The backend's hosted DEMO payment page. */
  checkoutUrl: string;
  status: string;
  expiresAt: number;
}

export type SubscriptionStatus = 'trialing' | 'active' | 'past_due' | 'canceled' | 'expired';

export interface Invoice {
  id: string;
  number: string;
  kind: string;
  amount: string;
  currency: string;
  status: string;
  periodStart: number;
  periodEnd: number;
  failureReason: string | null;
  paidAt: number | null;
  refundedAt: number | null;
}

export interface Subscription {
  id: string;
  expert: { id: string; name: string };
  planName: string;
  status: SubscriptionStatus;
  price: string;
  currency: string;
  interval: PlanInterval;
  perks: PlanPerks;
  currentPeriodEnd: number;
  cancelAtPeriodEnd: boolean;
  nextChargeAt: number | null;
  graceEndsAt: number | null;
  endedAt: number | null;
  /** Demo card brand and last 4 digits only. */
  paymentMethod: { brand: string | null; last4: string | null } | null;
  invoices: Invoice[];
  createdAt: number;
}

export interface Conversation {
  id: string;
  expertId: string;
  other: { id: string; name: string; role: UserRole };
  status: 'open' | 'closed' | 'blocked';
  canSend: boolean;
  readOnlyReason: string | null;
  unread: number;
  lastMessage: { excerpt: string | null; createdAt: number } | null;
}

/** An expert's signal feed item (subscribers with the `signals_feed` perk). Shape owned by the backend. */
export type ExpertSignal = Record<string, unknown>;

/* ------------------------------------------------------ expert self-service */

export interface ExpertProfile {
  headline: string;
  bio: string;
  markets: string[];
  languages: string[];
  chatEnabled: boolean;
  responseTimeHint: string | null;
  isListed: boolean;
}

export const EXPERT_MARKETS = ['forex', 'gold', 'commodities', 'indices', 'stocks', 'crypto'] as const;
export const EXPERT_LANGUAGES = ['en', 'ar', 'fr', 'de', 'es', 'tr'] as const;

export interface PlanInput {
  name: string;
  description: string;
  price: string;
  currency: 'USD' | 'EUR';
  interval: PlanInterval;
  trialDays: number;
  perks: PlanPerks;
  isActive: boolean;
}

export interface Earnings {
  currency: string;
  platformFeePct: number;
  activeSubscribers: number;
  mrr: string;
  churn30dPct: number | null;
  months: { month: string; gross: string; platformFee: string; net: string; refunded: string; invoices: number }[];
  recentInvoices: { number: string; amount: string; currency: string; status: string; subscriber: string; plan: string; paidAt: number | null }[];
}

/** One conversation with its moderation state (GET /conversations/{id}, block/unblock). */
export interface ConversationDetail extends Conversation {
  blockedByMe: boolean;
  myRole: string;
}

/** A chat message as the backend returns it after an edit. */
export interface EditedMessage {
  id: string;
  body: string | null;
  editedAt: number | null;
  deleted: boolean;
}
