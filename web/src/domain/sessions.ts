import { isFxMarketOpen } from './market';

/**
 * Major FX trading sessions in UTC (standard-time approximation; DST shifts of
 * ±1h are not modelled — see docs/KNOWN_ISSUES.md).
 */
export const FX_SESSIONS = [
  { id: 'sydney', label: 'Sydney', openUtc: 22, closeUtc: 7 },
  { id: 'tokyo', label: 'Tokyo', openUtc: 0, closeUtc: 9 },
  { id: 'london', label: 'London', openUtc: 8, closeUtc: 17 },
  { id: 'newyork', label: 'New York', openUtc: 13, closeUtc: 22 },
] as const;

export type SessionId = (typeof FX_SESSIONS)[number]['id'];

function withinHours(hour: number, open: number, close: number): boolean {
  return open < close ? hour >= open && hour < close : hour >= open || hour < close;
}

export interface SessionState {
  id: SessionId;
  label: string;
  open: boolean;
}

/** Which sessions are open at a moment (all closed over the weekend). */
export function sessionStates(epochMs: number): SessionState[] {
  const marketOpen = isFxMarketOpen(Math.floor(epochMs / 1000));
  const hour = new Date(epochMs).getUTCHours();
  return FX_SESSIONS.map((s) => ({ id: s.id, label: s.label, open: marketOpen && withinHours(hour, s.openUtc, s.closeUtc) }));
}

/** Short description of current market conditions, e.g. "London · New York overlap". */
export function sessionSummary(epochMs: number): string {
  if (!isFxMarketOpen(Math.floor(epochMs / 1000))) return 'Market closed (weekend)';
  const open = sessionStates(epochMs).filter((s) => s.open);
  if (open.length === 0) return 'Between sessions';
  if (open.length === 1) return `${open[0]?.label} session`;
  return `${open.map((s) => s.label).join(' · ')} overlap`;
}
