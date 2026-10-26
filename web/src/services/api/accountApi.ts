import { z } from 'zod';
import type { ApiKey } from '@/domain/apiKeys';
import type { ChannelInfo, NotificationPreferences } from '@/domain/notificationSettings';
import type { ServerWorkspace, ServerWorkspaceSummary } from '@/domain/serverWorkspaces';
import type { ExpertPlan, ExpertProfile } from '@/domain/social';
import { isApiError } from '../errors';
import type { AlertService, ApiKeyService, ExpertStudioService, NotificationSettingsService, Unsubscribe, WorkspaceSyncService } from '../types';
import { page } from './backend';
import { endpoints } from './endpoints';
import type { HttpClient } from './http';
import type { MarketSocket } from './marketSocket';

/**
 * Account-scoped backend capabilities: delivery preferences and channels
 * (docs/notifications.md), alert history (docs/price-alerts.md), server
 * workspaces (docs/workspaces.md), the expert's own profile and plans
 * (docs/subscriptions.md) and API keys (docs/api-keys.md).
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

/* ------------------------------------------------- notification settings */

const PreferencesRead = z.object({
  matrix: z.record(z.string(), z.record(z.string(), z.boolean())),
  min_signal_strength: z.number(),
  only_valid_plans: z.boolean(),
  quiet_hours: z.object({ start: z.string(), end: z.string(), tz: z.string() }).nullable(),
  language: z.enum(['ar', 'en']),
  max_per_hour: z.record(z.string(), z.number()),
  updated_at: z.string(),
});
const toPreferences = (p: z.infer<typeof PreferencesRead>): NotificationPreferences => ({
  matrix: p.matrix,
  minSignalStrength: p.min_signal_strength,
  onlyValidPlans: p.only_valid_plans,
  quietHours: p.quiet_hours,
  language: p.language,
  maxPerHour: p.max_per_hour,
  updatedAt: msReq(p.updated_at),
});

const ChannelInfoRead = z.object({
  enabled_on_server: z.boolean(),
  linked: z.boolean().nullable().optional(),
  username: z.string().nullable().optional(),
  mode: z.string().nullable().optional(),
  address: z.string().nullable().optional(),
  devices: z.number().int().nullable().optional(),
});
const toChannel = (c: z.infer<typeof ChannelInfoRead>): ChannelInfo => ({
  enabledOnServer: c.enabled_on_server,
  linked: c.linked ?? null,
  username: c.username ?? null,
  mode: c.mode ?? null,
  address: c.address ?? null,
  devices: c.devices ?? null,
});
const ChannelsRead = z.object({ in_app: ChannelInfoRead, telegram: ChannelInfoRead, email: ChannelInfoRead, push: ChannelInfoRead });

export function apiNotificationSettings(http: HttpClient): NotificationSettingsService {
  return {
    getPreferences: async (o) => toPreferences(await http.request('GET', endpoints.notificationSettings.preferences, { schema: PreferencesRead, ...opt(o?.signal) })),
    savePreferences: async (p) =>
      toPreferences(
        await http.request('PUT', endpoints.notificationSettings.preferences, {
          body: {
            matrix: p.matrix,
            min_signal_strength: p.minSignalStrength,
            only_valid_plans: p.onlyValidPlans,
            quiet_hours: p.quietHours,
            language: p.language,
            max_per_hour: p.maxPerHour,
          },
          schema: PreferencesRead,
        }),
      ),
    channels: async (o) => {
      const c = await http.request('GET', endpoints.notificationSettings.channels, { schema: ChannelsRead, ...opt(o?.signal) });
      return { in_app: toChannel(c.in_app), telegram: toChannel(c.telegram), email: toChannel(c.email), push: toChannel(c.push) };
    },
    sendTest: async (channel) => {
      const r = await http.request('POST', endpoints.notificationSettings.test, {
        body: { channel },
        schema: z.object({ deliveries: z.array(z.object({ channel: z.string(), target: z.string(), status: z.string(), last_error: z.string().nullable().optional() })) }),
      });
      return r.deliveries.map((d) => ({ channel: d.channel, target: d.target, status: d.status, lastError: d.last_error ?? null }));
    },
    linkTelegram: async () => {
      const r = await http.request('POST', endpoints.notificationSettings.telegramLink, {
        schema: z.object({ code: z.string(), deep_link: z.string().nullable(), bot_username: z.string().nullable(), expires_in: z.number().int() }),
      });
      return { code: r.code, deepLink: r.deep_link, botUsername: r.bot_username, expiresInSeconds: r.expires_in };
    },
    unlinkTelegram: async () => {
      await http.request('DELETE', endpoints.notificationSettings.telegram, { schema: Empty });
    },
  };
}

