import { expect, test } from '@playwright/test';
import { settle, useTheme } from './fixtures';

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
  await page.setViewportSize({ width: 1440, height: 900 });
});

test('about: a complete page that answers who, why, what, how, AI, risk, audience, next step', async ({ page }) => {
  await page.goto('/about');
  await settle(page);
  await expect(page).toHaveTitle('About · AI Trading Assistance');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('A clearer way');
  for (const id of ['about-problem', 'capabilities', 'workflow', 'approach-ai', 'risk-transparency', 'audience']) await expect(page.locator(`#${id}`)).toHaveCount(1);
  await expect(page.getByRole('navigation', { name: 'Site' }).first().getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
  // The risk demo uses the real calculator: doubling risk doubles the loss at the stop.
  await page.locator('#risk-transparency').scrollIntoViewIfNeeded();
  const loss = page.locator('#risk-transparency').getByText('Loss if the stop is hit').locator('xpath=following-sibling::dd');
  const at1 = Number((await loss.textContent())?.replace(/[^\d.]/g, ''));
  await page.getByRole('radio', { name: '2 %' }).click();
  await expect.poll(async () => Number((await loss.textContent())?.replace(/[^\d.]/g, ''))).toBeCloseTo(at1 * 2, 1);
  await page.getByRole('link', { name: 'Create an account' }).click();
  await expect(page).toHaveURL(/\/register$/);
});

test('research assistant page: prompt → structured answer → follow-up → typed question → clear', async ({ page }) => {
  await page.goto('/ai-assistant');
  await settle(page);
  await expect(page.getByText('Rule-based demo — not a language model')).toBeVisible();
  const console_ = page.getByRole('region', { name: 'Research assistant' });
  await console_.getByRole('button', { name: 'Explain the current analysis' }).click();
  await expect(console_.getByText('Composing an answer from the context…')).toBeVisible();
  const first = console_.getByRole('article', { name: 'Assistant answer: Analysis summary' });
  await expect(first).toBeVisible();
  await expect(first.getByText('Simulated data.')).toBeVisible();
  await first.getByRole('button', { name: /Summarise the evidence behind this signal/ }).click();
  await expect(console_.getByRole('article', { name: 'Assistant answer: Evidence' })).toBeVisible();
  const input = console_.getByRole('textbox', { name: 'Ask the assistant' });
  await input.fill('Calculate the risk for my capital and stop-loss');
  await input.press('Shift+Enter'); // newline, not send
  await expect(console_.getByRole('article')).toHaveCount(2);
  await input.press('Enter');
  await expect(console_.getByRole('article', { name: 'Assistant answer: Risk sizing' })).toBeVisible();
  await expect(console_.getByRole('article', { name: 'Assistant answer: Risk sizing' })).toContainText('$250.00');
  await console_.getByRole('button', { name: 'Clear conversation' }).click();
  await expect(console_.getByRole('article')).toHaveCount(0);
  await expect(console_.getByText(/question the evidence/i)).toBeVisible();
});

test('launcher: appears after the hero, opens the assistant sheet, steps aside at the footer', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  const launcher = page.getByRole('button', { name: 'Ask the research assistant' });
  await expect(launcher).toBeHidden();
  await page.evaluate(() => window.scrollTo(0, window.innerHeight * 1.5));
  await expect(launcher).toBeVisible();
  await launcher.click();
  const sheet = page.getByRole('dialog', { name: 'Research assistant' });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByText('Rule-based demo')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect(launcher).toBeHidden();
});

test('footer: every link opens a real page or anchor; apps and socials are honest', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  const footer = page.getByRole('contentinfo');
  await expect(footer.getByText('Download the app')).toBeVisible();
  await expect(footer.getByText(/coming soon/i)).toHaveCount(2);
  expect(await footer.locator('a[href^="http"]').count()).toBe(0);
  const hrefs = [...new Set(await footer.locator('a[href^="/"]').evaluateAll((as) => as.map((a) => a.getAttribute('href') ?? '')))];
  expect(hrefs.length).toBeGreaterThan(15);
  for (const href of hrefs) {
    await page.goto(href);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByRole('heading', { name: /not found/i }), href).toHaveCount(0);
    const hash = href.split('#')[1];
    if (hash) await expect(page.locator(`[id="${hash}"]`), href).toHaveCount(1, { timeout: 5000 });
  }
});

test('landing: anatomy of a setup shows zones, checks and labelled sample context', async ({ page }) => {
  await page.goto('/#anatomy');
  await settle(page);
  const scene = page.locator('#anatomy');
  await expect(scene.getByRole('img', { name: /entry, stop and target zones/ })).toBeVisible();
  await expect(scene.getByText('Stop (invalidation)')).toBeVisible();
  await expect(scene.getByText('Sample content').first()).toBeVisible();
  await expect(scene).toContainText('not a current recommendation');
});

test('legal pages exist and are indexable', async ({ page }) => {
  for (const [path, title] of [
    ['/legal/risk-disclosure', 'Risk disclosure'],
    ['/legal/data-storage', 'Data stored in your browser'],
  ] as const) {
    await page.goto(path);
    await settle(page);
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'index, follow');
  }
});

test('phones: about, assistant and footer fit 390 px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/about', '/ai-assistant', '/legal/data-storage']) {
    await page.goto(path);
    await settle(page);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(390);
  }
});
