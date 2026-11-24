"""The backtest engine: an event loop over bars, plain Python on lists (no pandas per bar).

Execution model (also in README.md, docs/backtesting.md and docs/risk-management.md):

* A signal on bar ``t`` (computed on the closed bar) is filled at the **open of bar t + 1**.
  Only signals on bars inside the trading window are taken; bars before it are warm-up.
* Each bar ``i`` is processed in this order:
  1. **gaps**: for a position opened before bar ``i``, a stop already beyond the open closes
     it at the open; otherwise every target already beyond the open is filled at the open;
  2. ``max_bars_held``: closed at the open of the bar ``max_bars_held`` bars after the entry;
  3. the signal of bar ``i - 1``: opens a position when flat (after the account guards and the
     trade plan: :meth:`RiskContext.plan` decides stop, targets and size), closes on an
     opposite signal and, with ``long_short``, reverses at the same open;
  4. stop and targets **inside** the bar from its low/high: the stop first (if both are
     touched, the stop is assumed first), then the targets in order (partial exits). Checked
     on the entry bar too when ``check_entry_bar`` (the default; the fill is at its open);
  5. at the close: trailing stop / breakeven are updated from this bar's data; the new stop
     applies from the next bar;
  6. equity is marked to market at the close; the drawdown and daily-loss guards are updated.
* An open position is closed at the last close (``end_of_data``).
* Every fill pays slippage against you (buy at ``price * (1 + s)``, sell at ``price * (1 - s)``)
  and the fee ``fill * quantity * fee_rate``, on entry and on every exit fill.
* With ``config.cost_per_unit`` (a fixed round-trip cost per unit, per instrument: XAU/USD 0.25)
  there is no slippage and no bps fee: every fill is at the chart price (the stop and the
  targets fill exactly at their levels) and the whole round trip, ``cost_per_unit * quantity``,
  is charged **at the entry** as the trade's fee (partial exits pay nothing more). A long's net
  P&L is ``(exit - entry - cost) * quantity``, a short's ``(entry - exit - cost) * quantity``.
  The breakeven stop is ``entry + side * cost``.
* Accounting: ``cash`` plus the position's value (longs: ``+q * price``; shorts: the sale
  proceeds are in cash and ``-q * price`` is owed).
* With ``config.conversion`` (an account currency that is not the quote currency) the money is
  kept in the account currency: the size is computed on the equity converted to the quote
  currency, ``cash`` moves only by the fees and the P&L of each fill (converted at that fill),
  and an open position adds its unrealised P&L converted at the close. Without it the code
  path is the one above, unchanged.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from trading_backtest.config import BacktestConfig
from trading_backtest.risk import INVALID_REASONS, RiskContext, breakeven_level

LONG, SHORT = 1, -1
EXIT_REASONS = (
    "opposite_signal",
    "stop_loss",
    "trailing_stop",
    "breakeven_stop",
    "take_profit",
    "partial_tp",
    "max_bars",
    "end_of_data",
)
STOP_REASONS = ("stop_loss", "trailing_stop", "breakeven_stop")
GUARD_REASONS = ("max_drawdown", "daily_loss", "cooldown", "loss_streak")
SKIP_REASONS = (*GUARD_REASONS, *INVALID_REASONS)


@dataclass(frozen=True)
class Trade:
    number: int
    side: str  # "long" | "short"
    entry_time: pd.Timestamp
    entry_price: float  # fill, slippage included
    exit_time: pd.Timestamp  # of the last exit fill
    exit_price: float  # quantity-weighted average of the exit fills
    quantity: float  # entry quantity
    gross_pnl: float  # sum over exit fills of (exit - entry) * quantity * direction
    fees: float  # entry + all exits
    net_pnl: float
    return_pct: float  # net_pnl / entry notional * 100
    bars_held: int  # bars the position was open in (an exit at a bar's open excludes that bar)
    entry_reason: str | None  # the strategy's reason code
    exit_reason: str  # of the last exit fill
    entry_index: int  # positions in the frame passed to the engine
    exit_index: int
    initial_stop: float | None = None
    risk_amount: float | None = None  # money lost at the initial stop, fees included
    risk_pct: float | None = None  # risk_amount / equity at entry * 100
    r_multiple: float | None = None  # net_pnl / risk_amount
    entry_equity: float | None = None
    fills: tuple[dict[str, Any], ...] = ()  # every exit fill: time, index, price, quantity, reason

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["entry_time"] = self.entry_time.isoformat()
        d["exit_time"] = self.exit_time.isoformat()
        d["fills"] = [dict(f) for f in self.fills]
        return d


@dataclass
class Simulation:
    trades: list[Trade]
    equity: np.ndarray  # mark-to-market at each close of the window
    start: int  # index of the first window bar
    skipped: dict[str, int]  # entries not taken, by reason


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

    fee, slip = config.fee_rate, config.slippage_rate  # both 0 with cost_per_unit
    cost = config.cost_per_unit
    exits, guards = config.exits, config.guards
    conv = config.conversion
    ctx = RiskContext(df, config)
    long_short = config.direction == "long_short"
    max_bars = exits.max_bars_held
    on_opposite = exits.exit_on_opposite_signal
    check_entry = exits.check_entry_bar
    trail = exits.trailing
    trail_atr = ctx.atr[trail.length].tolist() if trail and trail.type == "atr" else None
    daily_limit = guards.max_daily_loss_pct
    dd_limit = guards.max_drawdown_pct
    days = index.values.astype("datetime64[D]").astype(np.int64).tolist() if daily_limit else None

    cash = float(config.initial_capital)
    side = 0
    qty = qty0 = entry_px = entry_fee = 0.0
    entry_i = -1
    entry_why: str | None = None
    stop = math.nan
    stop_kind = "stop_loss"
    init_stop: float | None = None
    per_unit = risk_amount = risk_pct = entry_equity = None
    targets: list[list[float]] = []  # [price, quantity] still to fill, in order
    fills: list[dict[str, Any]] = []
    gross = exit_fees = 0.0
    extreme = 0.0
    trailing_on = be_done = False
    trades: list[Trade] = []
    equity = np.empty(n - start)
    skipped: dict[str, int] = {}

    # guards
    peak = cash
    halted = day_halted = False
    day = day_start = None
    blocked_until, block_reason = -1, "cooldown"
    streak = 0
    last_equity = cash

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    def open_position(i: int, s: int, price: float, reason: str | None) -> None:
        nonlocal cash, side, qty, qty0, entry_px, entry_fee, entry_i, entry_why, stop
        nonlocal stop_kind, init_stop, per_unit, risk_amount, risk_pct, entry_equity, targets
        nonlocal fills, gross, exit_fees, extreme, trailing_on, be_done, halted, day_halted
        if halted:
            return skip("max_drawdown")
        if dd_limit and (cash / peak - 1) * 100 <= -dd_limit:
            halted = True
            return skip("max_drawdown")
        if daily_limit and (day_halted or (cash / day_start - 1) * 100 <= -daily_limit):
            day_halted = True
            return skip("daily_loss")
        if i <= blocked_until:
            return skip(block_reason)
        fill = price * (1 + s * slip)  # a buy pays more, a short sale receives less
        if conv is None:
            plan = ctx.plan(i - 1, s, cash, entry=fill)  # flat: equity == cash
        else:
            plan = ctx.plan(i - 1, s, cash, entry=fill, conversion_rate=conv.at(fill))
        if plan.invalid_reason is not None:
            return skip(plan.invalid_reason)
        q = plan.quantity
        entry_equity = cash
        entry_fee = fill * q * fee if cost is None else cost * q  # the whole round trip
        if conv is None:
            cash -= s * fill * q + entry_fee
        else:
            entry_fee *= conv.at(fill)
            cash -= entry_fee
        side, qty, qty0, entry_px, entry_i, entry_why = s, q, q, fill, i, reason
        init_stop = None if plan.stop is None else float(plan.stop)
        stop = math.nan if init_stop is None else init_stop
        stop_kind = "stop_loss"
        per_unit = abs(fill - plan.stop) if plan.stop is not None else None
        risk_amount, risk_pct = plan.risk_amount, plan.risk_pct
        targets, left, done = [], q, 0.0
        for t in plan.targets:  # quantities of the targets; the one reaching 100 % takes the rest
            done += t["close_pct"] / 100
            part = left if done >= 1 - 1e-9 else min(left, q * t["close_pct"] / 100)
            targets.append([float(t["price"]), part])
            left -= part
        fills, gross, exit_fees = [], 0.0, 0.0
        extreme = fill
        trailing_on = trail is not None and trail.activation_r is None
        be_done = False

    def exit_fill(i: int, price: float, q: float, reason: str, at_open: bool) -> None:
        nonlocal cash, side, qty, gross, exit_fees, blocked_until, block_reason, streak
        fill = price * (1 - side * slip)  # a long sells lower, a short buys back higher
        fee_paid = fill * q * fee if cost is None else 0.0  # a fixed cost was paid at entry
        if conv is None:
            cash += side * fill * q - fee_paid
            gross += side * (fill - entry_px) * q
        else:
            rate = conv.at(fill)
            fee_paid *= rate
            pnl = side * (fill - entry_px) * q * rate
            cash += pnl - fee_paid
            gross += pnl
        exit_fees += fee_paid
        qty -= q
        final = qty <= qty0 * 1e-12
        fills.append(
            {
                "time": index[i].isoformat(),
                "index": i,
                "price": float(fill),
                "quantity": float(q),
                "reason": reason if final or reason != "take_profit" else "partial_tp",
            }
        )
        if not final:
            return
        fees = entry_fee + exit_fees
        net = gross - fees
        exit_price = (
            fills[0]["price"]
            if len(fills) == 1
            else sum(f["price"] * f["quantity"] for f in fills) / sum(f["quantity"] for f in fills)
        )
        trades.append(
            Trade(
                number=len(trades) + 1,
                side="long" if side == LONG else "short",
                entry_time=index[entry_i],
                entry_price=entry_px,
                exit_time=index[i],
                exit_price=exit_price,
                quantity=qty0,
                gross_pnl=gross,
                fees=fees,
                net_pnl=net,
                return_pct=net / (entry_px * qty0 * conv.at(entry_px)) * 100
                if conv
                else net / (entry_px * qty0) * 100,
                bars_held=i - entry_i + (0 if at_open else 1),
                entry_reason=entry_why,
                exit_reason=reason,
                entry_index=entry_i,
                exit_index=i,
                initial_stop=init_stop,
                risk_amount=risk_amount,
                risk_pct=risk_pct,
                r_multiple=net / risk_amount if risk_amount else None,
                entry_equity=entry_equity,
                fills=tuple(fills),
            )
        )
        side, qty = 0, 0.0
        if guards.cooldown_bars and reason in STOP_REASONS:
            if i + guards.cooldown_bars > blocked_until:
                blocked_until, block_reason = i + guards.cooldown_bars, "cooldown"
        streak = streak + 1 if net <= 0 else 0
        if guards.max_consecutive_losses and streak >= guards.max_consecutive_losses:
            if i + guards.cooldown_bars > blocked_until:
                blocked_until, block_reason = i + guards.cooldown_bars, "loss_streak"
            streak = 0

    def close_all(i: int, price: float, reason: str, at_open: bool) -> None:
        exit_fill(i, price, qty, reason, at_open)

    def fill_targets(i: int, reach: float, at_open: bool) -> None:
        """Fill every target the price ``reach`` (the open, or the bar's high/low) got to."""
        while side and targets and side * (reach - targets[0][0]) >= 0:
            price, part = targets.pop(0)
            if part >= qty * (1 - 1e-12):
                part = qty
            exit_fill(i, reach if at_open else price, part, "take_profit", at_open)

    for i in range(start, n):
        o = opn[i]
        if days is not None and days[i] != day:
            day, day_start, day_halted = days[i], last_equity, False
        # 1. gaps: a stop or targets already beyond the open
        if side and i > entry_i:
            if stop == stop and side * (o - stop) <= 0:
                close_all(i, o, stop_kind, True)
            elif targets:
                fill_targets(i, o, True)
        # 2. held long enough
        if side and max_bars is not None and i - entry_i >= max_bars:
            close_all(i, o, "max_bars", True)
        # 3. the previous bar's signal, at this open
        if i > start:
            s = sig[i - 1]
            if s:
                if not side:
                    if s == LONG or long_short:
                        open_position(i, s, o, why[i - 1])
                elif s == -side and on_opposite:
                    close_all(i, o, "opposite_signal", True)
                    if long_short:
                        open_position(i, s, o, why[i - 1])
        # 4. stop, then targets, inside the bar (stop first when both are touched)
        if side and (i > entry_i or check_entry):
            if side == LONG:
                if stop == stop and low[i] <= stop:
                    close_all(i, stop, stop_kind, False)
                elif targets:
                    fill_targets(i, high[i], False)
            else:
                if stop == stop and high[i] >= stop:
                    close_all(i, stop, stop_kind, False)
                elif targets:
                    fill_targets(i, low[i], False)
        # 5. trailing stop / breakeven from this bar's data, effective from the next bar
        if side and trail is not None:
            extreme = max(extreme, high[i]) if side == LONG else min(extreme, low[i])
            moved = side * (extreme - entry_px) / per_unit if per_unit else None
            if trail.breakeven_r is not None and not be_done and moved >= trail.breakeven_r:
                be_done = True
                level = breakeven_level(side, entry_px, fee, slip, cost)
                if stop != stop or side * (level - stop) > 0:
                    stop, stop_kind = level, "breakeven_stop"
            if trail.type != "breakeven":
                if not trailing_on and moved is not None and moved >= trail.activation_r:
                    trailing_on = True
                if trailing_on:
                    if trail.type == "percent":
                        level = extreme * (1 - side * trail.value / 100)
                    else:
                        level = extreme - side * trail.multiplier * trail_atr[i]
                    if level == level and (stop != stop or side * (level - stop) > 0):
                        stop, stop_kind = level, "trailing_stop"
        # 6. mark to market; guards
        if conv is None:
            eq = cash + side * qty * close[i]
        else:
            eq = cash + side * qty * (close[i] - entry_px) * conv.at(close[i]) if side else cash
        equity[i - start] = last_equity = eq
        if dd_limit:
            peak = max(peak, eq)
            if (eq / peak - 1) * 100 <= -dd_limit:
                halted = True
        if daily_limit and (eq / day_start - 1) * 100 <= -daily_limit:
            day_halted = True

    if side:
        close_all(n - 1, close[n - 1], "end_of_data", False)
        equity[-1] = cash
    return Simulation(trades=trades, equity=equity, start=start, skipped=skipped)
