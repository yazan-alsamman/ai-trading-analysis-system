"""Pre-approval candidate counts (docs/strategies/PREREG.md, section 12): run on the frozen commit,
before approval, and descriptive only (no count is a gate, section 15).

Per strategy, type, instrument, period and year: candidates, armed candidates, rejections by
signal-time reason, armed candidates per trading day (mean, median, share of days with 0, 1, 2 or
more) and per week (share of weeks with 0, 1 to 9, 10 or more). A trading day is a New York
weekday that is not a US market holiday and has an entry-frame bar, plus any other date with a
candidate (S3 can signal on a Sunday evening); a week is Monday to Sunday by New York date. From
the armed candidates of the primary period: a_S and delta*_S (section 8).

Candidates use bars up to and including the signal bar only. Nothing here resolves, manages or
replays a trade: this module and everything it imports never load ``app.setups.labels``,
``app.management`` or E0 (``app.research.baselines``), and the tables have no outcome column
(``check_no_outcomes``); tests check both. The swap term of a_S reads only bar *times* after the
signal bar (the end of the registered horizon), never a price after it and never an exit. Rows of
the holdout period carry ``HOLDOUT_LABEL``; an end past the lockbox start is refused."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Instrument, SignalSpec, instruments, signal_specs, splits
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ, market_holidays
from app.research.decide import assumed_cost_r, delta_star
from app.strategies import frames as research_frames
from app.strategies import swap
from app.strategies.base import STEP, Candidate
from app.strategies.rules import Frames, candidates

HOLDOUT_LABEL = (
    "candidate-generation statistics only: not served signals, not an executable portfolio, "
    "not performance"
)
REASONS = (
    "holiday",
    "outside_liquid_window",
    "incomplete_range",
    "range_width",
    "regime",
    "move_too_small",
    "non_positive_risk",
    "r_out_of_range",
    "cost_filter",
    "no_time_left",
)
# A column whose name matches is an outcome (or could carry one) and never enters a count table.
OUTCOME = re.compile(
    r"exit|net_?r\b|gross|pnl|outcome|mfe|mae|equity|hit_?rate|win_?rate|^r$|^y$|price|reali[sz]ed",
    re.IGNORECASE,
)


def check_no_outcomes(table: pd.DataFrame) -> pd.DataFrame:
    """``table`` unchanged, or ValueError if a column is an outcome or holds timestamps."""
    bad = [c for c in table.columns if OUTCOME.search(str(c))]
    bad += [c for c in table.columns if pd.api.types.is_datetime64_any_dtype(table[c])]
    if bad:
        raise ValueError(f"a count table may not carry outcomes or times: {sorted(set(bad))}")
    return table


def bounds() -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    """Primary start, holdout start and lockbox start (UTC)."""
    s = splits()
    return tuple(
        pd.Timestamp(d, tz="UTC")
        for d in (s.walk_forward[0], s.secondary_holdout[0], s.lockbox_start)
    )


def period_of(t: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    primary, holdout, _ = bounds()
    t = pd.DatetimeIndex(t)
    return np.where(t < primary, "before_primary", np.where(t < holdout, "primary", "holdout"))


def assumed_r(
    c: Candidate,
    close_utc: pd.Series,
    inst: Instrument,
    spec: SignalSpec,
    sw: swap.SwapSpec | None,
) -> float:
    """The assumed part of the cost model of one armed candidate, in R (section 8): the extra
    cost term, the SL slippage and max(0, -s_h), s_h the decision-scenario swap (W1; W2 is not
    available) from the entry to the end of the registered horizon, at the entry price. A scalp
    or intraday horizon ends by its session end, before any rollover (tested), so its s_h is 0
    by construction and needs no swap export; a swing strategy's s_h needs ``sw`` (NaN
    without it)."""
    if spec.session_end is not None:
        s_h = 0.0
    elif sw is None:
        return np.nan
    else:
        entry = close_utc.iloc[c.idx]
        end = swap.horizon_end(close_utc, c.idx, c.horizon_bars, STEP[spec.frame], c.deadline)
        s_h = swap.swap_r(sw, c.direction, entry, end, c.risk, c.entry)
    a = assumed_cost_r(
        np.array([c.spread]), np.array([c.risk]), inst.cost_extra_frac, inst.cost_extra_min,
        inst.sl_slippage, np.array([s_h]),
    )  # fmt: skip
    return float(a[0])


def candidate_rows(
    frames: Frames,
    inst: Instrument,
    specs: Iterable[SignalSpec],
    sw: swap.SwapSpec | None = None,
) -> pd.DataFrame:
    """One row per candidate: when and where it was raised, its state and reason, and its assumed
    cost in R if armed (a swing strategy's only with a swap spec). Nothing after the signal bar
    but bar times."""
    parts = []
    for spec in specs:
        cs = candidates(frames, inst, spec)
        if not cs:
            continue
        close = frames[spec.frame]["close_utc"]
        entry = pd.DatetimeIndex([close.iloc[c.idx] for c in cs])
        armed = [c.state == "ARMED" for c in cs]
        parts.append(
            pd.DataFrame(
                {
                    "symbol": inst.symbol,
                    "strategy": spec.name,
                    "family": spec.family,
                    "type": spec.type,
                    "entry_utc": entry,
                    "ny_date": pd.DatetimeIndex([c.ts_utc for c in cs])
                    .tz_convert(MARKET_TZ)
                    .tz_localize(None)
                    .normalize(),
                    "state": [c.state for c in cs],
                    "reason": [c.reason for c in cs],
                    "assumed_r": [
                        assumed_r(c, close, inst, spec, sw) if a else np.nan
                        for c, a in zip(cs, armed, strict=True)
                    ],
                }
            )
        )
    if not parts:
        return pd.DataFrame(
            columns=[
                "symbol",
                "strategy",
                "family",
                "type",
                "entry_utc",
                "ny_date",
                "state",
                "reason",
                "assumed_r",
                "period",
            ]  # fmt: skip
        )
    rows = pd.concat(parts, ignore_index=True)
    rows["period"] = period_of(rows["entry_utc"])
    return rows


def trading_days(frames: Frames, inst: Instrument, specs: Iterable[SignalSpec]) -> pd.DataFrame:
    """The New York dates (weekdays, not US market holidays) with a bar of any entry frame."""
    ts = pd.concat([frames[f]["ts_utc"] for f in {s.frame for s in specs}])
    d = pd.DatetimeIndex(ts).tz_convert(MARKET_TZ).tz_localize(None).normalize().unique()
    if len(d):
        hol = pd.DatetimeIndex(sorted(market_holidays(d.year.min(), d.year.max())))
        d = d[(d.day_of_week < 5) & ~d.isin(hol)]
    d = d.sort_values()
    return pd.DataFrame({"symbol": inst.symbol, "ny_date": d})


def _stats(rows: pd.DataFrame, dates: pd.DatetimeIndex) -> dict:
    armed = rows[rows["state"] == "ARMED"]
    out = {"candidates": len(rows), "armed": len(armed)}
    for r in REASONS:
        out[f"rejected_{r}"] = int((rows["reason"] == r).sum())
    days = dates.union(pd.DatetimeIndex(armed["ny_date"].unique()))
    per_day = armed.groupby("ny_date").size().reindex(days, fill_value=0)
    week = days - pd.to_timedelta(days.day_of_week, "D")
    per_week = per_day.groupby(week).sum()
    n_days, n_weeks = max(len(days), 1), max(len(per_week), 1)
    out.update(
        days=len(days),
        per_day_mean=float(per_day.mean()) if len(days) else 0.0,
        per_day_median=float(per_day.median()) if len(days) else 0.0,
        days_0=float((per_day == 0).sum() / n_days),
        days_1=float((per_day == 1).sum() / n_days),
        days_2plus=float((per_day >= 2).sum() / n_days),
        weeks=len(per_week),
        weeks_0=float((per_week == 0).sum() / n_weeks),
        weeks_1_to_9=float(((per_week >= 1) & (per_week < 10)).sum() / n_weeks),
        weeks_10plus=float((per_week >= 10).sum() / n_weeks),
    )
    return out


def report(
    rows: pd.DataFrame, days: pd.DataFrame, specs: Iterable[SignalSpec]
) -> dict[str, pd.DataFrame]:
    """The count tables: ``by_year`` (strategy x instrument x period x year), ``summary``
    (strategy x instrument and all instruments, from the primary start), ``by_type`` (all
    instruments, from the primary start) and ``allowance`` (a_S, delta*_S per strategy)."""
    specs = list(specs)
    primary, _, _ = bounds()
    days = days.assign(
        period=period_of(pd.DatetimeIndex(days["ny_date"]).tz_localize("UTC")),
        year=pd.DatetimeIndex(days["ny_date"]).year,
    )
    rows = rows.assign(year=pd.DatetimeIndex(rows["ny_date"]).year)
    by_year = []
    for (symbol, period, year), d in days.groupby(["symbol", "period", "year"]):
        dates = pd.DatetimeIndex(d["ny_date"].unique())
        for sp in specs:
            r = rows[
                (rows["symbol"] == symbol) & (rows["strategy"] == sp.name)
                & (rows["period"] == period) & (rows["year"] == year)
            ]  # fmt: skip
            by_year.append(
                {
                    "strategy": sp.name,
                    "family": sp.family,
                    "type": sp.type,
                    "symbol": symbol,
                    "period": period,
                    "year": int(year),
                    **_stats(r, dates),
                    "note": HOLDOUT_LABEL if period == "holdout" else "",
                }  # fmt: skip
            )
    window_days = days[days["ny_date"] >= primary.tz_localize(None)]
    window_rows = rows[rows["entry_utc"] >= primary]
    note = HOLDOUT_LABEL if (window_days["period"] == "holdout").any() else ""
    summary = []
    for sp in specs:
        r_sp = window_rows[window_rows["strategy"] == sp.name]
        for symbol in [*sorted(days["symbol"].unique()), "all"]:
            d = window_days if symbol == "all" else window_days[window_days["symbol"] == symbol]
            r = r_sp if symbol == "all" else r_sp[r_sp["symbol"] == symbol]
            summary.append(
                {
                    "strategy": sp.name,
                    "family": sp.family,
                    "type": sp.type,
                    "symbol": symbol,
                    **_stats(r, pd.DatetimeIndex(d["ny_date"].unique())),
                    "note": note,
                }  # fmt: skip
            )
    by_type = []
    for t in sorted({sp.type for sp in specs}):
        names = [sp.name for sp in specs if sp.type == t]
        r = window_rows[window_rows["strategy"].isin(names)]
        dates = pd.DatetimeIndex(window_days["ny_date"].unique())
        by_type.append({"type": t, "symbol": "all", **_stats(r, dates), "note": note})
    allowance = []
    for sp in specs:
        a = rows[
            (rows["strategy"] == sp.name) & (rows["state"] == "ARMED")
            & (rows["period"] == "primary")
        ]["assumed_r"].dropna()  # fmt: skip
        allowance.append(
            {
                "strategy": sp.name,
                "armed_primary": len(a),
                "a_S": float(np.median(a)) if len(a) else np.nan,
                "delta_star": delta_star(a.to_numpy()) if len(a) else np.nan,
            }  # fmt: skip
        )
    tables = {
        "by_year": pd.DataFrame(by_year),
        "summary": pd.DataFrame(summary),
        "by_type": pd.DataFrame(by_type),
        "allowance": pd.DataFrame(allowance),
    }
    return {k: check_no_outcomes(v) for k, v in tables.items()}


def run(
    symbols: Iterable[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    store: Path = STORE,
    swaps: dict[str, swap.SwapSpec] | None = None,
) -> dict[str, pd.DataFrame]:
    """The count tables for ``symbols`` on bars opened from ``start`` and closed by ``end``. An
    end past the lockbox start is refused before anything is read."""
    _, _, lockbox = bounds()
    if end > lockbox:
        raise ValueError(f"end {end} is past the lockbox start {lockbox}")
    specs = list(signal_specs().values())
    rows, days = [], []
    for symbol in symbols:
        f = research_frames.load(symbol, start, end, store)
        inst = instruments()[symbol]
        rows.append(candidate_rows(f, inst, specs, None if swaps is None else swaps[symbol]))
        days.append(trading_days(f, inst, specs))
    return report(pd.concat(rows, ignore_index=True), pd.concat(days, ignore_index=True), specs)
