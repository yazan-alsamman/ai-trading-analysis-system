import { z } from 'zod';
import { INDICATOR_IDS } from '@/domain/indicators';
import { INSTRUMENT_SYMBOLS } from '@/domain/instruments';
import type { Preferences, Workspace } from '@/domain/preferences';
import { ACCOUNT_CURRENCIES, DEFAULT_RISK_PROFILE } from '@/domain/risk';
import { DEFAULT_SIGNAL_PROFILE } from '@/domain/signalProfile';
import { SymbolSchema, TimeframeSchema } from '@/services/schemas';

export const PREFERENCES_KEY = 'ata.preferences.v1';

const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(40),
  symbol: SymbolSchema,
  timeframe: TimeframeSchema,
  chartType: z.enum(['candles', 'bars', 'line', 'area']),
  indicators: z.array(z.enum(INDICATOR_IDS)),
  showOpportunityOverlay: z.boolean(),
  showForecast: z.boolean(),
});

const finite = z.number().refine(Number.isFinite);

export const RiskProfileSchema = z.object({
  capital: finite.positive().nullable(),
  currency: z.enum(ACCOUNT_CURRENCIES),
  maxRiskPerTradePct: finite.positive().max(100),
  dailyLossLimitPct: finite.positive().max(100),
  maxOpenRiskPct: finite.positive().max(100),
  maxOpenPositions: z.number().int().min(1).max(50),
  openRisk: finite.min(0),
  realisedLossToday: finite.min(0),
  openPositions: z.number().int().min(0),
  contractSizes: z.partialRecord(z.enum(INSTRUMENT_SYMBOLS), finite.positive()),
  volumeStep: finite.positive().nullable(),
});

export const SignalProfileSchema = z.object({
  symbols: z.array(SymbolSchema).min(1),
  timeframes: z.array(TimeframeSchema).min(1),
  directions: z.array(z.enum(['long', 'short'])).min(1),
  minProbability: z.number().min(0).max(0.99),
  minRiskReward: z.number().min(0).max(20),
  requireRiskFit: z.boolean(),
});

export const PreferencesSchema = z
  .object({
    theme: z.enum(['system', 'dark', 'light']),
    density: z.enum(['comfortable', 'compact']),
    timeZone: z.string().min(1),
    channels: z.object({
      app: z.object({ enabled: z.boolean() }),
      email: z.object({ enabled: z.boolean(), address: z.string() }),
      telegram: z.object({ enabled: z.boolean(), handle: z.string() }),
    }),
    workspaces: z.array(WorkspaceSchema).min(1),
    activeWorkspaceId: z.string(),
    // Added in round 3. Defaults keep older stored preferences (and their workspaces) valid.
    riskProfile: RiskProfileSchema.default(DEFAULT_RISK_PROFILE),
    signalProfile: SignalProfileSchema.default(DEFAULT_SIGNAL_PROFILE),
  })
  .refine((p) => p.workspaces.some((w) => w.id === p.activeWorkspaceId), 'Active workspace must exist');

export function defaultWorkspace(id = 'ws-main', name = 'Main workspace'): Workspace {
  return {
    id,
    name,
    // Gold first: the platform's initial research focus.
    symbol: 'XAUUSD',
    timeframe: '1h',
    chartType: 'candles',
    indicators: ['volume', 'ema50'],
    showOpportunityOverlay: true,
    showForecast: true,
  };
}

export const DEFAULT_PREFERENCES: Preferences = {
  theme: 'system',
  density: 'comfortable',
  timeZone: 'UTC',
  channels: {
    app: { enabled: true },
    email: { enabled: false, address: '' },
    telegram: { enabled: false, handle: '' },
  },
  workspaces: [defaultWorkspace()],
  activeWorkspaceId: 'ws-main',
  riskProfile: DEFAULT_RISK_PROFILE,
  signalProfile: DEFAULT_SIGNAL_PROFILE,
};

/** Validate that a stored zone id is usable by Intl. */
export function isSupportedTimeZone(tz: string): boolean {
  if (tz === 'local' || tz === 'UTC') return true;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}
