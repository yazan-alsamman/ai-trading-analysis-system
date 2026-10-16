"""Builder strategies: every op on hand-built series, groups, edge-triggering, NaN handling,
strength, details, history, and exact replicas of global strategies."""

import json

import numpy as np
import pytest
import trading_indicators as ti

import trading_strategies as ts
from tests.conftest import synthetic_ohlcv
from tests.custom_utils import (
    MA_CROSSOVER_REPLICA,
    RSI_REVERSAL_REPLICA,
    builder,
    cond,
    const,
    frame,
    ind,
    price,
    signal_bars,
)

CLOSE = price("close")


def run(definition: dict, df):
    return ts.BuilderStrategy(definition).generate(df)


def buy_when(node: dict, df) -> dict[int, int]:
    return signal_bars(run(builder(buy={"all": [node]}), df))


# --- operators -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "expected"),
    [
        (">", {2: 1}),  # close [1, 2, 3, 2, 1] > 2 only on bar 2
        ("<", {0: 1, 4: 1}),
        (">=", {1: 1}),  # true on 1..3: one event when it becomes true
        ("<=", {0: 1, 3: 1}),  # true on 0, 1, then 3, 4
    ],
)
def test_comparisons(op: str, expected: dict) -> None:
    df = frame([1, 2, 3, 2, 1])
    assert buy_when(cond(CLOSE, op, const(2)), df) == expected


def test_crosses_above_and_below() -> None:
    df = frame([1, 3, 3, 1, 2, 4, 1])
    # above 2: prev <= 2 < now on bars 1 and 5; below 2: prev >= 2 > now on bars 3 and 6
    assert buy_when(cond(CLOSE, "crosses_above", const(2)), df) == {1: 1, 5: 1}
    assert buy_when(cond(CLOSE, "crosses_below", const(2)), df) == {3: 1, 6: 1}


def test_crosses_with_touch() -> None:
    # touching the level and leaving on the same side is not a cross; from == level it is
    df = frame([1, 2, 1, 2, 3])
    assert buy_when(cond(CLOSE, "crosses_above", const(2)), df) == {4: 1}


def test_crosses_with_shift() -> None:
    df = frame([1, 2, 3, 4, 1, 1])
    # close shifted 1: [nan, 1, 2, 3, 4, 1] crosses above 2 on bar 3 (2 -> 3)
    assert buy_when(cond(price("close", shift=1), "crosses_above", const(2)), df) == {3: 1}
    # close vs. its own value 2 bars ago: [1,2,3,4,1,1] vs [nan,nan,1,2,3,4]
    # close > close[2] on 2, 3; crosses_below on 4 (4 > 2 -> 1 < 3)
    assert buy_when(cond(CLOSE, "crosses_below", price("close", shift=2)), df) == {4: 1}


def test_shift_larger_than_the_data_is_all_nan() -> None:
    df = frame([1, 2, 3])
    assert buy_when(cond(price("close", shift=100), "<", const(10)), df) == {}


def test_between_is_inclusive() -> None:
    df = frame([1, 2, 3, 4, 5, 3])
    node = {"op": "between", "value": CLOSE, "lower": const(2), "upper": const(4)}
    assert buy_when(node, df) == {1: 1, 5: 1}  # true on 1..3 and 5


def test_rising_and_falling_are_strict() -> None:
    df = frame([1, 2, 3, 3, 4, 5, 6, 5, 4, 3])
    rising = {"op": "rising", "value": CLOSE, "bars": 2}
    falling = {"op": "falling", "value": CLOSE, "bars": 2}
    # rising over 2 bars: c[t] > c[t-1] > c[t-2]: bars 2, 5, 6 (3 == 3 breaks it)
    assert buy_when(rising, df) == {2: 1, 5: 1}
    # falling over 2 bars: 8, 9
    assert buy_when(falling, df) == {8: 1}
    assert buy_when({"op": "rising", "value": CLOSE, "bars": 1}, df) == {1: 1, 4: 1}


