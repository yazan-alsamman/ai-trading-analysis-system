"""P6 task 2: request bars -> research frames, and the data-quality checks."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import instruments, profiles, strategy
from app.contract import EvaluateRequest, iso_z, make_request_id
from app.data.importer import DEFAULT_OUT as STORE
from app.data.sessions import is_open
from app.live.frames import DataQualityError, build_frames, frames_for, longest_gap_minutes

P = strategy("L1")
PROF = profiles()["intraday"]
SPEC = {
    "contract_size": 100,
    "tick_size": 0.01,
    "lot_step": 0.01,
    "min_lot": 0.01,
    "max_lot": 100,
    "price_basis": "bid",
}
OHLC = ["ts_utc", "close_utc", "open", "high", "low", "close"]


def request(
    bars15: pd.DataFrame, symbol: str = "XAUUSD", spread: str = "spread_mean", tf: str = "15m"
):
    close = bars15["close_utc"].iloc[-1]
    return EvaluateRequest.model_validate(
        {
            "request_id": make_request_id(symbol, "intraday", close.to_pydatetime()),
            "instrument": symbol,
            "profile": "intraday",
            "bar_close_ts": iso_z(close.to_pydatetime()),
            "bars": {
                tf: [
                    {
                        "ts": iso_z(r.ts_utc.to_pydatetime()),
                        "o": r.open,
                        "h": r.high,
                        "l": r.low,
                        "c": r.close,
                        "spread": None if pd.isna(getattr(r, spread)) else getattr(r, spread),
                    }
                    for r in bars15.itertuples()
                ]
            },
            "instrument_spec": SPEC,
        }
    )


def synthetic(days: int = 9, start: str = "2015-03-01 23:00") -> pd.DataFrame:
    """Gold-like 15m bars inside trading hours, a random walk."""
    inst = instruments()["XAUUSD"]
    grid = pd.date_range(start, periods=days * 96 + 200, freq="15min", tz="UTC")
    grid = grid[is_open(grid, inst)][: days * 92 + 40]
    rng = np.random.default_rng(7)
    close = 1200 + np.cumsum(rng.normal(0, 0.8, len(grid)))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "ts_utc": grid,
            "close_utc": grid + pd.Timedelta(minutes=15),
            "open": open_,
            "high": np.maximum(open_, close) + 0.3,
            "low": np.minimum(open_, close) - 0.3,
            "close": close,
            "spread_mean": 0.3,
        }
    )


def test_synthetic_frames_are_closed_and_complete() -> None:
    bars = synthetic()
    live = build_frames(request(bars), instruments()["XAUUSD"], P, PROF)
    first, as_of = bars["ts_utc"].iloc[0], live.as_of
    for name, f in live.frames.items():
        assert (f["close_utc"] <= as_of).all(), name
        assert (f["ts_utc"] >= first).all(), name
    assert len(live.frames["D1"]) >= PROF.history_trading_days
    assert live.frames["15m"]["spread_mean"].eq(0.3).all()


def test_a_5m_entry_frame_builds_every_longer_frame() -> None:
    """The scalp strategies (docs/strategies/PREREG.md) read 5m bars: the request's 5m bars give
    the 5m frame and, aggregated, the 15m, 1h, 4h and D1 frames."""
    b15 = synthetic()
    b5 = pd.concat(
        [b15.assign(ts_utc=b15["ts_utc"] + pd.Timedelta(minutes=k)) for k in (0, 5, 10)]
    ).sort_values("ts_utc", ignore_index=True)
    b5["close_utc"] = b5["ts_utc"] + pd.Timedelta(minutes=5)
    live = frames_for(request(b5, tf="5m"), instruments()["XAUUSD"], "5m", PROF)
    assert list(live.frames) == ["5m", "15m", "1h", "4h", "D1"]
    assert len(live.frames["5m"]) == len(b5)
    f15 = live.frames["15m"]
    assert (f15["high"].to_numpy() == b15["high"].to_numpy()[: len(f15)]).all()
    assert "5m" not in build_frames(request(b15), instruments()["XAUUSD"], P, PROF).frames


def test_misaligned_bar() -> None:
    bars = synthetic()
    bars.loc[5, "ts_utc"] += pd.Timedelta(minutes=1)
    bars.loc[5, "close_utc"] += pd.Timedelta(minutes=1)
    with pytest.raises(DataQualityError) as e:
        build_frames(request(bars), instruments()["XAUUSD"], P, PROF)
    assert e.value.reason == "misaligned_bars"


def test_missing_spread() -> None:
    bars = synthetic()
    bars.loc[10, "spread_mean"] = np.nan
    with pytest.raises(DataQualityError) as e:
        build_frames(request(bars), instruments()["XAUUSD"], P, PROF)
    assert e.value.reason == "missing_spread"


def test_gap_inside_trading_hours() -> None:
    bars = synthetic()
    n = len(bars)
    bars = bars.drop(index=range(n - 60, n - 40)).reset_index(drop=True)  # 5 h missing, recent
    with pytest.raises(DataQualityError) as e:
        build_frames(request(bars), instruments()["XAUUSD"], P, PROF)
    assert e.value.reason == "gap"
    assert e.value.detail["longest_gap_minutes"] == 300


def test_older_gaps_are_left_to_the_rules() -> None:
    bars = synthetic().drop(index=range(300, 320)).reset_index(drop=True)
    build_frames(request(bars), instruments()["XAUUSD"], P, PROF)


def test_weekend_and_daily_break_are_not_gaps() -> None:
    bars = synthetic(days=9)
    assert longest_gap_minutes(bars["ts_utc"], instruments()["XAUUSD"], pd.Timedelta("15min")) == 0


def test_insufficient_history() -> None:
    bars = synthetic(days=4)
    with pytest.raises(DataQualityError) as e:
        build_frames(request(bars), instruments()["XAUUSD"], P, PROF)
    assert e.value.reason == "insufficient_history"


# --- against the research store (local, untracked) ----------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "end"),
    [
        ("XAUUSD", "2015-03-18 14:15"),  # development period
        ("EURUSD", "2017-06-14 09:30"),
        ("GBPUSD", "2017-11-08 20:00"),  # a clock-corrected segment
    ],
)
def test_aggregation_equals_the_store(symbol: str, end: str) -> None:
    store: Path = STORE / symbol
    if not (store / "15m.parquet").exists():
        pytest.skip("research store not present")
    end_ts = pd.Timestamp(end, tz="UTC")
    lo = end_ts - pd.Timedelta(days=14)
    load = {
        tf: pd.read_parquet(
            store / f"{tf}.parquet", filters=[("close_utc", "<=", end_ts), ("ts_utc", ">=", lo)]
        )
        for tf in ("15m", "1h", "4h", "D1")
    }
    bars = load["15m"].reset_index(drop=True)
    inst = instruments()[symbol]
    live = build_frames(request(bars, symbol), inst, P, PROF)
    first = bars["ts_utc"].iloc[0]
    for tf in ("1h", "4h", "D1"):
        want = load[tf][load[tf]["ts_utc"] >= first].reset_index(drop=True)
        got = live.frames[tf]
        assert len(want) > 0, tf
        pd.testing.assert_frame_equal(got[OHLC], want[OHLC], check_dtype=False, obj=tf)
    entry = bars[is_open(bars["ts_utc"], inst)].reset_index(drop=True)
    cols = [*OHLC, "spread_mean"]
    pd.testing.assert_frame_equal(live.frames["15m"][cols], entry[cols], check_dtype=False)
