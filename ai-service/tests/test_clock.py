import pandas as pd
import pytest

from app.config import instruments
from app.data import clock

EUR = instruments()["EURUSD"]
XAU = instruments()["XAUUSD"]
TZ = "Europe/Athens"


def weeks(
    first_sunday: str, n: int, open_clock: str = TZ, open_time: str = "00:00"
) -> pd.DataFrame:
    """Bars every 30 min for ``n`` five-day weeks. FxPro FX opens Monday 00:00 on the server
    clock every week; gold opens at a fixed New York time (Sunday 18:00)."""
    parts = []
    for k in range(n):
        sunday = pd.Timestamp(first_sunday) + pd.Timedelta(weeks=k)
        day = sunday + pd.Timedelta(days=1) if open_clock == TZ else sunday
        start = pd.Timestamp(f"{day:%Y-%m-%d} {open_time}", tz=open_clock)
        end = start + pd.Timedelta(days=5) - pd.Timedelta(hours=1, minutes=30)
        parts.append(pd.Series(pd.date_range(start, end, freq="30min").tz_convert("UTC")))
    ts = pd.DatetimeIndex(pd.concat(parts)).as_unit("ns")
    return pd.DataFrame({"ts_utc": ts, "close": range(len(ts))})


def shifted(bars: pd.DataFrame, hours: int, lo: str, hi: str) -> pd.DataFrame:
    out = bars.copy()
    ts = out["ts_utc"]
    rows = (ts >= pd.Timestamp(lo, tz="UTC")) & (ts < pd.Timestamp(hi, tz="UTC"))
    out.loc[rows, "ts_utc"] = ts[rows] + pd.Timedelta(hours=hours)
    return out


def _runs(segs: list[dict]) -> list[tuple[int, int]]:
    return [(s["offset_hours"], s["weeks"]) for s in segs]


def test_a_clean_export_is_one_zero_segment_across_dst_mismatch_weeks() -> None:
    clean = weeks("2023-02-26", 8)  # includes 2023-03-12 .. 03-26 (US on DST, EU not yet)
    segs = clock.detect(clean["ts_utc"], EUR, TZ)
    assert _runs(segs) == [(0, 8)]
    pd.testing.assert_frame_equal(clock.apply(clean, segs), clean)


def test_gold_opening_on_new_york_time_is_not_corrected() -> None:
    gold = weeks("2023-02-26", 8, "America/New_York", "18:00")  # mismatch weeks look 1 h early
    assert _runs(clock.detect(gold["ts_utc"], XAU, TZ)) == [(0, 8)]


def test_shifted_periods_are_found_and_moved_back() -> None:
    clean = weeks("2021-09-05", 20)
    raw = shifted(clean, +1, "2021-09-01", "2021-10-24")  # 7 weeks one hour ahead
    raw = shifted(raw, -1, "2021-11-21", "2022-01-30")  # 9 weeks one hour behind
    segs = clock.detect(raw["ts_utc"], EUR, TZ)
    assert _runs(segs) == [(1, 7), (0, 4), (-1, 9)]
    assert segs[0]["weeks_agreeing"] == 7
    pd.testing.assert_frame_equal(clock.apply(raw, segs), clean)


def test_runs_shorter_than_four_weeks_are_noise() -> None:
    clean = weeks("2021-09-05", 12)
    raw = shifted(clean, +1, "2021-10-01", "2021-10-16")  # two weeks only
    assert _runs(clock.detect(raw["ts_utc"], EUR, TZ)) == [(0, 12)]


def test_a_week_opening_on_a_weekday_gives_no_evidence() -> None:
    clean = weeks("2021-09-05", 6)
    third = clean["ts_utc"] >= clean["ts_utc"].iloc[0] + pd.Timedelta(weeks=2)
    first = clean.index[third][0]
    holiday = clean[~(third & (clean.index < first + 100))]  # that week opens on Wednesday
    segs = clock.detect(holiday["ts_utc"], EUR, TZ)
    assert [(s["offset_hours"], s["weeks"], s["weeks_with_evidence"]) for s in segs] == [(0, 6, 5)]


def test_a_sparse_week_gives_no_evidence() -> None:
    clean = weeks("2021-09-05", 12)
    ts = clean["ts_utc"]
    lo, hi = ts.iloc[0] + pd.Timedelta(weeks=5), ts.iloc[0] + pd.Timedelta(weeks=9)
    inside = (ts >= lo) & (ts < hi)
    sparse = clean[~inside | (clean.index % 20 == 7)]  # four weeks with 1 bar in 20, first late
    segs = clock.detect(sparse["ts_utc"], EUR, TZ)
    assert [(s["offset_hours"], s["weeks"], s["weeks_with_evidence"]) for s in segs] == [(0, 12, 8)]


