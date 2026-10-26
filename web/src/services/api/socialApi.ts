import { z } from 'zod';
import type { Subscription } from '@/domain/social';
import type { SocialService } from '../types';
import { PostRead, Role } from './backend';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';
import { toPost } from './mappers';
import { PlanRead, toPlan } from './accountApi';

/**
 * Community interactions (docs/news-posts.md), expert detail and DEMO-payment
 * subscriptions (docs/subscriptions.md), and the conversation list
 * (docs/chat.md). Authorisation is the server's: the client only shows the
 * actions the server says the viewer may take (`can_edit`, `followable`…)
 * and surfaces the server's reason when it refuses.
 */

const Empty = z.unknown();
const Json = z.record(z.string(), z.unknown());
const opt = (signal?: AbortSignal): { signal?: AbortSignal } => (signal ? { signal } : {});
const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
};
const msReq = (iso: string) => ms(iso) ?? 0;

const Person = z.object({ id: z.string(), display_name: z.string(), role: Role });
const LikeRead = z.object({ liked: z.boolean(), likes_count: z.number().int() });
const FollowRead = z.object({ following: z.boolean(), followers_count: z.number().int() });
const FollowEntryRead = z.object({ user: Person, since: z.string() });
const pageOf = <T extends z.ZodType>(item: T) => z.object({ items: z.array(item), total: z.number().int() });

const ProfileRead = z.object({
  id: z.string(),
  display_name: z.string(),
  role: Role,
  member_since: z.string(),
  posts_count: z.number().int(),
  followers_count: z.number().int(),
  following_count: z.number().int(),
  followable: z.boolean(),
  is_following: z.boolean(),
  recent_posts: z.array(z.object({ id: z.string(), title: z.string(), created_at: z.string() })),
  public_strategies: z.array(z.object({ id: z.string(), name: z.string(), description: z.string(), kind: z.string() })),
});

const ExpertDetailRead = z.object({
  id: z.string(),
  display_name: z.string(),
  headline: z.string(),
  bio: z.string(),
  markets: z.array(z.string()),
  languages: z.array(z.string()),
  chat_enabled: z.boolean(),
  response_time_hint: z.string().nullable(),
  followers_count: z.number().int(),
  subscribers_count: z.number().int(),
  member_since: z.string(),
  is_subscribed: z.boolean(),
  plans: z.array(PlanRead),
  entitlements: Json,
});

const InvoiceRead = z.object({
  id: z.string(),
  number: z.string(),
  kind: z.string(),
  amount: z.string(),
  currency: z.string(),
  status: z.string(),
  period_start: z.string(),
  period_end: z.string(),
  failure_reason: z.string().nullable(),
  paid_at: z.string().nullable(),
  refunded_at: z.string().nullable(),
});
const SubscriptionRead = z.object({
  id: z.string(),
  expert: Person,
  plan: Json,
  status: z.enum(['trialing', 'active', 'past_due', 'canceled', 'expired']),
  price: z.string(),
  currency: z.string(),
  interval: z.enum(['month', 'year']),
  perks: Json,
  current_period_end: z.string(),
  cancel_at_period_end: z.boolean(),
  next_charge_at: z.string().nullable(),
  grace_ends_at: z.string().nullable(),
  ended_at: z.string().nullable(),
  payment_method: Json.nullable(),
  created_at: z.string(),
  invoices: z.array(InvoiceRead),
});
const str = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const toSubscription = (s: z.infer<typeof SubscriptionRead>): Subscription => ({
  id: s.id,
  expert: { id: s.expert.id, name: s.expert.display_name },
  planName: str(s.plan.name) ?? 'Plan',
  status: s.status,
  price: s.price,
  currency: s.currency,
  interval: s.interval,
  perks: { premiumPosts: s.perks.premium_posts === true, chat: s.perks.chat === true, signalsFeed: s.perks.signals_feed === true },
  currentPeriodEnd: msReq(s.current_period_end),
  cancelAtPeriodEnd: s.cancel_at_period_end,
  nextChargeAt: ms(s.next_charge_at),
  graceEndsAt: ms(s.grace_ends_at),
  endedAt: ms(s.ended_at),
  paymentMethod: s.payment_method ? { brand: str(s.payment_method.brand), last4: str(s.payment_method.last4) } : null,
  invoices: s.invoices.map((i) => ({
    id: i.id,
    number: i.number,
    kind: i.kind,
    amount: i.amount,
    currency: i.currency,
    status: i.status,
    periodStart: msReq(i.period_start),
    periodEnd: msReq(i.period_end),
    failureReason: i.failure_reason,
    paidAt: ms(i.paid_at),
    refundedAt: ms(i.refunded_at),
  })),
  createdAt: msReq(s.created_at),
});

const ConversationListRead = z.object({
  id: z.string(),
  expert_id: z.string(),
  other: Person,
  status: z.enum(['open', 'closed', 'blocked']),
  can_send: z.boolean(),
  read_only_reason: z.string().nullable(),
  unread: z.number().int(),
  last_message: z.object({ excerpt: z.string().nullable(), created_at: z.string() }).nullable(),
});

const toFollows = (items: z.infer<typeof FollowEntryRead>[]) => items.map((f) => ({ user: { id: f.user.id, name: f.user.display_name, role: f.user.role }, since: msReq(f.since) }));

