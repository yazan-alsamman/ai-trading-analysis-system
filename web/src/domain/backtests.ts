import type { BackendTimeframe, ChartMarker, StrategyParams } from './strategies';

/**
 * Backtests run by the backend engine (libs/backtest, docs/backtesting.md):
 * a strategy replayed over HISTORICAL candles with fees and slippage. Results
 * describe the past on the backend's data; they are not a forecast and not a
 * promise of future returns.
 */

export type BacktestStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface BacktestInstrument {
  id: string;
  symbol: string;
  source: string;
}

/** Headline metrics (always a subset of `BacktestMetrics`). Values are as the server computed them. */
export type BacktestMetrics = Record<string, unknown>;

export interface BacktestSummary {
  id: string;
  status: BacktestStatus;
  /** 0–100 (5 started, 30 candles loaded, 80 computed, 100 saved). */
  progress: number;
  instrument: BacktestInstrument;
  timeframe: BackendTimeframe;
  strategyKey: string;
  params: StrategyParams;
  start: number;
  end: number;
  bars: number | null;
  error: string | null;
  headline: BacktestMetrics | null;
  createdAt: number;
  finishedAt: number | null;
}

export interface Point {
  time: number;
  value: number;
}

export interface BacktestResult extends BacktestSummary {
  config: Record<string, unknown>;
  firstBar: number | null;
  lastBar: number | null;
  metrics: BacktestMetrics | null;
  equity: Point[];
  drawdown: Point[];
  markers: ChartMarker[];
  durationMs: number | null;
}

export interface BacktestTrade {
  number: number;
  side: string;
  entryTime: number;
  entryPrice: number;
  exitTime: number;
  exitPrice: number;
  quantity: number;
  grossPnl: number;
  fees: number;
  netPnl: number;
  returnPct: number;
  barsHeld: number;
  entryReason: string | null;
  exitReason: string;
  initialStop: number | null;
  riskAmount: number | null;
  rMultiple: number | null;
}

export interface BacktestInput {
  instrumentId: string;
  timeframe: BackendTimeframe;
  strategyKey: string;
  params: StrategyParams;
  /** ISO 8601 (UTC). */
  start: string;
  end: string;
  /** Engine configuration (docs/backtesting.md); omitted fields take the server defaults. */
  config: Record<string, unknown> | null;
}

export interface BacktestComparison {
  items: {
    id: string;
    instrument: BacktestInstrument;
    timeframe: string;
    strategyKey: string;
    params: StrategyParams;
    start: number;
    end: number;
    metrics: BacktestMetrics;
    /** Equity normalised to 100 at the start. */
    equity: Point[];
  }[];
}

/** A progress event pushed on the user's WebSocket topic. */
export interface BacktestProgressEvent {
  backtestId: string;
  status: BacktestStatus;
  progress: number;
  error: string | null;
}

export const ACTIVE_BACKTEST_STATUSES: readonly BacktestStatus[] = ['queued', 'running'];

/** The metrics shown on a results page, with their meaning (docs/backtesting.md). */
export const METRIC_LABELS: readonly { key: string; label: string; kind: 'pct' | 'number' | 'money' | 'int' | 'ratio'; hint: string }[] = [
  { key: 'total_return_pct', label: 'Total return', kind: 'pct', hint: 'Final equity vs initial capital, after fees and slippage' },
  { key: 'buy_and_hold_return_pct', label: 'Buy & hold', kind: 'pct', hint: 'Holding from the first window bar’s open to the last close' },
  { key: 'cagr_pct', label: 'CAGR', kind: 'pct', hint: 'Compound annual growth rate over the window' },
  { key: 'max_drawdown_pct', label: 'Max drawdown', kind: 'pct', hint: 'Largest peak-to-trough fall of equity' },
  { key: 'sharpe', label: 'Sharpe', kind: 'ratio', hint: 'Annualised from per-bar returns, risk-free rate 0' },
  { key: 'sortino', label: 'Sortino', kind: 'ratio', hint: 'Like Sharpe, penalising only downside returns' },
  { key: 'calmar', label: 'Calmar', kind: 'ratio', hint: 'CAGR divided by the maximum drawdown' },
  { key: 'trades', label: 'Trades', kind: 'int', hint: 'Closed trades in the window' },
  { key: 'win_rate_pct', label: 'Win rate', kind: 'pct', hint: 'Share of trades with a positive net result' },
  { key: 'profit_factor', label: 'Profit factor', kind: 'ratio', hint: 'Gross wins divided by gross losses' },
  { key: 'expectancy', label: 'Expectancy', kind: 'money', hint: 'Average net result per trade' },
  { key: 'avg_win', label: 'Average win', kind: 'money', hint: 'Average net result of winning trades' },
  { key: 'avg_loss', label: 'Average loss', kind: 'money', hint: 'Average net result of losing trades' },
  { key: 'best_trade_pct', label: 'Best trade', kind: 'pct', hint: 'Best single-trade return' },
  { key: 'worst_trade_pct', label: 'Worst trade', kind: 'pct', hint: 'Worst single-trade return' },
  { key: 'avg_bars_held', label: 'Avg bars held', kind: 'number', hint: 'Average trade length in bars' },
  { key: 'exposure_pct', label: 'Exposure', kind: 'pct', hint: 'Share of bars with an open position' },
  { key: 'total_fees', label: 'Fees paid', kind: 'money', hint: 'Sum of fees on every fill' },
  { key: 'final_equity', label: 'Final equity', kind: 'money', hint: 'Equity at the last bar' },
  { key: 'avg_r', label: 'Average R', kind: 'ratio', hint: 'Average result in multiples of the initial risk (with a stop)' },
  { key: 'max_consecutive_losses', label: 'Max losing streak', kind: 'int', hint: 'Longest run of losing trades' },
];

export function metricNumber(metrics: BacktestMetrics | null | undefined, key: string): number | null {
  const v = metrics?.[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}
