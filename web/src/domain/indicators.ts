/**
 * Technical indicators that are actually implemented (src/lib/indicators.ts).
 * SF5 — "globally recognised indicators". Custom indicator code (SF6) is
 * cancelled: this list is fixed in code and is never user-scriptable.
 */
export const INDICATOR_IDS = ['volume', 'sma20', 'ema50', 'bb20', 'rsi14'] as const;

export type IndicatorId = (typeof INDICATOR_IDS)[number];

export interface IndicatorDefinition {
  id: IndicatorId;
  label: string;
  description: string;
  /** 'price' overlays the main pane; 'separate' gets its own pane. */
  pane: 'price' | 'separate';
}

export const INDICATORS: readonly IndicatorDefinition[] = [
  { id: 'volume', label: 'Volume', description: 'Tick volume histogram', pane: 'price' },
  { id: 'sma20', label: 'SMA 20', description: 'Simple moving average, 20 periods', pane: 'price' },
  { id: 'ema50', label: 'EMA 50', description: 'Exponential moving average, 50 periods', pane: 'price' },
  { id: 'bb20', label: 'Bollinger Bands', description: '20 periods, 2 standard deviations', pane: 'price' },
  { id: 'rsi14', label: 'RSI 14', description: 'Relative strength index, separate pane', pane: 'separate' },
];

export function isIndicatorId(value: string): value is IndicatorId {
  return (INDICATOR_IDS as readonly string[]).includes(value);
}
