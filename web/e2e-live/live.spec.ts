import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

/**
 * LIVE integration: real browser + real backend-mode bundle + REAL running backend
 * (FastAPI + PostgreSQL/TimescaleDB + Redis). No request is mocked, except where a
 * test name says "fault injection". Server-side effects are verified through the
 * backend's own API. See playwright.live.config.ts.
 */
const BACKEND = process.env.LIVE_BACKEND_URL ?? 'http://127.0.0.1:8000';
const API = `${BACKEND}/api/v1`;
const PASSWORD = 'Live-pass1234';

interface Account {
  email: string;
  name: string;
  access: string;
  refresh: string;
}

async function newAccount(request: APIRequestContext, name = 'Live Tester'): Promise<Account> {
  const email = `live-e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`;
  const reg = await request.post(`${API}/auth/register`, { data: { email, password: PASSWORD, full_name: name } });
  expect(reg.status()).toBe(201);
  const login = await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } });
  const t = (await login.json()) as { access_token: string; refresh_token: string };
  return { email, name, access: t.access_token, refresh: t.refresh_token };
}

const auth = (a: { access: string }) => ({ Authorization: `Bearer ${a.access}` });

async function signInThroughUi(page: Page, a: Account, target = '/overview') {
  await page.goto(target);
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email').fill(a.email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Sign in/ }).click();
  await expect(page).toHaveURL(new RegExp(`${target.replace(/[/?]/g, '\\$&')}$`));
}

const storedSession = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem('ata.session.v1') ?? 'null') as { token: string; refreshToken: string; expiresAt: number } | null);

test.beforeAll(async ({ request }) => {
  const health = await request.get(`${API}/health/ready`);
  expect(health.status(), `backend not reachable at ${BACKEND}`).toBe(200);
  expect(await health.json()).toMatchObject({ checks: { database: 'ok', redis: 'ok' } });
});

test('register through the UI creates a real account in the database', async ({ page, request }) => {
  const email = `live-e2e-ui-${Date.now()}@example.com`;
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Live UI Register');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  await page.getByLabel(/I understand this platform provides analysis only/).check();
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/welcome/);
  // The account exists on the server and its name was stored.
  const login = await request.post(`${API}/auth/login`, { data: { email, password: PASSWORD } });
  expect(login.status()).toBe(200);
  const me = await request.get(`${API}/users/me`, { headers: auth({ access: ((await login.json()) as { access_token: string }).access_token }) });
  expect(await me.json()).toMatchObject({ email, full_name: 'Live UI Register', role: 'trader' });
  // Registering the same email again is refused by the server and explained in the UI.
  await page.context().clearCookies();
  await page.evaluate(() => localStorage.clear());
  await page.goto('/register');
  await page.getByLabel('Full name').fill('Duplicate');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Confirm password').fill(PASSWORD);
  await page.getByLabel(/I understand this platform provides analysis only/).check();
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText(/already exists/).first()).toBeVisible();
});

test('protected route → real sign-in → back to the page; all calls go to the same-origin API', async ({ page, request }) => {
  const a = await newAccount(request, 'Live Sign In');
  const foreign: string[] = [];
  page.on('request', (r) => {
    const u = new URL(r.url());
    if (u.pathname.startsWith('/api/') && u.origin !== 'http://localhost:4175') foreign.push(r.url());
  });
  await page.goto('/login');
  await page.getByLabel('Email').fill(a.email);
  await page.getByLabel('Password', { exact: true }).fill('wrong-pass99');
  await page.getByRole('button', { name: /^Sign in/ }).click();
  await expect(page.getByText('The email or password is incorrect.')).toBeVisible();
  await signInThroughUi(page, a, '/settings');
  await expect(page.getByRole('region', { name: 'Account' })).toContainText(a.email);
  await expect(page.getByRole('button', { name: 'Account menu for Live Sign In' })).toBeVisible();
  expect(foreign).toEqual([]);
});

