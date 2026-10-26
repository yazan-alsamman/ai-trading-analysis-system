import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiAISetupService, apiCalendarService } from './aiApi';
import { createHttpClient } from './http';
import type { MarketSocket } from './marketSocket';

/**
 * AI setups and the economic calendar against RECORDED responses of the real
 * backend (docs/postman/tools/examples.json). Requests are checked against the
 * backend's documented paths and parameters.
 */
type Recorded = Record<string, { code: number; body: string; variant?: string }[]>;
const examples = JSON.parse(readFileSync(resolve(process.cwd(), '../docs/postman/tools/examples.json'), 'utf8')) as Recorded;
const rec = (name: string, code?: number): unknown => {
  const e = examples[name]?.find((x) => code === undefined || x.code === code) ?? examples[name]?.[0];
  if (!e) throw new Error(`No recorded example "${name}"`);
  return JSON.parse(e.body);
};

function respond(status: number, payload: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(status === 204 ? null : JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } }),
  );
}
const http = () => createHttpClient({ baseUrl: 'http://api.test/api/v1', timeoutMs: 1000, getToken: () => 'tok', onUnauthorized: vi.fn() });
const noSocket = {} as MarketSocket;
const lastUrl = (f: ReturnType<typeof vi.fn>) => new URL((f.mock.calls.at(-1) as [string])[0]);
const lastInit = (f: ReturnType<typeof vi.fn>) => (f.mock.calls.at(-1) as [string, RequestInit])[1];

afterEach(() => vi.unstubAllGlobals());

describe('AI setups (recorded backend responses)', () => {
  it('follows: list and upsert with a minimum grade', async () => {
    const f = respond(200, rec('ai_follows'));
    vi.stubGlobal('fetch', f);
    const ai = apiAISetupService(http(), noSocket);
    const list = await ai.follows();
    expect(list[0]).toMatchObject({ profile: 'intraday', minGrade: 'B' });
    vi.stubGlobal('fetch', respond(200, rec('ai_follow')));
    const put = vi.mocked(fetch);
    await ai.follow('7f560b7c-da33-4814-8201-47dcb3134566', 'intraday', 'B');
    expect(lastUrl(put).pathname).toBe('/api/v1/me/ai/follows/7f560b7c-da33-4814-8201-47dcb3134566/intraday');
    expect(lastInit(put).method).toBe('PUT');
    expect(JSON.parse(String(lastInit(put).body))).toEqual({ min_grade: 'B' });
  });

  it('size keeps the server numbers and warnings (no client-side sizing)', async () => {
    vi.stubGlobal('fetch', respond(200, rec('ai_setup_size')));
    const s = await apiAISetupService(http(), noSocket).size('xauusd-intraday-2026-10-19T14:15:00Z-buy');
    const raw = rec('ai_setup_size') as { lots: number; risk_amount: number; warnings: string[]; source: string };
    expect(s).toMatchObject({ lots: raw.lots, riskAmount: raw.risk_amount, source: raw.source, warnings: raw.warnings, feasible: true });
    expect(s.inputs.sources).toMatchObject({ balance: 'profile' });
  });

  it('explanation: verified text is shown; an unavailable one stays null', async () => {
    vi.stubGlobal('fetch', respond(200, rec('ai_setup_explanation')));
    const ai = apiAISetupService(http(), noSocket);
    const ar = await ai.explanation('x', 'ar');
    expect(lastUrl(vi.mocked(fetch)).searchParams.get('lang')).toBe('ar');
    expect(ar).toMatchObject({ status: 'verified', lang: 'ar' });
    expect(ar.text).toBeTruthy();
    const unavailable = (examples.ai_setup_explanation ?? []).find((e) => e.variant?.includes('Unavailable'));
    vi.stubGlobal('fetch', respond(200, JSON.parse(unavailable?.body ?? '{}')));
    expect(await ai.explanation('x', 'en')).toMatchObject({ text: null, status: 'unavailable' });
  });

  it('take sends only the fields the user set; trades map the setup state', async () => {
    const f = respond(201, rec('ai_setup_take'));
    vi.stubGlobal('fetch', f);
    const ai = apiAISetupService(http(), noSocket);
    const t = await ai.take('xauusd-intraday-2026-10-19T14:15:00Z-buy', { lots: null, entryPrice: 2400.5 });
    expect(JSON.parse(String(lastInit(f).body))).toEqual({ entry_price: 2400.5 });
    expect(t).toMatchObject({ lots: 0.2, entryPrice: 2400.5, closedAt: null });
    vi.stubGlobal('fetch', respond(200, rec('ai_trades')));
    const trades = await ai.trades({ limit: 50, offset: 0 });
    expect(trades.total).toBe(1);
    expect(trades.items[0]).toMatchObject({ state: 'ACTIVE', direction: 'buy', entry: 2400, sl: 2395, tp: 2410 });
  });

  it('recent: the latest state per setup from ai_setup notifications; malformed items are skipped, nulls stay null', async () => {
    // Shape of `data` built by backend app/ai/alerts.py::_base_data (no notification was recorded).
    const data = (state: string, at: string) => ({
      setup_id: 's-1',
      state,
      transition: { from: 'DEVELOPING', to: state, at, reason: 'rules', realized_r: null },
      direction: 'buy',
      instrument: { id: 'i-xau', symbol: 'XAU/USD', source: 'twelvedata', price_precision: 2, quantity_precision: 2 },
      profile: 'intraday',
      entry: 2400,
      sl: 2395,
      tp: 2410,
      r_multiple: 2,
      probability: null,
      ev_r: null,
      grade: null,
      valid_until: '2026-10-19T15:15:00Z',
      reason: 'rules',
      realized_r: null,
      late: false,
    });
    const items = [
      { id: 'n2', type: 'ai_setup', title: '', body: '', severity: 'info', created_at: '2026-10-19T15:00:00Z', read_at: null, data: data('ACTIVE', '2026-10-19T15:00:00Z') },
      { id: 'n1', type: 'ai_setup', title: '', body: '', severity: 'warning', created_at: '2026-10-19T14:15:00Z', read_at: null, data: data('ARMED', '2026-10-19T14:15:00Z') },
      { id: 'n0', type: 'ai_setup', title: '', body: '', severity: 'info', created_at: '2026-10-19T14:00:00Z', read_at: null, data: { setup_id: 'broken' } },
    ];
    const f = respond(200, { items, total: 3, limit: 100, offset: 0 });
    vi.stubGlobal('fetch', f);
    const list = await apiAISetupService(http(), noSocket).recent();
    expect(lastUrl(f).pathname).toBe('/api/v1/me/notifications');
    expect(lastUrl(f).searchParams.get('type')).toBe('ai_setup');
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ setupId: 's-1', state: 'ACTIVE', probability: null, evR: null, grade: null, instrument: { symbol: 'XAU/USD' } });
  });

  it('live frames on ai:setups:<id> become setups; other frames are ignored', () => {
    let handler: ((m: Record<string, unknown>) => void) | undefined;
    const socket = {
      subscribeTopic: vi.fn((_t: string, _i: string, _k: string, h: (m: Record<string, unknown>) => void) => {
        handler = h;
        return () => undefined;
      }),
    } as unknown as MarketSocket;
    const onEvent = vi.fn();
    apiAISetupService(http(), socket).subscribe({ id: 'i-xau', symbol: 'XAU/USD', pricePrecision: 2 }, onEvent);
    expect(socket.subscribeTopic).toHaveBeenCalledWith('ai_setups', 'i-xau', 'ai:setups:i-xau', expect.any(Function));
    handler?.({ type: 'ai_setup', topic: 'ai:setups:i-xau', setup: { setup_id: 's-2', state: 'ARMED', direction: 'sell', entry: 2400, sl: 2405, tp: 2390, probability: null }, transition: { at: '2026-10-19T14:15:00Z' } });
    handler?.({ type: 'something_else' });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0]?.[0]).toMatchObject({ instrumentId: 'i-xau', setup: { setupId: 's-2', state: 'ARMED', direction: 'sell', probability: null } });
  });
});

