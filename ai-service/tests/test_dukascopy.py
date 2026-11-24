import lzma
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.data import crosscheck, dukascopy


def test_sample_is_four_full_weeks_a_year_plus_the_hole_days() -> None:
    days = dukascopy.sample_days(2024)
    assert len(days) == 2 * 4 * 5 + 2
    assert days[0] == date(2024, 2, 5) and all(d.weekday() < 5 for d in days)
    assert date(2024, 7, 2) in days and date(2025, 7, 2) in days
    assert max(days) < date(2026, 1, 10)


def test_lockbox_days_are_never_requested() -> None:
    with pytest.raises(dukascopy.LockboxError):
        dukascopy.url("XAUUSD", date(2026, 1, 12))
    assert dukascopy.url("XAUUSD", date(2019, 2, 5)).endswith(
        "/XAUUSD/2019/01/05/BID_candles_min_1.bi5"
    )


def test_decode_reads_the_bi5_records() -> None:
    rows = [
        (0, 1312345, 1312400, 1312300, 1312450, 1.5),
        (60, 1312400, 1312380, 1312350, 1312420, 2.0),
    ]
    raw = lzma.compress(b"".join(dukascopy.RECORD.pack(*r) for r in rows), format=lzma.FORMAT_ALONE)
    df = dukascopy.decode(raw, "XAUUSD", date(2019, 2, 5))
    assert list(df["ts_utc"]) == [
        pd.Timestamp("2019-02-05 00:00", tz="UTC"),
        pd.Timestamp("2019-02-05 00:01", tz="UTC"),
    ]
    assert df.iloc[0][["open", "high", "low", "close"]].tolist() == [
        1312.345,
        1312.45,
        1312.3,
        1312.4,
    ]
    assert dukascopy.decode(b"", "XAUUSD", date(2019, 2, 5)).empty


def _feed(seed: int, n: int = 5 * 1440) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2019-02-04", periods=n, freq="1min", tz="UTC")
    close = 1.1 * np.exp(np.cumsum(rng.normal(0, 2e-4, n)))
    return pd.DataFrame(
        {"ts_utc": ts.as_unit("ns"), "high": close * 1.0001, "low": close * 0.9999, "close": close}
    )


def test_two_feeds_of_the_same_market_agree_at_lag_zero() -> None:
    fx = _feed(0)
    duka = fx.assign(close=fx["close"] * (1 + np.random.default_rng(1).normal(0, 2e-5, len(fx))))
    m = crosscheck.compare_frames(fx, duka)
    assert m["corr"] > 0.9 and m["best_lag_min"] == 0
    assert m["price_gap_x_range"] < 1


def test_a_feed_one_hour_off_shows_the_lag() -> None:
    fx = _feed(0)
    duka = fx.assign(ts_utc=fx["ts_utc"] + pd.Timedelta(hours=1))
    m = crosscheck.compare_frames(fx, duka)
    assert m["best_lag_min"] == 60 and m["best_lag_corr"] > 0.99
    assert m["corr"] < 0.2
