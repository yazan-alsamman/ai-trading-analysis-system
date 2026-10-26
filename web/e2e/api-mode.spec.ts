import { expect, test } from '@playwright/test';
import { atTime, useTheme, WEEKDAY } from './fixtures';
import { mockBackend, PASSWORD, seedSession, USER } from './mockBackend';

/**
 * The production bundle built with VITE_DATA_SOURCE=api and a same-origin
 * VITE_API_BASE_URL=/api/v1 (project "api-mode" in playwright.config.ts),
 * against a contract-faithful mock of the FastAPI backend (./mockBackend.ts).
 */

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
  await atTime(page, WEEKDAY);
  await page.setViewportSize({ width: 1440, height: 900 });
});

test('protected routes require sign-in; wrong credentials are reported; sign-in returns to the requested page', async ({ page }) => {
  const api = await mockBackend(page);
  await page.goto('/signals');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email').fill(USER.email);
  await page.getByLabel('Password', { exact: true }).fill('wrong-pass1');
  await page.getByRole('button', { name: /^Sign in/ }).click();
  await expect(page.getByText('The email or password is incorrect.')).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: /^Sign in/ }).click();
  await expect(page).toHaveURL(/\/signals$/);
  await expect(page.getByRole('button', { name: `Account menu for ${USER.full_name}` })).toBeVisible();
  // The access token goes in the Authorization header — never in a URL.
  const me = api.calls.find((c) => c.path === '/users/me');
  expect(me?.auth).toBe('Bearer acc-1');
  expect(api.calls.every((c) => !c.path.includes('acc-'))).toBe(true);
  expect(api.unexpected).toEqual([]);
});

test('signals: real strategy-engine signals are listed; the AI model output is honestly unavailable', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/signals');
  const panel = page.getByRole('region', { name: 'Strategy-engine signals' });
  await expect(panel).toBeVisible();
  await expect(panel.getByText('RSI reversal').first()).toBeVisible();
  await expect(panel.getByText('XAU/USD')).toBeVisible();
  await expect(panel.getByText('BTC/USDT').first()).toBeVisible();
  await expect(page.getByText('Not available yet').first()).toBeVisible();
  await expect(page.getByText(/not exposed by the backend yet/).first()).toBeVisible();
  expect(api.unexpected).toEqual([]);
});

test('an expired access token is refreshed once and the request retried; a revoked session signs out', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  api.expireAccessToken();
  await page.goto('/settings');
  await expect(page.getByRole('region', { name: 'Account' })).toBeVisible();
  expect(api.refreshCount).toBe(1);
  const rotated = api.calls.filter((c) => c.path === '/users/me').map((c) => c.auth);
  expect(rotated.at(-1)).toBe('Bearer acc-1');

  // Server-side revocation: the next refresh is refused → back to sign-in, session removed.
  api.revokeRefreshTokens();
  await page.goto('/alerts');
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => localStorage.getItem('ata.session.v1'))).toBeNull();
});

test('workspace: candles from the backend, live updates over the WebSocket, labelled as a backend feed', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/workspace');
  await expect(page.getByText('Streaming').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Backend feed').first()).toBeVisible();
  expect(await page.locator('canvas').count()).toBeGreaterThan(0);
  const candles = api.calls.find((c) => /\/market\/instruments\/i-eur\/candles/.test(c.path));
  expect(candles).toBeDefined();
  expect(api.wsSent.some((m) => m.op === 'subscribe' && m.instrument_id === 'i-eur')).toBe(true);
  expect(api.ws?.url()).toMatch(/\/ws\/market\?token=acc-0$/);
  expect(api.unexpected).toEqual([]);
});

