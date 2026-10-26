import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiAdminService } from './adminApi';
import { apiMarketContextService } from './extrasApi';
import { createHttpClient } from './http';
import { apiSocialService } from './socialApi';
import { apiNotificationSettings, apiWorkspaceSync } from './accountApi';
import type { MarketSocket } from './marketSocket';

/**
 * Admin console, workspace sharing, chat moderation, news/indicator/risk
 * extras and data health against RECORDED responses of the real backend
 * (docs/postman/tools/examples.json). Every recorded success body must parse.
 */
type Recorded = Record<string, { code: number; body: string; variant?: string }[]>;
const examples = JSON.parse(readFileSync(resolve(process.cwd(), '../docs/postman/tools/examples.json'), 'utf8')) as Recorded;
const rec = (name: string, code?: number): unknown => {
  const e = examples[name]?.find((x) => code === undefined || x.code === code) ?? examples[name]?.[0];
  if (!e) throw new Error(`No recorded example "${name}"`);
  return e.body ? JSON.parse(e.body) : null;
};
function respond(status: number, payload: unknown) {
  return vi.fn().mockImplementation(() =>
    Promise.resolve(new Response(status === 204 ? null : JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } })),
  );
}
const http = () => createHttpClient({ baseUrl: 'http://api.test/api/v1', timeoutMs: 1000, getToken: () => 'tok', onUnauthorized: vi.fn() });
const lastCall = (f: ReturnType<typeof vi.fn>) => {
  const [url, init] = f.mock.calls.at(-1) as [string, RequestInit];
  return { url: new URL(url), init, body: init.body ? (init.body instanceof FormData ? init.body : JSON.parse(String(init.body))) : undefined };
};
const use = (status: number, payload: unknown) => {
  const f = respond(status, payload);
  vi.stubGlobal('fetch', f);
  return f;
};

afterEach(() => vi.unstubAllGlobals());

