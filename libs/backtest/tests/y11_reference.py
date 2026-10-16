"""The Y11 engine (main @ 230b5ab, ``trading_backtest/engine.py::simulate``), kept verbatim as a
reference: new configs with ``check_entry_bar: false`` must give bit-identical results to it on
whatever machine runs the tests. Only the config accessors changed (``_y11_quantity``,
``_y11_levels``: the Y11 ``Sizer.quantity`` and ``ExitRules.levels``) and the return value.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from trading_backtest.config import BacktestConfig
from trading_backtest.engine import LONG, Trade


def _y11_quantity(sizer, equity: float, fill_price: float, fee_rate: float) -> float:
    if equity <= 0 or fill_price <= 0:
        return 0.0
    if sizer.mode == "fraction":
        return sizer.value * equity / (fill_price * (1 + fee_rate))
    notional = min(sizer.value, equity / (1 + fee_rate))
    return notional / fill_price


def _y11_levels(exits, side: int, entry_price: float) -> tuple[float, float]:
    sl = tp = math.nan
    if exits.stop_loss_pct is not None:
        sl = entry_price * (1 - side * exits.stop_loss_pct / 100)
    if exits.take_profit_pct is not None:
        tp = entry_price * (1 + side * exits.take_profit_pct / 100)
    return sl, tp


def y11_simulate(
    df: pd.DataFrame,
    signal: np.ndarray,
    reasons: np.ndarray | None,
    config: BacktestConfig,
    start: int = 0,
) -> tuple[list[Trade], np.ndarray]:
    """Run the bar loop over ``df[start:]``; ``df[:start]`` is warm-up (no trading)."""
    n = len(df)
    if not 0 <= start < n:
        raise ValueError("the trading window has no bars")
    opn = df["open"].to_numpy(dtype=np.float64).tolist()
    high = df["high"].to_numpy(dtype=np.float64).tolist()
    low = df["low"].to_numpy(dtype=np.float64).tolist()
    close = df["close"].to_numpy(dtype=np.float64).tolist()
    sig = np.asarray(signal, dtype=np.int64).tolist()
    why = reasons.tolist() if reasons is not None else [None] * n
    index = df.index

    fee, slip = config.fee_rate, config.slippage_rate
    sizer, exits = config.sizing, config.exits
    long_short = config.direction == "long_short"
    has_sl = exits.stop_loss_pct is not None
    has_tp = exits.take_profit_pct is not None
    max_bars = exits.max_bars_held
    on_opposite = exits.exit_on_opposite_signal

    cash = float(config.initial_capital)
    side = 0
    qty = entry_px = entry_fee = 0.0
    entry_i = -1
    entry_why: str | None = None
    sl = tp = math.nan
    trades: list[Trade] = []
    equity = np.empty(n - start)

    def open_position(i: int, s: int, price: float, reason: str | None) -> None:
        nonlocal cash, side, qty, entry_px, entry_fee, entry_i, entry_why, sl, tp
        fill = price * (1 + s * slip)  # a buy pays more, a short sale receives less
        q = _y11_quantity(sizer, cash, fill, fee)  # flat: equity == cash
        if q <= 0:
            return
        entry_fee = fill * q * fee
        cash -= s * fill * q + entry_fee
        side, qty, entry_px, entry_i, entry_why = s, q, fill, i, reason
        sl, tp = _y11_levels(exits, s, fill)

    def close_position(i: int, price: float, reason: str, at_open: bool) -> None:
        nonlocal cash, side, qty
        fill = price * (1 - side * slip)  # a long sells lower, a short buys back higher
        exit_fee = fill * qty * fee
        cash += side * fill * qty - exit_fee
        gross = side * (fill - entry_px) * qty
        fees = entry_fee + exit_fee
        net = gross - fees
        trades.append(
            Trade(
                number=len(trades) + 1,
                side="long" if side == LONG else "short",
                entry_time=index[entry_i],
                entry_price=entry_px,
                exit_time=index[i],
                exit_price=fill,
                quantity=qty,
                gross_pnl=gross,
                fees=fees,
                net_pnl=net,
                return_pct=net / (entry_px * qty) * 100,
                bars_held=i - entry_i + (0 if at_open else 1),
                entry_reason=entry_why,
                exit_reason=reason,
                entry_index=entry_i,
                exit_index=i,
            )
        )
        side, qty = 0, 0.0

    for i in range(start, n):
        o = opn[i]
        # 1. stop / target already beyond the open (gap): fill at the open
        if side and i > entry_i:
            if side == LONG:
                if has_sl and o <= sl:
                    close_position(i, o, "stop_loss", True)
                elif has_tp and o >= tp:
                    close_position(i, o, "take_profit", True)
            else:
                if has_sl and o >= sl:
                    close_position(i, o, "stop_loss", True)
                elif has_tp and o <= tp:
                    close_position(i, o, "take_profit", True)
        # 2. held long enough
        if side and max_bars is not None and i - entry_i >= max_bars:
            close_position(i, o, "max_bars", True)
        # 3. the previous bar's signal, at this open
        if i > start:
            s = sig[i - 1]
            if s:
                if not side:
                    if s == LONG or long_short:
                        open_position(i, s, o, why[i - 1])
                elif s == -side and on_opposite:
                    close_position(i, o, "opposite_signal", True)
                    if long_short:
                        open_position(i, s, o, why[i - 1])
        # 4. stop / target inside the bar (stop first when both are touched)
        if side and i > entry_i and (has_sl or has_tp):
            if side == LONG:
                if has_sl and low[i] <= sl:
                    close_position(i, sl, "stop_loss", False)
                elif has_tp and high[i] >= tp:
                    close_position(i, tp, "take_profit", False)
            else:
                if has_sl and high[i] >= sl:
                    close_position(i, sl, "stop_loss", False)
                elif has_tp and low[i] <= tp:
                    close_position(i, tp, "take_profit", False)
        # 5. mark to market
        equity[i - start] = cash + side * qty * close[i]

    if side:
        close_position(n - 1, close[n - 1], "end_of_data", False)
        equity[-1] = cash
    return trades, equity
