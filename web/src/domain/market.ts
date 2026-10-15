import type { InstrumentSymbol } from './instruments';

/** Timeframes from the Feature 12 spec: 15m primary, 1h confirmation, 4h regime. */
export const TIMEFRAMES = [
  { id: '15m', label: '15m', seconds: 15 * 60, description: 'Primary — opportunity detection' },
  { id: '1h', label: '1h', seconds: 60 * 60, description: 'Confirmation' },
  { id: '4h', label: '4h', seconds: 4 * 60 * 60, description: 'Market regime / trend context' },
] as const;

export type Timeframe = (typeof TIMEFRAMES)[number]['id'];

export function timeframeSeconds(tf: Timeframe): number {
  const found = TIMEFRAMES.find((t) => t.id === tf);
  if (!found) throw new Error(`Unknown timeframe: ${tf}`);
  return found.seconds;
}

export function isTimeframe(value: string): value is Timeframe {
  return TIMEFRAMES.some((t) => t.id === value);
}

/**
 * Where a value came from. Every data object carries this so the UI can label
 * simulated content and never present it as live market data.
 */
export type Provenance = 'demo' | 'live';

/** One OHLCV bar. `time` is the bar OPEN time in UTC epoch seconds. */
export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** FX has no central volume; most feeds supply tick volume. */
export type VolumeKind = 'tick' | 'real';

export interface CandleSeries {
  symbol: InstrumentSymbol;
  timeframe: Timeframe;
  candles: Candle[];
  volumeKind: VolumeKind;
  provenance: Provenance;
  /** When the series was produced (epoch ms). */
  asOf: number;
}

export interface Quote {
  symbol: InstrumentSymbol;
  price: number;
  /** Reference price 24h earlier, used for the change figures. */
  reference: number;
  /** Epoch ms of the last price update. */
  time: number;
  provenance: Provenance;
}

export type ChartType = 'candles' | 'bars' | 'line' | 'area';

export const CHART_TYPES: readonly { id: ChartType; label: string }[] = [
  { id: 'candles', label: 'Candles' },
  { id: 'bars', label: 'OHLC bars' },
  { id: 'line', label: 'Line' },
  { id: 'area', label: 'Area' },
];

/**
 * Connection state of a price stream.
 *  - live: real-time data from the backend
 *  - demo: simulated stream (never shown as "Live")
 *  - delayed: updates arrive but late
 *  - stale: no update within the freshness window
 *  - closed: FX market closed (weekend)
 *  - offline: browser has no network
 *  - error: stream failed
 */
export type FeedStatus = 'connecting' | 'live' | 'demo' | 'delayed' | 'stale' | 'closed' | 'offline' | 'error';

/**
 * FX trades from Sunday 22:00 UTC to Friday 22:00 UTC.
 * Daylight-saving shifts of the real session are ignored here.
 */
export function isFxMarketOpen(epochSeconds: number): boolean {
  const d = new Date(epochSeconds * 1000);
  const day = d.getUTCDay();
  const hour = d.getUTCHours();
  if (day === 6) return false;
  if (day === 5 && hour >= 22) return false;
  if (day === 0 && hour < 22) return false;
  return true;
}

/** Floor a timestamp (seconds) to the start of its timeframe bucket. */
export function bucketStart(epochSeconds: number, tf: Timeframe): number {
  const size = timeframeSeconds(tf);
  return Math.floor(epochSeconds / size) * size;
}
