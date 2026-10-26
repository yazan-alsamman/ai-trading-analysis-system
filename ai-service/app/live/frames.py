"""Request bars -> the research frames (P6 task 2).

The live scanner runs the research code unchanged, so it needs the frames the research store
holds: ``15m`` (entry), ``1h``, ``4h`` and ``D1`` with the store's columns. All four are built
from the request's 15m bars with the importer's aggregation (``app.data.aggregate``), as of
``bar_close_ts``: only buckets that have closed are kept, and a bucket that starts before the
first 15m bar is dropped, because its earlier bars are not in the request. Higher-timeframe bars
in the request are not used; the store builds every frame from M1 the same way, so the OHLC of
an aggregated bucket equals the store's (the spread statistics of higher frames differ: they are
means of 15m means, and no rule reads them).

Spread is in price units in both the contract and the store: no conversion. With a rule set that
treats the daily break as a gap (L1), entry bars opening in closed hours are removed after the
aggregation, as ``app.setups.counts.history_frames`` does.

The lockbox guard does not apply: these are live bars sent by the backend, not the export files.

Data-quality checks raise ``DataQualityError`` (``data_quality_failed`` with an abstention):
OHLC consistency, order and the ``bar_close_ts`` rule are already enforced by the contract
(422)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import Instrument, Profile, Strategy
from app.contract import TIMEFRAMES, EvaluateRequest
from app.data.aggregate import aggregate, trading_day
from app.data.mt5 import BAR_COLUMNS
from app.data.sessions import MARKET_TZ, is_open, market_holidays

FRAMES = ("15m", "1h", "4h", "D1")


class DataQualityError(Exception):
    def __init__(self, reason: str, detail: dict):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class LiveFrames:
    frames: dict[str, pd.DataFrame]  # research frames, as the rules read them
    as_of: pd.Timestamp  # bar_close_ts


def bars_frame(req: EvaluateRequest, timeframe: str) -> pd.DataFrame:
    """The request's bars of one timeframe in the importer's bar layout (``BAR_COLUMNS``)."""
    bars = req.bars[timeframe]
    df = pd.DataFrame(
        {
            "ts_utc": pd.DatetimeIndex([b.ts for b in bars]).tz_convert("UTC").as_unit("ns"),
            "open": [b.o for b in bars],
            "high": [b.h for b in bars],
            "low": [b.l for b in bars],
            "close": [b.c for b in bars],
            "tick_volume": np.nan,
            "spread": [np.nan if b.spread is None else b.spread for b in bars],
        }
    )
    return df[BAR_COLUMNS]


def longest_gap_minutes(ts: pd.Series, inst: Instrument, step: pd.Timedelta) -> int:
    """The longest run of missing ``step`` bars inside trading hours. US market holidays are
    excluded, by New York date and by trading day (the evening before Good Friday belongs to
    Good Friday's trading day)."""
    if len(ts) < 2:
        return 0
    grid = pd.date_range(ts.iloc[0], ts.iloc[-1], freq=step)
    ny_day = grid.tz_convert(MARKET_TZ).tz_localize(None).normalize()
    t_day = pd.DatetimeIndex(trading_day(pd.Series(grid)))
    holidays = list(market_holidays(int(ny_day.year.min()), int(t_day.year.max())))
    expected = is_open(grid, inst) & ~ny_day.isin(holidays) & ~t_day.isin(holidays)
    missing = expected & ~grid.isin(pd.DatetimeIndex(ts))
    longest = run = 0
    for m in missing:
        run = run + 1 if m else 0
        longest = max(longest, run)
    return int(longest * step / pd.Timedelta(minutes=1))


def build_frames(req: EvaluateRequest, inst: Instrument, p: Strategy, prof: Profile) -> LiveFrames:
    tf = p.entry_timeframe
    step = pd.Timedelta(TIMEFRAMES[tf])
    if tf not in req.bars:
        raise DataQualityError("missing_timeframe", {"timeframe": tf})
    bars = bars_frame(req, tf)
    as_of = pd.Timestamp(req.bar_close_ts).tz_convert("UTC").as_unit("ns")

    off_grid = bars["ts_utc"] != bars["ts_utc"].dt.floor(step)
    if off_grid.any():
        first = bars["ts_utc"][off_grid].iloc[0]
        raise DataQualityError(
            "misaligned_bars", {"timeframe": tf, "first_off_grid": first.isoformat()}
        )
    if bars["spread"].isna().any():
        n = int(bars["spread"].isna().sum())
        raise DataQualityError("missing_spread", {"timeframe": tf, "bars_without_spread": n})
    # from the last bar before the gap window, so a gap across its start counts
    cutoff = as_of - pd.Timedelta(hours=prof.gap_window_hours)
    i = max(int(np.searchsorted(bars["ts_utc"], cutoff)) - 1, 0)
    gap = longest_gap_minutes(bars["ts_utc"].iloc[i:].reset_index(drop=True), inst, step)
    if gap > prof.max_gap_minutes:
        raise DataQualityError(
            "gap", {"longest_gap_minutes": gap, "max_gap_minutes": prof.max_gap_minutes}
        )

    first = bars["ts_utc"].iloc[0]
    frames = {}
    for name in FRAMES:
        out = aggregate(bars, name, step, as_of)
        if name != tf:
            out = out[out["ts_utc"] >= first].reset_index(drop=True)
        frames[name] = out
    days = len(frames["D1"])
    if days < prof.history_trading_days:
        raise DataQualityError(
            "insufficient_history",
            {"complete_trading_days": days, "required": prof.history_trading_days},
        )
    if p.break_is_gap:
        e = frames[tf]
        frames[tf] = e[is_open(e["ts_utc"], inst)].reset_index(drop=True)
    return LiveFrames(frames, as_of)
