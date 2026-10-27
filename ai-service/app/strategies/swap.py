"""Rollover instants and swap in R (docs/strategies/PREREG.md, section 6). Every swap number is an
**estimated retrospective scenario**, never a historical cost: the MT5 exports have no swap.

**Rollover (D9).** One instant per trading day at 00:00 server time (Europe/Athens), computed from
UTC: 17:00 New York, 18:00 in the weeks a year when US and EU daylight saving differ. The instant
that ends server day D is charged when D is Monday to Friday. A trade open at the instant (entry
before it, exit at or after it) pays one night times the day weight: the per-day multipliers when
the terminal exports them, else 3 on ``SYMBOL_SWAP_ROLLOVER3DAYS`` and 1 on the other days.
Holiday nights are not added.

**Conversion to R.** For a swap value S per lot and night, R = (S in the profit currency per lot)
/ (risk_price x contract_size); lot size and account currency cancel. P is the price at the
rollover: in trade results the close of the last entry-frame bar closed by the instant
(``close_before``); in a_S the entry price, because a_S reads no price after the signal bar; for
``INTEREST_OPEN`` always the open price. By ``SYMBOL_SWAP_MODE``: ``DISABLED`` 0;
``POINTS`` S x point / risk_price; ``CURRENCY_SYMBOL`` base to profit (x P); ``CURRENCY_MARGIN``
x P if the margin currency is the base, as is if it is the profit currency; ``CURRENCY_DEPOSIT``
as is if the deposit currency is the profit currency, x P if it is the base; ``CURRENCY_PROFIT`` as
is; ``INTEREST_CURRENT`` P x S / 100 / 360 / risk_price; ``INTEREST_OPEN`` the same at the open
price; ``REOPEN_CURRENT`` and ``REOPEN_BID`` approximated as ``POINTS`` (labelled). In MT5 a
negative value is a charge, so a negative R lowers net R.

Scenarios: W0 none; W1 the dated snapshot's rates; W2 from policy rates (stage F addendum, not
here); W3 every rollover charged twice the worse side of W1, whatever the direction; the decision
scenario is per trade the more costly of W1 and W2, W1 alone where W2 is not available."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import splits

MODES = (
    "DISABLED",
    "POINTS",
    "CURRENCY_SYMBOL",
    "CURRENCY_MARGIN",
    "CURRENCY_DEPOSIT",
    "CURRENCY_PROFIT",
    "INTEREST_CURRENT",
    "INTEREST_OPEN",
    "REOPEN_CURRENT",
    "REOPEN_BID",
)
APPROXIMATED = ("REOPEN_CURRENT", "REOPEN_BID")
# MT5 ENUM_DAY_OF_WEEK: SUNDAY = 0 ... SATURDAY = 6
MT5_DAY = {
    "SUNDAY": 0,
    "MONDAY": 1,
    "TUESDAY": 2,
    "WEDNESDAY": 3,
    "THURSDAY": 4,
    "FRIDAY": 5,
    "SATURDAY": 6,
}


@dataclass(frozen=True)
class SwapSpec:
    """One symbol's swap fields from the MT5 export (PREREG section 6a)."""

    symbol: str
    mode: str
    long: float
    short: float
    rollover3days: int  # MT5 day of week
    point: float
    contract_size: float
    currency_base: str
    currency_profit: str
    currency_margin: str
    deposit_currency: str = "USD"
    day_multipliers: dict[int, float] | None = None  # MT5 day of week -> weight

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"unknown swap mode {self.mode!r}")


def instants(start: pd.Timestamp, end: pd.Timestamp, spec: SwapSpec) -> pd.DataFrame:
    """The rollover instants (UTC) in ``(start, end]`` with their day weights."""
    tz = splits().server_tz
    lo = start.tz_convert(tz).normalize().tz_localize(None) - pd.Timedelta(days=1)
    hi = end.tz_convert(tz).normalize().tz_localize(None) + pd.Timedelta(days=1)
    days = pd.date_range(lo, hi, freq="D")  # server days D; the instant ends D at D + 1 00:00
    at = (days + pd.Timedelta(days=1)).tz_localize(tz).tz_convert("UTC")
    mt5_dow = (days.day_of_week.to_numpy() + 1) % 7  # pandas Monday = 0 -> MT5 Monday = 1
    trading = (mt5_dow >= 1) & (mt5_dow <= 5)
    if spec.day_multipliers is not None:
        weight = np.array([spec.day_multipliers.get(int(x), 0.0) for x in mt5_dow])
    else:
        weight = np.where(mt5_dow == spec.rollover3days, 3.0, 1.0)
    keep = trading & (at > start) & (at <= end)
    return pd.DataFrame({"at": at[keep], "weight": weight[keep]}).reset_index(drop=True)


