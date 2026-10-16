"""Entry points: :func:`backtest` (a strategy from ``trading_strategies``) and
:func:`run_backtest` (any signal frame, e.g. from a custom strategy or a model)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import trading_strategies as ts

from trading_backtest import metrics as m
from trading_backtest.config import BacktestConfig
from trading_backtest.engine import Trade, simulate

OHLC = ("open", "high", "low", "close")


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]
    equity: pd.Series  # mark-to-market equity at each bar close of the window
    drawdown: pd.Series  # percent below the running peak (<= 0)
    metrics: dict[str, Any]

    @property
    def bars(self) -> int:
        return len(self.equity)

    def trades_frame(self) -> pd.DataFrame:
        columns = list(Trade.__dataclass_fields__)
        return pd.DataFrame([t.__dict__ for t in self.trades], columns=columns)

    def to_dict(self) -> dict[str, Any]:
        """JSON-able (curves as ``[unix seconds, value]`` pairs)."""
        times = m.unix_seconds(self.equity.index).tolist()
        return {
            "config": self.config.to_dict(),
            "metrics": self.metrics,
            "trades": [t.to_dict() for t in self.trades],
            "equity": [[t, v] for t, v in zip(times, self.equity.tolist(), strict=True)],
            "drawdown": [[t, v] for t, v in zip(times, self.drawdown.tolist(), strict=True)],
        }


def _check_frame(df: pd.DataFrame) -> None:
    missing = [c for c in OHLC if c not in df.columns]
    if missing:
        raise ValueError(f"missing column(s): {', '.join(missing)}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("the frame needs a DatetimeIndex")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("the index must be strictly increasing")


def _window(index: pd.DatetimeIndex, start: Any, end: Any) -> tuple[int, int]:
    """(first window bar, bars up to end) positions."""
    stop = len(index) if end is None else int(index.searchsorted(pd.Timestamp(end), "right"))
    first = 0 if start is None else int(index.searchsorted(pd.Timestamp(start), "left"))
    if first >= stop:
        raise ValueError("no bars in [start, end]")
    return first, stop


def run_backtest(
    df: pd.DataFrame,
    signals: pd.DataFrame | pd.Series,
    config: BacktestConfig | Mapping[str, Any] | None = None,
    *,
    start: Any = None,
    end: Any = None,
    bars_per_year: float | None = None,
) -> BacktestResult:
    """Backtest precomputed signals (``1`` buy, ``-1`` sell, ``0`` nothing per bar, aligned to
    ``df.index``; a frame may carry ``reason`` codes). Bars before ``start`` are warm-up: no
    trading, no equity. Bars after ``end`` are ignored. ``bars_per_year`` defaults to the value
    implied by the median bar spacing (24/7)."""
    _check_frame(df)
    if not isinstance(config, BacktestConfig):
        config = BacktestConfig.from_dict(config)
    if isinstance(signals, pd.Series):
        signals = signals.to_frame("signal")
    if not signals.index.equals(df.index):
        raise ValueError("signals must be aligned to the OHLCV index")
    first, stop = _window(df.index, start, end)
    df, signals = df.iloc[:stop], signals.iloc[:stop]
    sig = signals["signal"].to_numpy()
    if not np.isin(sig, (-1, 0, 1)).all():
        raise ValueError("signal values must be -1, 0 or 1")
    reasons = signals["reason"].to_numpy(dtype=object) if "reason" in signals else None

    sim = simulate(df, sig, reasons, config, start=first)
    times = df.index[first:]
    dd = m.drawdown(sim.equity, config.initial_capital)
    ppy = bars_per_year or m.periods_per_year(df.index)
    metrics = m.compute(
        sim.equity,
        times,
        sim.trades,
        config.initial_capital,
        benchmark=(float(df["open"].iloc[first]), float(df["close"].iloc[-1])),
        bars_per_year=ppy,
    )
    return BacktestResult(
        config=config,
        trades=sim.trades,
        equity=pd.Series(sim.equity, index=times, name="equity"),
        drawdown=pd.Series(dd * 100, index=times, name="drawdown_pct"),
        metrics=metrics,
    )


def backtest(
    df: pd.DataFrame,
    strategy: str | ts.Strategy,
    params: Mapping[str, Any] | None = None,
    config: BacktestConfig | Mapping[str, Any] | None = None,
    *,
    start: Any = None,
    end: Any = None,
    bars_per_year: float | None = None,
) -> BacktestResult:
    """Backtest a ``trading_strategies`` strategy. Give the frame enough bars before ``start``
    for the strategy's warm-up (``strategy.history(params)``)."""
    if isinstance(strategy, str):
        strategy = ts.get_strategy(strategy)
    _check_frame(df)
    _, stop = _window(df.index, start, end)
    data = df.iloc[:stop]
    signals = strategy.generate(data, params)
    return run_backtest(data, signals, config, start=start, end=end, bars_per_year=bars_per_year)