describe('admin console (recorded backend responses)', () => {
  const admin = () => apiAdminService(http());

  it('status blocks are passed through as the server sent them', async () => {
    use(200, rec('admin_system_status'));
    expect(await admin().systemStatus()).toMatchObject({ environment: 'development' });
    use(200, rec('admin_realtime'));
    expect(await admin().realtimeStats()).toHaveProperty('clients');
    use(200, rec('admin_rate_limits'));
    expect(await admin().rateLimitStats()).toHaveProperty('rejected');
    use(200, rec('admin_payment_stats'));
    expect(await admin().paymentStats()).toHaveProperty('mrr');
    use(503, { status: 'unavailable' });
    expect(await admin().readiness()).toEqual({ status: 'not_ready' });
  });

  it('users: filters as query parameters; role and status changes', async () => {
    const f = use(200, rec('admin_users'));
    const page = await admin().users({ limit: 20, offset: 0, role: 'trader', isActive: true, search: 'sara' });
    const q = lastCall(f).url.searchParams;
    expect([q.get('role'), q.get('is_active'), q.get('q')]).toEqual(['trader', 'true', 'sara']);
    expect(page.items[0]).toMatchObject({ email: expect.any(String), role: expect.any(String) });
    const user = (rec('admin_users') as { items: Record<string, unknown>[] }).items[0];
    const g = use(200, { ...user, role: 'analyst' });
    expect((await admin().setRole(String(user?.id), 'analyst')).role).toBe('analyst');
    expect(lastCall(g).body).toEqual({ role: 'analyst' });
  });

  it('moderation: reports with the reported excerpt; resolve sends action and note', async () => {
    use(200, rec('admin_reports'));
    const reports = await admin().reports({ status: 'open', limit: 50, offset: 0 });
    expect(reports.items[0]).toMatchObject({ targetType: 'post', status: 'open', target: { title: 'ETH/BTC: momentum is turning' } });
    const f = use(200, rec('admin_report_resolve'));
    await admin().resolveReport(reports.items[0]?.id ?? '', 'hide', 'Promises guaranteed profits');
    expect(lastCall(f).body).toEqual({ action: 'hide', note: 'Promises guaranteed profits' });
    use(200, rec('admin_conversations'));
    expect((await admin().conversations({ limit: 50, offset: 0 })).items[0]).toHaveProperty('status');
  });

  it('payments: subscriptions, refund and demo fast-forward', async () => {
    use(200, rec('admin_subscriptions'));
    expect((await admin().subscriptions({ limit: 50, offset: 0 })).items[0]).toMatchObject({ currency: 'USD', user: { name: 'Lina Analyst' } });
    use(200, rec('admin_refund'));
    expect(await admin().refundInvoice('4ff1ec67-efd6-40a3-a671-a3bb85d1856f')).toMatchObject({ number: 'INV-2026-000001' });
    const f = use(200, rec('admin_fast_forward'));
    expect((await admin().fastForward('s', 'period_end')).outcome).toBe('renewed');
    expect(lastCall(f).body).toEqual({ to: 'period_end' });
  });

  it('API keys, news sources, broadcast, calendar refresh', async () => {
    use(200, rec('admin_keys'));
    expect((await admin().apiKeys({ limit: 50, offset: 0 })).items[0]).toHaveProperty('ownerEmail');
    use(200, rec('news_sources'));
    expect((await admin().newsSources())[0]).toMatchObject({ key: 'coindesk_rss', kind: 'rss' });
    const s = use(200, rec('admin_news_source'));
    await admin().updateNewsSource('id', { fetchIntervalMinutes: 30 });
    expect(lastCall(s).body).toEqual({ fetch_interval_minutes: 30 });
    const b = use(202, rec('admin_notif_broadcast'));
    expect(await admin().broadcast({ title: 'Maintenance', body: 'Tonight', severity: 'info', roles: null })).toMatchObject({ recipients: 1 });
    expect(lastCall(b).body).toMatchObject({ roles: null, severity: 'info' });
    use(200, rec('admin_calendar_refresh'));
    expect(await admin().refreshCalendar()).toHaveProperty('status');
  });

  it('calendar import is a multipart upload with the dry-run flag', async () => {
    const f = use(200, rec('admin_calendar_import'));
    await admin().importCalendar(new File(['date,currency\n'], 'cal.csv', { type: 'text/csv' }), { dryRun: true, source: 'manual' });
    const call = lastCall(f);
    expect(call.url.searchParams.get('dry_run')).toBe('true');
    expect(call.body).toBeInstanceOf(FormData);
    expect((call.init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });

  it('AI engine: setups, detail, outbox, models', async () => {
    use(200, rec('admin_ai_setups'));
    const setups = await admin().aiSetups({ limit: 50 });
    expect(setups[0]).toMatchObject({ profile: 'intraday' });
    use(200, rec('admin_ai_setup'));
    const detail = await admin().aiSetup(setups[0]?.setupId ?? '');
    expect(Array.isArray(detail.events)).toBe(true);
    use(200, rec('admin_ai_outbox'));
    expect((await admin().aiOutbox({ limit: 50, offset: 0 })).items[0]).toHaveProperty('status');
    use(200, rec('admin_ai_models'));
    expect((await admin().aiModels())[0]).toMatchObject({ modelId: 'lgbm-2026-10-01' });
  });

  it('instruments: create returns the specs as sent; candles report how many were written', async () => {
    use(201, rec('admin_instrument_create'));
    const i = await admin().createInstrument({ symbol: 'AUD/USD', source: 'twelvedata', market: 'forex' });
    expect(i.symbol).toBeTruthy();
    expect(i.specs).toBeTypeOf('object');
    use(200, rec('admin_candles_upsert'));
    expect(await admin().uploadCandles(i.id, [{ ts: '2026-10-19T14:00:00Z', open: 1, high: 1, low: 1, close: 1, volume: 0 }])).toBeGreaterThanOrEqual(0);
  });
});

describe('user-facing extras (recorded backend responses)', () => {
  it('workspace share, shared copy, import and reorder', async () => {
    const ws = apiWorkspaceSync(http(), {} as MarketSocket);
    use(200, rec('ws_share'));
    expect(await ws.share('w')).toEqual({ isShared: true, slug: 'lw70_hvGpjdW0Pnu' });
    use(200, rec('ws_shared_get'));
    expect((await ws.shared('lw70_hvGpjdW0Pnu')).owner).toEqual({ name: 'Yazan Alsamman', role: 'expert' });
    use(201, rec('ws_shared_import'));
    expect((await ws.importShared('lw70_hvGpjdW0Pnu')).id).toBeTruthy();
    const f = use(200, rec('ws_reorder'));
    await ws.reorder(['a', 'b']);
    expect(lastCall(f).body).toEqual({ ids: ['a', 'b'] });
  });

  it('chat: conversation detail, block and message edit', async () => {
    const social = apiSocialService(http());
    use(200, rec('chat_get'));
    expect(await social.conversation('c')).toMatchObject({ blockedByMe: false });
    use(200, rec('chat_block'));
    expect((await social.blockConversation('c')).status).toBe('blocked');
    const f = use(200, rec('chat_edit'));
    expect((await social.editMessage('m', 'Hi!')).editedAt).not.toBeNull();
    expect(lastCall(f).body).toEqual({ body: 'Hi!' });
  });

  it('news article, sentiment window, indicators, risk schema, devices', async () => {
    const ctx = apiMarketContextService(http());
    use(200, rec('news_get'));
    expect((await ctx.article('a')).source.key).toBe('postman');
    const s = use(200, rec('news_sentiment'));
    expect((await ctx.sentiment('7d', null)).window).toBe('7d');
    expect(lastCall(s).url.searchParams.get('window')).toBe('7d');
    use(200, rec('indicators_catalog'));
    expect((await ctx.indicatorCatalog())[0]).toMatchObject({ name: 'sma', placement: 'overlay', lookback: 19 });
    const c = use(200, rec('indicators_compute'));
    const results = await ctx.computeIndicators('i', { timeframe: '1h', limit: 3, indicators: [{ name: 'rsi', params: { length: 14 } }] });
    expect(results[0]?.outputs.rsi?.length).toBeGreaterThan(0);
    expect(lastCall(c).body).toMatchObject({ timeframe: '1h', indicators: [{ name: 'rsi' }] });
    use(200, rec('risk_schema'));
    expect((await ctx.riskSchema()).defaultTemplate).toBe('balanced');
    use(200, rec('notif_devices'));
    expect((await apiNotificationSettings(http()).devices())[0]).toMatchObject({ platform: 'android' });
  });

  it('data health: a 503 still carries the quality report, sent without a token', async () => {
    const f = use(503, rec('health_data'));
    const h = await apiMarketContextService(http()).dataHealth();
    expect(h.status).toBe('no_data');
    expect(h.instruments[0]).toMatchObject({ instrument: 'fxpro:XAU/USD', status: 'no_data' });
    expect((lastCall(f).init.headers as Record<string, string>).Authorization).toBeUndefined();
  });
});
