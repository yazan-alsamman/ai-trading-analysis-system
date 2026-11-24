/**
 * 1-minute candle CSV for POST /admin/instruments/{id}/candles (max 5,000 per
 * request). Header: ts,open,high,low,close,volume[,spread,source]; `ts` is ISO
 * 8601 UTC. Every row is checked before anything is sent.
 */

export const MAX_CANDLES = 5000;

export interface ParsedCandles {
  candles: Record<string, unknown>[];
  errors: string[];
}

export function parseCandleCsv(text: string): ParsedCandles {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const errors: string[] = [];
  if (lines.length < 2) return { candles: [], errors: ['Paste a header line and at least one candle.'] };
  const header = (lines[0] ?? '').split(',').map((h) => h.trim().toLowerCase());
  for (const need of ['ts', 'open', 'high', 'low', 'close', 'volume']) if (!header.includes(need)) errors.push(`Missing column “${need}”.`);
  if (errors.length) return { candles: [], errors };
  const col = (name: string) => header.indexOf(name);
  const rows = lines.slice(1);
  if (rows.length > MAX_CANDLES) return { candles: [], errors: [`${rows.length} rows: at most ${MAX_CANDLES} per upload.`] };

  const candles: Record<string, unknown>[] = [];
  rows.forEach((line, i) => {
    const cells = line.split(',').map((c) => c.trim());
    const at = (name: string) => (col(name) >= 0 ? (cells[col(name)] ?? '') : '');
    const n = (name: string) => Number(at(name));
    const ts = at('ts');
    const [open, high, low, close, volume] = [n('open'), n('high'), n('low'), n('close'), n('volume')];
    const where = `Line ${i + 2}`;
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})$/.test(ts) || !Number.isFinite(Date.parse(ts))) {
      errors.push(`${where}: ts must be ISO 8601 with a time zone (e.g. 2026-10-26T14:31:00Z).`);
      return;
    }
    if (![open, high, low, close, volume].every(Number.isFinite) || volume < 0) {
      errors.push(`${where}: open, high, low, close and volume must be numbers (volume ≥ 0).`);
      return;
    }
    if (high < Math.max(open, close) || low > Math.min(open, close) || low > high) {
      errors.push(`${where}: high must be ≥ open/close and low ≤ open/close.`);
      return;
    }
    const candle: Record<string, unknown> = { ts, open, high, low, close, volume };
    const spread = at('spread');
    if (spread !== '') {
      const s = Number(spread);
      if (!Number.isFinite(s) || s < 0) {
        errors.push(`${where}: spread must be a number ≥ 0.`);
        return;
      }
      candle.spread = s;
    }
    const source = at('source');
    if (source !== '') candle.source = source;
    candles.push(candle);
  });
  return { candles: errors.length ? [] : candles, errors: errors.slice(0, 10).concat(errors.length > 10 ? [`…and ${errors.length - 10} more problems.`] : []) };
}

/** Numeric spec fields of an instrument (docs/instruments.md) and their limits. */
export const NUMERIC_SPECS: readonly { key: string; label: string; hint: string; min?: number; max?: number }[] = [
  { key: 'contract_size', label: 'Contract size', hint: 'Units per 1.0 lot (XAU/USD 100 oz, FX 100,000)' },
  { key: 'tick_size', label: 'Tick size', hint: 'Minimum price increment' },
  { key: 'lot_step', label: 'Lot step', hint: 'Volume step in lots' },
  { key: 'min_lot', label: 'Minimum lot', hint: '' },
  { key: 'max_lot', label: 'Maximum lot', hint: '' },
  { key: 'margin_rate', label: 'Margin rate', hint: 'Fraction of notional at 1:1 (0.01 = 1:100); empty = the user’s leverage', max: 1 },
  { key: 'cost_per_unit', label: 'Cost per unit', hint: 'Fixed round-trip cost per unit, price units (XAU/USD 0.25)', min: 0 },
];
