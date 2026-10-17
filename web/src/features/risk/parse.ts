/**
 * Parse a user-typed number. Accepts thousands separators ("2,350.5") and
 * surrounding spaces; rejects anything else (letters, two decimal points,
 * "1.2.3"). Empty input is `null` (= not entered), never 0.
 */
export function parseDecimal(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  const text = raw.trim().replace(/[\s,_]/g, '');
  if (text === '') return null;
  if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(text)) return Number.NaN;
  return Number(text);
}

/** Field-level message for a parsed value, or undefined when acceptable. */
export function numberError(value: number | null, opts: { required?: boolean; min?: number; max?: number; integer?: boolean; label: string }): string | undefined {
  if (value === null) return opts.required ? `Enter ${opts.label}.` : undefined;
  if (Number.isNaN(value)) return `Enter ${opts.label} as a number, e.g. 2350.5.`;
  if (opts.integer && !Number.isInteger(value)) return `Use a whole number for ${opts.label}.`;
  if (opts.min !== undefined && value < opts.min) return `${capitalise(opts.label)} must be at least ${opts.min}.`;
  if (opts.max !== undefined && value > opts.max) return `${capitalise(opts.label)} must be at most ${opts.max}.`;
  return undefined;
}

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Valid, finite and positive — usable in a calculation. */
export const usable = (v: number | null): v is number => v !== null && Number.isFinite(v) && v > 0;
