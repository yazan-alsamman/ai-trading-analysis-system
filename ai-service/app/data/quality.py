"""Data-quality report of the research store (P1 task 4).

    python -m app quality                    # every instrument in the store
    python -m app quality --symbol XAUUSD    # docs/data_quality/XAUUSD.{md,json}

Built from the M1 bars that ``python -m app import`` wrote, so it covers history before the
lockbox only. Sections:

* coverage: bars per year;
* gaps: every expected trading minute (from the session config) without a bar, grouped into runs
  and classed as ``holiday``, ``session_edge`` (touching a closed period: early closes, late
  opens, or session hours that differ from the config) or ``mid_session``;
* bars in closed hours: bars the session config says should not exist;
* week boundaries: the most common New York time of the first and last bar of each week;
* flat bars (open = high = low = close) per year;
* jumps: one-minute moves or ranges far above the trailing day's average;
* spread per year and per New York hour;
* clock check: on US jobs-report days (first Friday) the largest one-minute range between 07:30
  and 09:30 New York should sit at 08:30 if server time was converted with the right zone,
  including in the weeks when US and EU daylight saving disagree.

The report is deterministic: the same store gives the same files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import Instrument, instruments, splits
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import MARKET_TZ, is_open, market_holidays

REPORT_VERSION = 1
OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "data_quality"
M1 = pd.Timedelta(minutes=1)
JUMP_WINDOW = 1440  # trailing M1 bars (about one trading day)
JUMP_FACTOR = 20.0
TOP = 10


def _ny(ts) -> pd.Series:
    return pd.Series(pd.DatetimeIndex(ts).tz_convert(MARKET_TZ))


def _stamp(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%d %H:%M")


def _by_year(values: pd.Series, years: pd.Series) -> dict[str, int]:
    return {str(y): int(v) for y, v in values.groupby(years.to_numpy()).sum().items()}


def coverage(m1: pd.DataFrame) -> dict:
    years = m1["ts_utc"].dt.year
    return {
        "range_utc": [m1["ts_utc"].iloc[0].isoformat(), m1["ts_utc"].iloc[-1].isoformat()],
        "bars": len(m1),
        "bars_per_year": {str(y): int(n) for y, n in years.value_counts().sort_index().items()},
    }


def gaps(ts: pd.Series, instrument: Instrument) -> dict:
    """Expected trading minutes without a bar, as runs of consecutive minutes."""
    grid = pd.date_range(ts.iloc[0], ts.iloc[-1], freq="1min")
    expected = grid[is_open(grid, instrument)].asi8
    present = ts.to_numpy().astype("datetime64[ns]").astype(np.int64)
    pos = np.clip(np.searchsorted(present, expected), 0, len(present) - 1)
    missing = expected[present[pos] != expected]
    out = {"expected_minutes": int(len(expected)), "missing_minutes": int(len(missing))}
    if not len(missing):
        return out | {"by_class": {}, "by_year": {}, "longest_mid_session": []}

    step = M1.value
    starts = np.flatnonzero(np.r_[True, np.diff(missing) != step])
    ends = np.r_[starts[1:], len(missing)] - 1
    run_start = pd.DatetimeIndex(missing[starts], tz="UTC")
    run_end = pd.DatetimeIndex(missing[ends], tz="UTC")
    minutes = ends - starts + 1
    before_closed = ~is_open(run_start - M1, instrument)
    after_closed = ~is_open(run_end + M1, instrument)
    ny_day = _ny(run_start).dt.tz_localize(None).dt.normalize()
    holidays = market_holidays(int(ny_day.dt.year.min()), int(ny_day.dt.year.max()))
    cls = np.where(
        ny_day.isin(holidays).to_numpy(),
        "holiday",
        np.where(before_closed | after_closed, "session_edge", "mid_session"),
    )
    runs = pd.DataFrame(
        {"start": run_start, "end": run_end, "minutes": minutes, "cls": cls, "year": run_start.year}
    )
    by_class = runs.groupby("cls")["minutes"].agg(["size", "sum"])
    by_year = runs.pivot_table(index="year", columns="cls", values="minutes", aggfunc="sum")
    mid = runs[runs["cls"] == "mid_session"].sort_values(
        ["minutes", "start"], ascending=[False, True]
    )
    return out | {
        "by_class": {
            c: {"runs": int(r["size"]), "minutes": int(r["sum"])} for c, r in by_class.iterrows()
        },
        "by_year": {
            str(y): {c: int(v) for c, v in row.dropna().items()} for y, row in by_year.iterrows()
        },
        "longest_mid_session": [
            {
                "start_utc": _stamp(r.start),
                "start_ny": _stamp(r.start.tz_convert(MARKET_TZ)),
                "minutes": int(r.minutes),
            }
            for r in mid.head(TOP).itertuples()
        ],
    }


def closed_hour_bars(ts: pd.Series, instrument: Instrument) -> dict:
    closed = ~is_open(ts, instrument)
    ny = _ny(ts[closed])
    slots = (ny.dt.day_name().str[:3] + " " + ny.dt.strftime("%H:00")).value_counts()
    return {
        "bars": int(closed.sum()),
        "by_year": _by_year(pd.Series(closed.astype(int)), ts.dt.year),
        "top_ny_slots": {
            k: int(v)
            for k, v in slots.sort_index()
            .sort_values(ascending=False, kind="stable")
            .head(TOP)
            .items()
        },
    }


def week_boundaries(ts: pd.Series) -> dict:
    """Most common New York time of each week's first and last bar, per year."""
    gap = ts.diff() >= pd.Timedelta(hours=24)
    first = ts[gap.to_numpy()]
    last = ts[np.r_[gap.to_numpy()[1:], False]]
    out = {}
    for name, s in (("first_bar_ny", first), ("last_bar_ny", last)):
        ny = _ny(s)
        label = ny.dt.day_name().str[:3] + " " + ny.dt.strftime("%H:%M")
        out[name] = {
            str(y): label[ny.dt.year.to_numpy() == y].value_counts().sort_index().idxmax()
            for y in sorted(ny.dt.year.unique())
        }
    return out


