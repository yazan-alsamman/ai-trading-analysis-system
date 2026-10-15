import { z } from 'zod';
import { INDICATOR_IDS } from '@/domain/indicators';
import type { Preferences, Workspace } from '@/domain/preferences';
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
  })
  .refine((p) => p.workspaces.some((w) => w.id === p.activeWorkspaceId), 'Active workspace must exist');

export function defaultWorkspace(id = 'ws-main', name = 'Main workspace'): Workspace {
  return {
    id,
    name,
    symbol: 'EURUSD',
    timeframe: '15m',
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