describe('economic calendar (recorded backend responses)', () => {
  it('events: ISO window, currencies and minimum impact as the backend expects', async () => {
    const f = respond(200, rec('calendar_events'));
    vi.stubGlobal('fetch', f);
    const res = await apiCalendarService(http()).events({ start: Date.UTC(2024, 11, 16), end: Date.UTC(2024, 11, 23), currencies: ['USD'], minImpact: 'medium' });
    const q = lastUrl(f).searchParams;
    expect(q.get('start')).toBe('2024-12-16T00:00:00.000Z');
    expect(q.get('currencies')).toBe('USD');
    expect(q.get('min_impact')).toBe('medium');
    const fed = res.events.find((e) => e.title === 'Federal Funds Rate');
    expect(fed).toMatchObject({ impact: 'high', currency: 'USD', actual: '4.50%', scheduledAt: Date.parse('2024-12-18T19:00:00Z') });
  });

  it('history: every version, oldest first', async () => {
    vi.stubGlobal('fetch', respond(200, rec('calendar_event_history')));
    const versions = await apiCalendarService(http()).history('0d2a6087');
    expect(versions.length).toBeGreaterThan(1);
    expect(versions[0]?.actual).toBeNull();
  });

  it('a window over 31 days is refused by the server and surfaces as a validation error', async () => {
    vi.stubGlobal('fetch', respond(422, rec('calendar_events', 422)));
    await expect(apiCalendarService(http()).events({ start: 0, end: 40 * 86_400_000 })).rejects.toMatchObject({ kind: 'validation' });
  });
});
