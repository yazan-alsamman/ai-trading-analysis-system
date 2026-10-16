#!/usr/bin/env node
/**
 * Whole-page visual check for routes whose content scrolls inside <main>.
 * Grows the viewport to the content height, then screenshots.
 *
 *   BASE_URL=http://localhost:5173 node scripts/qa-page.mjs overview,risk 1440,390 dark,light
 *
 * PREFS_PATCH='{"riskProfile":{...}}' merges into stored preferences (only when they already exist).
 * Output: qa-screenshots/page/<route>-<width>-<theme>.png (git-ignored).
 * Reports horizontal overflow and console errors; exit code 1 on errors.
 */
import { mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';

const [routesArg = 'overview', widthsArg = '1440', themesArg = 'dark'] = process.argv.slice(2);
const base = process.env.BASE_URL ?? 'http://localhost:5173';
const heights = { 390: 844, 768: 1024, 1024: 768, 1280: 800, 1440: 900 };
const out = 'qa-screenshots/page';
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome' });
const errors = [];
for (const theme of themesArg.split(',')) {
  for (const width of widthsArg.split(',').map(Number)) {
    for (const routeArg of routesArg.split(',')) {
      const route = '/' + routeArg.replace(/^\/+/, '');
      const context = await browser.newContext({ viewport: { width, height: heights[width] ?? 900 }, timezoneId: 'UTC', colorScheme: theme });
      await context.addInitScript(([t, patch]) => {
        try {
          const raw = localStorage.getItem('ata.preferences.v1');
          const prefs = raw ? JSON.parse(raw) : { theme: t };
          prefs.theme = t;
          Object.assign(prefs, patch);
          localStorage.setItem('ata.preferences.v1', JSON.stringify(prefs));
          sessionStorage.setItem('ata.demoBannerDismissed', '1');
        } catch {}
      }, [theme, JSON.parse(process.env.PREFS_PATCH ?? '{}')]);
      const page = await context.newPage();
      page.on('pageerror', (e) => errors.push(`${route} ${width} ${theme}: ${e.message}`));
      page.on('console', (m) => m.type() === 'error' && errors.push(`${route} ${width} ${theme} console: ${m.text()}`));
      await page.goto(base + route.replace(/~/g, '?').replace(/!/g, '&'), { waitUntil: 'networkidle' });
      await page.waitForTimeout(Number(process.env.WAIT_MS ?? 1800));
      const full = await page.evaluate(() => {
        const main = document.querySelector('main');
        const extra = main ? main.scrollHeight - main.clientHeight : 0;
        return document.documentElement.scrollHeight + Math.max(0, extra);
      });
      if (!process.env.VIEWPORT_ONLY) await page.setViewportSize({ width, height: Math.min(full, 9000) });
      await page.waitForTimeout(500);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      const name = `${out}/${routeArg.replace(/[\/~!=&?]/g, '_')}-${width}-${theme}.png`;
      await page.screenshot({ path: name, fullPage: true });
      console.log(`${name}  height=${full}  horizontal-overflow=${overflow}px`);
      await context.close();
    }
  }
}
await browser.close();
if (errors.length) {
  console.log('\nErrors:\n' + errors.join('\n'));
  process.exitCode = 1;
}
