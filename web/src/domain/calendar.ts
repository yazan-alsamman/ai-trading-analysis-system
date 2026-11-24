/**
 * Economic calendar (docs/economic-calendar.md): scheduled macro events from
 * ForexFactory, stored with their history ("point in time": every version with
 * the time it became known). ai-service abstains within ±30 minutes of a
 * high-impact event.
 */

export const EVENT_IMPACTS = ['holiday', 'low', 'medium', 'high'] as const;
export type EventImpact = (typeof EVENT_IMPACTS)[number];

export const IMPACT_LABELS: Record<EventImpact, string> = { holiday: 'Holiday', low: 'Low', medium: 'Medium', high: 'High' };

/** The server allows at most 31 days per request. */
export const CALENDAR_MAX_DAYS = 31;

/** Currencies of the instruments the platform covers (a filter preset, not a limit). */
export const CALENDAR_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD', 'CNY'] as const;

export interface CalendarEvent {
  /** Stable identity across versions. */
  key: string;
  /** UTC epoch ms; null for "All Day" or "Tentative". */
  scheduledAt: number | null;
  /** The event's day in New York (ForexFactory's day), YYYY-MM-DD. */
  scheduledDate: string;
  timeLabel: string | null;
  currency: string;
  impact: EventImpact;
  title: string;
  /** As published (e.g. "4.50%"). */
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  /** When this version became known. */
  fetchedAt: number;
  source: string;
}

export interface CalendarQuery {
  /** Epoch ms; the window is at most CALENDAR_MAX_DAYS long. */
  start: number;
  end: number;
  currencies?: readonly string[];
  minImpact?: EventImpact;
}

export interface CalendarResult {
  asOf: number;
  events: CalendarEvent[];
}