test('workspace: real candles, and live updates over the real WebSocket', async ({ page, request }) => {
  const a = await newAccount(request);
  const frames: string[] = [];
  page.on('websocket', (ws) => ws.on('framereceived', (f) => frames.push(String(f.payload))));
  await signInThroughUi(page, a, '/workspace');
  await expect(page.getByText('Streaming').first()).toBeVisible();
  await expect(page.getByText('Backend feed').first()).toBeVisible();
  expect(await page.locator('canvas').count()).toBeGreaterThan(0);
  const types = () => frames.map((f) => (JSON.parse(f) as { type?: string }).type);
  await expect.poll(types, { timeout: 20_000 }).toContain('subscribed');
  await expect.poll(types, { timeout: 20_000 }).toContain('snapshot');
  // simulate-live (backend CLI) publishes the current EUR/USD candle every 2 s while this suite runs.
  await expect.poll(types, { timeout: 25_000 }).toContain('candle');
});

test('signals: the real strategy-engine list; the AI model output is reported unavailable', async ({ page, request }) => {
  const a = await newAccount(request);
  const live = (await (await request.get(`${API}/signals`, { headers: auth(a) })).json()) as { total: number };
  await signInThroughUi(page, a, '/signals');
  const panel = page.getByRole('region', { name: 'Strategy-engine signals' });
  if (live.total === 0) await expect(panel.getByText('No strategy signals yet')).toBeVisible();
  else await expect(panel.locator('tbody tr')).toHaveCount(Math.min(live.total, 50));
  await expect(page.getByText('Not available yet').first()).toBeVisible();
});

test('price alert: created in the UI, stored on the server, deleted in the UI', async ({ page, request }) => {
  const a = await newAccount(request);
  await signInThroughUi(page, a, '/alerts');
  const instruments = (await (await request.get(`${API}/market/instruments`, { headers: auth(a), params: { limit: 100 } })).json()) as { items: { id: string; symbol: string }[] };
  const xau = instruments.items.find((i) => i.symbol === 'XAU/USD');
  if (!xau) throw new Error('XAU/USD not seeded');
  const candles = (await (await request.get(`${API}/market/instruments/${xau.id}/candles`, { headers: auth(a), params: { timeframe: '1h', limit: 2 } })).json()) as { candles: { close: number }[] };
  const target = Math.round((candles.candles.at(-1)?.close ?? 2400) * 1.2 * 100) / 100;

  await page.getByRole('button', { name: 'New price alert' }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Instrument').selectOption('XAUUSD');
  await dialog.getByLabel('Condition').selectOption('crosses_above');
  await dialog.getByLabel(/Price/).first().fill(String(target));
  await dialog.getByRole('button', { name: /Create|Save/ }).last().click();
  await expect(dialog).toBeHidden();

  const stored = (await (await request.get(`${API}/me/price-alerts`, { headers: auth(a) })).json()) as { items: { id: string; value: number; condition: string; instrument: { symbol: string } }[] };
  expect(stored.items).toHaveLength(1);
  expect(stored.items[0]).toMatchObject({ value: target, condition: 'crosses_above', instrument: { symbol: 'XAU/USD' } });

  await page.getByRole('button', { name: 'Delete alert for XAU/USD' }).click();
  await page.getByRole('button', { name: 'Delete alert', exact: true }).click();
  await expect.poll(async () => ((await (await request.get(`${API}/me/price-alerts`, { headers: auth(a) })).json()) as { total: number }).total).toBe(0);
});

test('a server notification reaches the bell; marking it read is saved on the server', async ({ page, request }) => {
  const a = await newAccount(request);
  await signInThroughUi(page, a, '/overview');
  const sent = await request.post(`${API}/me/notifications/test`, { headers: auth(a), data: { channel: 'in_app' } });
  expect(sent.status()).toBe(201);
  const bell = page.getByRole('button', { name: /^Notifications/ });
  await expect(bell).toHaveAccessibleName(/unread/, { timeout: 20_000 });
  await bell.click();
  await page.getByRole('button', { name: 'Mark read' }).click();
  await expect
    .poll(async () => ((await (await request.get(`${API}/me/notifications`, { headers: auth(a) })).json()) as { items: { read_at: string | null }[] }).items.every((n) => n.read_at !== null))
    .toBe(true);
});

test('settings: name saved on the server; wrong current password is refused by the server', async ({ page, request }) => {
  const a = await newAccount(request, 'Live Settings');
  await signInThroughUi(page, a, '/settings');
  const account = page.getByRole('region', { name: 'Account' });
  await account.getByLabel('Display name').fill('Live Settings Edited');
  await account.getByRole('button', { name: 'Save name' }).click();
  await expect(page.getByText('Name saved.')).toBeVisible();
  expect(await (await request.get(`${API}/users/me`, { headers: auth(a) })).json()).toMatchObject({ full_name: 'Live Settings Edited' });

  await account.getByLabel('Current password').fill('not-my-password1');
  await account.getByLabel('New password', { exact: true }).fill('Another-pass99');
  await account.getByLabel('Confirm new password').fill('Another-pass99');
  await account.getByRole('button', { name: 'Change password' }).click();
  await expect(account.getByText('Current password is incorrect')).toBeVisible();
});

test("posting as a trader shows the server's own refusal", async ({ page, request }) => {
  const a = await newAccount(request);
  await signInThroughUi(page, a, '/community/posts');
  await page.getByLabel('New post').fill('Gold is holding the range.');
  await page.getByRole('button', { name: /^Post|Publish/ }).first().click();
  await expect(page.getByText('Your role cannot publish posts')).toBeVisible();
});

test('access token close to expiry is refreshed against the real server (rotation)', async ({ page, request }) => {
  const a = await newAccount(request);
  await signInThroughUi(page, a, '/settings');
  const before = await storedSession(page);
  if (!before) throw new Error('no session stored');
  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem('ata.session.v1') ?? '{}') as { expiresAt: number };
    s.expiresAt = Date.now() + 5_000;
    localStorage.setItem('ata.session.v1', JSON.stringify(s));
  });
  const refreshed = page.waitForResponse((r) => r.url().endsWith('/api/v1/auth/refresh'));
  await page.reload();
  expect((await refreshed).status()).toBe(200);
  await expect(page.getByRole('region', { name: 'Account' })).toBeVisible();
  const after = await storedSession(page);
  // Rotation: a new refresh token was issued and persisted. (The access JWT may be byte-identical when
  // reissued within the same second: the backend's tokens carry second-precision iat/exp and no jti.)
  expect(after?.refreshToken).toBeTruthy();
  expect(after?.refreshToken).not.toBe(before.refreshToken);
  expect(after?.expiresAt).toBeGreaterThan(Date.now() + 60_000);
  // The old refresh token is spent on the server; the new one is the live one.
  expect((await request.post(`${API}/auth/refresh`, { data: { refresh_token: before.refreshToken } })).status()).toBe(401);
});

