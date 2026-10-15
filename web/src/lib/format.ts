/**
 * The ONLY place numbers, prices and times are turned into text.
 * Locale is fixed to en-US so that figures stay consistent across machines.
 */

export const MISSING = '—';
/** True minus sign (U+2212) — same width as "+" in tabular figures. */
export const MINUS = '−';

const numberFormatters = new Map<string, Intl.NumberFormat>();
function numberFormat(minDigits: number, maxDigits: number, compact = false): Intl.NumberFormat {
  const key = `${minDigits}:${maxDigits}:${compact}`;
  let f = numberFormatters.get(key);
  if (!f) {
    f = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: minDigits,
      maximumFractionDigits: maxDigits,
      ...(compact ? { notation: 'compact' as const } : {}),
    });
    numberFormatters.set(key, f);
  }
  return f;
}

const isFiniteNumber = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

function withSign(text: string, value: number): string {
  if (value > 0) return `+${text}`;
  if (value < 0) return `${MINUS}${text}`;
  return text;
}

/** Price at the instrument's precision, e.g. 1.08214 or 2,345.67. */
export function formatPrice(value: number | null | undefined, precision: number): string {
  if (!isFiniteNumber(value)) return MISSING;
  return numberFormat(precision, precision).format(value);
}

/** Signed price difference, e.g. "+0.00087" / "−0.00087". */
export function formatPriceChange(delta: number | null | undefined, precision: number): string {
  if (!isFiniteNumber(delta)) return MISSING;
  const rounded = Number(delta.toFixed(precision));
  return withSign(numberFormat(precision, precision).format(Math.abs(rounded)), rounded);
}

/** Signed percentage from a ratio: 0.0042 → "+0.42%". */
export function formatPercentChange(ratio: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(ratio)) return MISSING;
  const pct = Number((ratio * 100).toFixed(digits));
  return `${withSign(numberFormat(digits, digits).format(Math.abs(pct)), pct)}%`;
}

/** Unsigned percentage from a ratio: 0.683 → "68%" (probabilities, rates). */
export function formatPercent(ratio: number | null | undefined, digits = 0): string {
  if (!isFiniteNumber(ratio)) return MISSING;
  return `${numberFormat(digits, digits).format(ratio * 100)}%`;
}

/** Probability band, e.g. "61–74%". */
export function formatProbabilityBand(band: { low: number; high: number } | undefined): string {
  if (!band) return MISSING;
  return `${numberFormat(0, 0).format(band.low * 100)}–${numberFormat(0, 0).format(band.high * 100)}%`;
}

/** Distance in pips: 0.00124 with pipSize 0.0001 → "12.4 pips". */
export function formatPips(distance: number | null | undefined, pipSize: number): string {
  if (!isFiniteNumber(distance)) return MISSING;
  const pips = Math.abs(distance) / pipSize;
  return `${numberFormat(1, 1).format(pips)} pips`;
}

/** Expected value / realised result in R multiples: "+0.36R". */
export function formatR(value: number | null | undefined, digits = 2): string {
  if (!isFiniteNumber(value)) return MISSING;
  const rounded = Number(value.toFixed(digits));
  return `${withSign(numberFormat(digits, digits).format(Math.abs(rounded)), rounded)}R`;
}

/** Reward-to-risk: 2 → "1 : 2.0". */
export function formatRiskReward(rr: number | null | undefined): string {
  if (!isFiniteNumber(rr)) return MISSING;
  return `1 : ${numberFormat(1, 1).format(rr)}`;
}

/** Compact counts: 1234 → "1.2K". */
export function formatCompact(value: number | null | undefined): string {
  if (!isFiniteNumber(value)) return MISSING;
  return numberFormat(0, 1, true).format(value);
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (!isFiniteNumber(value)) return MISSING;
  return numberFormat(digits, digits).format(value);
}

/* ------------------------------------------------------------------ time */

/** 'local' → browser zone; otherwise the IANA id itself. */
export function resolveTimeZone(pref: string): string {
  if (pref === 'local') return Intl.DateTimeFormat().resolvedOptions().timeZone;
  return pref;
}

const dateFormatters = new Map<string, Intl.DateTimeFormat>();
function dateFormat(timeZone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${timeZone}|${JSON.stringify(options)}`;
  let f = dateFormatters.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat('en-GB', { timeZone, hourCycle: 'h23', ...options });
    dateFormatters.set(key, f);
  }
  return f;
}

/** Short zone label: "UTC", "GMT+3". */
export function timeZoneLabel(timeZone: string, at = Date.now()): string {
  if (timeZone === 'UTC') return 'UTC';
  const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'shortOffset' })
    .formatToParts(at)
    .find((p) => p.type === 'timeZoneName');
  return part?.value ?? timeZone;
}

/** "14:30:05" in the chosen zone. */
export function formatClock(epochMs: number | null | undefined, timeZone: string, seconds = true): string {
  if (!isFiniteNumber(epochMs)) return MISSING;
  return dateFormat(timeZone, { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}) }).format(epochMs);
}

/** "15 Oct 14:30" in the chosen zone. */
export function formatDateTime(epochMs: number | null | undefined, timeZone: string): string {
  if (!isFiniteNumber(epochMs)) return MISSING;
  return dateFormat(timeZone, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(epochMs);
}

/** "15 Oct 2026" in the chosen zone. */
export function formatDate(epochMs: number | null | undefined, timeZone: string): string {
  if (!isFiniteNumber(epochMs)) return MISSING;
  return dateFormat(timeZone, { day: '2-digit', month: 'short', year: 'numeric' }).format(epochMs);
}

/** "just now", "42s ago", "5m ago", "3h ago", "2d ago". */
export function formatRelative(epochMs: number | null | undefined, nowMs: number = Date.now()): string {
  if (!isFiniteNumber(epochMs)) return MISSING;
  const s = Math.round((nowMs - epochMs) / 1000);
  if (s < 0) return 'in the future';
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Direction of a change, used to choose the up/down token AND the arrow. */
export type Trend = 'up' | 'down' | 'flat';
export function trendOf(delta: number | null | undefined): Trend {
  if (!isFiniteNumber(delta) || delta === 0) return 'flat';
  return delta > 0 ? 'up' : 'down';
}
