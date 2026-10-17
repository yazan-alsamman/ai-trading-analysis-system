import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { getInstrument } from '@/domain/instruments';
import type { Opportunity } from '@/domain/opportunity';
import type { Resource } from '@/hooks/useResource';
import { AppShell } from '@/layouts/AppShell';
import { ApiError } from '@/services/errors';
import { renderWithProviders } from '@/test/render';
import { AlertsPage } from './alerts/AlertsPage';
import { OpportunityPanel } from './opportunity/OpportunityPanel';

const NOW = Date.parse('2026-10-15T12:00:00Z');

const opportunity: Opportunity = {
  id: 'o1',
  symbol: 'EURUSD',
  timeframe: '15m',
  status: 'detected',
  direction: 'long',
  setupType: 'trend_following',
  riskLevel: 'medium',
  probability: 0.68,
  confidenceBand: { low: 0.61, high: 0.74 },
  entryZone: { low: 1.0849, high: 1.0851 },
  stopLossZone: { low: 1.083, high: 1.0832 },
  takeProfitZone: { low: 1.0888, high: 1.089 },
  riskReward: 2,
  expectedValueR: 1.04,
  factors: [{ id: 'f', label: 'EMA 20 above EMA 50', detail: 'Spread 0.8 ATR', contribution: 0.2 }],
  horizonCandles: 20,
  signalCandleTime: NOW / 1000 - 900,
  generatedAt: NOW - 60_000,
  validUntil: NOW + 600_000,
  modelVersion: 'demo-heuristic-0.1',
  provenance: 'demo',
};

const resource = (patch: Partial<Resource<Opportunity>>): Resource<Opportunity> => ({
  status: 'success',
  data: opportunity,
  error: undefined,
  isRefreshing: false,
  reload: vi.fn(),
  setData: vi.fn(),
  ...patch,
});

function renderPanel(res: Resource<Opportunity>, now = NOW) {
  return renderWithProviders(
    <OpportunityPanel resource={res} instrument={getInstrument('EURUSD')} timeframe="15m" currentPrice={1.085} timeZone="UTC" now={now} />,
  );
}

describe('OpportunityPanel', () => {
  it('shows probability, band, levels, provenance and the no-guarantee disclosure', () => {
    renderPanel(resource({}));
    expect(screen.getByText('Opportunity detected')).toBeInTheDocument();
    expect(screen.getByText('68%')).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: /probability 68%, confidence band 61–74%/i })).toBeInTheDocument();
    expect(screen.getByText('1.08490 – 1.08510')).toBeInTheDocument();
    expect(screen.getByText('Trade plan')).toBeInTheDocument();
    expect(screen.getByText(/not a guarantee of profit/i)).toBeInTheDocument();
    expect(screen.getAllByText('Simulated').length).toBeGreaterThan(0);
    expect(screen.getByText(/not SHAP output/i)).toBeInTheDocument();
  });

  it('does not suggest levels when no opportunity is detected', () => {
    renderPanel(resource({ data: { ...opportunity, status: 'not_detected', direction: 'neutral' } }));
    expect(screen.getByText('No opportunity')).toBeInTheDocument();
    expect(screen.queryByText('Take-profit zone')).not.toBeInTheDocument();
  });

  it('warns when the analysis is stale', () => {
    renderPanel(resource({}), opportunity.validUntil + 1);
    expect(screen.getByText(/older than its validity window/i)).toBeInTheDocument();
  });

  it('shows a plain-language error with retry instead of an endless spinner', async () => {
    const reload = vi.fn();
    renderPanel(resource({ status: 'error', data: undefined, error: new ApiError('network', 'x'), reload }));
    expect(screen.getByRole('alert')).toHaveTextContent(/could not reach the server/i);
    await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(reload).toHaveBeenCalled();
  });
});

describe('Alerts flow (demo services)', () => {
  it('validates, creates and deletes a price alert', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AlertsPage />);

    // Seeded example alerts load.
    expect(await screen.findByText('Crosses above', {}, { timeout: 3000 })).toBeInTheDocument();
    const before = screen.getAllByRole('row').length;

    await user.click(screen.getByRole('button', { name: /new price alert/i }));
    const dialog = await screen.findByRole('dialog', { name: /new price alert/i });

    // The hint shows the current (simulated) price; read it before an error replaces the hint.
    const hint = await within(dialog).findByText(/current eur\/usd/i, {}, { timeout: 3000 });
    const current = Number(hint.textContent?.match(/(\d+\.\d+)/)?.[1]);
    expect(current).toBeGreaterThan(0);

    await user.click(within(dialog).getByRole('button', { name: /create alert/i }));
    expect(await within(dialog).findByText(/enter a price level/i)).toBeInTheDocument();

    await user.clear(within(dialog).getByLabelText(/price level/i));
    await user.type(within(dialog).getByLabelText(/price level/i), (current + 0.005).toFixed(5));
    await user.click(within(dialog).getByRole('button', { name: /create alert/i }));

    await waitFor(() => expect(screen.getAllByRole('row').length).toBe(before + 1), { timeout: 3000 });

    // Delete requires confirmation.
    await user.click(screen.getAllByRole('button', { name: /delete alert for eur\/usd/i })[0]!);
    const confirm = await screen.findByRole('dialog', { name: /delete price alert/i });
    await user.click(within(confirm).getByRole('button', { name: /delete alert/i }));
    await waitFor(() => expect(screen.getAllByRole('row').length).toBe(before), { timeout: 3000 });
  }, 15_000);
});

describe('Application shell', () => {
  it('labels demo mode and exposes primary navigation', () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<p>content</p>} />
        </Route>
      </Routes>,
    );
    expect(screen.getByText(/prices, ai opportunities and statistics are simulated/i)).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    for (const label of ['Workspace', 'Signals', 'Alerts', 'Insights', 'Community', 'Settings']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole('link', { name: /skip to main content/i })).toBeInTheDocument();
  });

  it('never offers order execution controls (cancelled AI 13/19, SF1)', () => {
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<p>content</p>} />
        </Route>
      </Routes>,
    );
    expect(screen.queryByRole('button', { name: /buy|sell|place order|close trade|execute/i })).not.toBeInTheDocument();
  });
});