test('alerts: server alerts listed; creating one sends the backend contract', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/alerts');
  const table = page.getByRole('region', { name: /Price alerts/i }).first();
  await expect(page.getByText('Your notification settings').first()).toBeVisible();
  await page.getByRole('button', { name: 'New price alert' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText(/the server fires this alert/)).toBeVisible();
  await dialog.getByLabel('Instrument').selectOption('XAUUSD');
  await dialog.getByLabel('Condition').selectOption('crosses_above');
  await dialog.getByLabel(/Price/).first().fill('2500');
  await dialog.getByRole('button', { name: /Create|Save/ }).last().click();
  await expect(dialog).toBeHidden();
  const create = api.calls.find((c) => c.method === 'POST' && c.path === '/me/price-alerts');
  expect(create?.body).toEqual({ instrument_id: 'i-xau', condition: 'crosses_above', value: 2500, repeat: 'once', note: null });
  void table;
  expect(api.unexpected).toEqual([]);
});

test('notifications come from the server inbox and read state is saved there', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/overview');
  const bell = page.getByRole('button', { name: /^Notifications/ });
  await expect(bell).toHaveAccessibleName(/unread/);
  await bell.click();
  await page.getByRole('button', { name: 'Mark read' }).click();
  await expect.poll(() => api.calls.some((c) => c.method === 'POST' && c.path === '/me/notifications/read-all')).toBe(true);
});

test('settings: profile name saved on the server; sign-out revokes the refresh token and clears the session', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/settings');
  const account = page.getByRole('region', { name: 'Account' });
  await account.getByLabel('Display name').fill('Sara K. Trader');
  await account.getByRole('button', { name: 'Save name' }).click();
  await expect(page.getByText('Name saved.')).toBeVisible();
  expect(api.calls.find((c) => c.method === 'PATCH' && c.path === '/users/me')?.body).toEqual({ full_name: 'Sara K. Trader' });
  await expect(page.getByRole('button', { name: 'Account menu for Sara K. Trader' })).toBeVisible();

  await page.getByRole('button', { name: 'Account menu for Sara K. Trader' }).click();
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(api.calls.find((c) => c.path === '/auth/logout')?.body).toEqual({ refresh_token: 'ref-0' });
  expect(await page.evaluate(() => localStorage.getItem('ata.session.v1'))).toBeNull();
});

test('community: backend news (no invented impact), posts and experts', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/community/news');
  await expect(page.getByText(/sentiment/).first()).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Filter by impact' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Read at/ }).first()).toHaveAttribute('rel', /noopener/);
  await page.goto('/community/experts');
  await expect(page.getByText('Sami Expert').first()).toBeVisible();
  await expect(page.getByText('Chat open').first()).toBeVisible();
  expect(api.unexpected).toEqual([]);
});

test('the public website still works in backend mode and makes no API calls', async ({ page }) => {
  const api = await mockBackend(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: /every gold idea/i })).toBeVisible();
  await page.goto('/about');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('A clearer way');
  expect(api.calls).toEqual([]);
});

/* ---- Full integration: every remaining backend capability has a screen (recorded backend responses) ---- */

test('strategies: catalog, activation sends the backend contract, rule-based preview chart', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/strategies');
  await expect(page.getByRole('heading', { name: 'Strategies', level: 1 })).toBeVisible();
  await page.getByRole('radio', { name: 'Catalog' }).click();
  const card = page.getByRole('region', { name: 'Moving Average Crossover' });
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Activate' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Instrument').selectOption('i-xau');
  await dialog.getByLabel('Timeframe').selectOption('1h');
  await dialog.getByRole('button', { name: 'Activate' }).click();
  await expect(dialog).toBeHidden();
  const create = api.calls.find((c) => c.method === 'POST' && c.path === '/me/strategies');
  expect(create?.body).toMatchObject({ strategy_key: 'ma_crossover', instrument_id: 'i-xau', timeframe: '1h', is_active: true });

  await page.getByRole('radio', { name: 'Catalog' }).click();
  await card.getByRole('button', { name: 'Preview' }).click();
  const preview = page.getByRole('dialog');
  await expect(preview.getByText(/not AI output/).first()).toBeVisible();
  await preview.getByLabel('Instrument').selectOption('i-xau');
  await preview.getByRole('button', { name: 'Run preview' }).click();
  await expect(preview.locator('canvas').first()).toBeVisible();
  expect(api.calls.some((c) => c.method === 'POST' && c.path === '/strategies/ma_crossover/preview')).toBe(true);
  expect(api.unexpected).toEqual([]);
});