export function apiSocialService(http: HttpClient): SocialService {
  return {
    likePost: async (id) => {
      const r = await http.request('POST', endpoints.social.like(id), { schema: LikeRead });
      return { liked: r.liked, likes: r.likes_count };
    },
    unlikePost: async (id) => {
      const r = await http.request('DELETE', endpoints.social.like(id), { schema: LikeRead });
      return { liked: r.liked, likes: r.likes_count };
    },
    updatePost: async (id, p) => {
      const body: Record<string, unknown> = {};
      if (p.title !== undefined) body.title = p.title.trim();
      if (p.body !== undefined) body.body = p.body.trim();
      if (p.direction !== undefined) body.direction = p.direction;
      if (p.visibility !== undefined) body.visibility = p.visibility;
      return toPost(await http.request('PATCH', endpoints.social.post(id), { body, schema: PostRead }));
    },
    deletePost: async (id) => {
      await http.request('DELETE', endpoints.social.post(id), { schema: Empty });
    },
    updateComment: async (id, body) => {
      await http.request('PATCH', endpoints.social.comment(id), { body: { body: body.trim() }, schema: Empty });
    },
    deleteComment: async (id) => {
      await http.request('DELETE', endpoints.social.comment(id), { schema: Empty });
    },
    report: async (target, targetId, reason) => {
      await http.request('POST', endpoints.social.reports, { body: { target_type: target, target_id: targetId, reason: reason.trim() }, schema: Empty });
    },
    profile: async (userId, o) => {
      const p = await http.request('GET', endpoints.social.profile(userId), { schema: ProfileRead, ...opt(o?.signal) });
      return {
        id: p.id,
        name: p.display_name,
        role: p.role,
        memberSince: msReq(p.member_since),
        posts: p.posts_count,
        followers: p.followers_count,
        following: p.following_count,
        followable: p.followable,
        isFollowing: p.is_following,
        recentPosts: p.recent_posts.map((x) => ({ id: x.id, title: x.title, createdAt: msReq(x.created_at) })),
        publicStrategies: p.public_strategies,
      };
    },
    follow: async (userId) => {
      const r = await http.request('POST', endpoints.social.follow(userId), { schema: FollowRead });
      return { following: r.following, followers: r.followers_count };
    },
    unfollow: async (userId) => {
      const r = await http.request('DELETE', endpoints.social.follow(userId), { schema: FollowRead });
      return { following: r.following, followers: r.followers_count };
    },
    following: async (o) => toFollows((await http.request('GET', endpoints.social.following, { query: { limit: 100 }, schema: pageOf(FollowEntryRead), ...opt(o?.signal) })).items),
    followers: async (o) => toFollows((await http.request('GET', endpoints.social.followers, { query: { limit: 100 }, schema: pageOf(FollowEntryRead), ...opt(o?.signal) })).items),
    expert: async (id, o) => {
      const e = await http.request('GET', endpoints.expertsExtra.item(id), { schema: ExpertDetailRead, ...opt(o?.signal) });
      return {
        id: e.id,
        name: e.display_name,
        headline: e.headline,
        bio: e.bio,
        markets: e.markets,
        languages: e.languages,
        chatEnabled: e.chat_enabled,
        responseTimeHint: e.response_time_hint,
        followers: e.followers_count,
        subscribers: e.subscribers_count,
        memberSince: msReq(e.member_since),
        isSubscribed: e.is_subscribed,
        plans: e.plans.map(toPlan),
        entitlements: e.entitlements,
      };
    },
    expertSignals: async (id, o) => (await http.request('GET', endpoints.expertsExtra.signals(id), { query: { limit: 50 }, schema: pageOf(Json), ...opt(o?.signal) })).items,
    checkout: async (planId, returnUrl) => {
      const c = await http.request('POST', endpoints.expertsExtra.checkout, {
        body: { plan_id: planId, ...(returnUrl ? { return_url: returnUrl } : {}) },
        schema: z.object({ checkout_id: z.string(), checkout_url: z.string(), status: z.string(), expires_at: z.string() }),
      });
      return { checkoutId: c.checkout_id, checkoutUrl: c.checkout_url, status: c.status, expiresAt: msReq(c.expires_at) };
    },
    subscriptions: async (o) => (await http.request('GET', endpoints.expertsExtra.subscriptions, { schema: z.array(SubscriptionRead), ...opt(o?.signal) })).map(toSubscription),
    cancelSubscription: async (id) => toSubscription(await http.request('POST', endpoints.expertsExtra.cancel(id), { schema: SubscriptionRead })),
    resumeSubscription: async (id) => toSubscription(await http.request('POST', endpoints.expertsExtra.resume(id), { schema: SubscriptionRead })),
    conversations: async (o) =>
      (await http.request('GET', endpoints.chat.open, { schema: z.array(ConversationListRead), ...opt(o?.signal) })).map((c) => ({
        id: c.id,
        expertId: c.expert_id,
        other: { id: c.other.id, name: c.other.display_name, role: c.other.role },
        status: c.status,
        canSend: c.can_send,
        readOnlyReason: c.read_only_reason,
        unread: c.unread,
        lastMessage: c.last_message ? { excerpt: c.last_message.excerpt, createdAt: msReq(c.last_message.created_at) } : null,
      })),
    markConversationRead: async (id) => {
      await http.request('POST', endpoints.chat.read(id), { schema: Empty });
    },
  };
}
