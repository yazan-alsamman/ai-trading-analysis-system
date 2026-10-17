import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { ROUTES, settle, useTheme, type Theme } from './fixtures';

/**
 * Automated accessibility scan (WCAG 2.1 A/AA rules, incl. colour contrast)
 * for every route in both themes. Canvas chart content is excluded; it is
 * described by the container's accessible name instead.
 */
for (const theme of ['dark', 'light'] as Theme[]) {
  for (const route of ROUTES) {
    test(`a11y ${theme} ${route}`, async ({ page }) => {
      await useTheme(page, theme);
      await page.setViewportSize({ width: 1280, height: 800 });
      await page.goto(route);
      await settle(page);
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .exclude('canvas')
        .analyze();
      const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
      const summary = serious.map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`);
      expect(summary, summary.join('\n')).toEqual([]);
    });
  }
}

test('keyboard: skip link, visible focus, dialog Escape returns focus', async ({ page }) => {
  await useTheme(page, 'dark');
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/alerts');
  await settle(page);

  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: /skip to main content/i })).toBeFocused();

  const newAlert = page.getByRole('button', { name: /new price alert/i });
  await newAlert.focus();
  const outline = await newAlert.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe('none');

  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: /new price alert/i })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(newAlert).toBeFocused();
});
