"""Detect and correct periods where an export's clock is off ``Europe/Athens`` by whole hours.

Some FxPro histories were stored on an older server clock: before 2023, GBPUSD, USDJPY, AUDUSD
and USDCAD are about one hour off (``docs/data_quality/README.md``). The evidence is the weekly
open: on the server clock the market opens every week at the same time (the configured New York
open + 7 h, e.g. Monday 00:00 for FX and 01:00 for gold), so a week whose first bar comes a whole
number of hours earlier or later was stamped on a shifted clock.

The rule:

1. Each week starts at the first bar after a break of 24 h or more (and at the first bar of the
   file). Its open is the first bar of the week followed by trading (``OPEN_MIN_BARS`` bars within
   an hour), so stray ticks before the open are skipped. The week's offset is the open's server
   time minus the expected open, rounded to the hour. A week open can also come early because a
   pair starts trading early (AUDUSD), so each week is then checked with the US 08:30 New York
   releases (weekly jobless claims and others) on the week moved by that offset: if the mean
   one-minute range at 07:30 or 09:30 New York is at least ``SPIKE_FACTOR`` times the week's
   median 07:00-10:00 range and the other two, the week takes one hour less or more.
   Weeks more than 3 h 15 min off (holiday weeks opening on a weekday) or with fewer than half
   the median week's bars (sparse data, whose first bar is a late tick) give no evidence and take
   the offset of the week before.
2. Runs of fewer than ``MIN_RUN_WEEKS`` consecutive weeks with the same offset are noise (a late
   first tick; gold, which opens on New York time, in the weeks when US and EU daylight saving
   disagree) and take the offset of the nearest run of at least that length before them (after
   them at the start of the file).
3. Every bar of a week is moved by minus that week's offset. Weeks are separated by the weekend,
   so moving a whole week by an hour or two can never reorder or merge bars.
4. The week open cannot tell which daylight-saving rule a clock follows: FxPro opens FX at Monday
   00:00 on its own clock whatever the rule. So within each segment the weeks when US and EU
   daylight saving disagree (the "mismatch weeks", about three a year) are checked with the US
   08:30 New York releases (jobless claims, jobs report, CPI): the mean one-minute range at 07:30,
   08:30 and 09:30 New York on their weekdays, as a multiple of the median 07:00-10:00 range. If
   07:30 or 09:30 is at least ``SPIKE_FACTOR`` times the median and the 08:30 value, the segment's
   mismatch weeks are moved by one more hour (later or earlier). Since late 2021 the four pairs
   above follow US daylight saving (New York + 7 h), which only shows in these weeks. Mismatch
   periods start and end on weekend nights, so this move cannot reorder bars either.

Steps 1-3 were set after looking at the week-open pattern of all six exports, step 4 after looking
at the release spikes, and the stray-tick and weekly release-spike checks of step 1 after the
Dukascopy cross-check showed two AUDUSD weeks moved by mistake (all on 2026-10-22). The
segments, with their evidence, go into ``import.json``; the data-quality report confirms each one
with the US jobs-report spike (08:30 New York), and the Dukascopy cross-check with an independent
feed."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import Instrument
from app.data.sessions import hhmm_minutes

MIN_RUN_WEEKS = 4
MAX_EVIDENCE_MINUTES = 3 * 60 + 15
MIN_BARS_SHARE = 0.5  # a week with fewer bars than this share of the median week is too sparse
OPEN_MIN_BARS = 20  # the week opens at the first bar followed by this many bars within an hour
WEEK_BREAK = pd.Timedelta(hours=24)
SERVER_TO_NY_HOURS = 7  # the server clock is New York + 7 h outside the DST-mismatch weeks
SPIKE_FACTOR = 2.0
MIN_MISMATCH_WEEKDAYS = 5
MARKET_TZ = "America/New_York"


def week_starts(ts: pd.Series) -> np.ndarray:
    """Positions of the first bar of each week."""
    return np.flatnonzero(np.r_[True, (ts.diff() >= WEEK_BREAK).to_numpy()[1:]])


def sustained_open(ts: pd.Series, starts: np.ndarray) -> np.ndarray:
    """For each week, the first bar followed by trading (``OPEN_MIN_BARS`` bars within the next
    hour), so a few stray ticks before the real open do not count as the open. Falls back to the
    week's first bar when no bar of the week qualifies."""
    t = ts.to_numpy().astype("datetime64[ns]").astype(np.int64)
    ahead = np.searchsorted(t, t + pd.Timedelta(hours=1).value) - np.arange(len(t))
    # the next qualifying position at or after each position (len(t) when there is none)
    pos = np.where(ahead >= OPEN_MIN_BARS, np.arange(len(t)), len(t))
    nxt = np.minimum.accumulate(pos[::-1])[::-1]
    ends = np.r_[starts[1:], len(t)]
    picked = nxt[starts]
    return np.where(picked < ends, picked, starts)


