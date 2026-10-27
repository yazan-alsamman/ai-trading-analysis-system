"""Rollover instants, swap conversion to R, the scenarios, and the zero-swap property of scalp and
intraday horizons (docs/strategies/PREREG.md, section 6)."""

import pandas as pd
import pytest

from app.config import instruments, signal_specs
from app.strategies import swap
from app.strategies.base import STEP
from app.strategies.rules import candidates
from app.strategies.swap import SwapSpec
from tests.strategy_data import market


def spec(mode="POINTS", long=-50.0, short=10.0, **kw) -> SwapSpec:
    base = dict(symbol="XAUUSD", mode=mode, long=long, short=short, rollover3days=3, point=0.01,
                contract_size=100.0, currency_base="XAU", currency_profit="USD",
                currency_margin="XAU")  # fmt: skip
    return SwapSpec(**{**base, **kw})


def T(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def test_one_week_has_five_rollovers_with_a_triple_wednesday() -> None:
    got = swap.instants(T("2024-06-10 00:00"), T("2024-06-17 00:00"), spec())
    # summer: 00:00 Athens = 21:00 UTC = 17:00 New York, Monday to Friday
    assert list(got["at"]) == [T(f"2024-06-{d} 21:00") for d in (10, 11, 12, 13, 14)]
    assert list(got["weight"]) == [1, 1, 3, 1, 1]


def test_rollover_is_18_00_new_york_in_the_mismatch_week() -> None:
    got = swap.instants(T("2024-10-28 00:00"), T("2024-10-29 00:00"), spec())
    (at,) = got["at"]
    assert at == T("2024-10-28 22:00")  # EU on winter time, US still on summer time
    assert at.tz_convert("America/New_York").hour == 18
    (winter,) = swap.instants(T("2024-11-05 00:00"), T("2024-11-06 00:00"), spec())["at"]
    assert winter.tz_convert("America/New_York").hour == 17


def test_open_at_the_instant_means_entry_before_and_exit_at_or_after() -> None:
    t = T("2024-06-11 21:00")
    s = spec()
    assert len(swap.instants(t - pd.Timedelta(minutes=1), t, s)) == 1
    assert len(swap.instants(t - pd.Timedelta(minutes=1), t - pd.Timedelta(seconds=1), s)) == 0
    assert len(swap.instants(t, t + pd.Timedelta(hours=1), s)) == 0


def test_day_multipliers_replace_the_triple_day() -> None:
    s = spec(day_multipliers={1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 3.0})
    got = swap.instants(T("2024-06-10 00:00"), T("2024-06-17 00:00"), s)
    assert list(got["weight"]) == [1, 1, 1, 1, 3]


def test_conversion_to_r_by_swap_mode() -> None:
    risk = 2.0
    assert swap.per_night_r(spec("DISABLED"), "buy", 2000, 2000, risk) == 0.0
    assert swap.per_night_r(spec("POINTS"), "buy", 2000, 2000, risk) == pytest.approx(-0.25)
    assert swap.per_night_r(spec("POINTS"), "sell", 2000, 2000, risk) == pytest.approx(0.05)
    assert swap.per_night_r(spec("REOPEN_BID"), "buy", 2000, 2000, risk) == pytest.approx(-0.25)
    eur = dict(symbol="EURUSD", point=1e-5, contract_size=1e5, currency_base="EUR",
               currency_profit="USD", currency_margin="EUR")  # fmt: skip
    r = 0.002
    assert swap.per_night_r(spec("CURRENCY_SYMBOL", long=-5, **eur), "buy", 1.1, 1.0, r) == (
        pytest.approx(-5 * 1.1 / (r * 1e5))
    )
    assert swap.per_night_r(spec("CURRENCY_MARGIN", long=-5, **eur), "buy", 1.1, 1.0, r) == (
        pytest.approx(-5 * 1.1 / (r * 1e5))
    )
    assert swap.per_night_r(spec("CURRENCY_PROFIT", long=-5, **eur), "buy", 1.1, 1.0, r) == (
        pytest.approx(-5 / (r * 1e5))
    )
    assert swap.per_night_r(spec("CURRENCY_DEPOSIT", long=-5, **eur), "buy", 1.1, 1.0, r) == (
        pytest.approx(-5 / (r * 1e5))
    )  # USD deposit = the profit currency
    jpy = dict(symbol="USDJPY", point=1e-3, contract_size=1e5, currency_base="USD",
               currency_profit="JPY", currency_margin="USD")  # fmt: skip
    assert swap.per_night_r(spec("CURRENCY_DEPOSIT", long=-5, **jpy), "buy", 150, 150, 0.3) == (
        pytest.approx(-5 * 150 / (0.3 * 1e5))
    )
    assert swap.per_night_r(spec("INTEREST_CURRENT", long=-2, **eur), "buy", 1.2, 1.0, r) == (
        pytest.approx(1.2 * -2 / 100 / 360 / r)
    )
    assert swap.per_night_r(spec("INTEREST_OPEN", long=-2, **eur), "buy", 1.2, 1.0, r) == (
        pytest.approx(1.0 * -2 / 100 / 360 / r)
    )
    with pytest.raises(ValueError):
        swap.per_night_r(spec("CURRENCY_MARGIN", currency_margin="GBP"), "buy", 1, 1, 1)
    with pytest.raises(ValueError):
        spec("SOMETHING")


def test_scenarios_w1_stress_and_decision() -> None:
    s = spec()  # POINTS: long -0.25 R a night, short +0.05 R at risk 2.0
    a, b = T("2024-06-10 12:00"), T("2024-06-13 12:00")  # Mon, Tue, Wed (x3) rollovers
    assert swap.swap_r(s, "buy", a, b, 2.0, 2000) == pytest.approx(-0.25 * 5)
    assert swap.swap_r(s, "sell", a, b, 2.0, 2000) == pytest.approx(0.05 * 5)
    assert swap.stress_r(s, a, b, 2.0, 2000) == pytest.approx(-2 * 0.25 * 5)
    assert swap.decision_r(-0.3, None) == -0.3
    assert swap.decision_r(-0.3, -0.5) == -0.5


def test_results_use_the_price_at_each_rollover() -> None:
    e = market("XAUUSD")["4h"]
    price_at = swap.close_before(e)
    t = T("2024-10-01 21:00")  # a rollover instant
    i = int((e["close_utc"] <= t).to_numpy().nonzero()[0][-1])
    assert price_at(t) == e["close"].iloc[i]
    s = spec("INTEREST_CURRENT", long=-2.0)
    a, b = e["close_utc"].iloc[3], e["close_utc"].iloc[40]
    nights = swap.instants(a, b, s)
    expect = sum(w * price_at(x) * -2.0 / 100 / 360 / 5.0 for x, w in nights.values)
    assert swap.swap_r(s, "buy", a, b, 5.0, 1.0, price_at) == pytest.approx(expect)
    assert swap.swap_r(s, "buy", a, b, 5.0, 2000.0) != pytest.approx(expect)  # entry price
    with pytest.raises(ValueError):
        price_at(e["close_utc"].iloc[0] - pd.Timedelta(hours=1))


@pytest.mark.parametrize("symbol", ["XAUUSD", "EURUSD"])
def test_scalp_and_intraday_horizons_never_cross_a_rollover(symbol: str) -> None:
    """Every armed scalp and intraday candidate, from its entry to the end of its registered
    horizon, on a market that spans both autumn daylight-saving changes."""
    f, inst, s = market(symbol), instruments()[symbol], spec()
    crossing = {}
    for sp in signal_specs().values():
        e = f[sp.frame]
        for c in candidates(f, inst, sp):
            if c.state != "ARMED":
                continue
            end = swap.horizon_end(e["close_utc"], c.idx, c.horizon_bars, STEP[sp.frame],
                                   c.deadline)  # fmt: skip
            n = len(swap.instants(e["close_utc"].iloc[c.idx], end, s))
            crossing[sp.type] = crossing.get(sp.type, 0) + (n > 0)
    assert crossing["scalp"] == 0 and crossing["intraday"] == 0
    assert crossing["swing"] > 0  # S3 holds for days: the check can see a crossing
