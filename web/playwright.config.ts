import { defineConfig } from '@playwright/test';

/**
 * End-to-end, accessibility and visual QA.
 * Uses the locally installed Google Chrome (channel: 'chrome'), so no browser
 * download is required. Runs against production builds via `vite preview`:
 *  - project "demo": the default build (VITE_DATA_SOURCE=demo), port 4173;
 *  - project "api-mode": a build with VITE_DATA_SOURCE=api and a same-origin
 *    VITE_API_BASE_URL=/api/v1 (as deployed behind one Nginx), port 4174,
 *    tested against a contract-faithful backend mock (e2e/mockBackend.ts).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 2,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    channel: 'chrome',
    timezoneId: 'UTC',
    locale: 'en-GB',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'demo', testIgnore: /api-mode\.spec\.ts/, use: { baseURL: 'http://localhost:4173' } },
    { name: 'api-mode', testMatch: /api-mode\.spec\.ts/, use: { baseURL: 'http://localhost:4174' } },
  ],
  webServer: [
    {
      command: 'pnpm build && pnpm preview',
      url: 'http://localhost:4173',
      reuseExistingServer: true,
      timeout: 180_000,
    },
    {
      command: 'pnpm exec vite build --outDir dist-api && pnpm exec vite preview --outDir dist-api --port 4174 --strictPort',
      url: 'http://localhost:4174',
      reuseExistingServer: true,
      timeout: 180_000,
      env: { VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: '/api/v1' },
    },
  ],
});
