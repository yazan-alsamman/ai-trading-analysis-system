import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import instruments
from app.data.aggregate import aggregate, buckets
from app.data.importer import find_exports, import_symbol, main
from app.data.mt5 import parse_export

M1 = pd.Timedelta(minutes=1)
XAU = instruments()["XAUUSD"]
HEADER = b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\r\n"


def line(server: str, o=2000.0, h=2001.0, lo=1999.0, c=2000.5, spread=25) -> bytes:
    day, time = server.split(" ")
    return f"{day}\t{time}:00\t{o}\t{h}\t{lo}\t{c}\t10\t0\t{spread}\r\n".encode()


def parse(*rows: bytes):
    return parse_export([HEADER, *rows], XAU, M1, "Europe/Athens")


@pytest.mark.parametrize(
    "server, utc",
    [
        ("2024.01.15 10:00", "2024-01-15 08:00"),  # winter: UTC+2
        ("2024.07.15 10:00", "2024-07-15 07:00"),  # EU summer time: UTC+3
        ("2024.03.20 10:00", "2024-03-20 08:00"),  # US already on DST, EU not yet
    ],
)
def test_server_time_becomes_utc_with_europe_athens(server: str, utc: str) -> None:
    bars = parse(line(server)).bars
    assert bars["ts_utc"].iloc[0] == pd.Timestamp(utc, tz="UTC")


def test_spread_points_become_price_units() -> None:
    assert parse(line("2024.01.15 10:00", spread=25)).bars["spread"].iloc[0] == 0.25


def test_every_rejected_row_is_counted_by_reason() -> None:
    r = parse(
        line("2024.01.15 10:00"),
        b"2024.01.15\t10:01:00\t1\t2\r\n",  # wrong field count
        line("2024.01.15 10:02", h=1990.0),  # high below open/close
        line("2024.01.15 10:03").replace(b"10:03:00", b"10:03:30"),  # off the minute grid
        line("2024.03.31 03:30"),  # does not exist on the server clock (EU spring forward)
        b"2024.13.40\t10:05:00\t1\t1\t1\t1\t1\t0\t1\r\n",  # bad date
        line("2024.01.15 10:00"),  # identical duplicate
        line("2024.01.15 10:00", c=2000.9),  # conflicting duplicate
    )
    assert r.stats["rows_read"] == 8 and r.stats["rows_kept"] == 1
    assert r.stats["rejected_by_reason"] == {
        "bad_timestamp": 1,
        "dst_gap_or_overlap": 1,
        "duplicate_conflicting": 1,
        "duplicate_identical": 1,
        "field_count": 1,
        "off_grid": 1,
        "ohlc_inconsistent": 1,
    }


def test_out_of_order_rows_are_sorted_and_counted() -> None:
    r = parse(line("2024.01.15 10:01"), line("2024.01.15 10:00"))
    assert r.bars["ts_utc"].is_monotonic_increasing
    assert r.stats["out_of_order_rows"] == 1


def _m1(start_utc: str, n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "ts_utc": pd.date_range(start_utc, periods=n, freq="1min", tz="UTC"),
            "open": open_,
            "high": np.maximum(open_, close) + 0.1,
            "low": np.minimum(open_, close) - 0.1,
            "close": close,
            "tick_volume": pd.array(rng.integers(1, 50, n), dtype="Int64"),
            "spread": rng.integers(10, 40, n) / 100,
        }
    )


def test_aggregated_values() -> None:
    m1 = _m1("2024-01-15 08:00", 10)
    five = aggregate(m1, "5m", M1)
    assert len(five) == 2
    first = five.iloc[0]
    assert first["open"] == m1["open"].iloc[0] and first["close"] == m1["close"].iloc[4]
    assert first["high"] == m1["high"].iloc[:5].max() and first["low"] == m1["low"].iloc[:5].min()
    assert first["tick_volume"] == m1["tick_volume"].iloc[:5].sum() and first["n_bars"] == 5
    assert first["spread_min"] == m1["spread"].iloc[:5].min()
    assert first["close_utc"] == pd.Timestamp("2024-01-15 08:05", tz="UTC")


