import { expect, test, type Page } from '@playwright/test';
import { settle, useTheme } from './fixtures';

/** Seed a risk profile (on top of the default preferences) before the app loads. */
async function seedRisk(page: Page, capital: number | null) {
  await page.addInitScript((cap) => {
    try {
      const raw = localStorage.getItem('ata.preferences.v1');
      const prefs = raw ? JSON.parse(raw) : null;
      if (prefs && !prefs.riskProfile)
        prefs.riskProfile = {
          capital: cap,
          currency: 'USD',
          maxRiskPerTradePct: 1,
          dailyLossLimitPct: 3,
          maxOpenRiskPct: 5,
          maxOpenPositions: 3,
          openRisk: 300,
          realisedLossToday: 120,
          openPositions: 1,
          contractSizes: { XAUUSD: 100 },
          volumeStep: 0.01,
        };
      if (prefs) localStorage.setItem('ata.preferences.v1', JSON.stringify(prefs));
    } catch {
      /* storage unavailable */
    }
  }, capital);
}

test.beforeEach(async ({ page }) => {
  await useTheme(page, 'dark');
  await page.setViewportSize({ width: 1440, height: 900 });
});

test('the app Overview shows the seven modules and honest statuses', async ({ page }) => {
  // Since round 4, "/" is the public website; the app overview has its own route.
  await page.goto('/overview');
  await settle(page);
  await expect(page.getByRole('heading', { level: 1, name: /read the market/i })).toBeVisible();
  const modules = page.getByRole('region', { name: /seven modules/i }).locator('ol > li');
  await expect(modules).toHaveCount(8); // 7 modules + "What it never does"
  await expect(page.getByText('Fully working')).toBeVisible();
  await expect(page.getByText('Rule-based demo').first()).toBeVisible();
});

test('risk: sizes gold from capital and stop, rounds lots down, flags the daily limit', async ({ page }) => {
  await seedRisk(page, 25_000);
  await page.goto('/risk?symbol=XAUUSD&entry=2240&stop=2228&target=2270');
  await settle(page);
  const result = page.getByRole('region', { name: 'Result' });
  // $250 budget / $12 stop = 20.83 oz = 0.2083 lots → 0.20 lots → 20 oz → $240 at risk.
  await expect(result.getByRole('definition').filter({ hasText: '20.00 oz' })).toBeVisible();
  await expect(result.getByText('0.20 lots')).toBeVisible();
  await expect(result.getByText('$240.00', { exact: true })).toBeVisible();
  await expect(result.getByText('$600.00', { exact: true })).toBeVisible();
  // 120 realised + 300 open + 240 = 660 of 750 (≥ 80 %) → near the daily limit.
  await expect(page.getByRole('meter', { name: /daily loss limit/i })).toBeVisible();
  await expect(page.getByText('Near limit').first()).toBeVisible();
});

test('risk: withholds results and names the missing input instead of guessing', async ({ page }) => {
  await page.goto('/risk?symbol=XAUUSD&entry=2240&stop=2228');
  await settle(page);
  const result = page.getByRole('region', { name: 'Result' });
  await expect(result.getByText(/nothing is calculated until every required input is known/i)).toBeVisible();
  await expect(result.getByText('Enter your account capital.')).toBeVisible();

  // An inconsistent plan is rejected with a reason.
  await page.getByLabel('Account capital').fill('10000');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await page.getByLabel('Target').fill('2230');
  await expect(result.getByText(/target must be above the entry/i)).toBeVisible();
});

test('personalised signals: profile filter, provenance sheet and sizing link', async ({ page }) => {
  await page.goto('/signals');
  await settle(page);
  await expect(page.getByRole('tab', { name: /for you/i })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('button', { name: /^Details for/ }).first().click();
  const sheet = page.getByRole('dialog');
  await expect(sheet.getByRole('heading', { name: 'What the model returned' })).toBeVisible();
  await expect(sheet.getByRole('heading', { name: 'Your preferences' })).toBeVisible();
  await expect(sheet.getByText('Set your account capital in Capital & risk to evaluate this.')).toBeVisible();
  await sheet.getByRole('link', { name: /size this trade/i }).click();
  await expect(page).toHaveURL(/\/risk\?.*origin=model/);
  await expect(page.getByText('Model plan (zone midpoints)')).toBeVisible();
});

test('assistant: labelled as a rule-based demo, answers from context, can be cleared', async ({ page }) => {
  await seedRisk(page, 10_000);
  await page.goto('/assistant?symbol=EURUSD&tf=4h');
  await settle(page);
  await expect(page.getByText('Rule-based demo').first()).toBeVisible();
  await expect(page.getByRole('list', { name: 'Data available to the assistant' })).toContainText('Model output (simulated)');
  await page.getByRole('button', { name: 'What information is missing before I can evaluate this?' }).click();
  const log = page.getByRole('log', { name: 'Conversation' });
  await expect(log.getByText('Prices are simulated.', { exact: false })).toBeVisible();
  await expect(log.getByText(/rule-based, not a language model/)).toBeVisible();
  await page.getByRole('button', { name: 'Clear conversation' }).click();
  await expect(log.getByText(/question the evidence/i)).toBeVisible();
  await expect(log.getByText(/rule-based, not a language model/)).toHaveCount(0);
});

test('workspace: AI panel lists invalidation and opens the assistant side sheet', async ({ page }) => {
  await page.goto('/workspace');
  await settle(page);
  await page.getByRole('button', { name: 'Ask the assistant about this analysis' }).click();
  const sheet = page.getByRole('dialog', { name: 'Assistant' });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole('list', { name: 'Data available to the assistant' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
});

test('register: password strength mirrors backend rules and visibility toggles', async ({ page }) => {
  await page.goto('/register');
  await settle(page);
  const pw = page.getByLabel('Password', { exact: true });
  await pw.fill('abcdefgh');
  await expect(page.getByText('Strength: Too weak')).toBeVisible();
  await pw.fill('abcdefg1');
  await expect(page.getByText('Strength: Acceptable')).toBeVisible();
  await expect(pw).toHaveAttribute('type', 'password');
  await page.getByRole('button', { name: 'Show password' }).first().click();
  await expect(pw).toHaveAttribute('type', 'text');
  await page.getByRole('link', { name: 'Sign in' }).first().click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('button', { name: 'Forgot password?' }).click();
  await expect(page.getByText(/no stored password/i)).toBeVisible();
});
