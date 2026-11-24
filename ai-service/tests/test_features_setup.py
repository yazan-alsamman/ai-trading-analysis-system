import numpy as np
import pandas as pd
import pytest

from app.config import strategy
from app.data.sessions import MARKET_TZ
from app.features.setup_features import (
    FEATURES,
    _last_closed,
    _spread_vs_hour,
    _trend,
    features,
)
from app.setups.labels import label_all
from tests.test_smc_detector import _frame, _resample, _walk

L1 = strategy("L1")


def _frames(n: int = 16000) -> dict[str, pd.DataFrame]:
    m15 = _walk(n, seed=11, freq="15min")
    m15["spread_mean"] = 0.2 + 0.1 * (np.arange(n) % 7 == 0)
    return {
        "15m": m15,
        "1h": _resample(m15, "1h"),
        "4h": _resample(m15, "4h"),
        "D1": _resample(m15, "1D"),
    }


def _table(frames: dict[str, pd.DataFrame], symbol: str = "XAUUSD") -> pd.DataFrame:
    df = label_all(frames, symbol, L1)
    df = df[df["state"] != "REJECTED"].reset_index(drop=True)
    f = features(frames, df, symbol, L1)[FEATURES]
    return pd.concat([df.drop(columns=[c for c in FEATURES if c in df]), f], axis=1)


def test_last_closed_uses_only_bars_closed_by_then() -> None:
    f = _frame([(1, 2, 0, 1)] * 3, "2024-01-01 00:00", "1h")  # closes 01:00, 02:00, 03:00
    t = pd.to_datetime(["2024-01-01 00:30", "2024-01-01 02:00", "2024-01-01 02:59"], utc=True)
    assert list(_last_closed(f, t.to_numpy())) == [-1, 1, 1]


def test_trend_is_zero_on_a_flat_market_and_positive_above_its_average() -> None:
    flat = _frame([(100, 101, 99, 100)] * 40, "2024-01-01", "1h")
    t = flat["close_utc"].to_numpy()[-1:]
    assert _trend(flat, t, 14)[0] == pytest.approx(0.0)
    up = _frame([(100 + i, 101 + i, 99 + i, 100 + i) for i in range(40)], "2024-01-01", "1h")
    assert _trend(up, up["close_utc"].to_numpy()[-1:], 14)[0] > 0


def test_spread_vs_hour_is_one_for_a_constant_spread_and_uses_earlier_days_only() -> None:
    m15 = _walk(96 * 30, seed=3, freq="15min")
    m15["spread_mean"] = 0.3
    ny = pd.DatetimeIndex(m15["ts_utc"]).tz_convert(MARKET_TZ)
    r = _spread_vs_hour(m15, ny)
    assert np.nanmax(np.abs(r - 1.0)) < 1e-12
    assert np.isnan(r[:96]).all()  # no earlier day to compare with
    m15.loc[m15.index[-1], "spread_mean"] = 3.0  # the last bar's own spread is not its reference
    assert _spread_vs_hour(m15, ny)[-1] == pytest.approx(10.0)


def test_features_hold_their_definitions() -> None:
    t = _table(_frames())
    assert len(t) >= 3
    assert (t["choch_margin_atr"] > 0).all()  # the decision bar closes beyond the broken swing
    assert (t["displacement_atr"] > 0).all()  # and away from the sweep extreme
    assert np.allclose(t["hour_sin"] ** 2 + t["hour_cos"] ** 2, 1.0)
    assert (t["sym_XAUUSD"] == 1).all() and (t["sym_EURUSD"] == 0).all()
    assert (t["usd_long"] == 1 - t["direction_buy"]).all()  # USD is the quote currency of gold
    assert ((t["has_fvg"] == 0) == (t["fvg_size_atr"] == 0)).all()
    assert (t["r_multiple"] >= L1.min_r).all()


def test_usd_long_follows_the_base_currency() -> None:
    t = _table(_frames(), symbol="USDJPY")
    assert (t["usd_long"] == t["direction_buy"]).all()


def test_tp_in_usd_on_the_smallest_lot() -> None:
    gold = _table(_frames())
    assert np.allclose(gold["tp_usd_min_lot"], (gold["tp"] - gold["entry"]).abs())  # 1 oz
    jpy = _table(_frames(), symbol="USDJPY")  # 1,000 USD of a JPY-quoted pair: yen / price
    assert np.allclose(
        jpy["tp_usd_min_lot"], (jpy["tp"] - jpy["entry"]).abs() * 1000 / jpy["entry"]
    )


def test_features_never_change_when_bars_are_appended() -> None:
    full = _frames()
    whole = _table(full).set_index("setup_id")
    for n in (6000, 12000):
        cut = full["15m"]["close_utc"].iloc[n - 1]
        part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
        got = _table(part).set_index("setup_id")
        assert len(got) >= 1
        pd.testing.assert_frame_equal(got[FEATURES], whole.loc[got.index, FEATURES])