test('sign-out revokes the refresh token on the server and clears the browser session', async ({ page, request }) => {
  const a = await newAccount(request, 'Live Sign Out');
  await signInThroughUi(page, a, '/overview');
  const s = await storedSession(page);
  await page.getByRole('button', { name: 'Account menu for Live Sign Out' }).click();
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await storedSession(page)).toBeNull();
  const reuse = await request.post(`${API}/auth/refresh`, { data: { refresh_token: s?.refreshToken } });
  expect(reuse.status()).toBe(401);
});

test('an invalid stored session is rejected by the server and the user is sent to sign-in', async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('seeded')) return;
    sessionStorage.setItem('seeded', '1');
    localStorage.setItem(
      'ata.session.v1',
      JSON.stringify({ user: { id: 'x', name: 'Ghost', email: 'ghost@example.com', role: 'trader' }, token: 'invalid', refreshToken: 'invalid', expiresAt: Date.now() + 3_600_000, isDemo: false }),
    );
  });
  await page.goto('/overview');
  await expect(page).toHaveURL(/\/login$/);
  expect(await storedSession(page)).toBeNull();
});

test('fault injection: when market requests fail the UI says so and never shows demo data', async ({ page, request }) => {
  const a = await newAccount(request);
  await signInThroughUi(page, a, '/overview');
  await page.route('**/api/v1/market/**', (r) => r.abort('connectionrefused'));
  await page.goto('/workspace');
  await expect(page.getByText(/Could not reach the server/).first()).toBeVisible();
  await expect(page.getByText('Simulated', { exact: true })).toHaveCount(0);
});
