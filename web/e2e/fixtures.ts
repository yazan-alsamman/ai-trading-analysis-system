import type { Page } from '@playwright/test';

export const ROUTES = ['/', '/about', '/ai-assistant', '/legal/risk-disclosure', '/legal/data-storage', '/membership', '/overview', '/workspace', '/signals', '/risk', '/assistant', '/alerts', '/insights', '/community/news', '/community/posts', '/community/experts', '/settings', '/login', '/register'] as const;
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

/** Wednesday 14 Oct 2026 14:00 UTC: FX market open (London/New York overlap). */
export const WEEKDAY = new Date('2026-10-14T14:00:00Z');
/** Saturday 17 Oct 2026 16:00 UTC: FX market closed. */
export const WEEKEND = new Date('2026-10-17T16:00:00Z');

/**
 * Pin the page's clock (Date only; timers keep running). The demo market
 * follows real FX hours, so tests that need live signals or an open feed must
 * not depend on the day they run — they failed every weekend before this.
 */
export async function atTime(page: Page, time: Date): Promise<void> {
  await page.clock.setFixedTime(time);
}

/**
 * Scroll a pinned scene to a given progress (0–1) of its scroll distance. The
 * pinned element is the section itself or the descendant with an `h-[Nvh]` height.
 */
export async function scrollSequence(page: Page, id: string, progress: number): Promise<void> {
  await page.evaluate(
    ([sid, p]) => {
      const sec = document.getElementById(sid);
      if (!sec) throw new Error(`No section #${sid}`);
      const tall = [sec, ...Array.from(sec.querySelectorAll<HTMLElement>('div'))].find((e) => /h-\[\d+vh\]/.test(e.className)) ?? sec;
      const top = tall.getBoundingClientRect().top + window.scrollY;
      window.scrollTo(0, top + p * Math.max(0, tall.offsetHeight - window.innerHeight));
    },
    [id, progress] as const,
  );
  await page.waitForTimeout(500);
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
