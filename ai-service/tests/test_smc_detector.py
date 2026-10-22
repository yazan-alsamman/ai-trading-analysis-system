import numpy as np
import pandas as pd

from app.config import strategy
from app.smc import detector

P = strategy()
START = pd.Timestamp("2024-01-16 01:00", tz="UTC")
J = 20


def _frame(data, start, freq) -> pd.DataFrame:
    data = np.asarray(data, float).reshape(-1, 4)
    ts = pd.date_range(start, periods=len(data), freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta(freq),
            "open": data[:, 0],
            "high": data[:, 1],
            "low": data[:, 2],
            "close": data[:, 3],
        }
    )


EMPTY = _frame(np.empty((0, 4)), START, "1h")
PATTERN = [
    (101, 102, 100.5, 101.5),
    (101.5, 103, 101, 102.5),
    (102.5, 103.5, 102, 103),  # swing high 103.5
    (103, 103.2, 101.5, 102),
    (102, 102.5, 100.8, 101),
    (101, 101.2, 99.4, 100.4),  # J + 5: sweeps 100 (and 99.8), closes back
    (100.4, 101.0, 100.2, 100.9),
    (100.9, 102.5, 100.8, 102.4),
    (102.4, 104.2, 101.6, 104.0),  # J + 8: FVG 101.0-101.6 and CHoCH above 103.5
]


def frames(d1_lows: list[float], h1: pd.DataFrame = EMPTY) -> dict[str, pd.DataFrame]:
    entry = _frame([(101, 102, 100, 101)] * J + PATTERN, START, "15min")
    d1 = _frame([(103, 110, low, 104) for low in d1_lows], "2024-01-14 22:00", "1D")
    d1["ts_utc"] -= pd.Timedelta(days=len(d1_lows) - 1)
    d1["close_utc"] -= pd.Timedelta(days=len(d1_lows) - 1)
    return {"15m": entry, "1h": h1, "4h": EMPTY, "D1": d1}


def test_a_sweep_choch_fvg_becomes_one_pattern() -> None:
    (pt,) = detector.detect(frames([100.0]), P)
    assert pt.direction == "buy" and pt.primary.price == 100.0
    assert (pt.sweep.first_idx, pt.choch.idx, pt.fvg.idx) == (J + 5, J + 8, J + 8)
    assert pt.pattern_id.startswith("buy:pd:low:")


def test_one_sweep_bar_taking_two_levels_is_one_pattern_named_by_the_furthest() -> None:
    (pt,) = detector.detect(frames([99.8, 100.0]), P)  # two previous days, two lows taken
    assert [lv.price for lv in pt.levels] == [99.8, 100.0]
    assert pt.primary.price == 99.8


def test_the_table_has_one_row_per_pattern() -> None:
    f = frames([100.0])
    df = detector.table(detector.detect(f, P), f["15m"])
    assert len(df) == 1
    assert df.loc[0, ["levels_taken", "bars_sweep_to_choch", "fvg_low", "fvg_high"]].tolist() == [
        1,
        3,
        101.0,
        101.6,
    ]


def _walk(n: int, seed: int, freq: str) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 1.5, n)
    low = np.minimum(open_, close) - rng.uniform(0, 1.5, n)
    return _frame(np.c_[open_, high, low, close], "2024-01-15 23:00", freq)


def _resample(m15: pd.DataFrame, freq: str) -> pd.DataFrame:
    g = m15.groupby(m15["ts_utc"].dt.floor(freq))
    out = g.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    out = out.rename_axis("ts_utc").reset_index()
    out["close_utc"] = out["ts_utc"] + pd.Timedelta(freq)
    return out[out["close_utc"] <= m15["close_utc"].iloc[-1]]


def test_patterns_never_change_when_bars_are_appended() -> None:
    m15 = _walk(16000, seed=11, freq="15min")
    full = {"15m": m15, "1h": _resample(m15, "1h"), "4h": _resample(m15, "4h"), "D1": EMPTY}
    whole = detector.detect(full, P)
    assert len(whole) >= 5
    for n in (4000, 11000):
        cut = m15["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        assert detector.detect(part, P) == [pt for pt in whole if pt.choch.idx < n]


def test_load_frames_never_reads_past_the_end(tmp_path) -> None:
    m15 = _walk(200, seed=1, freq="15min")
    (tmp_path / "X").mkdir()
    for tf in ("15m", "1h", "4h", "D1"):
        m15.to_parquet(tmp_path / "X" / f"{tf}.parquet", index=False)
    end = m15["close_utc"].iloc[99]
    got = detector.load_frames("X", end, tmp_path)
    assert all(len(v) == 100 and v["close_utc"].max() == end for v in got.values())