def test_a_correction_that_would_reorder_bars_is_refused() -> None:
    bars = weeks("2021-09-05", 2)
    bad = [
        {
            "from_utc_as_parsed": bars["ts_utc"].iloc[5].isoformat(),
            "to_utc_as_parsed": bars["ts_utc"].iloc[-1].isoformat(),
            "offset_hours": 1,  # moves bars 5.. back by 1 h, before bars 3 and 4
        }
    ]
    with pytest.raises(ValueError):
        clock.apply(bars, bad)


def minute_bars(first: str, last: str) -> pd.DataFrame:
    """Weekday M1 bars with a range spike at 08:30 New York every weekday (US releases)."""
    ts = pd.date_range(first, last, freq="1min", tz="UTC")
    ny = ts.tz_convert("America/New_York")
    ts = ts[ny.dayofweek < 5]
    ny = ts.tz_convert("America/New_York")
    spike = (ny.hour == 8) & (ny.minute == 30)
    rng = pd.Series(1.0, index=range(len(ts))).where(~spike, 6.0).to_numpy() * 1e-4
    return pd.DataFrame(
        {"ts_utc": ts.as_unit("ns"), "high": 1.1 + rng, "low": 1.1 - rng, "close": 1.1}
    )


def _whole(bars: pd.DataFrame) -> list[dict]:
    return [
        {
            "from_utc_as_parsed": bars["ts_utc"].iloc[0].isoformat(),
            "to_utc_as_parsed": bars["ts_utc"].iloc[-1].isoformat(),
            "offset_hours": 0,
        }
    ]


def test_mismatch_weeks_on_a_us_dst_clock_are_moved_back() -> None:
    clean = minute_bars("2023-03-06", "2023-04-01")  # US/EU mismatch 2023-03-12 .. 03-26
    mis = clock.dst_mismatch(clean["ts_utc"], TZ)
    raw = clean.copy()
    raw.loc[mis, "ts_utc"] = raw["ts_utc"][mis] + pd.Timedelta(hours=1)  # a New York + 7 h clock
    segs = clock.check_mismatch_weeks(raw, _whole(raw), TZ)
    assert segs[0]["mismatch_weeks"]["extra_offset_hours"] == 1
    assert segs[0]["mismatch_weeks"]["range_0930_x_median"] > 2
    fixed = clock.apply_mismatch_weeks(raw, segs, TZ)
    pd.testing.assert_frame_equal(fixed, clean)


def test_mismatch_weeks_on_the_right_clock_are_left_alone() -> None:
    clean = minute_bars("2023-03-06", "2023-04-01")
    segs = clock.check_mismatch_weeks(clean, _whole(clean), TZ)
    assert segs[0]["mismatch_weeks"]["extra_offset_hours"] == 0
    pd.testing.assert_frame_equal(clock.apply_mismatch_weeks(clean, segs, TZ), clean)


def test_stray_ticks_before_the_open_are_not_the_open() -> None:
    weeks_ = []
    for k in range(6):
        monday = pd.Timestamp("2022-11-07", tz=TZ) + pd.Timedelta(weeks=k)
        stray = pd.Series([monday - pd.Timedelta(minutes=57)])  # Sunday 23:03 server time
        trading = pd.Series(
            pd.date_range(monday, monday + pd.Timedelta(days=4, hours=23), freq="1min")
        )
        weeks_ += [stray, trading]
    ts = pd.Series(pd.DatetimeIndex(pd.concat(weeks_)).tz_convert("UTC").as_unit("ns"))
    assert _runs(clock.detect(ts, EUR, TZ)) == [(0, 6)]


def test_a_week_that_opens_early_but_trades_on_time_is_not_moved() -> None:
    # Six weeks of a pair that sometimes starts trading an hour early (AUDUSD), on the right
    # clock: the US 08:30 release spike says the clock is right, whatever the week open says.
    bars = []
    for k in range(10):
        day = pd.Timestamp("2022-10-03") + pd.Timedelta(weeks=k)
        monday = day.tz_localize(TZ)  # 00:00 on the server clock, across the DST change
        start = monday - pd.Timedelta(hours=1) if k >= 4 else monday
        bars.append(
            pd.Series(pd.date_range(start, monday + pd.Timedelta(days=4, hours=23), freq="1min"))
        )
    ts = pd.DatetimeIndex(pd.concat(bars)).tz_convert("UTC").as_unit("ns")
    ny = ts.tz_convert("America/New_York")
    spike = ((ny.hour == 8) & (ny.minute == 30)).astype(float) * 5 + 1
    df = pd.DataFrame(
        {"ts_utc": ts, "high": 1.1 + spike * 1e-4, "low": 1.1 - spike * 1e-4, "close": 1.1}
    )
    assert _runs(clock.detect(df["ts_utc"], EUR, TZ)) == [
        (0, 5),
        (-1, 5),
    ]  # week open alone; 10-31 is a mismatch week
    segs = clock.detect(df, EUR, TZ)
    assert _runs(segs) == [(0, 10)]
    assert segs[0]["weeks_moved_by_release_spike"] == 6
