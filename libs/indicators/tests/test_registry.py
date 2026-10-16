"""Catalog consistency and compute() parameter validation."""

import json

import numpy as np
import pandas as pd
import pytest

import trading_indicators as ti
from tests.conftest import binance_btcusdt, synthetic_ohlcv

CATEGORIES = {"trend", "momentum", "volatility", "volume"}


def test_catalog_is_json_and_complete() -> None:
    catalog = ti.catalog()
    json.dumps(catalog)
    names = [entry["name"] for entry in catalog]
    assert len(names) == len(set(names)) == 21
    assert set(names) == set(ti.INDICATORS)
    for entry in catalog:
        assert entry["category"] in CATEGORIES
        assert entry["placement"] in {"overlay", "pane"}
        assert entry["title"] and entry["outputs"] and entry["description"]
        assert isinstance(entry["lookback"], int) and entry["lookback"] >= 0
        for p in entry["params"]:
            assert p["type"] in {"int", "float"}
            assert p["min"] <= p["default"] <= p["max"]
        if entry["levels"]:
            assert entry["placement"] == "pane"
    rsi = next(e for e in catalog if e["name"] == "rsi")
    assert rsi["levels"] == [30.0, 70.0] and rsi["lookback"] == 14
    macd = next(e for e in catalog if e["name"] == "macd")
    assert macd["outputs"] == ["macd", "signal", "histogram"]


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
@pytest.mark.parametrize("data", [synthetic_ohlcv, binance_btcusdt])
def test_every_indicator_computes_and_lookback_is_exact(name: str, data) -> None:
    spec = ti.get_indicator(name)
    df = data()
    out = ti.compute(name, df)
    assert list(out.columns) == list(spec.outputs)
    assert out.index.equals(df.index)
    lookback = spec.lookback()
    # enough: every output is valid from the lookback bar on
    assert not out.iloc[lookback:].isna().any().any()
    # and tight: at least one output is still warming up one bar earlier
    if lookback > 0:
        assert out.iloc[lookback - 1].isna().any()


@pytest.mark.parametrize("name", sorted(ti.INDICATORS))
def test_lookback_holds_for_random_params(name: str) -> None:
    spec = ti.get_indicator(name)
    rng = np.random.default_rng(len(name))
    df = synthetic_ohlcv(800, seed=4)
    for _ in range(5):
        params = {}
        for p in spec.params:
            hi = min(p.max, 60 if p.type == "int" else 5.0)
            value = rng.uniform(p.min, hi)
            params[p.name] = int(round(value)) if p.type == "int" else round(value, 2)
        if name == "macd" and params["fast"] >= params["slow"]:
            params["fast"], params["slow"] = params["slow"] - 1 or 1, params["slow"] + 1
        if name == "macd" and params["fast"] == params["slow"]:
            params["slow"] += 1
        out = ti.compute(name, df, **params)
        lookback = spec.lookback(params)
        assert not out.iloc[lookback:].isna().any().any(), params
        if lookback > 0:
            assert out.iloc[lookback - 1].isna().any(), params


def test_resolve_fills_defaults_and_validates() -> None:
    spec = ti.get_indicator("macd")
    assert spec.resolve({"fast": 5}) == {"fast": 5, "slow": 26, "signal": 9}
    assert spec.resolve({"fast": 5.0})["fast"] == 5
    with pytest.raises(ValueError, match="unknown parameter"):
        spec.resolve({"length": 3})
    with pytest.raises(ValueError, match="between 1 and 1000"):
        spec.resolve({"fast": 0})
    with pytest.raises(ValueError, match="must be an integer"):
        spec.resolve({"fast": 2.5})
    with pytest.raises(ValueError, match="must be a number"):
        spec.resolve({"fast": "12"})
    with pytest.raises(ValueError, match="must be smaller than slow"):
        spec.resolve({"fast": 30})
    assert ti.get_indicator("bollinger").resolve({"std": 3}) == {"length": 20, "std": 3.0}
    with pytest.raises(ValueError, match="unknown parameter"):
        ti.get_indicator("obv").resolve({"length": 3})


def test_compute_unknown_indicator() -> None:
    with pytest.raises(ValueError, match="unknown indicator 'nope'"):
        ti.compute("nope", synthetic_ohlcv(10))


def test_compute_checks_required_columns() -> None:
    df = synthetic_ohlcv(50).drop(columns="volume")
    with pytest.raises(ValueError, match="missing column"):
        ti.compute("mfi", df)
    ti.compute("rsi", df[["close"]])  # only what the indicator needs is required


@pytest.mark.parametrize("name", sorted(set(ti.INDICATORS) - {"obv", "vwap"}))
def test_convergence_makes_values_independent_of_the_start(name: str) -> None:
    """With lookback + convergence bars of history, values match a much longer history.
    (OBV is cumulative and VWAP anchored to the day: tested separately below.)"""
    spec = ti.get_indicator(name)
    df = synthetic_ohlcv(3000, seed=12)
    window = 100
    full = ti.compute(name, df).iloc[-window:]
    needed = spec.lookback() + spec.convergence()
    short = ti.compute(name, df.iloc[-(window + needed) :]).iloc[-window:]
    np.testing.assert_allclose(short.to_numpy(), full.to_numpy(), rtol=1e-5, atol=1e-6)


def test_obv_level_depends_on_start() -> None:
    df = synthetic_ohlcv(500, seed=12)
    full, short = ti.obv(df), ti.obv(df.iloc[100:])
    diff = (full.iloc[100:] - short).to_numpy()
    assert np.allclose(diff, diff[0])  # same shape, shifted level


def test_vwap_only_needs_the_current_utc_day() -> None:
    df = synthetic_ohlcv(24 * 5, seed=12)  # 5 days of hourly bars
    assert ti.get_indicator("vwap").anchor == "day"
    full = ti.vwap(df)
    from_day_start = ti.vwap(df.loc["2025-01-03":])
    pd.testing.assert_series_equal(from_day_start, full.loc["2025-01-03":])
