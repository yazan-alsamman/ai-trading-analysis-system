import type { InstrumentSymbol } from './instruments';

/**
 * A signal from the backend's rule-based STRATEGY ENGINE (GET /api/v1/signals),
 * e.g. an RSI reversal or a moving-average cross. It is NOT the AI model's
 * output: it has a side, a price and a rule-specific strength, but no
 * probability, no entry/stop/target zones and no forecast.
 */
export interface StrategySignal {
  id: string;
  /** Web-client symbol, or null when the instrument is not one the web client supports. */
  symbol: InstrumentSymbol | null;
  /** The backend's symbol, e.g. "XAU/USD" or "BTC/USDT". */
  instrumentLabel: string;
  timeframe: string;
  strategyKey: string;
  side: 'buy' | 'sell';
  /** Strategy-specific, 0–1 scale where the strategy defines one. Not a probability. */
  strength: number;
  /** Price of the bar that produced the signal. */
  price: number;
  /** Machine reason code, e.g. `rsi_cross_down_overbought`. */
  reason: string;
  details: Record<string, unknown>;
  /** Bar time, epoch seconds. */
  time: number;
  createdAt: number;
}

/** The backend's built-in strategy catalogue (GET /strategies, libs/strategies). */
const STRATEGY_NAMES: Record<string, string> = {
  ma_crossover: 'Moving-average crossover',
  rsi_reversal: 'RSI reversal',
  macd_cross: 'MACD cross',
  bollinger_reversion: 'Bollinger reversion',
  supertrend_flip: 'Supertrend flip',
  donchian_breakout: 'Donchian breakout',
};

/** "rsi_reversal" → "RSI reversal"; unknown keys are humanised, not invented. */
export function strategyName(key: string): string {
  return STRATEGY_NAMES[key] ?? key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

/** "rsi_cross_down_overbought" → "RSI cross down overbought". */
export function reasonText(reason: string): string {
  return reason
    .split('_')
    .map((w, i) => (/^(rsi|ma|ema|sma|macd|atr)$/.test(w) ? w.toUpperCase() : i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(' ');
}
