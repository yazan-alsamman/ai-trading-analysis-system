import json

import pandas as pd
import pytest

from app.data.aggregate import TIMEFRAMES, aggregate, bucket_start
from app.data.importer import import_symbol
from app.data.mt5 import parse_mt5_text
from app.data.quality import find_gaps
from app.data.schema import INSTRUMENTS, content_hash
from app.data.sessions import dst_mismatch, is_open

XAU = INSTRUMENTS["XAUUSD"]
EUR = INSTRUMENTS["EURUSD"]
HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def row(server: str, o=2000.0, h=2001.0, lo=1999.0, c=2000.5, tv=10, spread=15) -> str:
    ts = pd.Timestamp(server)
    return f"{ts:%Y.%m.%d}\t{ts:%H:%M:%S}\t{o}\t{h}\t{lo}\t{c}\t{tv}\t0\t{spread}"


def export(*rows: str) -> str:
    return "\r\n".join([HEADER, *rows]) + "\r\n"


def series(server_times: list[str]) -> str:
    return export(*(row(t) for t in server_times))


def utc(text: str) -> pd.Timestamp:
    return pd.Timestamp(text, tz="UTC")


def parse(text: str, **kw):
    return parse_mt5_text(text, XAU, last_bar_closed=True, **kw)


# ----------------------------------------------------------------------------------------- timezone


@pytest.mark.parametrize(
    ("server", "expected_utc", "label"),
    [
        # Winter: server UTC+2, New York EST.
        ("2024-01-08 01:00", "2024-01-07 23:00", "winter weekly open, Sun 18:00 EST"),
        ("2024-01-12 23:55", "2024-01-12 21:55", "winter Friday last bar, 16:55 EST"),
        # Summer: server UTC+3, New York EDT.
        ("2024-07-08 01:00", "2024-07-07 22:00", "summer weekly open, Sun 18:00 EDT"),
        ("2024-07-10 15:30", "2024-07-10 12:30", "summer jobs-report time 08:30 EDT"),
        # US already on DST, EU not yet (2024-03-10 .. 2024-03-31): server UTC+2, New York EDT.
        ("2024-03-11 00:00", "2024-03-10 22:00", "mismatch weekly open, Sun 18:00 EDT"),
        ("2024-03-15 22:55", "2024-03-15 20:55", "mismatch Friday last bar, 16:55 EDT"),
        ("2024-03-08 23:55", "2024-03-08 21:55", "week before US DST starts"),
        ("2024-04-01 01:00", "2024-03-31 22:00", "week after EU DST starts"),
        # EU back on winter time, US still on DST (2024-10-27 .. 2024-11-03).
        ("2024-10-28 00:00", "2024-10-27 22:00", "autumn mismatch weekly open"),
        ("2024-11-01 14:30", "2024-11-01 12:30", "autumn mismatch jobs report, 08:30 EDT"),
        ("2024-11-04 01:00", "2024-11-03 23:00", "week after US DST ends"),
    ],
)
def test_server_time_to_utc(server: str, expected_utc: str, label: str) -> None:
    bars = parse(series([server])).bars
    assert bars["ts_utc"].iloc[0] == utc(expected_utc), label
    assert is_open(bars["ts_utc"], XAU.session)[0], label


def test_dst_mismatch_weeks_are_detected() -> None:
    ts = pd.Series(
        [
            utc("2024-03-12 12:00"),
            utc("2024-04-02 12:00"),
            utc("2024-10-29 12:00"),
            utc("2024-11-05 12:00"),
        ]
    )
    assert dst_mismatch(ts).tolist() == [True, False, True, False]


def test_times_skipped_or_repeated_on_the_server_clock_are_rejected() -> None:
    # EU spring forward skips 03:00-04:00 server time; autumn repeats 03:00-04:00.
    res = parse(series(["2024-03-31 03:30", "2024-10-27 03:30", "2024-10-28 01:00"]))
    assert res.stats["rejected_by_reason"] == {"dst_gap_or_overlap": 2}
    assert len(res.bars) == 1


def test_daily_break_and_weekend_are_closed() -> None:
    closed = ["2024-01-10 22:00", "2024-01-12 22:00", "2024-01-13 12:00", "2024-01-14 22:55"]
    opened = ["2024-01-10 21:55", "2024-01-10 23:00", "2024-01-12 21:55", "2024-01-14 23:00"]
    assert not is_open(pd.DatetimeIndex(closed, tz="UTC"), XAU.session).any()
    assert is_open(pd.DatetimeIndex(opened, tz="UTC"), XAU.session).all()


