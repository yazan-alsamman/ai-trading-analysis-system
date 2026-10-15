import { expect, test } from '@playwright/test';
import { HEIGHTS, ROUTES, settle, useTheme, WIDTHS, type Theme } from './fixtures';

/**
 * Visual QA matrix: every route × 5 widths × 2 themes.
 * Saves screenshots to qa-screenshots/ for manual review and asserts that the
 * page never scrolls horizontally and no runtime errors occur.
 */
for (const theme of ['dark', 'light'] as Theme[]) {
  for (const width of WIDTHS) {
    test(`layout ${theme} ${width}px`, async ({ page }) => {
      test.setTimeout(120_000);
      await useTheme(page, theme);
      await page.setViewportSize({ width, height: HEIGHTS[width] ?? 900 });
      const errors: string[] = [];
      page.on('pageerror', (e) => errors.push(e.message));
      page.on('console', (m) => {
        if (m.type() === 'error') errors.push(m.text());
      });

      for (const route of ROUTES) {
        await page.goto(route);
        await settle(page);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `${route} overflows horizontally by ${overflow}px`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `qa-screenshots/matrix/${theme}-${width}${route.replace(/\//g, '_')}.png` });
      }
      expect(errors, errors.join('\n')).toEqual([]);
    });
  }
}