/* ------------------------------------------------------------ alert history */

const TriggerRead = z.object({
  notification_id: z.string(),
  alert_id: z.string().nullable(),
  symbol: z.string().nullable(),
  condition: z.string().nullable(),
  value: z.number().nullable(),
  price: z.number().nullable(),
  bar_time: z.string().nullable(),
  change_pct: z.number().nullable(),
  note: z.string().nullable(),
  created_at: z.string(),
});

export function apiAlertHistory(http: HttpClient): AlertService['history'] {
  return async (q, o) => {
    const p = await http.request('GET', endpoints.alertHistory, { query: { alert_id: q?.alertId, limit: Math.min(q?.limit ?? 50, 100) }, schema: page(TriggerRead), ...opt(o?.signal) });
    return p.items.map((t) => ({
      notificationId: t.notification_id,
      alertId: t.alert_id,
      symbol: t.symbol,
      condition: t.condition,
      value: t.value,
      price: t.price,
      barTime: ms(t.bar_time),
      changePct: t.change_pct,
      note: t.note,
      createdAt: msReq(t.created_at),
    }));
  };
}

/* --------------------------------------------------------------- workspaces */

const WorkspaceSummaryRead = z.object({
  id: z.string(),
  name: z.string(),
  position: z.number().int(),
  is_default: z.boolean(),
  version: z.number().int(),
  panel_count: z.number().int().optional(),
  is_shared: z.boolean(),
  updated_at: z.string(),
});
const WorkspaceRead = WorkspaceSummaryRead.extend({
  state: Json,
  share_slug: z.string().nullable(),
  unavailable_instrument_ids: z.array(z.string()).default([]),
});
const toWorkspaceSummary = (w: z.infer<typeof WorkspaceSummaryRead>): ServerWorkspaceSummary => ({
  id: w.id,
  name: w.name,
  position: w.position,
  isDefault: w.is_default,
  version: w.version,
  panelCount: w.panel_count ?? 0,
  isShared: w.is_shared,
  updatedAt: msReq(w.updated_at),
});
const toWorkspace = (w: z.infer<typeof WorkspaceRead>): ServerWorkspace => ({
  ...toWorkspaceSummary(w),
  // The full workspace carries the state instead of a count.
  panelCount: Array.isArray(w.state.panels) ? w.state.panels.length : (w.panel_count ?? 0),
  state: w.state,
  shareSlug: w.share_slug,
  unavailableInstrumentIds: w.unavailable_instrument_ids,
});

export function apiWorkspaceSync(http: HttpClient, socket: MarketSocket): WorkspaceSyncService {
  return {
    list: async (o) => (await http.request('GET', endpoints.workspaces.list, { schema: z.array(WorkspaceSummaryRead), ...opt(o?.signal) })).map(toWorkspaceSummary),
    get: async (id, o) => toWorkspace(await http.request('GET', endpoints.workspaces.item(id), { schema: WorkspaceRead, ...opt(o?.signal) })),
    create: async ({ name, state }) => toWorkspace(await http.request('POST', endpoints.workspaces.list, { body: { name: name.trim(), ...(state ? { state } : {}) }, schema: WorkspaceRead })),
    // The version goes in the body AND as If-Match (docs/workspaces.md); a stale one is a 409 with current_version.
    replaceState: async (id, state, version) =>
      toWorkspace(await http.request('PUT', endpoints.workspaces.item(id), { body: { state, version }, headers: { 'If-Match': `"${version}"` }, schema: WorkspaceRead })),
    update: async (id, p) =>
      toWorkspace(
        await http.request('PATCH', endpoints.workspaces.item(id), {
          body: { ...(p.name !== undefined ? { name: p.name.trim() } : {}), ...(p.isDefault ? { is_default: true } : {}) },
          schema: WorkspaceRead,
        }),
      ),
    remove: async (id) => {
      await http.request('DELETE', endpoints.workspaces.item(id), { schema: Empty });
    },
    duplicate: async (id) => toWorkspace(await http.request('POST', endpoints.workspaces.duplicate(id), { schema: WorkspaceRead })),
    subscribe(onEvent): Unsubscribe {
      return socket.onUserEvent('workspace_updated', (msg) =>
        onEvent({
          workspaceId: typeof msg.workspace_id === 'string' ? msg.workspace_id : null,
          version: typeof msg.version === 'number' ? msg.version : null,
          action: typeof msg.action === 'string' ? msg.action : 'unknown',
        }),
      );
    },
  };
}