def test_a_forming_bucket_is_never_emitted() -> None:
    m1 = _m1("2024-01-15 08:00", 7)  # 08:00-08:06: the 08:05 bucket is still forming
    assert list(aggregate(m1, "5m", M1)["ts_utc"]) == [pd.Timestamp("2024-01-15 08:00", tz="UTC")]
    assert aggregate(m1, "1h", M1).empty


@pytest.mark.parametrize("month", ["2024-01-15", "2024-07-15", "2024-03-12"])
def test_4h_and_d1_follow_the_new_york_trading_day(month: str) -> None:
    ts = pd.Series(pd.date_range(f"{month} 00:00", periods=24 * 60, freq="1min", tz="UTC"))
    for tf in ("4h", "D1"):
        start, _ = buckets(ts, tf)
        ny = start.dt.tz_convert("America/New_York")
        assert set(ny.dt.minute) == {0}
        hours = {17} if tf == "D1" else {17, 21, 1, 5, 9, 13}
        assert set(ny.dt.hour) <= hours


def test_appending_future_bars_never_changes_past_buckets() -> None:
    full = _m1("2024-01-12 00:00", 4 * 24 * 60, seed=3)
    for tf in ("5m", "15m", "1h", "4h", "D1"):
        whole = aggregate(full, tf, M1)
        for n in (1, 777, 3000, 4 * 24 * 60 - 1):
            prefix = aggregate(full.iloc[:n], tf, M1)
            as_of = full["ts_utc"].iloc[n - 1] + M1
            expected = whole[whole["close_utc"] <= as_of].reset_index(drop=True)
            pd.testing.assert_frame_equal(prefix, expected, check_exact=True)


def _export(raw: Path, name: str, rows: list[bytes]) -> Path:
    raw.mkdir(exist_ok=True)
    path = raw / name
    path.write_bytes(HEADER + b"".join(rows))
    return path


def test_import_stops_at_the_lockbox_and_is_repeatable(tmp_path: Path) -> None:
    rows = [line(f"2026.01.09 {h:02d}:{m:02d}") for h in (10, 11) for m in range(60)]
    rows += [line("2026.01.12 01:01")] + [b"\xff never decoded\r\n"]
    raw = tmp_path / "raw"
    _export(raw, "XAUUSD_M1_201001110105_202610192259.csv", rows)
    out = tmp_path / "store"

    assert main(["--raw-dir", str(raw), "--out", str(out)]) == 0
    record = json.loads((out / "XAUUSD" / "import.json").read_text(encoding="utf-8"))
    assert record["input"]["stopped_at_lockbox"] is True
    assert record["parse"]["rows_kept"] == 120
    assert record["range_utc"][1] == "2026-01-09T09:59:00+00:00"
    assert record["frames"]["1h"]["rows"] == 2
    first = {p.name: p.read_bytes() for p in (out / "XAUUSD").iterdir()}

    import_symbol("XAUUSD", raw / "XAUUSD_M1_201001110105_202610192259.csv", out)
    assert {p.name: p.read_bytes() for p in (out / "XAUUSD").iterdir()} == first
    assert set(first) == {
        "m1.parquet",
        "5m.parquet",
        "15m.parquet",
        "1h.parquet",
        "4h.parquet",
        "D1.parquet",
        "import.json",
    }


def test_only_configured_m1_exports_are_found(tmp_path: Path) -> None:
    for name in (
        "XAUUSD_M1_201001110105_202601092359.csv",
        "XAUUSD_M5_201001110105_202601092359.csv",
        "XAGUSD_M1_201001110105_202601092359.csv",
        "notes.csv",
    ):
        (tmp_path / name).write_bytes(HEADER)
    assert list(find_exports(tmp_path)) == ["XAUUSD"]
