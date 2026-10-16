import { expect, test, type Page } from '@playwright/test';
import { settle, useTheme } from './fixtures';

/** Scroll a pinned sequence to a given progress (0–1) of its scroll distance. */
async function scrollSequence(page: Page, id: string, progress: number) {
  await page.evaluate(
    ([sid, p]) => {
      const sec = document.getElementById(sid as string)!;
      const tall = (sec.querySelector('.h-\\[340vh\\], .h-\\[360vh\\]') as HTMLElement | null) ?? sec;
      const top = tall.getBoundingClientRect().top + window.scrollY;
      window.scrollTo(0, top + (p as number) * (tall.offsetHeight - window.innerHeight));
    },
    [id, progress],
  );
  await page.waitForTimeout(500);
}

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
  await page.setViewportSize({ width: 1440, height: 900 });
});

test('public landing explains the platform before any sign-in', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  await expect(page.getByRole('heading', { level: 1, name: /every gold idea/i })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Site' }).first()).toContainText('Membership');
  for (const id of ['problem', 'platform', 'how-it-works', 'risk', 'signals', 'methodology', 'membership', 'faq']) {
    await expect(page.locator(`#${id}`)).toHaveCount(1);
  }
  // Honest results: simulated data is labelled and no live results are claimed.
  await expect(page.getByText('No verified live results exist yet.')).toBeVisible();
  await expect(page).toHaveTitle('AI Trading Assistance');
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'index, follow');
});

test('scroll storytelling: the platform sequence follows scroll and its tabs stay usable', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  await scrollSequence(page, 'platform', 0.05);
  await expect(page.getByRole('tab', { name: /Market intelligence/ })).toHaveAttribute('aria-selected', 'true');
  await scrollSequence(page, 'platform', 0.62);
  await expect(page.getByRole('tab', { name: /Personalised signals/ })).toHaveAttribute('aria-selected', 'true');
  // Clicking a tab scrolls to its step (scroll stays the single source of truth).
  await page.getByRole('tab', { name: /AI assistant/ }).click();
  await expect(page.getByRole('tab', { name: /AI assistant/ })).toHaveAttribute('aria-selected', 'true', { timeout: 5000 });
  // Sequence C reveals the risk plan only at its step.
  await scrollSequence(page, 'how-it-works', 0.1);
  await expect(page.getByText('Step 1 of 6')).toBeVisible();
  await scrollSequence(page, 'how-it-works', 0.75);
  await expect(page.getByText('Step 5 of 6')).toBeVisible();
});

test('reduced motion: no pinning, no running animations, hero readable immediately', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto('/');
  await page.waitForTimeout(200);
  await expect(page.getByRole('heading', { level: 1, name: /every gold idea/i })).toBeVisible();
  expect(await page.locator('.sticky').count()).toBe(0);
  const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
  expect(running).toBe(0);
  const hiddenCtas = await page.getByRole('link', { name: 'Get started' }).evaluateAll((els) => els.filter((e) => getComputedStyle(e).opacity === '0').length);
  expect(hiddenCtas).toBe(0);
  await context.close();
});

test('mobile: menu is a dialog that opens, navigates and closes with Escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await settle(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button', { name: 'Open menu' }).click();
  const menu = page.getByRole('dialog', { name: 'Site menu' });
  await expect(menu).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await page.getByRole('button', { name: 'Open menu' }).click();
  await menu.getByRole('link', { name: /Membership/ }).click();
  await expect(page).toHaveURL(/\/membership$/);
});

test('membership journey: compare → select → register with plan → review → demo preview → gated module', async ({ page }) => {
  await page.goto('/membership');
  await settle(page);
  await expect(page.getByText('Pricing to be announced').first()).toBeVisible();
  await page.getByRole('radio', { name: 'Choose Professional' }).click();
  const sheet = page.getByRole('dialog', { name: 'Your selection' });
  await expect(sheet.getByText(/Paid activation is not available yet/)).toBeVisible();
  await sheet.getByRole('link', { name: /Create account with Professional/ }).click();

  await expect(page).toHaveURL(/\/register\?plan=professional$/);
  await expect(page.getByRole('navigation', { name: 'Sign-up progress' })).toBeVisible();
  await expect(page.getByText('Professional', { exact: true })).toBeVisible();
  // The Sign in / Create account switch keeps the plan.
  await expect(page.getByRole('navigation', { name: 'Account' }).getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login?plan=professional');

  await page.getByLabel('Full name').fill('Sara Khalil');
  await page.getByLabel('Email').fill('sara@example.com');
  await page.getByLabel('Password', { exact: true }).fill('Gold2026x');
  await page.getByLabel('Confirm password').fill('Gold2026x');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Create account', exact: true }).click();

  await expect(page).toHaveURL(/\/welcome\?plan=professional$/);
  await expect(page.getByText(/Activation isn’t available yet/)).toBeVisible();
  await page.getByRole('button', { name: /Preview Professional as a demo/ }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole('link', { name: /Demo plan · Professional/ })).toBeVisible();
  await page.goto('/assistant');
  await expect(page.getByRole('region', { name: /AI assistant is not included/ })).toBeVisible();
  await page.getByRole('button', { name: 'Exit plan preview' }).click();
  await expect(page.getByRole('log', { name: 'Conversation' })).toBeVisible();
});

test('public pages are indexable; app pages are not', async ({ page }) => {
  await page.goto('/membership');
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'index, follow');
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', /\/membership$/);
  await page.goto('/overview');
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow');
  const robots = await (await page.request.get('/robots.txt')).text();
  expect(robots).toContain('Disallow: /overview');
});