def test_multiplier() -> None:
    df = frame([10, 10, 10], volume=[10, 16, 14])
    vol_avg = ind("volume_sma", length=1, multiplier=1.5)  # 1.5 x the volume itself
    assert buy_when(cond(price("volume", shift=1), "<", vol_avg), df) == {1: 1}
    # volume[t-1] < 1.5 * volume[t]: 10 < 24 on bar 1, 16 < 21 on bar 2 (still true)
    out = run(builder(buy={"all": [cond({**CLOSE, "multiplier": 2}, ">", const(15))]}), df)
    assert signal_bars(out) == {0: 1}
    assert out["details"].iloc[0]["conditions"][0]["left"] == 20.0


def test_price_fields() -> None:
    df = frame([10, 10], open_=[1, 1], high=[20, 20], low=[0, 0], volume=[5, 50])
    expect = {"hl2": 10.0, "hlc3": 10.0, "ohlc4": 31 / 4, "open": 1.0, "volume": 5.0}
    for field, value in expect.items():
        out = run(builder(buy={"all": [cond(price(field), ">=", const(value))]}), df)
        assert signal_bars(out) == {0: 1}, field
        details = out["details"].iloc[0]["conditions"][0]
        assert details["left"] == pytest.approx(value)
    assert buy_when(cond(price("volume"), ">", const(10)), df) == {1: 1}


def test_indicator_operand_values_match_the_library() -> None:
    df = synthetic_ohlcv(400, seed=3)
    out = run(builder(buy={"all": [cond(ind("rsi", length=14), "<", const(35))]}), df)
    rsi = ti.rsi(df["close"], 14).to_numpy()
    with np.errstate(invalid="ignore"):
        tree = rsi < 35
    expected = np.flatnonzero(tree & ~np.concatenate(([False], tree[:-1])))
    assert list(signal_bars(out)) == expected.tolist()
    t = int(expected[0])
    assert out["details"].iloc[t]["conditions"][0]["left"] == pytest.approx(rsi[t], abs=1e-6)


def test_multi_output_indicator() -> None:
    df = synthetic_ohlcv(300, seed=4)
    bands = ti.bollinger(df["close"], 20, 2.0)
    out = run(
        builder(buy={"all": [cond(CLOSE, "<", ind("bollinger", output="lower", length=20))]}), df
    )
    below = (df["close"] < bands["lower"]).to_numpy()
    assert (
        list(signal_bars(out))
        == np.flatnonzero(below & ~np.concatenate(([False], below[:-1]))).tolist()
    )


# --- groups, edges, conflicts, NaN ----------------------------------------------------------------


def test_nested_and_or() -> None:
    df = frame([1, 5, 2, 6, 3, 7, 4])
    # buy when close > 4 AND (close > 6 OR close < 6): any is always true except at 6
    node = {"any": [cond(CLOSE, ">", const(6)), cond(CLOSE, "<", const(6))]}
    out = run(builder(buy={"all": [cond(CLOSE, ">", const(4)), node]}), df)
    assert signal_bars(out) == {1: 1, 5: 1}  # bar 3 (6): the OR is false
    inner = {"all": [cond(CLOSE, ">", const(5)), cond(CLOSE, "<", const(7))]}
    out = run(builder(buy={"any": [cond(CLOSE, "<", const(2)), inner]}), df)
    assert signal_bars(out) == {0: 1, 3: 1}


def test_edge_triggered() -> None:
    df = frame([1, 2, 3, 4, 1, 2, 3])
    # close > 1 is true on 1, 2, 3, then 5, 6: one event per run of true bars
    assert buy_when(cond(CLOSE, ">", const(1)), df) == {1: 1, 5: 1}
    # true on the very first bar: the bar before the data counts as false
    assert buy_when(cond(CLOSE, ">", const(0)), df) == {0: 1}


def test_buy_and_sell_on_the_same_bar_give_nothing() -> None:
    df = frame([1, 3, 1, 3, 5])
    d = builder(
        buy={"all": [cond(CLOSE, ">", const(2))]},
        sell={"all": [cond(CLOSE, ">", const(4))]},
    )
    assert signal_bars(run(d, df)) == {1: 1, 3: 1, 4: -1}
    d["sell"] = {"all": [cond(CLOSE, ">=", const(3))]}  # fires with buy on 1 and 3
    assert signal_bars(run(d, df)) == {}


