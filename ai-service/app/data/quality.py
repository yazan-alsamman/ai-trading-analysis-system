"""Data-quality report for an imported bar history (machine-readable dict plus a markdown
rendering)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.schema import BASE_TIMEFRAME, InstrumentSpec
from app.data.sessions import MARKET_TZ, dst_mismatch, is_open, market_holidays, open_slots

JUMP_WINDOW = 288  # one trading day of 5m bars
JUMP_RATIO = 30.0  # a move this many times the trailing median move is flagged
TOP_N = 15


def _years(ts: pd.Series) -> pd.Series:
    return ts.dt.year


def _per_year(values: pd.Series, ts: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in values.groupby(_years(ts)).sum().items()}


def _stamp(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d %H:%M")


def _ny(ts: pd.Timestamp) -> str:
    return ts.tz_convert(MARKET_TZ).strftime("%a %Y-%m-%d %H:%M")


def find_gaps(ts: pd.Series, instrument: InstrumentSpec) -> pd.DataFrame:
    """Runs of consecutive missing 5m bars inside expected trading hours, with a class:

    * ``holiday`` - on a US market holiday or a Christmas / New Year eve (thin or closed trading);
    * ``session_edge`` - touching the daily break or the weekend (the broker opened late or closed
      early);
    * ``mid_session`` - anything else: the gaps that matter."""
    slots = pd.Series(open_slots(ts.iloc[0], ts.iloc[-1], instrument.session))
    missing = ~slots.isin(ts).to_numpy()
    if not missing.any():
        empty = pd.Series([], dtype="datetime64[ns, UTC]")
        return pd.DataFrame(
            {
                "start": empty,
                "end": empty,
                "bars": pd.Series([], dtype="int64"),
                "kind": pd.Series([], dtype=str),
                "dst_mismatch": pd.Series([], dtype=bool),
            }
        )
    idx = np.flatnonzero(missing)
    # contiguous[i]: slot i directly follows slot i-1 (no closed time between them)
    contiguous = np.r_[False, (slots.diff() == BASE_TIMEFRAME).to_numpy()[1:]]
    # A run of missing slots ends where the next missing slot is not the next open slot, or where a
    # break or
    # weekend separates them.
    breaks = np.flatnonzero((np.diff(idx) != 1) | ~contiguous[idx[1:]])
    run_start = idx[np.r_[0, breaks + 1]]
    run_end = idx[np.r_[breaks, len(idx) - 1]]

    prev_closed = ~contiguous[run_start]
    next_closed = np.r_[~contiguous[1:], True][run_end]

    start, end = (
        slots.iloc[run_start].reset_index(drop=True),
        slots.iloc[run_end].reset_index(drop=True),
    )
    holidays = market_holidays(range(ts.iloc[0].year, ts.iloc[-1].year + 1))
    ny_start = start.dt.tz_convert(MARKET_TZ).dt.tz_localize(None).dt.normalize()
    ny_end = end.dt.tz_convert(MARKET_TZ).dt.tz_localize(None).dt.normalize()
    # A trading day is named after the day it ends, so an evening gap belongs to the next day.
    ny_next = (
        end.dt.tz_convert(MARKET_TZ).dt.tz_localize(None) + pd.Timedelta(hours=7)
    ).dt.normalize()
    on_holiday = (
        ny_start.isin(holidays) | ny_end.isin(holidays) | ny_next.isin(holidays)
    ).to_numpy()

    kind = np.where(
        on_holiday, "holiday", np.where(prev_closed | next_closed, "session_edge", "mid_session")
    )
    return pd.DataFrame(
        {
            "start": start,
            "end": end,
            "bars": run_end - run_start + 1,
            "kind": kind,
            "dst_mismatch": dst_mismatch(start),
        }
    )


def _gap_section(m5: pd.DataFrame, instrument: InstrumentSpec) -> dict:
    ts = m5["ts_utc"]
    gaps = find_gaps(ts, instrument)
    slots = pd.Series(open_slots(ts.iloc[0], ts.iloc[-1], instrument.session))
    expected = slots.groupby(slots.dt.year).size()
    present = ts.groupby(ts.dt.year).size()
    per_year = {}
    for y in expected.index:
        g = gaps[gaps["start"].dt.year == y]
        per_year[str(y)] = {
            "expected_bars": int(expected[y]),
            "present_bars": int(present.get(y, 0)),
            "coverage_pct": round(100 * float(present.get(y, 0)) / float(expected[y]), 2),
            **{
                f"{k}_gaps": int((g["kind"] == k).sum())
                for k in ("mid_session", "session_edge", "holiday")
            },
            **{
                f"{k}_missing_bars": int(g.loc[g["kind"] == k, "bars"].sum())
                for k in ("mid_session", "session_edge", "holiday")
            },
        }
    mid = gaps[gaps["kind"] == "mid_session"]
    size_buckets = pd.cut(
        mid["bars"], [0, 1, 3, 12, 48, np.inf], labels=["5m", "10-15m", "20m-1h", "1h-4h", ">4h"]
    )
    largest = mid.sort_values(["bars", "start"], ascending=[False, True]).head(TOP_N)
    return {
        "definition": (
            "Missing 5m bars inside expected trading hours (New York: Sunday 18:00 to Friday 17:00"
            + (
                ", minus the daily {}-{} break".format(*instrument.session.daily_break)
                if instrument.session.daily_break
                else ""
            )
            + "). Weekend and daily-break time is never a gap."
        ),
        "total_gaps": {
            k: int((gaps["kind"] == k).sum()) for k in ("mid_session", "session_edge", "holiday")
        },
        "total_missing_bars": {
            k: int(gaps.loc[gaps["kind"] == k, "bars"].sum())
            for k in ("mid_session", "session_edge", "holiday")
        },
        "mid_session_by_length": {
            str(k): int(v) for k, v in size_buckets.value_counts(sort=False).items()
        },
        "session_edge_in_dst_mismatch_weeks": int(
            gaps.loc[gaps["kind"] == "session_edge", "dst_mismatch"].sum()
        ),
        "per_year": per_year,
        "largest_mid_session": [
            {"start_utc": _stamp(r.start), "start_ny": _ny(r.start), "missing_bars": int(r.bars)}
            for r in largest.itertuples()
        ],
    }


def _release_times(ny_wall: pd.Series, rng: pd.Series, rows: np.ndarray) -> dict[str, int]:
    """For each first Friday of a month (the usual US jobs-report day, released 08:30 New York), the
    New York time of the widest bar between 07:00 and 10:00. A correct clock puts most of them at
    08:30."""
    sel = (
        rows
        & (ny_wall.dt.dayofweek == 4).to_numpy()
        & (ny_wall.dt.day <= 7).to_numpy()
        & ny_wall.dt.hour.between(7, 9).to_numpy()
    )
    df = pd.DataFrame({"ny": ny_wall[sel], "rng": rng[sel]})
    if df.empty:
        return {}
    top = df.loc[df.groupby(df["ny"].dt.normalize())["rng"].idxmax(), "ny"]
    return {k: int(v) for k, v in top.dt.strftime("%H:%M").value_counts().head(4).items()}


def _timezone_section(m5: pd.DataFrame, instrument: InstrumentSpec, server_tz: str) -> dict:
    ts = m5["ts_utc"]
    ny = ts.dt.tz_convert(MARKET_TZ).dt.tz_localize(None)
    week = (ny + pd.Timedelta(hours=6)).dt.to_period("W-SUN")
    first = ny.groupby(week).min()
    labels = first.dt.strftime("%a %H:%M").value_counts()
    expected_open = f"Sun {instrument.session.week_open}"

    in_closed = ~is_open(ts, instrument.session)
    # The alternative reading of the clock: server time is always New York time + 7 h.
    server_wall = ts.dt.tz_convert(server_tz).dt.tz_localize(None)
    alt = (server_wall - pd.Timedelta(hours=7)).dt.tz_localize(
        MARKET_TZ, ambiguous="NaT", nonexistent="NaT"
    )
    alt_closed = ~is_open(alt.dropna().dt.tz_convert("UTC"), instrument.session)
    mismatch = dst_mismatch(ts)
    alt_ny = alt.dt.tz_localize(None)
    rng = m5["high"] - m5["low"]
    everywhere = np.ones(len(ts), bool)
    return {
        "server_clock": f"{server_tz} (UTC+2 winter / UTC+3 EU summer time)",
        "weekly_open_expected_ny": expected_open,
        "weeks": int(len(first)),
        "weekly_first_bar_ny": {k: int(v) for k, v in labels.head(8).items()},
        "weeks_opening_at_expected_time": int(labels.get(expected_open, 0)),
        "bars_in_dst_mismatch_weeks": int(mismatch.sum()),
        "bars_inside_closed_hours": int(in_closed.sum()),
        "bars_inside_closed_hours_by_year": _per_year(pd.Series(in_closed, index=ts.index), ts),
        "bars_inside_closed_hours_if_server_were_ny_plus_7": int(alt_closed.sum()),
        "examples_inside_closed_hours": [_ny(t) for t in ts[in_closed].head(5)],
        "jobs_report_bar_ny": {
            "all_first_fridays": _release_times(ny, rng, everywhere),
            "first_fridays_in_dst_mismatch_weeks": _release_times(ny, rng, mismatch),
            "first_fridays_in_dst_mismatch_weeks_if_ny_plus_7": _release_times(
                alt_ny, rng, mismatch
            ),
        },
    }


def _jumps(m5: pd.DataFrame) -> dict:
    ts = m5["ts_utc"]
    after_gap = (ts.diff() != BASE_TIMEFRAME).to_numpy()

    def flagged(series: pd.Series, label: str) -> dict:
        base = series.rolling(JUMP_WINDOW, min_periods=50).median().shift(1)
        ratio = series / base.replace(0, np.nan)
        hit = ratio >= JUMP_RATIO
        top = ratio[hit].sort_values(ascending=False).head(TOP_N)
        return {
            "count": int(hit.sum()),
            "after_a_gap": int((hit & after_gap).sum()),
            "by_year": {k: v for k, v in _per_year(hit.astype(int), ts).items() if v},
            "top": [
                {
                    "ts_utc": _stamp(ts[i]),
                    "ny": _ny(ts[i]),
                    label: round(float(series[i]), 5),
                    "ratio": round(float(ratio[i]), 1),
                    "after_gap": bool(after_gap[i]),
                    "close": float(m5["close"][i]),
                }
                for i in top.index
            ],
        }

    move = (m5["close"] - m5["close"].shift(1)).abs()
    rng = m5["high"] - m5["low"]
    return {
        "definition": (
            "A bar is flagged when its close-to-close move (or its high-low range) is at least "
            f"{JUMP_RATIO:g}x "
            f"the median of the previous {JUMP_WINDOW} bars. Flags are reported, not removed: most "
            "are real "
            "news moves."
        ),
        "close_to_close": flagged(move, "move"),
        "range": flagged(rng, "range"),
    }


def _spread(m5: pd.DataFrame) -> dict:
    s = m5["spread"]
    if s.isna().all():
        return {"available": False}
    q = [0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    per_year = {}
    for y, g in s.groupby(_years(m5["ts_utc"])):
        qs = g.quantile(q)
        per_year[str(y)] = {
            "min": float(g.min()),
            **{f"p{int(k * 100):02d}": round(float(v), 5) for k, v in qs.items()},
            "max": float(g.max()),
            "mean": round(float(g.mean()), 5),
            "zero_bars": int((g == 0).sum()),
        }
    return {"available": True, "unit": "price (USD for XAUUSD)", "per_year": per_year}


def build_report(
    m5: pd.DataFrame,
    aggregates: dict[str, pd.DataFrame],
    parse_stats: dict,
    rejected: pd.DataFrame,
    instrument: InstrumentSpec,
    input_info: dict,
    hashes: dict,
    server_tz: str,
) -> dict:
    ts = m5["ts_utc"]
    flat = (m5["open"] == m5["high"]) & (m5["high"] == m5["low"]) & (m5["low"] == m5["close"])
    by_reason = parse_stats["rejected_by_reason"]
    return {
        "report_version": 1,
        "symbol": instrument.symbol,
        "input": input_info,
        "range_utc": {"first_bar": _stamp(ts.iloc[0]), "last_bar": _stamp(ts.iloc[-1])},
        "parse": {
            **{k: v for k, v in parse_stats.items() if k != "columns_in_export"},
            "columns_in_export": parse_stats["columns_in_export"],
            "rejected_examples": rejected.head(TOP_N).to_dict("records"),
        },
        "bars_per_year": {
            "5m": {str(k): int(v) for k, v in ts.groupby(ts.dt.year).size().items()},
            **{
                tf: {
                    str(k): int(v)
                    for k, v in df["ts_utc"].groupby(df["ts_utc"].dt.year).size().items()
                }
                for tf, df in aggregates.items()
            },
        },
        "bars_total": {"5m": int(len(m5)), **{tf: int(len(df)) for tf, df in aggregates.items()}},
        "partial_buckets": {
            tf: int((df["n_bars"] < df["n_expected"]).sum()) for tf, df in aggregates.items()
        },
        "timezone": _timezone_section(m5, instrument, server_tz),
        "gaps": _gap_section(m5, instrument),
        "ohlc": {
            "inconsistent_rows_rejected": int(by_reason.get("ohlc_inconsistent", 0)),
            "flat_bars_o_eq_h_eq_l_eq_c": int(flat.sum()),
            "flat_bars_by_year": {k: v for k, v in _per_year(flat.astype(int), ts).items() if v},
        },
        "duplicates": {
            "identical": int(by_reason.get("duplicate_identical", 0)),
            "conflicting": int(by_reason.get("duplicate_conflicting", 0)),
            "rule": "the first occurrence in file order is kept",
        },
        "jumps": _jumps(m5),
        "spread": _spread(m5),
        "hashes": hashes,
    }


# ----------------------------------------------------------------------------------------- markdown


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _n(x: int) -> str:
    return f"{x:,}"


def render_markdown(r: dict) -> str:
    tz, gaps, parse, jumps = r["timezone"], r["gaps"], r["parse"], r["jumps"]
    tfs = list(r["bars_per_year"].keys())
    years = list(r["bars_per_year"]["5m"].keys())
    md = [
        f"# Data-quality report: {r['symbol']} M5 (FxPro MT5 export)",
        "",
        "_Generated by `python -m app.data.importer`; do not edit by hand. The JSON next to this "
        "file has every "
        "number below._",
        "",
        "## Summary",
        "",
        _table(
            ["Item", "Value"],
            [
                ["Input file", f"`{r['input']['file']}` ({_n(r['input']['bytes'])} bytes)"],
                ["Input SHA-256", f"`{r['input']['sha256']}`"],
                [
                    "Range (UTC, bar open)",
                    f"{r['range_utc']['first_bar']} → {r['range_utc']['last_bar']}",
                ],
                [
                    "Rows read / kept / rejected",
                    f"{_n(parse['rows_read'])} / {_n(parse['rows_kept'])} / "
                    f"{_n(parse['rows_rejected'])}",
                ],
                ["Final bar dropped as possibly forming", parse["tail_bar_dropped"] or "no"],
                ["Bars", ", ".join(f"{tf}: {_n(n)}" for tf, n in r["bars_total"].items())],
                ["Server clock", tz["server_clock"]],
                [
                    "Bars inside closed hours (this clock / if NY+7)",
                    f"{_n(tz['bars_inside_closed_hours'])} / "
                    f"{_n(tz['bars_inside_closed_hours_if_server_were_ny_plus_7'])}",
                ],
                [
                    "Mid-session gaps (missing bars)",
                    f"{_n(gaps['total_gaps']['mid_session'])} "
                    f"({_n(gaps['total_missing_bars']['mid_session'])})",
                ],
                [
                    "OHLC inconsistencies / duplicates",
                    f"{r['ohlc']['inconsistent_rows_rejected']} / "
                    f"{r['duplicates']['identical'] + r['duplicates']['conflicting']}",
                ],
                [
                    "Jump flags (close-to-close / range)",
                    f"{jumps['close_to_close']['count']} / {jumps['range']['count']}",
                ],
                ["5m content hash", f"`{r['hashes']['5m']}`"],
            ],
        ),
        "",
        "## Parsing",
        "",
        _table(
            ["Reason", "Rows"],
            [[k, v] for k, v in parse["rejected_by_reason"].items()] or [["none", 0]],
        ),
        "",
        f"Out-of-order rows: {parse['out_of_order_rows']}. Columns in the export: "
        + ", ".join(f"`{c}`" for c in parse["columns_in_export"])
        + ".",
    ]
    if parse["rejected_examples"]:
        md += ["", "Rejected rows (first few):", ""]
        md += [
            _table(
                ["Line", "Reason", "Raw"],
                [[e["line"], e["reason"], f"`{e['raw']}`"] for e in parse["rejected_examples"]],
            )
        ]

    md += [
        "",
        "## Timezone verification",
        "",
        f"Server timestamps are converted with the `{tz['server_clock']}` clock. The weekly open "
        "should be "
        f"{tz['weekly_open_expected_ny']} New York time; {tz['weeks_opening_at_expected_time']} of "
        f"{tz['weeks']} weeks open exactly then. First bar of each week (New York time):",
        "",
        _table(["First bar (NY)", "Weeks"], [[k, v] for k, v in tz["weekly_first_bar_ny"].items()]),
        "",
        f"Bars that fall inside expected closed hours: **{_n(tz['bars_inside_closed_hours'])}** "
        "with this clock, "
        f"versus **{_n(tz['bars_inside_closed_hours_if_server_were_ny_plus_7'])}** if server time "
        "were always New "
        f"York + 7 h. {_n(tz['bars_in_dst_mismatch_weeks'])} bars fall in the US/EU "
        "daylight-saving mismatch weeks, "
        "where the two readings differ.",
    ]
    if tz["examples_inside_closed_hours"]:
        md += [
            "",
            "By year: "
            + ", ".join(f"{k}: {v}" for k, v in tz["bars_inside_closed_hours_by_year"].items() if v)
            + ". Examples (NY time): "
            + ", ".join(tz["examples_inside_closed_hours"])
            + ".",
        ]
    jr = tz["jobs_report_bar_ny"]

    def _fmt(d: dict) -> str:
        return ", ".join(f"{k} ({v})" for k, v in d.items()) or "none"

    md += [
        "",
        "Independent check: the US jobs report is released at 08:30 New York on most first Fridays "
        "of the month. "
        "New York time of the widest 5m bar between 07:00 and 10:00 on those days (count of days):",
        "",
        _table(
            ["Days", "Clock", "Widest bar at (NY)"],
            [
                [
                    "All first Fridays",
                    tz["server_clock"].split(" ")[0],
                    _fmt(jr["all_first_fridays"]),
                ],
                [
                    "First Fridays in DST mismatch weeks",
                    tz["server_clock"].split(" ")[0],
                    _fmt(jr["first_fridays_in_dst_mismatch_weeks"]),
                ],
                [
                    "First Fridays in DST mismatch weeks",
                    "New York + 7 h",
                    _fmt(jr["first_fridays_in_dst_mismatch_weeks_if_ny_plus_7"]),
                ],
            ],
        ),
    ]

    md += [
        "",
        "## Bars per year",
        "",
        _table(
            ["Year", *tfs, "Expected 5m", "Coverage"],
            [
                [
                    y,
                    *[_n(r["bars_per_year"][tf].get(y, 0)) for tf in tfs],
                    _n(gaps["per_year"].get(y, {}).get("expected_bars", 0)),
                    f"{gaps['per_year'].get(y, {}).get('coverage_pct', 0)}%",
                ]
                for y in years
            ],
        ),
        "",
        "Partial higher-timeframe bars (fewer 5m bars than expected slots): "
        + ", ".join(f"{tf}: {_n(n)}" for tf, n in r["partial_buckets"].items())
        + ".",
        "",
        "## Gaps",
        "",
        gaps["definition"],
        "",
        "- **mid_session**: inside trading hours and not next to a break; these are the gaps that "
        "matter.",
        "- **session_edge**: next to the daily break or the weekend (late open or early close by "
        "the broker). "
        f"{_n(gaps['session_edge_in_dst_mismatch_weeks'])} of them fall in DST mismatch weeks, "
        "where older data "
        "kept a fixed server-time session.",
        "- **holiday**: on a US market holiday or a Christmas / New Year eve.",
        "",
        _table(
            [
                "Year",
                "Mid-session gaps",
                "Missing bars",
                "Session-edge gaps",
                "Missing bars",
                "Holiday gaps",
                "Missing bars",
            ],
            [
                [
                    y,
                    v["mid_session_gaps"],
                    _n(v["mid_session_missing_bars"]),
                    v["session_edge_gaps"],
                    _n(v["session_edge_missing_bars"]),
                    v["holiday_gaps"],
                    _n(v["holiday_missing_bars"]),
                ]
                for y, v in gaps["per_year"].items()
            ],
        ),
        "",
        "Mid-session gaps by length: "
        + ", ".join(f"{k}: {v}" for k, v in gaps["mid_session_by_length"].items())
        + ".",
        "",
        "Largest mid-session gaps:",
        "",
        _table(
            ["Start (UTC)", "Start (NY)", "Missing 5m bars"],
            [
                [g["start_utc"], g["start_ny"], g["missing_bars"]]
                for g in gaps["largest_mid_session"]
            ],
        ),
        "",
        "## OHLC consistency and duplicates",
        "",
        f"- Rows rejected because high/low do not contain open/close, or a price is not positive: "
        f"{r['ohlc']['inconsistent_rows_rejected']}.",
        "- Flat bars (open = high = low = close), kept: "
        f"{_n(r['ohlc']['flat_bars_o_eq_h_eq_l_eq_c'])}"
        + (
            " (" + ", ".join(f"{k}: {v}" for k, v in r["ohlc"]["flat_bars_by_year"].items()) + ")"
            if r["ohlc"]["flat_bars_by_year"]
            else ""
        )
        + ".",
        f"- Duplicate timestamps: {r['duplicates']['identical']} identical, "
        f"{r['duplicates']['conflicting']} "
        f"conflicting ({r['duplicates']['rule']}).",
        "",
        "## Extreme jumps",
        "",
        jumps["definition"],
        "",
    ]
    for key, title in (("close_to_close", "Close-to-close moves"), ("range", "Bar ranges")):
        j = jumps[key]
        value_key = "move" if key == "close_to_close" else "range"
        md += [
            f"**{title}:** {j['count']} flagged ({j['after_a_gap']} right after a gap). By year: "
            + (", ".join(f"{k}: {v}" for k, v in j["by_year"].items()) or "none")
            + ".",
            "",
            _table(
                ["Bar (UTC)", "Bar (NY)", value_key.capitalize(), "× median", "After gap", "Close"],
                [
                    [
                        t["ts_utc"],
                        t["ny"],
                        t[value_key],
                        t["ratio"],
                        "yes" if t["after_gap"] else "",
                        t["close"],
                    ]
                    for t in j["top"]
                ],
            ),
            "",
        ]

    md += ["## Spread distribution per year", ""]
    if r["spread"]["available"]:
        md += [
            "MT5 records the **minimum** spread inside each bar, so these are lower bounds on the "
            "real cost. "
            f"Unit: {r['spread']['unit']}.",
            "",
            _table(
                [
                    "Year",
                    "Min",
                    "P05",
                    "P25",
                    "Median",
                    "P75",
                    "P95",
                    "P99",
                    "Max",
                    "Mean",
                    "Zero bars",
                ],
                [
                    [
                        y,
                        v["min"],
                        v["p05"],
                        v["p25"],
                        v["p50"],
                        v["p75"],
                        v["p95"],
                        v["p99"],
                        v["max"],
                        v["mean"],
                        _n(v["zero_bars"]),
                    ]
                    for y, v in r["spread"]["per_year"].items()
                ],
            ),
        ]
    else:
        md += ["The export has no spread column."]

    md += [
        "",
        "## Reproducibility",
        "",
        "Content hashes are SHA-256 over each output's columns, dtypes and values, so they do not "
        "depend on the "
        "Parquet library version. Re-running the importer on the same input gives the same hashes.",
        "",
        _table(["Output", "Content SHA-256"], [[k, f"`{v}`"] for k, v in r["hashes"].items()]),
        "",
    ]
    return "\n".join(md)
