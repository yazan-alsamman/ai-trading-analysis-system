"""Metrics on a known equity series against independent calculations."""

import math

import numpy as np
import pandas as pd
import pytest

from trading_backtest import metrics as m
from trading_backtest.engine import Trade

INITIAL = 10_000.0
EQUITY = np.array([11_000, 9_900, 10_450, 12_000, 10_200, 13_000, 12_350], dtype=float)
TIMES = pd.date_range("2025-03-01", periods=len(EQUITY), freq="h", tz="UTC")


def trade(net: float, ret: float, held: int, fees: float = 1.0) -> Trade:
    t = TIMES[0]
    return Trade(1, "long", t, 100, t, 100, 1, net + fees, fees, net, ret, held, None, "x", 0, 0)


TRADES = [trade(100, 1.0, 1), trade(-50, -0.5, 1), trade(200, 2.0, 2), trade(-25, -0.25, 1)]


@pytest.fixture
def result() -> dict:
    return m.compute(EQUITY, TIMES, TRADES, INITIAL, benchmark=(100.0, 130.0), bars_per_year=8760.0)


def test_returns_sharpe_sortino_cagr(result) -> None:
    series = pd.Series(np.concatenate(([INITIAL], EQUITY)))
    r = series.pct_change().dropna()  # independent: pandas
    assert result["sharpe"] == pytest.approx(r.mean() / r.std() * math.sqrt(8760))
    downside = math.sqrt((r.clip(upper=0) ** 2).mean())
    assert result["sortino"] == pytest.approx(r.mean() / downside * math.sqrt(8760))
    assert result["total_return_pct"] == pytest.approx(23.5)
    assert result["final_equity"] == 12_350
    years = len(EQUITY) / 8760
    expected_cagr = ((12_350 / 10_000) ** (1 / years) - 1) * 100
    assert result["cagr_pct"] == pytest.approx(expected_cagr, rel=1e-9)


def test_max_drawdown_and_its_dates(result) -> None:
    # peaks: 10,000 -> 11,000 -> 12,000 (bar 3); worst: 12,000 -> 10,200 = -15 % (bar 4)
    assert result["max_drawdown_pct"] == pytest.approx(-15.0)
    assert result["max_drawdown_start"] == TIMES[3].isoformat()
    assert result["max_drawdown_end"] == TIMES[4].isoformat()
    assert result["max_drawdown_recovered"] == TIMES[5].isoformat()
    assert result["calmar"] == pytest.approx(result["cagr_pct"] / 15.0)
    dd = m.drawdown(EQUITY, INITIAL)
    assert dd[1] == pytest.approx(9_900 / 11_000 - 1)
    assert dd[0] == 0 and dd[3] == 0


def test_trade_statistics(result) -> None:
    assert result["trades"] == 4
    assert result["win_rate_pct"] == 50
    assert result["profit_factor"] == pytest.approx(300 / 75)
    assert result["avg_win"] == 150 and result["avg_loss"] == -37.5
    assert result["expectancy"] == pytest.approx(56.25)
    assert (result["best_trade_pct"], result["worst_trade_pct"]) == (2.0, -0.5)
    assert result["avg_bars_held"] == pytest.approx(5 / 4)
    assert result["exposure_pct"] == pytest.approx(5 / 7 * 100)
    assert result["total_fees"] == 4
    assert result["buy_and_hold_return_pct"] == pytest.approx(30)


def test_undefined_ratios_are_none() -> None:
    flat = np.full(5, INITIAL)
    out = m.compute(flat, TIMES[:5], [], INITIAL, benchmark=(1, 1), bars_per_year=8760)
    assert out["sharpe"] is None and out["sortino"] is None and out["calmar"] is None
    assert out["profit_factor"] is None and out["win_rate_pct"] is None
    assert out["max_drawdown_pct"] == 0 and out["max_drawdown_start"] is None
    assert out["exposure_pct"] == 0 and out["trades"] == 0
    only_wins = m.compute(
        EQUITY, TIMES, [trade(10, 1, 1)], INITIAL, benchmark=(1, 1), bars_per_year=8760
    )
    assert only_wins["profit_factor"] is None  # no losses: undefined, not infinity


def test_initial_drawdown_starts_at_the_first_bar() -> None:
    out = m.compute(
        np.array([9_000.0, 9_500.0]), TIMES[:2], [], INITIAL, benchmark=(1, 1), bars_per_year=1
    )
    assert out["max_drawdown_pct"] == pytest.approx(-10)
    assert out["max_drawdown_start"] == TIMES[0].isoformat()
    assert out["max_drawdown_recovered"] is None


SECONDS_PER_STEP = {"h": 3600, "min": 60, "D": 86400}


@pytest.mark.parametrize(("freq", "expected"), [("h", 8760), ("min", 525_600), ("D", 365)])
def test_periods_per_year(freq: str, expected: int) -> None:
    index = pd.date_range("2025-01-01", periods=10, freq=freq, tz="UTC")
    assert m.periods_per_year(index) == pytest.approx(expected)
    assert m.periods_per_year(index[:1]) is None
    assert m.periods_per_year(index.as_unit("ns")) == pytest.approx(expected)
    assert m.unix_seconds(index.as_unit("ms"))[1] - m.unix_seconds(index)[0] == pytest.approx(
        SECONDS_PER_STEP[freq]
    )


def test_downsampling_keeps_extremes() -> None:
    rng = np.random.default_rng(3)
    equity = 10_000 * np.exp(np.cumsum(rng.normal(0, 0.01, 100_000)))
    dd = equity / np.maximum.accumulate(equity) - 1
    idx = m.downsample_indices(equity, dd, 2_000)
    assert len(idx) <= 2_000
    assert np.all(np.diff(idx) > 0)
    assert idx[0] == 0 and idx[-1] == len(equity) - 1
    for k in (np.argmin(equity), np.argmax(equity), np.argmin(dd)):
        assert k in idx
    small = m.downsample_indices(equity[:500])
    assert small.tolist() == list(range(500))
