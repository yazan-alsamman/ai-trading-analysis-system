"""The backtest engine: an event loop over bars, plain Python on lists (no pandas per bar).

Execution model (also in README.md / docs/backtesting.md):

* A signal on bar ``t`` (computed on the closed bar) is filled at the **open of bar t + 1**.
  Only signals on bars inside the trading window are taken; bars before it are warm-up.
* Each bar ``i`` is processed in this order:
  1. stop-loss / take-profit **gaps**: a position opened before bar ``i`` whose stop (or target)
     is already beyond the open is closed at the open;
  2. ``max_bars_held``: closed at the open of the bar ``max_bars_held`` bars after the entry bar;
  3. the signal of bar ``i - 1``: opens a position when flat (a sell opens a short only with
     ``long_short``), closes on an opposite signal (``exit_on_opposite_signal``) and, with
     ``long_short``, reverses at the same open; same-direction signals are ignored;
  4. stop-loss / take-profit **inside** the bar from its high/low, for positions opened before
     bar ``i`` (never on the entry bar); if both are touched, the stop is assumed first;
  5. equity is marked to market at the close.
* An open position is closed at the last close (``end_of_data``).
* Every fill pays slippage against you (buy at ``price * (1 + s)``, sell at ``price * (1 - s)``)
  and the fee ``fill * quantity * fee_rate``, on entry and on exit.
* Accounting: ``cash`` plus the position's value (longs: ``+q * price``; shorts: the sale
  proceeds are in cash and ``-q * price`` is owed).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from trading_backtest.config import BacktestConfig

LONG, SHORT = 1, -1
EXIT_REASONS = ("opposite_signal", "stop_loss", "take_profit", "max_bars", "end_of_data")


@dataclass(frozen=True)
class Trade:
    number: int
    side: str  # "long" | "short"
    entry_time: pd.Timestamp
    entry_price: float  # fill, slippage included
    exit_time: pd.Timestamp
    exit_price: float
    quantity: float
    gross_pnl: float  # (exit - entry) * quantity * direction
    fees: float  # entry + exit
    net_pnl: float
    return_pct: float  # net_pnl / entry notional * 100
    bars_held: int  # bars the position was open in (an exit at a bar's open excludes that bar)
    entry_reason: str | None  # the strategy's reason code
    exit_reason: str
    entry_index: int  # positions in the frame passed to the engine
    exit_index: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["entry_time"] = self.entry_time.isoformat()
        d["exit_time"] = self.exit_time.isoformat()
        return d


@dataclass
class Simulation:
    trades: list[Trade]
    equity: np.ndarray  # mark-to-market at each close of the window
    start: int  # index of the first window bar


def simulate(
    df: pd.DataFrame,
    signal: np.ndarray,
    reasons: np.ndarray | None,
    config: BacktestConfig,
    start: int = 0,
) -> Simulation:
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
        q = sizer.quantity(cash, fill, fee)  # flat: equity == cash
        if q <= 0:
            return
        entry_fee = fill * q * fee
        cash -= s * fill * q + entry_fee
        side, qty, entry_px, entry_i, entry_why = s, q, fill, i, reason
        sl, tp = exits.levels(s, fill)

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
    return Simulation(trades=trades, equity=equity, start=start)
