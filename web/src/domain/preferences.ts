import type { NotificationChannel } from './alerts';
import type { InstrumentSymbol } from './instruments';
import type { IndicatorId } from './indicators';
import type { ChartType, Timeframe } from './market';

export type ThemePreference = 'system' | 'dark' | 'light';
export type Density = 'comfortable' | 'compact';

/** 'local' resolves to the browser's zone; anything else is an IANA zone id. */
export type TimeZonePreference = 'UTC' | 'local' | string;

export const TIME_ZONE_OPTIONS: readonly { id: TimeZonePreference; label: string }[] = [
  { id: 'UTC', label: 'UTC (market data reference)' },
  { id: 'local', label: 'Browser local time' },
  { id: 'Asia/Damascus', label: 'Damascus' },
  { id: 'Europe/London', label: 'London' },
  { id: 'America/New_York', label: 'New York' },
  { id: 'Asia/Tokyo', label: 'Tokyo' },
  { id: 'Australia/Sydney', label: 'Sydney' },
];

/** SF18 — a saved analysis layout. */
export interface Workspace {
  id: string;
  name: string;
  symbol: InstrumentSymbol;
  timeframe: Timeframe;
  chartType: ChartType;
  indicators: IndicatorId[];
  showOpportunityOverlay: boolean;
  showForecast: boolean;
}

export interface ChannelSettings {
  app: { enabled: boolean };
  email: { enabled: boolean; address: string };
  telegram: { enabled: boolean; handle: string };
}

export interface Preferences {
  theme: ThemePreference;
  density: Density;
  timeZone: TimeZonePreference;
  channels: ChannelSettings;
  workspaces: Workspace[];
  activeWorkspaceId: string;
}

export function enabledChannels(channels: ChannelSettings): NotificationChannel[] {
  return (Object.keys(channels) as NotificationChannel[]).filter((c) => channels[c].enabled);
}