def flat_bars(m1: pd.DataFrame) -> dict[str, float]:
    flat = (m1["high"] == m1["low"]).astype(float)
    return {
        str(y): round(float(v), 4) for y, v in flat.groupby(m1["ts_utc"].dt.year).mean().items()
    }


def jumps(m1: pd.DataFrame) -> dict:
    """One-minute returns and ranges above ``JUMP_FACTOR`` times the trailing day's mean."""
    consecutive = (m1["ts_utc"].diff() == M1).to_numpy()
    r = np.log(m1["close"]).diff().abs().where(consecutive)
    rng = (m1["high"] - m1["low"]) / m1["close"]
    out = {"window_bars": JUMP_WINDOW, "factor": JUMP_FACTOR}
    for name, x in (("return", r), ("range", rng)):
        scale = x.rolling(JUMP_WINDOW, min_periods=JUMP_WINDOW // 4).mean().shift(1)
        ratio = x / scale
        hit = (ratio > JUMP_FACTOR).fillna(False)
        top = ratio[hit].sort_values(ascending=False, kind="stable").head(TOP)
        out[name] = {
            "count": int(hit.sum()),
            "by_year": {
                k: v for k, v in _by_year(hit.astype(int), m1["ts_utc"].dt.year).items() if v
            },
            "top": [
                {
                    "ts_utc": _stamp(m1["ts_utc"].iloc[i]),
                    "ts_ny": _stamp(m1["ts_utc"].iloc[i].tz_convert(MARKET_TZ)),
                    "times_mean": round(float(ratio.iloc[i]), 1),
                }
                for i in top.index
            ],
        }
    return out


def spread(m1: pd.DataFrame, instrument: Instrument) -> dict:
    s = m1["spread"]
    year = m1["ts_utc"].dt.year
    by_year = {}
    for y, g in s.groupby(year.to_numpy()):
        present = g.dropna()
        q = (
            present.quantile([0.5, 0.9, 0.99])
            if len(present)
            else pd.Series(np.nan, [0.5, 0.9, 0.99])
        )
        by_year[str(y)] = {
            "median": round(float(q[0.5]), 5),
            "p90": round(float(q[0.9]), 5),
            "p99": round(float(q[0.99]), 5),
            "zero_share": round(float((present == 0).mean()), 4) if len(present) else None,
            "missing_share": round(float(g.isna().mean()), 4),
        }
    hour = _ny(m1["ts_utc"]).dt.hour.to_numpy()
    last_year = int(year.iloc[-1]) - 1
    recent = (year == last_year).to_numpy()
    return {
        "units": "price",
        "point": instrument.point,
        "by_year": by_year,
        "median_by_ny_hour": {
            "all": {str(h): round(float(v), 5) for h, v in s.groupby(hour).median().items()},
            str(last_year): {
                str(h): round(float(v), 5)
                for h, v in s[recent].groupby(hour[recent]).median().items()
            },
        },
    }


def _dst_mismatch(ts: pd.DatetimeIndex) -> np.ndarray:
    athens = ts.tz_convert(splits().server_tz).tz_localize(None)
    ny = ts.tz_convert(MARKET_TZ).tz_localize(None)
    return np.asarray((athens - ny) != pd.Timedelta(hours=7))


def clock_check(m1: pd.DataFrame) -> dict:
    """Where the largest one-minute range of each first Friday 07:30-09:30 New York falls."""
    m1 = m1.reset_index(drop=True)  # also called on a slice (one clock segment)
    ny = _ny(m1["ts_utc"])
    wall = ny.dt.tz_localize(None)
    day = wall.dt.normalize()
    mins = (wall.dt.hour * 60 + wall.dt.minute).to_numpy()
    first_friday = ((wall.dt.dayofweek == 4) & (wall.dt.day <= 7)).to_numpy()
    window = first_friday & (mins >= 7 * 60 + 30) & (mins <= 9 * 60 + 30)
    sub = pd.DataFrame(
        {"day": day[window], "mins": mins[window], "range": (m1["high"] - m1["low"])[window]}
    )
    if sub.empty:
        return {"days": 0}
    peak = sub.loc[sub.groupby("day")["range"].idxmax()]
    aligned = peak["mins"].to_numpy() == 8 * 60 + 30
    mismatch = _dst_mismatch(m1["ts_utc"][peak.index].pipe(pd.DatetimeIndex))
    when = peak["mins"].map(lambda m: f"{m // 60:02d}:{m % 60:02d}")
    return {
        "days": int(len(peak)),
        "peak_at_0830_share": round(float(aligned.mean()), 3),
        "dst_mismatch_days": int(mismatch.sum()),
        "dst_mismatch_peak_at_0830": int(aligned[mismatch].sum()),
        "peak_time_counts": {k: int(v) for k, v in when.value_counts().head(5).items()},
    }


def clock_segments(m1: pd.DataFrame, segments: list[dict]) -> list[dict]:
    """The importer's clock segments, each confirmed by the jobs-report check on its corrected
    bars."""
    out = []
    for seg in segments:
        shift = pd.Timedelta(hours=seg["offset_hours"])
        lo = pd.Timestamp(seg["from_utc_as_parsed"]) - shift
        hi = pd.Timestamp(seg["to_utc_as_parsed"]) - shift
        part = m1[(m1["ts_utc"] >= lo) & (m1["ts_utc"] <= hi)]
        check = clock_check(part) if len(part) else {"days": 0}
        out.append(
            seg
            | {
                "from_utc": _stamp(lo),
                "to_utc": _stamp(hi),
                "jobs_report_days": check["days"],
                "peak_at_0830_share": check.get("peak_at_0830_share"),
            }
        )
    return out


def build(symbol: str, store: Path = STORE) -> dict:
    instrument = instruments()[symbol]
    imported = json.loads((store / symbol / "import.json").read_text(encoding="utf-8"))
    cols = ["ts_utc", "open", "high", "low", "close", "spread"]
    m1 = pd.read_parquet(store / symbol / "m1.parquet", columns=cols)
    ts = m1["ts_utc"]
    return {
        "report_version": REPORT_VERSION,
        "symbol": symbol,
        "input": imported["input"],
        "import_rejects": imported["parse"]["rejected_by_reason"],
        "m1_content_sha256": imported["frames"]["m1"]["content_sha256"],
        "session_config": {
            "week_open_ny": f"Sun {instrument.week_open}",
            "week_close_ny": f"Fri {instrument.week_close}",
            "daily_break_ny": list(instrument.daily_break) if instrument.daily_break else None,
        },
        "coverage": coverage(m1),
        "gaps": gaps(ts, instrument),
        "closed_hour_bars": closed_hour_bars(ts, instrument),
        "week_boundaries": week_boundaries(ts),
        "flat_bars_share": flat_bars(m1),
        "jumps": jumps(m1),
        "spread": spread(m1, instrument),
        "clock_check": clock_check(m1),
        "clock_segments": clock_segments(m1, imported.get("clock_segments", [])),
    }


def _mismatch_cell(m: dict) -> str:
    if "range_0830_x_median" not in m:
        return f"too few weekdays ({m.get('weekdays', 0)})"
    return (
        f"{m['extra_offset_hours']:+d}, {m['range_0830_x_median']}× / {m['range_0930_x_median']}×"
        f" ({m['weekdays']} days)"
    )


def _table(head: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(head) + " |", "|" + " --- |" * len(head)]
    return lines + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]