/* ----------------------------------------------------------- expert studio */

const ProfileRead = z.object({
  headline: z.string(),
  bio: z.string(),
  markets: z.array(z.string()),
  languages: z.array(z.string()),
  chat_enabled: z.boolean(),
  response_time_hint: z.string().nullable(),
  is_listed: z.boolean(),
});
const toProfile = (p: z.infer<typeof ProfileRead>): ExpertProfile => ({
  headline: p.headline,
  bio: p.bio,
  markets: p.markets,
  languages: p.languages,
  chatEnabled: p.chat_enabled,
  responseTimeHint: p.response_time_hint,
  isListed: p.is_listed,
});

export const PlanRead = z.object({
  id: z.string(),
  expert_id: z.string(),
  name: z.string(),
  description: z.string(),
  price: z.string(),
  currency: z.string(),
  interval: z.enum(['month', 'year']),
  trial_days: z.number().int(),
  perks: Json,
  is_active: z.boolean(),
});
export const toPlan = (p: z.infer<typeof PlanRead>): ExpertPlan => ({
  id: p.id,
  expertId: p.expert_id,
  name: p.name,
  description: p.description,
  price: p.price,
  currency: p.currency,
  interval: p.interval,
  trialDays: p.trial_days,
  perks: { premiumPosts: p.perks.premium_posts === true, chat: p.perks.chat === true, signalsFeed: p.perks.signals_feed === true },
  isActive: p.is_active,
});

const EarningsRead = z.object({
  currency: z.string(),
  platform_fee_pct: z.number(),
  active_subscribers: z.number().int(),
  mrr: z.string(),
  churn_30d_pct: z.number().nullable(),
  months: z.array(z.object({ month: z.string(), gross: z.string(), platform_fee: z.string(), net: z.string(), refunded: z.string(), invoices: z.number().int() })),
  recent_invoices: z.array(
    z.object({ number: z.string(), amount: z.string(), currency: z.string(), status: z.string(), subscriber: z.string(), plan: z.string(), paid_at: z.string().nullable() }),
  ),
});

export function apiExpertStudio(http: HttpClient): ExpertStudioService {
  const planBody = (p: Record<string, unknown>) => {
    const body: Record<string, unknown> = {};
    if (p.name !== undefined) body.name = String(p.name).trim();
    if (p.description !== undefined) body.description = String(p.description).trim();
    if (p.price !== undefined) body.price = p.price;
    if (p.currency !== undefined) body.currency = p.currency;
    if (p.interval !== undefined) body.interval = p.interval;
    if (p.trialDays !== undefined) body.trial_days = p.trialDays;
    if (p.isActive !== undefined) body.is_active = p.isActive;
    const perks = p.perks as { premiumPosts: boolean; chat: boolean; signalsFeed: boolean } | undefined;
    if (perks) body.perks = { premium_posts: perks.premiumPosts, chat: perks.chat, signals_feed: perks.signalsFeed };
    return body;
  };
  return {
    getProfile: async (o) => {
      try {
        return toProfile(await http.request('GET', endpoints.expertStudio.profile, { schema: ProfileRead, ...opt(o?.signal) }));
      } catch (e) {
        if (isApiError(e) && e.kind === 'not_found') return null; // not created yet
        throw e;
      }
    },
    saveProfile: async (p) =>
      toProfile(
        await http.request('PUT', endpoints.expertStudio.profile, {
          body: {
            headline: p.headline.trim(),
            bio: p.bio,
            markets: p.markets,
            languages: p.languages,
            chat_enabled: p.chatEnabled,
            response_time_hint: p.responseTimeHint?.trim() || null,
            is_listed: p.isListed,
          },
          schema: ProfileRead,
        }),
      ),
    listPlans: async (o) => (await http.request('GET', endpoints.expertStudio.plans, { schema: z.array(PlanRead), ...opt(o?.signal) })).map(toPlan),
    createPlan: async (i) => toPlan(await http.request('POST', endpoints.expertStudio.plans, { body: planBody({ ...i }), schema: PlanRead })),
    updatePlan: async (id, p) => toPlan(await http.request('PATCH', endpoints.expertStudio.plan(id), { body: planBody({ ...p }), schema: PlanRead })),
    deactivatePlan: async (id) => {
      await http.request('DELETE', endpoints.expertStudio.plan(id), { schema: Empty });
    },
    earnings: async (o) => {
      const e = await http.request('GET', endpoints.expertStudio.earnings, { schema: EarningsRead, ...opt(o?.signal) });
      return {
        currency: e.currency,
        platformFeePct: e.platform_fee_pct,
        activeSubscribers: e.active_subscribers,
        mrr: e.mrr,
        churn30dPct: e.churn_30d_pct,
        months: e.months.map((m) => ({ month: m.month, gross: m.gross, platformFee: m.platform_fee, net: m.net, refunded: m.refunded, invoices: m.invoices })),
        recentInvoices: e.recent_invoices.map((i) => ({ number: i.number, amount: i.amount, currency: i.currency, status: i.status, subscriber: i.subscriber, plan: i.plan, paidAt: ms(i.paid_at) })),
      };
    },
  };
}