def test_spread_points_become_price() -> None:
    bars = parse(export(row("2024-01-08 01:00", spread=73), row("2024-01-08 01:05", spread=0))).bars
    assert bars["spread"].tolist() == [0.73, 0.0]


# ----------------------------------------------------------------------------------- malformed data


def test_malformed_rows_are_dropped_and_reported() -> None:
    text = export(
        # shifted fields, like the EURUSD export's first row
        "2024.01.08\t2000.517:25:00\t\t2001\t1999\t2000\t1\t0\t5",
        row("2024-01-08 01:00"),
        "2024.01.08\t01:05:00\t2000\t2001",  # too few fields
        row("2024-01-08 01:10", o="abc"),
        row("2024-01-08 01:15", h=1999.5),  # high below open
        row("2024-01-08 01:17"),  # not on the 5-minute grid
        row("2024-01-08 01:20"),
    )
    res = parse(text)
    assert res.rejected[["line", "reason"]].values.tolist() == [
        [2, "bad_timestamp"],
        [4, "field_count"],
        [5, "bad_number"],
        [6, "ohlc_inconsistent"],
        [7, "off_grid"],
    ]
    assert len(res.bars) == 2


def test_export_without_spread_and_tick_volume() -> None:
    text = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n"
    text += "2000.05.30\t0.930217:25:00\t\t0.9302\t0.9302\t0.9302\n"
    text += "2024.01.08\t01:00:00\t1.10000\t1.10010\t1.09990\t1.10005\n"
    res = parse_mt5_text(text, EUR, last_bar_closed=True)
    assert res.stats["rejected_by_reason"] == {"bad_timestamp": 1}
    assert res.bars["spread"].isna().all() and res.bars["tick_volume"].isna().all()


def test_duplicates_keep_the_first_row() -> None:
    res = parse(
        export(
            row("2024-01-08 01:00", c=2000.5),
            row("2024-01-08 01:05"),
            row("2024-01-08 01:00", c=2000.5),
            row("2024-01-08 01:00", c=2000.9),
        )
    )
    assert res.stats["rejected_by_reason"] == {"duplicate_identical": 1, "duplicate_conflicting": 1}
    assert res.bars["close"].tolist() == [2000.5, 2000.5]
    assert res.bars["ts_utc"].is_monotonic_increasing


def test_out_of_order_rows_are_sorted() -> None:
    res = parse(series(["2024-01-08 01:05", "2024-01-08 01:00"]))
    assert res.stats["out_of_order_rows"] == 1
    assert res.bars["ts_utc"].is_monotonic_increasing


def test_final_bar_is_dropped_unless_the_session_closes_after_it() -> None:
    mid_session = parse_mt5_text(series(["2024-01-08 10:00", "2024-01-08 10:05"]), XAU)
    assert len(mid_session.bars) == 1 and mid_session.stats["tail_bar_dropped"]
    before_break = parse_mt5_text(series(["2024-01-08 23:50", "2024-01-08 23:55"]), XAU)
    assert len(before_break.bars) == 2 and before_break.stats["tail_bar_dropped"] is None


# -------------------------------------------------------------------------------------- aggregation


def m5_frame(start_utc: str, n: int) -> pd.DataFrame:
    ts = pd.date_range(utc(start_utc), periods=n, freq="5min")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "open": [100.0 + i for i in range(n)],
            "high": [101.0 + i for i in range(n)],
            "low": [99.0 + i for i in range(n)],
            "close": [100.5 + i for i in range(n)],
            "tick_volume": pd.array([1] * n, dtype="Int64"),
            "spread": [0.1 + 0.01 * (i % 3) for i in range(n)],
            "source": "test",
        }
    )


def test_aggregation_values() -> None:
    m5 = m5_frame("2024-01-09 14:00", 6)  # Tue 09:00-09:30 EST
    out = aggregate(m5, TIMEFRAMES["15m"], XAU.session)
    assert out["ts_utc"].tolist() == [utc("2024-01-09 14:00"), utc("2024-01-09 14:15")]
    first = out.iloc[0]
    assert (first.open, first.high, first.low, first.close) == (100.0, 103.0, 99.0, 102.5)
    assert first.tick_volume == 3 and first.n_bars == 3 and first.n_expected == 3
    assert first.spread == pytest.approx(0.10) and first.spread_max == pytest.approx(0.12)


