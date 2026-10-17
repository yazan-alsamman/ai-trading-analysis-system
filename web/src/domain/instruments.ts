/**
 * Supported instruments (Feature 12 specification, §3.1).
 *
 * `pricePrecision` and `pipSize` follow common FX conventions. They are the
 * client-side default until the backend exposes instrument metadata
 * (see docs/API_INTEGRATION.md → GET /instruments).
 */
export const INSTRUMENT_SYMBOLS = [
  'EURUSD',
  'GBPUSD',
  'USDJPY',
  'USDCHF',
  'AUDUSD',
  'USDCAD',
  'NZDUSD',
  'XAUUSD',
] as const;

export type InstrumentSymbol = (typeof INSTRUMENT_SYMBOLS)[number];

export interface Instrument {
  symbol: InstrumentSymbol;
  /** Display form, e.g. "EUR/USD". */
  display: string;
  name: string;
  base: string;
  quote: string;
  kind: 'fx' | 'metal';
  /** Decimal places shown for prices. */
  pricePrecision: number;
  /** Price increment that equals one pip. */
  pipSize: number;
}

const fx = (symbol: InstrumentSymbol, name: string, precision = 5): Instrument => ({
  symbol,
  display: `${symbol.slice(0, 3)}/${symbol.slice(3)}`,
  name,
  base: symbol.slice(0, 3),
  quote: symbol.slice(3),
  kind: 'fx',
  pricePrecision: precision,
  pipSize: precision === 3 ? 0.01 : 0.0001,
});

export const INSTRUMENTS: readonly Instrument[] = [
  fx('EURUSD', 'Euro / US Dollar'),
  fx('GBPUSD', 'British Pound / US Dollar'),
  fx('USDJPY', 'US Dollar / Japanese Yen', 3),
  fx('USDCHF', 'US Dollar / Swiss Franc'),
  fx('AUDUSD', 'Australian Dollar / US Dollar'),
  fx('USDCAD', 'US Dollar / Canadian Dollar'),
  fx('NZDUSD', 'New Zealand Dollar / US Dollar'),
  {
    symbol: 'XAUUSD',
    display: 'XAU/USD',
    name: 'Gold / US Dollar',
    base: 'XAU',
    quote: 'USD',
    kind: 'metal',
    pricePrecision: 2,
    pipSize: 0.1,
  },
];

const BY_SYMBOL = new Map(INSTRUMENTS.map((i) => [i.symbol, i]));

export function isInstrumentSymbol(value: string): value is InstrumentSymbol {
  return BY_SYMBOL.has(value as InstrumentSymbol);
}

export function getInstrument(symbol: InstrumentSymbol): Instrument {
  const instrument = BY_SYMBOL.get(symbol);
  if (!instrument) throw new Error(`Unknown instrument: ${symbol}`);
  return instrument;
}

/** Case-insensitive match on symbol ("eurusd", "eur/usd") or name. */
export function matchesInstrument(instrument: Instrument, query: string): boolean {
  const q = query.trim().toLowerCase().replace(/[\s/]/g, '');
  if (!q) return true;
  return (
    instrument.symbol.toLowerCase().includes(q) ||
    instrument.name.toLowerCase().replace(/[\s/]/g, '').includes(q)
  );
}
