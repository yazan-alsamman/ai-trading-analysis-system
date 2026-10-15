import { expect, test } from '@playwright/test';
import { settle, useTheme } from './fixtures';

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
});

test('workspace renders a labelled simulated chart and AI panel', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await expect(page).toHaveURL(/\/workspace$/);
  await settle(page);

  await expect(page.getByRole('heading', { level: 1, name: 'EUR/USD' })).toBeVisible();
  await expect(page.getByText('Simulated feed')).toBeVisible();
  await expect(page.getByRole('group', { name: 'Price chart' })).toHaveAccessibleDescription(/simulated eur\/usd 15m candles chart/i);
  await expect(page.getByRole('region', { name: 'AI opportunity' }).getByText(/not a guarantee of profit/i)).toBeVisible();
  // Canvas actually drew something.
  expect(await page.locator('canvas').count()).toBeGreaterThan(0);
});

test('watchlist, timeframe, chart type and indicators drive the chart', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/workspace');
  await settle(page);

  await page.getByRole('list', { name: 'Watchlist' }).getByRole('button', { name: /USD\/JPY/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'USD/JPY' })).toBeVisible();

  await page.getByRole('radio', { name: '4h' }).click();
  await expect(page.getByRole('radio', { name: '4h' })).toHaveAttribute('aria-checked', 'true');
  await expect(page).toHaveTitle(/USD\/JPY 4h/);

  await page.getByRole('radio', { name: 'Line' }).click();
  await settle(page);
  await expect(page.getByRole('group', { name: 'Price chart' })).toHaveAccessibleDescription(/line chart/i);

  await page.getByRole('button', { name: /indicators/i }).click();
  await page.getByRole('checkbox', { name: /RSI 14/ }).check();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: /indicators/i })).toContainText('3');

  // Selection persists across reloads (workspace saved).
  await page.reload();
  await settle(page);
  await expect(page.getByRole('heading', { level: 1, name: 'USD/JPY' })).toBeVisible();
});

test('quick search switches instrument from the keyboard', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/signals');
  await settle(page);
  await page.keyboard.press('Control+k');
  await page.getByRole('combobox', { name: /search instruments/i }).fill('gold');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole('heading', { level: 1, name: 'XAU/USD' })).toBeVisible();
});

test('signals filters live in the URL and open the workspace', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/signals');
  await settle(page);
  await page.getByLabel('Timeframe').selectOption('1h');
  await expect(page).toHaveURL(/tf=1h/);
  const rows = page.getByRole('region', { name: 'Signals table' }).locator('tbody tr');
  await expect(rows.first()).toBeVisible();
  for (const tf of await rows.locator('td:nth-child(2)').allTextContents()) expect(tf).toBe('1h');
  await rows.first().getByRole('button', { name: /open/i }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole('radio', { name: '1h' })).toHaveAttribute('aria-checked', 'true');
});

test('demo scenarios surface error and stale states', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/settings');
  await settle(page);
  await page.getByRole('radio', { name: /request failures/i }).check();
  await page.getByRole('link', { name: 'Signals' }).click();
  await expect(page.getByRole('alert').getByText(/server encountered an error/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();
});

test('theme toggle switches and persists', async ({ page }) => {
  await page.goto('/workspace');
  await page.getByRole('button', { name: /switch to light theme/i }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('login validates input and creates a labelled demo session', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText(/enter your email address/i)).toBeVisible();
  await page.getByLabel('Email').fill('elias@example.com');
  await page.getByLabel('Password').fill('secret123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await page.getByRole('button', { name: /account menu/i }).click();
  await expect(page.getByText('Demo session')).toBeVisible();
});

test('unknown routes show a helpful 404', async ({ page }) => {
  await page.goto('/nope');
  await expect(page.getByRole('heading', { name: /page not found/i })).toBeVisible();
});

test('keyboard shortcuts: help dialog, g-chord navigation, workspace keys', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/workspace');
  await settle(page);

  await page.keyboard.press('Shift+Slash');
  await expect(page.getByRole('dialog', { name: /keyboard shortcuts/i })).toBeVisible();
  await page.keyboard.press('Escape');

  await page.keyboard.press('3');
  await expect(page.getByRole('radio', { name: '4h' })).toHaveAttribute('aria-checked', 'true');
  await page.keyboard.press(']');
  await expect(page.getByRole('heading', { level: 1, name: 'GBP/USD' })).toBeVisible();

  await page.keyboard.press('g');
  await page.keyboard.press('s');
  await expect(page).toHaveURL(/\/signals$/);
  await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toContainText('Signals');
});

test('workspace shows timeframe alignment and notification centre', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/workspace');
  await settle(page);
  await expect(page.getByRole('group', { name: 'Analysis per timeframe' })).toBeVisible();
  await page.getByRole('button', { name: /^Notifications/ }).click();
  await expect(page.getByRole('group', { name: 'Notifications' })).toBeVisible();
});
