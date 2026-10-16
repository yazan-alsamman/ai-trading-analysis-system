import type { Page } from '@playwright/test';

export const ROUTES = ['/', '/membership', '/overview', '/workspace', '/signals', '/risk', '/assistant', '/alerts', '/insights', '/community/news', '/community/posts', '/community/experts', '/settings', '/login', '/register'] as const;
export const WIDTHS = [1440, 1280, 1024, 768, 390] as const;
export const HEIGHTS: Record<number, number> = { 1440: 900, 1280: 800, 1024: 768, 768: 1024, 390: 844 };
export type Theme = 'dark' | 'light';

/** Seed preferences before the app loads so the chosen theme applies on first paint. */
export async function useTheme(page: Page, theme: Theme): Promise<void> {
  await page.addInitScript((t) => {
    const prefs = {
      theme: t,
      density: 'comfortable',
      timeZone: 'UTC',
      channels: { app: { enabled: true }, email: { enabled: false, address: '' }, telegram: { enabled: false, handle: '' } },
      workspaces: [
        { id: 'ws-main', name: 'Main workspace', symbol: 'EURUSD', timeframe: '15m', chartType: 'candles', indicators: ['volume', 'ema50'], showOpportunityOverlay: true, showForecast: true },
      ],
      activeWorkspaceId: 'ws-main',
    };
    try {
      if (!localStorage.getItem('ata.preferences.v1')) localStorage.setItem('ata.preferences.v1', JSON.stringify(prefs));
    } catch {
      /* storage unavailable */
    }
  }, theme);
}

/** Wait until loading skeletons are gone. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(() => document.querySelectorAll('[aria-busy="true"]').length === 0, undefined, { timeout: 10_000 });
  // Let entrance animations finish so checks (e.g. axe contrast) see final states. Infinite loops are ignored.
  await page.waitForFunction(
    () => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.getComputedTiming().iterations === Infinity),
    undefined,
    { timeout: 10_000 },
  );
  await page.waitForTimeout(300);
}