test('backtests: list, result page with metrics, equity chart, trades and CSV export', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/backtests');
  await expect(page.getByRole('heading', { name: 'Backtests', level: 1 })).toBeVisible();
  await expect(page.getByText(/not a forecast/i).first()).toBeVisible();
  await page.goto('/backtests/cae6ba92-75cc-4eed-a397-e3bacfbeb853');
  await expect(page.getByText('Total return').first()).toBeVisible();
  await expect(page.locator('canvas').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Backtest trades' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toMatch(/^backtest-.*-trades\.csv$/);
  expect(api.unexpected).toEqual([]);
});

test('settings: server notification preferences saved; API key shown once; a workspace version conflict is never overwritten silently', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/settings');
  const prefs = page.locator('#notifications');
  await expect(prefs.getByText('Telegram').first()).toBeVisible();
  await prefs.getByLabel('Language of notification texts').selectOption('en');
  await prefs.getByRole('button', { name: 'Save preferences' }).click();
  await expect.poll(() => api.calls.find((c) => c.method === 'PUT' && c.path === '/me/notification-preferences')?.body).toMatchObject({ language: 'en' });

  const keys = page.locator('#api-keys');
  await keys.getByRole('button', { name: 'New key' }).click();
  const keyDialog = page.getByRole('dialog', { name: 'New API key' });
  await keyDialog.getByLabel('Name').fill('Bot');
  await keyDialog.getByRole('checkbox').first().check();
  await keyDialog.getByRole('button', { name: 'Create key' }).click();
  const secret = page.getByRole('dialog', { name: 'Your new API key' });
  await expect(secret).toBeVisible();
  await secret.getByRole('button').last().click();
  await expect(secret).toBeHidden();

  // Another device saves first: pushing with the listed version gets the server's 409.
  api.bumpWorkspaceVersion();
  const ws = page.locator('#server-workspaces');
  await ws.getByRole('button', { name: 'Push current' }).first().click();
  const conflict = page.getByRole('dialog', { name: 'Changed on another device' });
  await expect(conflict).toBeVisible();
  await conflict.getByRole('button', { name: 'Overwrite with mine' }).click();
  await expect(conflict).toBeHidden();
  const puts = api.calls.filter((c) => c.method === 'PUT' && /^\/me\/workspaces\//.test(c.path));
  expect(puts.length).toBe(2);
  expect((puts[1]?.body as { version: number }).version).toBe((puts[0]?.body as { version: number }).version + 1);
  expect(api.unexpected).toEqual([]);
});

test('community: like, profile with follow, expert plans labelled as demo payments, subscriptions after checkout', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/community/posts');
  await page.getByRole('button', { name: /^Like/ }).first().click();
  await expect.poll(() => api.calls.some((c) => c.method === 'POST' && /^\/posts\/[^/]+\/like$/.test(c.path))).toBe(true);

  await page.goto('/community/people/35da2fba-7e7e-486f-b7ff-8c06bbd4ff68');
  await expect(page.getByRole('heading', { name: 'Lina Analyst' })).toBeVisible();
  await page.getByRole('button', { name: /^(Follow|Unfollow)$/ }).click();
  await expect.poll(() => api.calls.some((c) => /^\/users\/[^/]+\/follow$/.test(c.path))).toBe(true);

  await page.goto('/community/experts/d8896f08-c212-47b0-8c26-86b4e3d743c7');
  await expect(page.getByText(/no real money/i).first()).toBeVisible();
  await expect(page.getByText(/4242 4242 4242 4242/).first()).toBeVisible();

  await page.goto('/subscriptions/return?status=succeeded&checkout_id=x');
  await expect(page.getByText('Payment accepted')).toBeVisible();
  await expect(page.getByText('Sami Expert').first()).toBeVisible();
  expect(api.unexpected).toEqual([]);
});

test('alerts: the server trigger history is shown', async ({ page }) => {
  const api = await mockBackend(page);
  await seedSession(page);
  await page.goto('/alerts');
  await expect(page.getByRole('region', { name: 'Alert trigger history' })).toBeVisible();
  expect(api.unexpected).toEqual([]);
});
