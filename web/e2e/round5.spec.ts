import { expect, test, type Page } from '@playwright/test';
import { scrollSequence, settle, useTheme } from './fixtures';

/** Video files the page requested (path under /media/). */
function trackMedia(page: Page): string[] {
  const seen: string[] = [];
  page.on('request', (r) => {
    const m = /\/media\/([^?]+\.mp4)/.exec(r.url());
    if (m?.[1] && !seen.includes(m[1])) seen.push(m[1]);
  });
  return seen;
}

const videoState = (page: Page, file: string) =>
  page.evaluate((f) => {
    const v = Array.from(document.querySelectorAll('video')).find((x) => x.currentSrc.includes(f) || x.src.includes(f));
    return v ? { state: v.dataset.videoState, paused: v.paused, muted: v.muted, time: v.currentTime } : null;
  }, file);

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
  await page.setViewportSize({ width: 1440, height: 900 });
});

test('cinematic hero: licensed footage plays muted, the chart builds, the ambient readout is labelled simulated', async ({ page }) => {
  const media = trackMedia(page);
  await page.goto('/');
  await expect(page.getByTestId('hero-footage').locator('video')).toHaveAttribute('poster', /hero-trader-desk\.webp/);
  await expect.poll(async () => (await videoState(page, 'hero-trader-desk'))?.state, { timeout: 8000 }).toBe('playing');
  const hero = await videoState(page, 'hero-trader-desk');
  expect(hero?.muted).toBe(true);
  // The crosshair starts once the intro has finished and always says the data is simulated.
  await expect(page.locator('#hero-title').locator('xpath=ancestor::section').getByText(/· simulated$/)).toBeVisible({ timeout: 8000 });
  // Below-the-fold footage is not fetched up front.
  expect(media).not.toContain('method-notebook.mp4');
  expect(media).not.toContain('closing-trader-profile.mp4');
});

test('footage plays only on screen: the hero pauses when the visitor scrolls away', async ({ page }) => {
  await page.goto('/');
  await expect.poll(async () => (await videoState(page, 'hero-trader-desk'))?.state, { timeout: 8000 }).toBe('playing');
  await page.evaluate(() => document.getElementById('methodology')?.scrollIntoView({ block: 'start' }));
  await expect.poll(async () => (await videoState(page, 'hero-trader-desk'))?.paused, { timeout: 5000 }).toBe(true);
  await expect.poll(async () => (await videoState(page, 'method-notebook'))?.state, { timeout: 8000 }).toBe('playing');
});

test('reduced motion: posters only — no video element and no video request', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const media = trackMedia(page);
  await page.goto('/');
  await settle(page);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(800);
  expect(await page.locator('video').count()).toBe(0);
  expect(await page.locator('img[data-video-state="poster"]').count()).toBeGreaterThan(0);
  expect(media).toEqual([]);
  await context.close();
});

test('phones: only the light hero rendition is fetched; other scenes show posters', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const media = trackMedia(page);
  await page.goto('/');
  await settle(page);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(800);
  expect(media).toEqual(['hero-trader-desk-sm.mp4']);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('workspace scene: the 3D laptop opens and turns with scroll, showing the product UI', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  const laptop = page.getByTestId('laptop');
  const lid = () => laptop.evaluate((el) => parseFloat(getComputedStyle(el).getPropertyValue('--lid')));
  await scrollSequence(page, 'workspace', 0);
  expect(await lid()).toBeLessThan(-60); // closed
  await scrollSequence(page, 'workspace', 0.6);
  expect(await lid()).toBeGreaterThan(0); // open
  await expect(laptop.getByText('Model output').first()).toBeVisible();
  expect(await laptop.evaluate((el) => getComputedStyle(el).transformStyle)).toBe('preserve-3d');
});

test('chart → plan: the sequence ends in a structured research plan labelled simulated', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  await scrollSequence(page, 'how-it-works', 0.97);
  await expect(page.getByText('Step 7 of 7')).toBeVisible();
  const plan = page.getByRole('article', { name: /Structured research plan/ });
  await expect(plan).toBeVisible();
  await expect(plan).toContainText('Research, not advice');
});

test('assistant scene stays labelled as a rule-based demo', async ({ page }) => {
  await page.goto('/');
  await settle(page);
  await page.evaluate(() => document.getElementById('assistant')?.scrollIntoView({ block: 'start' }));
  const scene = page.locator('#assistant');
  await expect(scene.getByText('Rule-based demo')).toBeVisible();
  await expect(scene.getByText(/Rule-based, not a language model/)).toBeVisible({ timeout: 6000 });
});

test('the selected plan card and the sign-up plan summary share a view-transition name', async ({ page }) => {
  await page.goto('/membership');
  await settle(page);
  await page.getByRole('radio', { name: 'Choose Professional' }).first().click();
  const names = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('.plan-card-inner')).map((e) => getComputedStyle(e).viewTransitionName));
  expect(names.filter((n) => n === 'selected-plan')).toHaveLength(1);
  await page.goto('/register?plan=professional');
  await settle(page);
  const summary = page.getByText('Selected plan').locator('xpath=ancestor::div[contains(@class,"rounded-xl")][1]');
  expect(await summary.evaluate((e) => getComputedStyle(e).viewTransitionName)).toBe('selected-plan');
});

test('footage files are small, local and served as video', async ({ request }) => {
  for (const f of ['hero-trader-desk', 'hero-trader-desk-sm', 'overload-price-board', 'workflow-laptop-chart', 'assistant-reflection', 'method-notebook', 'closing-trader-profile']) {
    const res = await request.get(`/media/${f}.mp4`);
    expect(res.ok()).toBe(true);
    expect(res.headers()['content-type']).toContain('video/mp4');
    expect((await res.body()).length).toBeLessThan(600_000);
    expect((await request.get(`/media/${f}.webp`)).ok()).toBe(true);
  }
});
