"""Catalog consistency, parameter validation, history() and the params hash."""

import json

import numpy as np
import pytest
import trading_indicators as ti

import trading_strategies as ts
from tests.conftest import synthetic_ohlcv

CATEGORIES = {"trend", "mean_reversion", "breakout", "momentum"}


def test_catalog() -> None:
    catalog = ts.catalog()
    json.dumps(catalog)
    assert [s["key"] for s in catalog] == [
        "ma_crossover",
        "rsi_reversal",
        "macd_cross",
        "bollinger_reversion",
        "supertrend_flip",
        "donchian_breakout",
    ]
    for s in catalog:
        assert s["category"] in CATEGORIES
        assert s["title"] and len(s["description"]) > 80
        assert s["history"] >= 1
        for p in s["params"]:
            assert p["min"] <= p["default"] <= p["max"]
        for ind in s["indicators"]:  # every line to draw is a valid indicator request
            ti.get_indicator(ind["name"]).resolve(ind["params"])
    ma = catalog[0]
    assert ma["indicators"] == [
        {"name": "ema", "params": {"length": 9}},
        {"name": "ema", "params": {"length": 21}},
    ]


@pytest.mark.parametrize(
    ("key", "params", "message"),
    [
        ("ma_crossover", {"fast": 21, "slow": 9}, "fast \\(21\\) must be smaller than slow"),
        ("ma_crossover", {"fast": 9, "slow": 9}, "must be smaller than slow"),
        ("macd_cross", {"fast": 30}, "must be smaller than slow"),
        ("rsi_reversal", {"oversold": 70, "overbought": 30}, "oversold .* must be below"),
        ("rsi_reversal", {"length": 0}, "length must be between 1 and 500"),
        ("rsi_reversal", {"period": 14}, "unknown parameter\\(s\\) period"),
        ("bollinger_reversion", {"std": "2"}, "std must be a number"),
        ("macd_cross", {"zero_filter": 2}, "zero_filter must be between 0 and 1"),
        ("donchian_breakout", {"length": 2.5}, "length must be an integer"),
        ("ma_crossover", {"adx_min": 101}, "adx_min must be between 0.0 and 100.0"),
    ],
)
def test_invalid_params(key: str, params: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ts.get_strategy(key).resolve(params)
    with pytest.raises(ValueError, match=message):
        ts.run(key, synthetic_ohlcv(50), **params)


def test_unknown_strategy_and_missing_columns() -> None:
    with pytest.raises(ValueError, match="unknown strategy 'nope'"):
        ts.get_strategy("nope")
    with pytest.raises(ValueError, match="missing column"):
        ts.run("donchian_breakout", synthetic_ohlcv(50).drop(columns="volume"))


def test_params_hash_is_stable() -> None:
    a = ts.params_hash("rsi_reversal", {})
    assert a == ts.params_hash("rsi_reversal", {"overbought": 70, "length": 14.0, "oversold": 30})
    assert a != ts.params_hash("rsi_reversal", {"length": 15})
    assert a != ts.params_hash("bollinger_reversion", {})
    assert len(a) == 32


@pytest.mark.parametrize("key", sorted(ts.STRATEGIES))
def test_history_is_enough(key: str) -> None:
    """From history() bars on, signals do not depend on how much earlier data exists."""
    strategy = ts.get_strategy(key)
    df = synthetic_ohlcv(3000, seed=33)
    full = strategy.generate(df)
    need = strategy.history()
    for start in (0, 500, 1700):
        part = strategy.generate(df.iloc[start:])
        tail = slice(need, None)
        np.testing.assert_array_equal(
            part["signal"].to_numpy()[tail], full["signal"].to_numpy()[start:][tail]
        )
        np.testing.assert_allclose(
            part["strength"].to_numpy()[tail],
            full["strength"].to_numpy()[start:][tail],
            rtol=1e-5,
            atol=1e-6,
        )


@pytest.mark.parametrize("key", sorted(ts.STRATEGIES))
def test_signals_on_random_data_are_well_formed(key: str) -> None:
    df = synthetic_ohlcv(3000, seed=34)
    out = ts.run(key, df)
    sig = out["signal"]
    assert set(sig.unique()) <= {-1, 0, 1}
    assert (sig == 1).sum() > 0 and (sig == -1).sum() > 0
    rows = out[sig != 0]
    assert rows["strength"].between(0, 1).all()
    assert rows["reason"].map(lambda x: isinstance(x, str) and x.replace("_", "").isalpha()).all()
    json.dumps(rows["details"].tolist())  # details are plain JSON numbers


@pytest.mark.parametrize("key", sorted(ts.STRATEGIES))
def test_short_and_empty_input(key: str) -> None:
    for n in (0, 1, 5):
        out = ts.run(key, synthetic_ohlcv(max(n, 1)).iloc[:n])
        assert len(out) == n and (out["signal"] == 0).all()