def test_sell_only_definition() -> None:
    df = frame([3, 1, 3, 1])
    assert signal_bars(run(builder(sell={"any": [cond(CLOSE, "<", const(2))]}), df)) == {
        1: -1,
        3: -1,
    }


def test_nan_makes_a_condition_false() -> None:
    df = frame([1, np.nan, 3, 4, np.nan, 6])
    assert buy_when(cond(CLOSE, ">", const(0)), df) == {0: 1, 2: 1, 5: 1}
    assert buy_when(cond(CLOSE, "<=", const(100)), df) == {0: 1, 2: 1, 5: 1}
    rising = {"op": "rising", "value": CLOSE, "bars": 1}
    assert buy_when(rising, df) == {3: 1}
    between = {"op": "between", "value": CLOSE, "lower": const(0), "upper": const(10)}
    assert buy_when(between, df) == {0: 1, 2: 1, 5: 1}
    # an OR with a NaN branch still fires through the other branch
    either = {"any": [cond(CLOSE, ">", const(0)), cond(CLOSE, "<", const(-1))]}
    assert buy_when(either, frame([np.nan, 1])) == {1: 1}


# --- strength, reason, details -------------------------------------------------------------------


def test_rule_ratio_and_fixed_strength() -> None:
    df = frame([1, 5, 5])
    children = [
        cond(CLOSE, ">", const(2)),
        cond(CLOSE, ">", const(4)),
        cond(CLOSE, ">", const(6)),
    ]
    out = run(builder(buy={"any": children}, strength="rule_ratio"), df)
    assert signal_bars(out) == {1: 1}
    assert out["strength"].iloc[1] == pytest.approx(2 / 3)
    assert out["reason"].iloc[1] == "builder_buy"
    details = out["details"].iloc[1]
    assert details["rules"] == "any" and details["true"] == 2 and details["total"] == 3
    assert [c["true"] for c in details["conditions"]] == [True, True, False]
    assert details["conditions"][0] == {"op": ">", "true": True, "left": 5.0, "right": 2.0}
    fixed = run(builder(buy={"any": children}), df)
    assert fixed["strength"].iloc[1] == 1.0


def test_details_of_every_op_are_json() -> None:
    df = frame([1, 2, 3, 4, 5, 6])
    group = {"all": [cond(CLOSE, ">", const(0))]}
    node = {
        "all": [
            cond(CLOSE, "crosses_above", const(3.5)),
            {"op": "between", "value": CLOSE, "lower": const(0), "upper": const(9)},
            {"op": "rising", "value": CLOSE, "bars": 3},
            group,
        ]
    }
    out = run(builder(sell=node), df)
    assert signal_bars(out) == {3: -1}
    details = out["details"].iloc[3]
    json.dumps(details)
    assert out["reason"].iloc[3] == "builder_sell"
    cross, between, rising, sub = details["conditions"]
    assert cross == {
        "op": "crosses_above",
        "true": True,
        "left": 4.0,
        "right": 3.5,
        "left_prev": 3.0,
        "right_prev": 3.5,
    }
    assert between == {"op": "between", "true": True, "value": 4.0, "lower": 0.0, "upper": 9.0}
    assert rising == {"op": "rising", "true": True, "value": 4.0, "value_start": 1.0, "bars": 3}
    assert sub == {"group": "all", "true": True}


# --- computation, inputs, history ----------------------------------------------------------------


def test_each_distinct_indicator_is_computed_once(monkeypatch) -> None:
    calls = []
    original = ti.compute

    def counting(name, df, **params):
        calls.append((name, tuple(sorted(params.items()))))
        return original(name, df, **params)

    monkeypatch.setattr(ti, "compute", counting)
    d = builder(
        buy={
            "all": [cond(ind("rsi", length=14), "<", const(30)), cond(ind("rsi"), "<", const(40))]
        },
        sell={
            "any": [
                cond(ind("rsi", shift=2), ">", const(70)),  # same rsi(14), shifted
                cond(ind("ema", length=9), ">", ind("ema", length=9, shift=1)),
            ]
        },
    )
    strategy = ts.BuilderStrategy(d)
    strategy.generate(synthetic_ohlcv(300))
    assert sorted(calls) == [("ema", (("length", 9),)), ("rsi", (("length", 14),))]
    assert strategy.indicators({}) == [
        {"name": "rsi", "params": {"length": 14}},
        {"name": "ema", "params": {"length": 9}},
    ]