/* ----------------------------------------------------------------- API keys */

const ApiKeyRead = z.object({
  id: z.string(),
  name: z.string(),
  prefix: z.string(),
  scopes: z.array(z.string()),
  rate_limit_per_minute: z.number().int().nullable(),
  expires_at: z.string().nullable(),
  last_used_at: z.string().nullable(),
  revoked: z.boolean(),
  created_at: z.string(),
});
const toApiKey = (k: z.infer<typeof ApiKeyRead>): ApiKey => ({
  id: k.id,
  name: k.name,
  prefix: k.prefix,
  scopes: k.scopes,
  rateLimitPerMinute: k.rate_limit_per_minute,
  expiresAt: ms(k.expires_at),
  lastUsedAt: ms(k.last_used_at),
  revoked: k.revoked,
  createdAt: msReq(k.created_at),
});

export function apiKeyService(http: HttpClient): ApiKeyService {
  return {
    list: async (o) => (await http.request('GET', endpoints.apiKeys.list, { schema: z.array(ApiKeyRead), ...opt(o?.signal) })).map(toApiKey),
    scopes: async (o) =>
      (
        await http.request('GET', endpoints.apiKeys.scopes, {
          schema: z.array(z.object({ scope: z.string(), description: z.string(), grantable: z.boolean() })),
          ...opt(o?.signal),
        })
      ).map((s) => ({ scope: s.scope, description: s.description, grantable: s.grantable })),
    create: async (i) => {
      const k = await http.request('POST', endpoints.apiKeys.list, {
        body: { name: i.name.trim(), scopes: i.scopes, expires_in_days: i.expiresInDays, rate_limit_per_minute: i.rateLimitPerMinute },
        schema: ApiKeyRead.extend({ key: z.string() }),
      });
      return { apiKey: toApiKey(k), secret: k.key };
    },
    update: async (id, p) => {
      const body: Record<string, unknown> = {};
      if (p.name !== undefined) body.name = p.name.trim();
      if (p.scopes !== undefined) body.scopes = p.scopes;
      if (p.rateLimitPerMinute !== undefined) body.rate_limit_per_minute = p.rateLimitPerMinute;
      return toApiKey(await http.request('PATCH', endpoints.apiKeys.item(id), { body, schema: ApiKeyRead }));
    },
    revoke: async (id) => {
      await http.request('DELETE', endpoints.apiKeys.item(id), { schema: Empty });
    },
    usage: async (id, o) =>
      (await http.request('GET', endpoints.apiKeys.usage(id), { schema: z.array(z.object({ date: z.string(), requests: z.number().int(), rejected: z.number().int() })), ...opt(o?.signal) })).map(
        (d) => ({ date: d.date, requests: d.requests, rejected: d.rejected }),
      ),
  };
}
