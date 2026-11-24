import numpy as np
import pandas as pd
import pytest

from app.config import instruments, strategy
from app.data.sessions import MARKET_TZ
from app.research.baselines import block_ci, compare, market, random_trade
from tests.test_smc_detector import EMPTY, _resample, _walk

L1 = strategy("L1")
XAU = instruments()["XAUUSD"]


def _frames(n: int = 6000) -> dict[str, pd.DataFrame]:
    m15 = _walk(n, seed=7, freq="15min")
    m15["spread_mean"] = 0.2
    return {"15m": m15, "1h": _resample(m15, "1h"), "4h": _resample(m15, "4h"), "D1": EMPTY}


def test_random_trade_keeps_year_hour_and_risk_in_atr() -> None:
    m = market(_frames(), L1)
    (year, hour), _ = max(m.pool.items(), key=lambda kv: len(kv[1]))
    rng = np.random.default_rng(1)
    got = [random_trade(m, year, hour, 1.5, rng, L1, XAU) for _ in range(30)]
    got = [g for g in got if g is not None]
    assert got, "no acceptable random draw"
    ts = pd.DatetimeIndex(m.entry["ts_utc"]).tz_convert(MARKET_TZ)
    for g in got:
        j = g["decision_idx"]
        assert (ts[j].year, ts[j].hour) == (year, hour)
        assert j + L1.horizon_bars < len(m.entry)
        assert g["y"] in (0, 1) and g["direction"] in ("buy", "sell")
        assert g["gross_r"] >= -1.0 - 1e-9 or g["y"] == 0  # a gap can lose more than 1R


def test_random_draws_repeat_with_the_seed() -> None:
    m = market(_frames(), L1)
    (year, hour), _ = max(m.pool.items(), key=lambda kv: len(kv[1]))
    a = [random_trade(m, year, hour, 1.5, np.random.default_rng(5), L1, XAU) for _ in range(3)]
    b = [random_trade(m, year, hour, 1.5, np.random.default_rng(5), L1, XAU) for _ in range(3)]
    assert a == b


def test_block_ci_of_a_constant_is_that_constant() -> None:
    weeks = np.array(["w1", "w1", "w2", "w3"])
    assert block_ci(np.full(4, 0.5), weeks, np.random.default_rng(0)) == pytest.approx((0.5, 0.5))


def test_compare_pairs_each_trade_with_its_own_random_trades() -> None:
    ts = pd.to_datetime(["2015-01-05", "2015-01-12"], utc=True)
    e1 = pd.DataFrame(
        {"symbol": "XAUUSD", "setup_id": ["a", "b"], "decision_utc": ts, "net_r": [1.0, -1.0]}
    )
    e0 = pd.DataFrame(
        {
            "rep": [0, 0, 1, 1],
            "symbol": "XAUUSD",
            "setup_id": ["a", "b", "a", "b"],
            "net_r": [-1.0, -1.0, 0.0, -1.0],
            "y": [0, 0, 0, 0],
        }
    )
    c = compare(e1, e0, np.random.default_rng(0))
    assert c["e0_mean"] == pytest.approx(-0.75)  # replication means -1.0 and -0.5
    assert c["diff"] == pytest.approx(((1.0 + 0.5) + (-1.0 + 1.0)) / 2)
    assert c["p"] == pytest.approx(1 / 3)  # no replication reaches the E1 mean of 0
