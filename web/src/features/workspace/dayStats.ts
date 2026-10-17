import type { Candle, Quote } from '@/domain/market';

/**
 * 24h figures. Price and change come from the quote (shared with the
 * watchlist); the high/low range comes from candles of the last 24 hours.
 */
export function dayStats(candles: readonly Candle[], quote: Quote | undefined) {
  const last = candles[candles.length - 1];
  if (!last) return null;
  const from = last.time - 24 * 3600;
  let i = candles.length - 1;
  while (i > 0 && (candles[i - 1]?.time ?? 0) > from) i--;
  const window = candles.slice(i);
  const price = quote?.price ?? last.close;
  const reference = quote?.reference ?? window[0]?.open ?? last.open;
  return {
    price,
    change: price - reference,
    changeRatio: (price - reference) / reference,
    high: Math.max(...window.map((c) => c.high)),
    low: Math.min(...window.map((c) => c.low)),
  };
}
