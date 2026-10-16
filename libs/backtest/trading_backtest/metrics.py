"""Performance metrics and equity-curve downsampling.

Formulas (``E_0`` = initial capital, ``E_1..E_n`` = equity at each bar close of the window,
``P`` = bars per year):

* per-bar returns ``r_i = E_i / E_(i-1) - 1`` (``r_1`` against ``E_0``);
* ``total_return_pct = (E_n / E_0 - 1) * 100``; ``CAGR = (E_n / E_0) ** (P / n) - 1`` (None
  if it overflows, e.g. a few hours annualized);
* ``sharpe = mean(r) / std(r, ddof=1) * sqrt(P)`` (risk-free rate 0);
* ``sortino = mean(r) / sqrt(mean(min(r, 0) ** 2)) * sqrt(P)`` (target 0, all periods);
* drawdown ``DD_i = E_i / max(E_0..E_i) - 1``; ``max_drawdown_pct = min(DD) * 100``, from the
  peak before the trough (``max_drawdown_start``) to the trough (``max_drawdown_end``);
* ``calmar = CAGR / |max drawdown|``;
* ``P`` = 365 days of 24 h divided by the bar length (crypto trades around the clock).

Risk metrics (trades with an initial stop; R = net P&L / money at risk at the initial stop):

* ``avg_r`` = mean R; ``expectancy_r`` = sum of net P&L / sum of money at risk (the R earned
  per unit of risk taken, weighted by risk); ``r_distribution`` = trades per R bucket;
* ``avg_risk_pct`` = mean money at risk as % of equity at entry;
* ``max_consecutive_losses`` = longest run of trades with net P&L <= 0;
* ``exits_by_reason`` = exit fills per reason (a partial target fill is ``partial_tp``);
* ``skipped_entries`` = entries not taken, per reason (guards, invalid plans, size below min).

Ratios that are undefined (no variance, no losses, no trades) are ``None``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from trading_backtest.engine import Trade

SECONDS_PER_YEAR = 365 * 24 * 3600
R_BUCKETS = (
    ("<-2", -math.inf, -2),
    ("-2..-1", -2, -1),
    ("-1..0", -1, 0),
    ("0..1", 0, 1),
    ("1..2", 1, 2),
    ("2..3", 2, 3),
    (">=3", 3, math.inf),
)


def periods_per_year(index: pd.DatetimeIndex) -> float | None:
    """Bars per year from the median bar spacing (24/7 markets)."""
    if len(index) < 2:
        return None
    # through datetime64[ns]: pandas indexes may have s/ms/us/ns resolution
    ns = index.values.astype("datetime64[ns]").astype(np.int64)
    step = float(np.median(np.diff(ns))) / 1e9
    return SECONDS_PER_YEAR / step if step > 0 else None


def _f(x: float) -> float | None:
    """JSON-safe float (None for NaN / inf)."""
    return float(x) if x is not None and math.isfinite(x) else None


def drawdown(equity: np.ndarray, initial: float) -> np.ndarray:
    """``E_i / running peak - 1`` (the initial capital counts as the first peak)."""
    peak = np.maximum.accumulate(np.concatenate(([initial], equity)))[1:]
    return equity / peak - 1


def compute(
    equity: np.ndarray,
    times: pd.DatetimeIndex,
    trades: Sequence[Trade],
    initial: float,
    *,
    benchmark: tuple[float, float],
    bars_per_year: float | None,
    skipped: dict[str, int] | None = None,
) -> dict[str, Any]:
    """All metrics of a run. ``benchmark`` = (first window open, last close) for buy & hold."""
    n = len(equity)
    final = float(equity[-1])
    series = np.concatenate(([initial], equity))
    returns = series[1:] / series[:-1] - 1
    p = bars_per_year

    sharpe = sortino = cagr = None
    if p and n > 1:
        std = float(np.std(returns, ddof=1))
        if std > 0:
            sharpe = float(np.mean(returns)) / std * math.sqrt(p)
        downside = math.sqrt(float(np.mean(np.minimum(returns, 0) ** 2)))
        if downside > 0:
            sortino = float(np.mean(returns)) / downside * math.sqrt(p)
    if p and final > 0:
        exponent = math.log(final / initial) * p / n
        # None when it does not fit a float (e.g. a few hours annualized)
        cagr = math.expm1(exponent) * 100 if exponent < 700 else None

    dd = drawdown(equity, initial)
    trough = int(np.argmin(dd))
    max_dd = float(dd[trough])
    dd_start = dd_end = recovered = None
    if max_dd < 0:
        peak_value = float(np.max(series[: trough + 2]))
        # the last bar at the peak before the trough (index -1 = the initial capital)
        peaks = np.flatnonzero(series[: trough + 2] == peak_value) - 1
        peak_at = int(peaks[-1])
        dd_start = times[max(peak_at, 0)].isoformat()
        dd_end = times[trough].isoformat()
        after = np.flatnonzero(equity[trough:] >= peak_value)
        recovered = times[trough + int(after[0])].isoformat() if len(after) else None
    calmar = cagr / abs(max_dd * 100) if cagr is not None and max_dd < 0 else None

    net = np.array([t.net_pnl for t in trades], dtype=np.float64)
    rets = np.array([t.return_pct for t in trades], dtype=np.float64)
    wins, losses = net[net > 0], net[net <= 0]
    gross_loss = float(-losses.sum())
    held = sum(t.bars_held for t in trades)
    first_open, last_close = benchmark

    return {
        "initial_capital": _f(initial),
        "final_equity": _f(final),
        "total_return_pct": _f((final / initial - 1) * 100),
        "cagr_pct": _f(cagr) if cagr is not None else None,
        "max_drawdown_pct": _f(max_dd * 100),
        "max_drawdown_start": dd_start,
        "max_drawdown_end": dd_end,
        "max_drawdown_recovered": recovered,
        "sharpe": _f(sharpe) if sharpe is not None else None,
        "sortino": _f(sortino) if sortino is not None else None,
        "calmar": _f(calmar) if calmar is not None else None,
        "trades": len(trades),
        "win_rate_pct": _f(len(wins) / len(net) * 100) if len(net) else None,
        "profit_factor": _f(float(wins.sum()) / gross_loss) if gross_loss > 0 else None,
        "avg_win": _f(float(wins.mean())) if len(wins) else None,
        "avg_loss": _f(float(losses.mean())) if len(losses) else None,
        "expectancy": _f(float(net.mean())) if len(net) else None,
        "best_trade_pct": _f(float(rets.max())) if len(rets) else None,
        "worst_trade_pct": _f(float(rets.min())) if len(rets) else None,
        "avg_bars_held": _f(held / len(trades)) if trades else None,
        "exposure_pct": _f(held / n * 100),
        "total_fees": _f(sum(t.fees for t in trades)),
        "buy_and_hold_return_pct": _f((last_close / first_open - 1) * 100),
        "bars": n,
        "bars_per_year": _f(p) if p else None,
        **risk_metrics(trades),
        "skipped_entries": dict(sorted((skipped or {}).items())),
    }


def risk_metrics(trades: Sequence[Trade]) -> dict[str, Any]:
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    risked = [t for t in trades if t.risk_amount]
    total_risk = sum(t.risk_amount for t in risked)
    risk_pcts = [t.risk_pct for t in trades if t.risk_pct is not None]
    longest = run = 0
    for t in trades:
        run = run + 1 if t.net_pnl <= 0 else 0
        longest = max(longest, run)
    exits: dict[str, int] = {}
    for t in trades:
        for f in t.fills or ({"reason": t.exit_reason},):
            exits[f["reason"]] = exits.get(f["reason"], 0) + 1
    return {
        "avg_r": _f(float(np.mean(rs))) if rs else None,
        "expectancy_r": _f(sum(t.net_pnl for t in risked) / total_risk) if total_risk else None,
        "r_distribution": {name: sum(1 for r in rs if lo <= r < hi) for name, lo, hi in R_BUCKETS}
        if rs
        else None,
        "avg_risk_pct": _f(float(np.mean(risk_pcts))) if risk_pcts else None,
        "max_consecutive_losses": longest,
        "exits_by_reason": dict(sorted(exits.items())),
    }


def unix_seconds(index: pd.DatetimeIndex) -> np.ndarray:
    """Unix seconds of a DatetimeIndex, whatever its resolution."""
    return index.values.astype("datetime64[s]").astype(np.int64)


def downsample_indices(
    equity: np.ndarray, dd: np.ndarray | None = None, max_points: int = 2000
) -> np.ndarray:
    """Indices of at most ``max_points`` points that keep the curve's shape: the first and last
    point, and in each of ``(max_points - 2) // 3`` equal buckets the equity minimum, the equity
    maximum and the deepest drawdown. So the global min/max and the worst drawdown always
    survive (unlike plain striding)."""
    n = len(equity)
    if n <= max_points:
        return np.arange(n)
    if dd is None:
        dd = equity / np.maximum.accumulate(equity) - 1
    buckets = max(1, (max_points - 2) // 3)
    edges = np.linspace(1, n - 1, buckets + 1).astype(np.int64)
    keep = {0, n - 1}
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b <= a:
            continue
        keep.add(int(a + np.argmin(equity[a:b])))
        keep.add(int(a + np.argmax(equity[a:b])))
        keep.add(int(a + np.argmin(dd[a:b])))
    return np.array(sorted(keep), dtype=np.int64)