def test_aggregation_never_emits_a_forming_bar() -> None:
    m5 = m5_frame("2024-01-09 14:00", 20)  # 14:00 .. 15:35, the 15:00 hour is still forming
    hourly = aggregate(m5, TIMEFRAMES["1h"], XAU.session)
    assert hourly["ts_utc"].tolist() == [utc("2024-01-09 14:00")]
    # Bars after as_of are not known yet and must not leak into the output.
    early = aggregate(m5, TIMEFRAMES["15m"], XAU.session, as_of=utc("2024-01-09 14:40"))
    assert early["ts_utc"].tolist() == [utc("2024-01-09 14:00"), utc("2024-01-09 14:15")]
    assert early["close"].iloc[-1] == m5["close"].iloc[5]


def test_appending_future_bars_never_changes_past_bars() -> None:
    m5 = m5_frame("2024-01-09 14:00", 200)
    for tf, freq in TIMEFRAMES.items():
        full = aggregate(m5, freq, XAU.session)
        for cut in (37, 101, 150):
            part = aggregate(m5.iloc[:cut], freq, XAU.session)
            pd.testing.assert_frame_equal(part, full.iloc[: len(part)], obj=f"{tf} cut {cut}")
            assert (
                part["ts_utc"] + freq <= m5["ts_utc"].iloc[cut - 1] + pd.Timedelta("5min")
            ).all()


@pytest.mark.parametrize("day", ["2024-01-09", "2024-07-09", "2024-03-12"])
def test_4h_bars_start_at_the_trading_day(day: str) -> None:
    ny = pd.DatetimeIndex(
        [f"{day} {h}:30" for h in ("16", "17", "21", "01", "05", "09", "13")], tz="America/New_York"
    )
    starts = bucket_start(pd.Series(ny.tz_convert("UTC")), TIMEFRAMES["4h"]).dt.tz_convert(
        "America/New_York"
    )
    assert starts.dt.strftime("%H:%M").tolist() == [
        "13:00",
        "17:00",
        "21:00",
        "01:00",
        "05:00",
        "09:00",
        "13:00",
    ]


# --------------------------------------------------------------------------------------------- gaps


def test_gap_classes() -> None:
    # Tue 2024-01-09 EST: 16:00-16:50 present, 16:55 missing (edge of the daily break), 18:00 onward
    # present
    # except 19:00 (mid-session).
    ts = pd.Series(pd.date_range(utc("2024-01-09 21:00"), utc("2024-01-10 01:00"), freq="5min"))
    ts = ts[is_open(ts, XAU.session)]
    ts = ts[~ts.isin([utc("2024-01-09 21:55"), utc("2024-01-10 00:00")])].reset_index(drop=True)
    gaps = find_gaps(ts, XAU)
    assert gaps[["start", "bars", "kind"]].values.tolist() == [
        [utc("2024-01-09 21:55"), 1, "session_edge"],
        [utc("2024-01-10 00:00"), 1, "mid_session"],
    ]


# --------------------------------------------------------------------------------------- end to end


def test_import_is_idempotent(tmp_path) -> None:
    times = pd.date_range(
        "2024-03-11 00:00", "2024-03-12 03:00", freq="5min"
    )  # a DST mismatch week
    times = times[times.hour != 23]  # the daily break is 23:00-00:00 server time in this week
    raw = tmp_path / "XAUUSD_M5_mt5.csv"
    raw.write_text(series([str(t) for t in times]), newline="")
    out, rep = tmp_path / "out", tmp_path / "rep"

    first = import_symbol("XAUUSD", raw, out, rep)
    files = sorted(p for p in tmp_path.rglob("*") if p.is_file() and p != raw)
    snapshot = {p: p.read_bytes() for p in files}
    second = import_symbol("XAUUSD", raw, out, rep)

    assert first == second
    assert {p: p.read_bytes() for p in files} == snapshot
    assert {p.name for p in files} == {
        "5m.parquet",
        "15m.parquet",
        "1h.parquet",
        "4h.parquet",
        "XAUUSD_M5.json",
        "XAUUSD_M5.md",
    }
    m5 = pd.read_parquet(out / "XAUUSD" / "5m.parquet")
    assert content_hash(m5) == first["hashes"]["5m"]
    assert str(m5["ts_utc"].dtype) == "datetime64[ns, UTC]"
    assert (
        json.loads((rep / "XAUUSD_M5.json").read_text())["timezone"]["bars_inside_closed_hours"]
        == 0
    )
