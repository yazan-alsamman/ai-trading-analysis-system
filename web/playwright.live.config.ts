import { defineConfig } from '@playwright/test';

/**
 * LIVE integration tests: the backend-mode production bundle, in Chrome, against a
 * REAL running backend (no request mocking). Opt-in — they need the backend stack:
 *
 *   LIVE_BACKEND_URL=http://127.0.0.1:8000 pnpm exec playwright test -c playwright.live.config.ts
 *
 * The bundle is served by `vite preview` on :4175 and reaches the backend through the
 * Vite proxy (/api, /ws → BACKEND_URL), exactly as in local development: same origin,
 * no CORS. See docs/BACKEND_INTEGRATION_SETUP.md. Never point this at production —
 * the tests register accounts and create data (prefix `live-e2e-`, removable with
 * `python -m app.cli purge-demo --prefix live-e2e- --yes`).
 */
const backend = process.env.LIVE_BACKEND_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  testDir: './e2e-live',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:4175',
    channel: 'chrome',
    timezoneId: 'UTC',
    locale: 'en-GB',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm exec vite build --outDir dist-live && pnpm exec vite preview --outDir dist-live --port 4175 --strictPort',
    url: 'http://localhost:4175',
    reuseExistingServer: false,
    timeout: 240_000,
    env: { VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: '/api/v1', BACKEND_URL: backend },
  },
});