def per_night_r(
    spec: SwapSpec, direction: str, price: float, price_open: float, risk_price: float
) -> float:
    """Swap of one night of weight 1 in R (negative: a charge)."""
    s = spec.long if direction == "buy" else spec.short
    lot = risk_price * spec.contract_size
    mode = spec.mode
    if mode == "DISABLED":
        return 0.0
    if mode in ("POINTS", *APPROXIMATED):
        return s * spec.point / risk_price
    if mode == "CURRENCY_SYMBOL":
        return s * price / lot
    if mode == "CURRENCY_MARGIN":
        if spec.currency_margin == spec.currency_base:
            return s * price / lot
        if spec.currency_margin == spec.currency_profit:
            return s / lot
        raise ValueError(f"{spec.symbol}: margin currency {spec.currency_margin} not handled")
    if mode == "CURRENCY_DEPOSIT":
        if spec.deposit_currency == spec.currency_profit:
            return s / lot
        if spec.deposit_currency == spec.currency_base:
            return s * price / lot
        raise ValueError(f"{spec.symbol}: deposit currency {spec.deposit_currency} not handled")
    if mode == "CURRENCY_PROFIT":
        return s / lot
    p = price if mode == "INTEREST_CURRENT" else price_open
    return p * s / 100 / 360 / risk_price


def close_before(frame: pd.DataFrame) -> Callable[[pd.Timestamp], float]:
    """``price_at`` for trade results: the close of the last ``frame`` bar closed by ``t``."""
    close_ns = pd.DatetimeIndex(frame["close_utc"]).as_unit("ns").asi8
    close = frame["close"].to_numpy(float)

    def at(t: pd.Timestamp) -> float:
        i = int(np.searchsorted(close_ns, t.value, side="right")) - 1
        if i < 0:
            raise ValueError(f"no bar closed by {t}")
        return float(close[i])

    return at


def swap_r(
    spec: SwapSpec,
    direction: str,
    entry_utc: pd.Timestamp,
    exit_utc: pd.Timestamp,
    risk_price: float,
    price_open: float,
    price_at: Callable[[pd.Timestamp], float] | None = None,
) -> float:
    """W1: the swap of a trade open from ``entry_utc`` to ``exit_utc``. ``price_at(t)`` gives the
    price at a rollover instant (``close_before`` for results; default the open price, as in
    a_S)."""
    total = 0.0
    for t, w in instants(entry_utc, exit_utc, spec).itertuples(index=False):
        p = price_open if price_at is None else price_at(t)
        total += w * per_night_r(spec, direction, p, price_open, risk_price)
    return total


def stress_r(
    spec: SwapSpec,
    entry_utc: pd.Timestamp,
    exit_utc: pd.Timestamp,
    risk_price: float,
    price_open: float,
) -> float:
    """W3: every rollover charged twice the worse side of W1 (at the open price), as a cost."""
    worse = min(per_night_r(spec, d, price_open, price_open, risk_price) for d in ("buy", "sell"))
    w = instants(entry_utc, exit_utc, spec)["weight"].sum()
    return -2.0 * abs(worse) * w


def decision_r(w1: float, w2: float | None) -> float:
    """The decision scenario: the more costly of W1 and W2 (W1 alone without W2)."""
    return w1 if w2 is None else min(w1, w2)


def horizon_end(
    close_utc: pd.Series,
    idx: int,
    horizon_bars: int,
    step: pd.Timedelta,
    deadline: pd.Timestamp | None,
) -> pd.Timestamp:
    """End of a trade's registered horizon for the swap allowance of a_S (PREREG section 8): the
    close of bar ``idx + horizon_bars`` (the bar grid past the data), capped by the session end."""
    k = idx + horizon_bars
    end = close_utc.iloc[k] if k < len(close_utc) else close_utc.iloc[idx] + horizon_bars * step
    return end if deadline is None else min(end, deadline)
