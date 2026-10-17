#!/usr/bin/env node
/**
 * Quick visual check: screenshot one route at one or more widths/themes.
 *
 *   node scripts/qa-shot.mjs workspace 1440 dark
 *   node scripts/qa-shot.mjs signals 390,1280 light,dark
 *
 * Requires a running server (default http://localhost:5173, override with BASE_URL).
 * Output: qa-screenshots/<route>-<width>-<theme>.png (git-ignored).
 */
import { mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';

const [routeArg = 'workspace', widthsArg = '1440', themesArg = 'dark'] = process.argv.slice(2);
// Pass routes without the leading slash ('community/news'): Git Bash on Windows
// rewrites arguments that start with '/' into file-system paths.
const route = '/' + routeArg.replace(/^\/+/, '');
const base = process.env.BASE_URL ?? 'http://localhost:5173';
const widths = widthsArg.split(',').map(Number);
const themes = themesArg.split(',');
const heights = { 390: 844, 768: 1024, 1024: 768, 1280: 800, 1440: 900 };

mkdirSync('qa-screenshots', { recursive: true });
const browser = await chromium.launch({ channel: 'chrome' });
const errors = [];
for (const theme of themes) {
  for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: heights[width] ?? 900 }, timezoneId: 'UTC', colorScheme: theme });
    await context.addInitScript((t) => {
      try {
        const raw = localStorage.getItem('ata.preferences.v1');
        const prefs = raw ? JSON.parse(raw) : null;
        if (prefs) {
          prefs.theme = t;
          localStorage.setItem('ata.preferences.v1', JSON.stringify(prefs));
        }
      } catch {}
    }, theme);
    const page = await context.newPage();
    page.on('pageerror', (e) => errors.push(`${route} ${width} ${theme}: ${e.message}`));
    page.on('console', (m) => m.type() === 'error' && errors.push(`${route} ${width} ${theme} console: ${m.text()}`));
    await page.goto(base + route, { waitUntil: 'networkidle' });
    await page.waitForTimeout(Number(process.env.WAIT_MS ?? 1500));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const name = `qa-screenshots/${route.replace(/\//g, '_').replace(/^_/, '') || 'root'}-${width}-${theme}.png`;
    await page.screenshot({ path: name, fullPage: process.env.FULL === '1' });
    console.log(`${name}  horizontal-overflow=${overflow}px`);
    await context.close();
  }
}
await browser.close();
if (errors.length) {
  console.log('\nErrors:\n' + errors.join('\n'));
  process.exitCode = 1;
}