def render(r: dict) -> str:
    g, cov, sp, clk = r["gaps"], r["coverage"], r["spread"], r["clock_check"]
    cls = g.get("by_class", {})
    mid = cls.get("mid_session", {}).get("minutes", 0)
    years = list(cov["bars_per_year"])
    lines = [
        f"# Data quality: {r['symbol']} (FxPro MT5 M1)",
        "",
        "_Generated by `python -m app quality`; do not edit by hand. The JSON next to this file has"
        " every number below._",
        "",
        "## Summary",
        "",
        *_table(
            ["Item", "Value"],
            [
                ["Input", f"`{r['input']['file']}`, {r['input']['bytes_read']:,} bytes read"],
                ["SHA-256 of the bytes read", f"`{r['input']['sha256_of_bytes_read']}`"],
                ["Stopped at the lockbox", r["input"]["stopped_at_lockbox"]],
                [
                    "Range (UTC, bar open)",
                    " → ".join(x[:16].replace("T", " ") for x in cov["range_utc"]),
                ],
                ["M1 bars", f"{cov['bars']:,}"],
                ["Rows rejected at import", r["import_rejects"] or "none"],
                [
                    "Expected trading minutes without a bar",
                    f"{g['missing_minutes']:,} of {g['expected_minutes']:,}",
                ],
                ["… of which mid-session", f"{mid:,} ({mid / max(g['expected_minutes'], 1):.3%})"],
                ["Bars in closed hours", f"{r['closed_hour_bars']['bars']:,}"],
                [
                    "Return / range jumps",
                    f"{r['jumps']['return']['count']} / {r['jumps']['range']['count']}",
                ],
                [
                    "Clock check (first Fridays, peak at 08:30 NY)",
                    f"{clk.get('peak_at_0830_share', 0):.0%} of {clk['days']} days",
                ],
                [
                    "… in US/EU DST mismatch weeks",
                    f"{clk.get('dst_mismatch_peak_at_0830', 0)}"
                    f" of {clk.get('dst_mismatch_days', 0)}",
                ],
                ["M1 content hash", f"`{r['m1_content_sha256']}`"],
            ],
        ),
        "",
        "## Session config (New York time)",
        "",
        f"Week open {r['session_config']['week_open_ny']}, week close"
        f" {r['session_config']['week_close_ny']}, daily break"
        f" {r['session_config']['daily_break_ny'] or 'none'}.",
        "",
        *_table(
            ["Year", "Bars", "First bar of the week (NY)", "Last bar of the week (NY)"],
            [
                [
                    y,
                    f"{cov['bars_per_year'][y]:,}",
                    r["week_boundaries"]["first_bar_ny"].get(y, ""),
                    r["week_boundaries"]["last_bar_ny"].get(y, ""),
                ]
                for y in years
            ],
        ),
        "",
        "## Missing trading minutes",
        "",
        *_table(
            ["Class", "Runs", "Minutes"],
            [[c, f"{v['runs']:,}", f"{v['minutes']:,}"] for c, v in cls.items()],
        ),
        "",
        *_table(
            ["Year", "holiday", "session_edge", "mid_session"],
            [
                [
                    y,
                    *(
                        f"{g['by_year'].get(y, {}).get(c, 0):,}"
                        for c in ("holiday", "session_edge", "mid_session")
                    ),
                ]
                for y in years
            ],
        ),
        "",
        "Longest mid-session holes:",
        "",
        *_table(
            ["Start (UTC)", "Start (NY)", "Minutes"],
            [
                [x["start_utc"], x["start_ny"], x["minutes"]]
                for x in g.get("longest_mid_session", [])
            ],
        ),
        "",
        "## Bars in closed hours",
        "",
        *_table(
            ["NY slot", "Bars"],
            [[k, f"{v:,}"] for k, v in r["closed_hour_bars"]["top_ny_slots"].items()],
        ),
        "",
        "## Spread (price units)",
        "",
        *_table(
            ["Year", "Median", "p90", "p99", "Zero", "Missing", "Flat bars"],
            [
                [
                    y,
                    v["median"],
                    v["p90"],
                    v["p99"],
                    v["zero_share"],
                    v["missing_share"],
                    r["flat_bars_share"].get(y, ""),
                ]
                for y, v in sp["by_year"].items()
            ],
        ),
        "",
        "Median by New York hour:",
        "",
        *_table(
            ["Hour", *sp["median_by_ny_hour"]],
            [
                [h, *(sp["median_by_ny_hour"][k].get(h, "") for k in sp["median_by_ny_hour"])]
                for h in sp["median_by_ny_hour"]["all"]
            ],
        ),
        "",
        f"## Jumps (one-minute value above {r['jumps']['factor']:g}× the trailing"
        f" {r['jumps']['window_bars']}-bar mean)",
        "",
    ]
    for name in ("return", "range"):
        j = r["jumps"][name]
        lines += [
            f"**{name.capitalize()}:** {j['count']} flags; by year {j['by_year'] or 'none'}.",
            "",
            *_table(
                ["UTC", "NY", "× mean"],
                [[x["ts_utc"], x["ts_ny"], x["times_mean"]] for x in j["top"]],
            ),
            "",
        ]
    lines += [
        "## Clock check",
        "",
        "Largest one-minute range on first Fridays, 07:30-09:30 New York (the US jobs report is at"
        " 08:30). Most common peak times: "
        + ", ".join(f"{k} ({v})" for k, v in clk.get("peak_time_counts", {}).items())
        + ".",
        "",
        "## Clock segments (corrected at import)",
        "",
        "Offset = hours by which the export's clock was ahead of `Europe/Athens` (from the weekly"
        " open, `app.data.clock`); the bars were moved back by it. Mismatch weeks = the weeks when"
        " US and EU daylight saving disagree: the extra hour they were moved by, from the 08:30 New"
        " York release spike (range at 08:30 / 09:30 as a multiple of the median 07:00-10:00"
        " range). The jobs-report check is run on the corrected bars of each segment.",
        "",
        *_table(
            [
                "From (UTC)",
                "To (UTC)",
                "Offset (h)",
                "Weeks",
                "Weeks agreeing",
                "Mismatch weeks: extra (h), 08:30 / 09:30 spike",
                "Jobs-report peak at 08:30",
            ],
            [
                [
                    s["from_utc"],
                    s["to_utc"],
                    f"{s['offset_hours']:+d}",
                    s["weeks"],
                    f"{s['weeks_agreeing']} of {s['weeks_with_evidence']}",
                    _mismatch_cell(s.get("mismatch_weeks", {})),
                    "n/a"
                    if s["peak_at_0830_share"] is None
                    else f"{s['peak_at_0830_share']:.0%} of {s['jobs_report_days']}",
                ]
                for s in r["clock_segments"]
            ],
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--symbol", action="append", help="default: every instrument in the store")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    symbols = args.symbol or sorted(
        p.parent.name for p in args.store.glob("*/import.json") if p.parent.name in instruments()
    )
    if not symbols:
        print(f"no imported instrument in {args.store}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for symbol in symbols:
        r = build(symbol, args.store)
        (args.out / f"{symbol}.json").write_text(
            json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        (args.out / f"{symbol}.md").write_text(render(r) + "\n", encoding="utf-8", newline="\n")
        g = r["gaps"]
        print(
            f"{symbol}: {g['missing_minutes']:,} missing trading minutes "
            f"{ {k: v['minutes'] for k, v in g.get('by_class', {}).items()} }, "
            f"{r['closed_hour_bars']['bars']:,} bars in closed hours, clock check "
            f"{r['clock_check'].get('peak_at_0830_share')}"
        )
    return 0
