"""The interface every signal strategy shares (docs/strategies/PREREG.md, sections 3-5).

A strategy reads closed bars only: its entry frame up to the signal bar, and higher frames only
through ``last_closed`` (a higher bar is used once it has closed, never earlier). It returns one
``Candidate`` per trigger, ``ARMED`` or ``REJECTED`` with one reason. Triggers are decided by the
strategy's own entry rule; the signal-time filters of section 3 are applied in ``finish``, in this
order, and the first that fails is the reason:

1. ``holiday``: the signal bar opens on a US market holiday (New York date);
2. ``outside_liquid_window``: it does not open 02:00-15:59 New York, Monday to Friday (not S3);
3. the strategy's own reason (``incomplete_range``, ``range_width``, ``regime``,
   ``move_too_small``), if any;
4. ``non_positive_risk``: the SL is not beyond the entry;
5. ``r_out_of_range``: a TP from a price level outside the registered R range;
6. ``cost_filter``: round trip plus SL slippage above ``cost_filter_r`` R;
7. ``no_time_left``: the type's session end leaves no bar to hold (``bar close + one bar >
   deadline``).

Entry is at market at the close of the signal bar. The horizon counts entry-frame bars after it
(``idx + horizon_bars``, as ``labels.resolve`` in close mode); scalp and intraday trades are also
forced out at the close of the last bar that can close by the session end (``deadline``, 16:45
New York): the first bar ``j`` with ``close_utc[j] + one bar > deadline`` (5m and 15m: the bar
ending 16:45; 1h: the bar ending 16:00). That is decided from the bar grid, so it never needs a
later bar; a signal whose next bar would close after the deadline is ``no_time_left`` (on 1h: the
bar opening 15:00). When bars are missing before the deadline, the trade leaves at the open of the
first bar in the data that closes after it (``session_end_gap``, ``app.management.engine``)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import Instrument, SignalSpec, common
from app.data.sessions import MARKET_TZ, hhmm_minutes, market_holidays
from app.setups.builder import Plan
from app.setups.costs import round_trip

STEP = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
}
BUY, SELL = "buy", "sell"


@dataclass(frozen=True)
class Candidate:
    strategy: str
    idx: int  # signal bar, entry-frame index
    ts_utc: pd.Timestamp  # its open time
    direction: str
    state: str  # "ARMED" or "REJECTED"
    reason: str  # "" when armed
    entry: float
    sl: float
    tp: float | None
    risk: float
    r_multiple: float | None
    spread: float  # the signal bar's spread (price units)
    atr: float  # the strategy's entry-frame ATR at the signal bar (risk in ATR units for E0)
    horizon_bars: int
    deadline: pd.Timestamp | None  # session end (UTC) of a scalp or intraday trade
    level: float | None = None  # the broken level of a breakout (L5)

    @property
    def sign(self) -> float:
        return 1.0 if self.direction == BUY else -1.0

    @property
    def plan(self) -> Plan:
        """The same plan type the L1 pipeline uses, so ``labels.resolve`` can read it."""
        return Plan(
            self.state, self.reason, self.entry, self.sl, self.tp, self.risk, self.r_multiple, None
        )


@dataclass(frozen=True)
class Thesis:
    """A thesis-invalidation series for L5 (pullbacks and ranges): ``against[j]`` is True when
    the source bar that closed last by entry bar ``j``'s close is against the trade, and
    ``source_close[j]`` is that bar's close time (ns), so a rule can ignore bars that closed
    before the entry."""

    against: np.ndarray
    source_close: np.ndarray


@dataclass(frozen=True)
class Trigger:
    """What a strategy's entry rule decides at a signal bar, before the common filters."""

    idx: int
    direction: str
    sl: float
    tp: float | None = None  # a price level (S2, S6, S8); None: tp_r x risk
    tp_r: float | None = None
    r_range: tuple[float, float] | None = None  # for a price-level TP
    reason: str = ""  # the strategy's own rejection, if any
    level: float | None = None


def ns(ts: pd.Series) -> np.ndarray:
    return pd.DatetimeIndex(ts).as_unit("ns").asi8


def last_closed(higher: pd.DataFrame, at: pd.Series) -> np.ndarray:
    """Per time in ``at`` (UTC): the index of the last ``higher`` bar closed by then, or -1."""
    return np.searchsorted(ns(higher["close_utc"]), ns(at), side="right") - 1