def test_inputs_follow_the_operands() -> None:
    assert ts.BuilderStrategy(builder(buy={"all": [cond(CLOSE, ">", const(1))]})).inputs == (
        "close",
    )
    d = builder(buy={"all": [cond(price("hl2"), ">", ind("volume_sma"))]})
    assert ts.BuilderStrategy(d).inputs == ("high", "low", "volume")
    with pytest.raises(ValueError, match="missing column"):
        ts.BuilderStrategy(d).generate(frame([1, 2]).drop(columns="volume"))


def test_history_formula() -> None:
    rsi = ti.get_indicator("rsi")
    warmup = rsi.lookback({"length": 14}) + rsi.convergence({"length": 14})
    d = builder(
        buy={"all": [{"op": "rising", "value": ind("rsi", shift=3), "bars": 5}]},
        sell={"all": [cond(CLOSE, "crosses_below", const(1))]},
    )
    assert ts.BuilderStrategy(d).history() == warmup + 3 + 5 + 2
    plain = builder(buy={"all": [cond(CLOSE, ">", const(1))]})
    assert ts.BuilderStrategy(plain).history() == 2
    with pytest.raises(ValueError, match="unknown parameter"):
        ts.BuilderStrategy(plain).history({"x": 1})


@pytest.mark.parametrize("seed", range(6))
def test_history_is_enough(seed: int) -> None:
    """From history() bars on, the signals do not depend on how much earlier data exists."""
    from tests.custom_utils import random_builder

    rng = np.random.default_rng(100 + seed)
    df = synthetic_ohlcv(1500, seed=seed)
    for _ in range(4):
        strategy = ts.BuilderStrategy(random_builder(rng))
        full = strategy.generate(df)["signal"].to_numpy()
        need = strategy.history()
        for start in (300, 777):
            part = strategy.generate(df.iloc[start:])["signal"].to_numpy()
            np.testing.assert_array_equal(part[need:], full[start:][need:])


def test_short_and_empty_input() -> None:
    strategy = ts.BuilderStrategy(MA_CROSSOVER_REPLICA)
    for n in (0, 1, 5):
        out = strategy.generate(synthetic_ohlcv(5).iloc[:n])
        assert len(out) == n and (out["signal"] == 0).all()


def test_to_dict_like_a_global_strategy() -> None:
    strategy = ts.BuilderStrategy(MA_CROSSOVER_REPLICA, key="custom:x", title="EMA cross")
    d = strategy.to_dict()
    json.dumps(d)
    assert d["key"] == "custom:x" and d["title"] == "EMA cross" and d["category"] == "trend"
    assert d["params"] == [] and d["history"] == strategy.history()


# --- replicas of the global strategies -----------------------------------------------------------


@pytest.mark.parametrize("seed", [42, 7, 2024])
def test_ma_crossover_replica_is_exact(seed: int) -> None:
    df = synthetic_ohlcv(5000, seed=seed)
    replica = ts.BuilderStrategy(MA_CROSSOVER_REPLICA).generate(df)
    original = ts.run("ma_crossover", df)
    assert (original["signal"] != 0).sum() > 100
    np.testing.assert_array_equal(replica["signal"].to_numpy(), original["signal"].to_numpy())


@pytest.mark.parametrize("seed", [42, 7, 2024])
def test_rsi_reversal_replica_is_exact(seed: int) -> None:
    df = synthetic_ohlcv(5000, seed=seed)
    replica = ts.BuilderStrategy(RSI_REVERSAL_REPLICA).generate(df)
    original = ts.run("rsi_reversal", df)
    assert (original["signal"] != 0).sum() > 50
    np.testing.assert_array_equal(replica["signal"].to_numpy(), original["signal"].to_numpy())