def weekly_spike(
    bars: pd.DataFrame, starts: np.ndarray, weekly: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per week, the extra hour the US 08:30 New York releases call for once the week is moved by
    ``weekly`` (+1 when the week's spike sits clearly at 09:30, -1 at 07:30, 0 at 08:30), and
    whether the spike was clear at all (no correction is taken from an unclear week)."""
    n = len(bars)
    week = np.searchsorted(starts, np.arange(n), side="right") - 1
    ts = bars["ts_utc"] - pd.to_timedelta(weekly[week], unit="h")
    ny = ts.dt.tz_convert(MARKET_TZ)
    mins = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    sel = (ny.dt.dayofweek < 5).to_numpy() & (mins >= 7 * 60) & (mins <= 10 * 60)
    rel = ((bars["high"] - bars["low"]) / bars["close"]).to_numpy()
    df = pd.DataFrame({"week": week[sel], "m": mins[sel], "r": rel[sel]})
    med = df.groupby("week")["r"].median()
    spikes = df[df["m"].isin([450, 510, 570])].pivot_table(
        index="week", columns="m", values="r", aggfunc="mean"
    )
    adj = np.zeros(len(starts), dtype=int)
    is_clear = np.zeros(len(starts), dtype=bool)
    if spikes.empty or spikes.shape[1] < 3:
        return adj, is_clear
    ratio = spikes.reindex(columns=[450, 510, 570]).div(med.reindex(spikes.index), axis=0).dropna()
    top = ratio.max(axis=1)
    second = pd.Series(np.sort(ratio.to_numpy(), axis=1)[:, -2], index=ratio.index)
    clear = (top >= SPIKE_FACTOR) & (top >= SPIKE_FACTOR * second)
    label = ratio.idxmax(axis=1).map({450: -1, 510: 0, 570: 1})
    adj[label.index[clear].to_numpy()] = label[clear].to_numpy()
    is_clear[label.index[clear].to_numpy()] = True
    return adj, is_clear


def detect(bars: pd.DataFrame | pd.Series, instrument: Instrument, server_tz: str) -> list[dict]:
    """Clock segments: consecutive weeks with one offset (hours), with the evidence for each.
    ``bars`` with ``high``, ``low`` and ``close`` adds the weekly release-spike evidence; a bare
    timestamp series uses the week open only."""
    ts = bars if isinstance(bars, pd.Series) else bars["ts_utc"]
    if ts.empty:
        return []
    starts = week_starts(ts)
    first = ts.iloc[sustained_open(ts, starts)]
    server = first.dt.tz_convert(server_tz)
    since_sunday = ((server.dt.dayofweek + 1) % 7) * 1440 + server.dt.hour * 60 + server.dt.minute
    expected = hhmm_minutes(instrument.week_open) + SERVER_TO_NY_HOURS * 60
    off = (since_sunday - expected).to_numpy()
    per_week = np.diff(np.r_[starts, len(ts)])
    dense = per_week >= MIN_BARS_SHARE * np.median(per_week)
    evidence = (np.abs(off) <= MAX_EVIDENCE_MINUTES) & dense
    hours = pd.Series(np.where(evidence, np.round(off / 60), np.nan)).ffill().bfill().fillna(0)
    weekly = hours.astype(int).to_numpy().copy()
    spike = np.zeros(len(starts), dtype=int)
    if isinstance(bars, pd.DataFrame) and {"high", "low", "close"} <= set(bars.columns):
        spike, _ = weekly_spike(bars, starts, weekly)
        weekly += spike
    # Mismatch weeks (step 4) do not set segment boundaries: they take the week before them.
    mismatch_week = dst_mismatch(ts.iloc[starts], server_tz)
    weekly = (
        (pd.Series(np.where(mismatch_week, np.nan, weekly)).ffill().bfill().fillna(0).astype(int))
        .to_numpy()
        .copy()
    )

    # A short run takes the offset of the nearest long run before it (or after it, at the start);
    # with no long run at all, every week takes the most common offset.
    run_id = np.r_[0, np.cumsum(weekly[1:] != weekly[:-1])]
    sizes = np.bincount(run_id)
    value = np.array([weekly[run_id == r][0] for r in range(len(sizes))])
    long = np.flatnonzero(sizes >= MIN_RUN_WEEKS)
    if not len(long):
        weekly[:] = np.bincount(weekly - weekly.min()).argmax() + weekly.min()
    else:
        for r in np.flatnonzero(sizes < MIN_RUN_WEEKS):
            before = long[long < r]
            weekly[run_id == r] = value[before[-1] if len(before) else long[long > r][0]]

    run_id = np.r_[0, np.cumsum(weekly[1:] != weekly[:-1])]
    segments = []
    for r in range(run_id.max() + 1):
        rows = np.flatnonzero(run_id == r)
        raw = np.round(off[rows] / 60)
        agree = evidence[rows] & (raw == weekly[rows[0]])
        last = starts[rows[-1] + 1] - 1 if rows[-1] + 1 < len(starts) else len(ts) - 1
        segments.append(
            {
                "from_utc_as_parsed": ts.iloc[starts[rows[0]]].isoformat(),
                "to_utc_as_parsed": ts.iloc[last].isoformat(),
                "offset_hours": int(weekly[rows[0]]),
                "weeks": int(len(rows)),
                "weeks_with_evidence": int(evidence[rows].sum()),
                "weeks_agreeing": int(agree.sum()),
                "weeks_moved_by_release_spike": int((spike[rows] != 0).sum()),
            }
        )
    return segments


def apply(bars: pd.DataFrame, segments: list[dict]) -> pd.DataFrame:
    """Move each segment's bars by minus its offset. Segments with offset 0 are left untouched."""
    out = bars.copy()
    ts = out["ts_utc"]
    for seg in segments:
        if not seg["offset_hours"]:
            continue
        rows = (ts >= pd.Timestamp(seg["from_utc_as_parsed"])) & (
            ts <= pd.Timestamp(seg["to_utc_as_parsed"])
        )
        out.loc[rows, "ts_utc"] = ts[rows] - pd.Timedelta(hours=seg["offset_hours"])
    if not out["ts_utc"].is_monotonic_increasing or out["ts_utc"].duplicated().any():
        raise ValueError("clock correction reordered bars; a segment does not end at a weekend")
    return out


def dst_mismatch(ts: pd.Series, server_tz: str) -> np.ndarray:
    """True where the server zone is not New York + 7 h (US and EU daylight saving disagree)."""
    server = ts.dt.tz_convert(server_tz).dt.tz_localize(None)
    ny = ts.dt.tz_convert(MARKET_TZ).dt.tz_localize(None)
    return ((server - ny) != pd.Timedelta(hours=SERVER_TO_NY_HOURS)).to_numpy()


def _segment_rows(ts: pd.Series, seg: dict) -> np.ndarray:
    """Rows of ``seg`` in bars already moved by its offset."""
    shift = pd.Timedelta(hours=seg["offset_hours"])
    lo = pd.Timestamp(seg["from_utc_as_parsed"]) - shift
    hi = pd.Timestamp(seg["to_utc_as_parsed"]) - shift
    return ((ts >= lo) & (ts <= hi)).to_numpy()


def check_mismatch_weeks(bars: pd.DataFrame, segments: list[dict], server_tz: str) -> list[dict]:
    """Step 4: the extra hour, if any, for each mismatch week (bars after step 3). A week with a
    clear release spike is decided by its own spike; otherwise by all the segment's mismatch weeks
    together."""
    ts = bars["ts_utc"]
    ny = ts.dt.tz_convert(MARKET_TZ)
    mins = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    weekday = (ny.dt.dayofweek < 5).to_numpy()
    rel = ((bars["high"] - bars["low"]) / bars["close"]).to_numpy()
    mismatch = dst_mismatch(ts, server_tz)
    day = ny.dt.normalize().to_numpy()
    starts = week_starts(ts)
    ends = np.r_[starts[1:], len(ts)] - 1
    week_adj, week_clear = weekly_spike(bars, starts, np.zeros(len(starts), dtype=int))
    out = []
    for seg in segments:
        rows = _segment_rows(ts, seg)
        base = rows & mismatch & weekday
        days = len(np.unique(day[base & (mins == 8 * 60 + 30)]))
        window = base & (mins >= 7 * 60) & (mins <= 10 * 60)
        check = {"weekdays": int(days), "extra_offset_hours": 0}
        if days >= MIN_MISMATCH_WEEKDAYS and window.any():
            med = np.median(rel[window])
            ratio = {t: float(rel[base & (mins == t)].mean() / med) for t in (450, 510, 570)}
            check |= {f"range_{t // 60:02d}30_x_median": round(r, 2) for t, r in ratio.items()}
            for minute, extra in ((570, 1), (450, -1)):  # spike late: clock ahead by one more hour
                r = ratio[minute]
                if r >= SPIKE_FACTOR and r >= SPIKE_FACTOR * ratio[510]:
                    check["extra_offset_hours"] = extra
        weeks = []
        for w in np.flatnonzero(mismatch[starts] & rows[starts]):
            own = bool(week_clear[w])
            weeks.append(
                {
                    "first_bar_utc": ts.iloc[starts[w]].isoformat(),
                    "last_bar_utc": ts.iloc[ends[w]].isoformat(),
                    "extra_offset_hours": int(week_adj[w]) if own else check["extra_offset_hours"],
                    "decided_by": "week" if own else "segment",
                }
            )
        out.append(seg | {"mismatch_weeks": check | {"weeks": weeks}})
    return out


def apply_mismatch_weeks(bars: pd.DataFrame, segments: list[dict], server_tz: str) -> pd.DataFrame:
    """Move each mismatch week's bars by minus its extra offset."""
    out = bars.copy()
    ts = out["ts_utc"]
    for seg in segments:
        for week in seg["mismatch_weeks"]["weeks"]:
            if week["extra_offset_hours"]:
                lo, hi = pd.Timestamp(week["first_bar_utc"]), pd.Timestamp(week["last_bar_utc"])
                rows = (ts >= lo) & (ts <= hi)
                out.loc[rows, "ts_utc"] = ts[rows] - pd.Timedelta(hours=week["extra_offset_hours"])
    if not out["ts_utc"].is_monotonic_increasing or out["ts_utc"].duplicated().any():
        raise ValueError("mismatch-week correction reordered bars")
    return out