def take(values: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """``values[idx]`` with NaN where ``idx`` is -1 (nothing closed yet)."""
    out = np.full(len(idx), np.nan)
    ok = idx >= 0
    out[ok] = np.asarray(values, float)[idx[ok]]
    return out


def local(ts_utc: pd.Series, zone: str) -> tuple[np.ndarray, np.ndarray]:
    """Minutes after midnight and the date (naive, day precision) in ``zone`` of each time."""
    t = ts_utc.dt.tz_convert(zone)
    mins = (t.dt.hour * 60 + t.dt.minute).to_numpy()
    return mins, t.dt.tz_localize(None).dt.normalize().to_numpy()


def between(mins: np.ndarray, window: list[str] | tuple[str, str]) -> np.ndarray:
    lo, hi = (hhmm_minutes(t) for t in window)
    return (mins >= lo) & (mins < hi)


def at_time(day: np.datetime64, hhmm: str, zone: str) -> pd.Timestamp:
    """``hhmm`` wall-clock in ``zone`` on ``day``, in UTC."""
    t = pd.Timestamp(day) + pd.Timedelta(minutes=hhmm_minutes(hhmm))
    return t.tz_localize(zone).tz_convert("UTC")


def spread_of(frame: pd.DataFrame) -> np.ndarray:
    col = f"spread_{common().spread_stat}"
    return frame[col].fillna(0.0).to_numpy(float) if col in frame else np.zeros(len(frame))


def finish(
    frame: pd.DataFrame,
    triggers: list[Trigger],
    spec: SignalSpec,
    inst: Instrument,
    atr: np.ndarray,
) -> list[Candidate]:
    """Plans and the common signal-time filters (module docstring) for the triggers of one
    strategy on one entry frame."""
    if not triggers:
        return []
    c = common()
    close = frame["close"].to_numpy(float)
    spread = spread_of(frame)
    ts = frame["ts_utc"]
    ny_mins, ny_day = local(ts, MARKET_TZ)
    dow = ts.dt.tz_convert(MARKET_TZ).dt.day_of_week.to_numpy()
    years = pd.DatetimeIndex(ny_day).year
    holidays = np.isin(
        ny_day, np.array(sorted(market_holidays(years.min(), years.max())), dtype="datetime64[ns]")
    )
    liquid = between(ny_mins, c.liquid_window) & (dow < 5)
    close_utc = frame["close_utc"]
    step = STEP[spec.frame]
    out = []
    for t in sorted(triggers, key=lambda t: (t.idx, t.direction)):
        j = t.idx
        s = 1.0 if t.direction == BUY else -1.0
        entry = float(close[j])
        risk = s * (entry - t.sl)
        if t.tp is not None:
            tp = t.tp
            r = s * (tp - entry) / risk if risk > 0 else None
        elif t.tp_r is not None:
            tp = entry + s * t.tp_r * risk if risk > 0 else None
            r = t.tp_r
        else:
            tp, r = None, None
        deadline = None
        if spec.session_end is not None:
            deadline = at_time(ny_day[j], spec.session_end, MARKET_TZ)
        if holidays[j]:
            reason = "holiday"
        elif spec.liquid_window and not liquid[j]:
            reason = "outside_liquid_window"
        elif t.reason:
            reason = t.reason
        elif not risk > 0:
            reason = "non_positive_risk"
        elif t.r_range is not None and not (t.r_range[0] <= r <= t.r_range[1]):
            reason = "r_out_of_range"
        elif (round_trip(spread[j], inst) + inst.sl_slippage) / risk > c.cost_filter_r:
            reason = "cost_filter"
        elif deadline is not None and close_utc.iloc[j] + step > deadline:
            reason = "no_time_left"
        else:
            reason = ""
        out.append(
            Candidate(
                strategy=spec.name,
                idx=j,
                ts_utc=ts.iloc[j],
                direction=t.direction,
                state="REJECTED" if reason else "ARMED",
                reason=reason,
                entry=entry,
                sl=float(t.sl),
                tp=None if tp is None else float(tp),
                risk=float(risk),
                r_multiple=None if r is None else float(r),
                spread=float(spread[j]),
                atr=float(atr[j]),
                horizon_bars=spec.horizon_bars,
                deadline=deadline,
                level=t.level,
            )
        )
    return out
