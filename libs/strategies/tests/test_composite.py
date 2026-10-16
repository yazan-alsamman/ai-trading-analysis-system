"""Composite strategies on hand-built member signals: votes and the window, every mode,
edge-triggering, strength and details, nesting and history."""

import json

import numpy as np
import pandas as pd
import pytest

import trading_strategies as ts
from tests.conftest import synthetic_ohlcv
from tests.custom_utils import (
    MA_CROSSOVER_REPLICA,
    UUID_A,
    UUID_B,
    UUID_C,
    builder,
    cond,
    const,
    price,
    signal_bars,
)
from trading_strategies.composite import votes

COLUMNS = ("open", "high", "low", "volume")
REFS = {c: f"custom:{i:08x}-0000-4000-8000-00000000000{i}" for i, c in enumerate(COLUMNS, 1)}


def pulse_member(column: str) -> dict:
    """Buys when ``column`` is 1 (a pulse), sells when it is -1: one member per column, so
    each member's events are written by hand."""
    return builder(
        buy={"all": [cond(price(column), ">", const(0.5))]},
        sell={"all": [cond(price(column), "<", const(-0.5))]},
    )


def events_frame(**members: list[int]) -> pd.DataFrame:
    n = len(next(iter(members.values())))
    data = {c: np.zeros(n) for c in COLUMNS}
    for column, events in members.items():
        data[column] = np.asarray(events, dtype=float)
    data["close"] = np.ones(n)
    index = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(data, index=index)[["open", "high", "low", "close", "volume"]]


def resolve(ref: str):
    for column, r in REFS.items():
        if r == ref:
            return "builder", pulse_member(column)
    raise LookupError(ref)


def composite(columns, mode: str, window: int = 1, weights=None, **extra):
    weights = weights or [1.0] * len(columns)
    members = [{"ref": REFS[c], "weight": w} for c, w in zip(columns, weights, strict=True)]
    definition = {
        "schema_version": 1,
        "members": members,
        "mode": mode,
        "window": window,
        **extra,
    }
    return ts.CompositeStrategy(definition, resolve)


def test_member_events_are_what_the_frame_says() -> None:
    df = events_frame(open=[0, 1, 0, -1, 0, 1])
    member = ts.BuilderStrategy(pulse_member("open"))
    assert signal_bars(member.generate(df)) == {1: 1, 3: -1, 5: 1}


def test_votes_and_window() -> None:
    sig = np.array([0, 1, 0, 0, 0, -1, 0, 0])
    buy, sell = votes(sig, 3)
    assert np.flatnonzero(buy).tolist() == [1, 2, 3]
    assert np.flatnonzero(sell).tolist() == [5, 6, 7]
    buy, sell = votes(sig, 1)
    assert np.flatnonzero(buy).tolist() == [1] and np.flatnonzero(sell).tolist() == [5]
    # a sell inside the window cancels the buy vote
    buy, sell = votes(np.array([1, 0, -1, 0, 0]), 5)
    assert np.flatnonzero(buy).tolist() == [0, 1]
    assert np.flatnonzero(sell).tolist() == [2, 3, 4]
    buy, sell = votes(np.zeros(4, dtype=int), 20)
    assert not buy.any() and not sell.any()


def test_mode_all_needs_everyone_within_the_window() -> None:
    df = events_frame(open=[0, 0, 1, 0, 0, 0], high=[0, 0, 0, 1, 0, 0])
    assert signal_bars(composite(["open", "high"], "all", window=1).generate(df)) == {}
    out = composite(["open", "high"], "all", window=2).generate(df)
    assert signal_bars(out) == {3: 1}
    assert out["strength"].iloc[3] == 1.0
    assert out["reason"].iloc[3] == "composite_buy"


def test_mode_any_and_conflicts() -> None:
    df = events_frame(open=[0, 1, 0, 0, 1, 0], high=[0, 0, -1, 0, -1, 0])
    out = composite(["open", "high"], "any").generate(df)
    # bar 1: open buys -> buy (1 of 2); bar 2: high sells -> sell; bar 4: both -> nothing
    assert signal_bars(out) == {1: 1, 2: -1}
    assert out["strength"].iloc[1] == 0.5
    out = composite(["open", "high"], "any", window=3).generate(df)
    # open's buy vote (bars 1-3) overlaps high's sell vote (2-4): conflict, nothing fires;
    # bar 4: both emit again -> conflict too
    assert signal_bars(out) == {1: 1}


def test_mode_majority() -> None:
    df = events_frame(open=[0, 1, 0, 0], high=[0, 0, 1, 0], low=[0, 0, 0, -1])
    out = composite(["open", "high", "low"], "majority", window=2).generate(df)
    # bar 1: 1 of 3; bar 2: 2 of 3 -> buy; bar 3: open's vote expired, high buys, low sells
    assert signal_bars(out) == {2: 1}
    assert out["strength"].iloc[2] == pytest.approx(2 / 3)
    two = events_frame(open=[0, 1, 0], high=[0, 0, 0])
    assert signal_bars(composite(["open", "high"], "majority").generate(two)) == {}  # 1 of 2


def test_mode_weighted() -> None:
    df = events_frame(open=[0, 1, 0, 0, 0], high=[0, 0, 0, 1, 0])
    weighted = composite(["open", "high"], "weighted", weights=[1, 2], threshold=0.6)
    out = weighted.generate(df)
    assert signal_bars(out) == {3: 1}  # open alone: 1/3 < 0.6; high alone: 2/3
    assert out["strength"].iloc[3] == pytest.approx(2 / 3)
    exact = composite(["open", "high"], "weighted", weights=[1, 2], threshold=2 / 3)
    assert signal_bars(exact.generate(df)) == {3: 1}  # >= threshold, despite float sums
    conflict = events_frame(open=[0, -1, 0], high=[0, 1, 0])
    low = composite(["open", "high"], "weighted", weights=[1, 2], threshold=0.3)
    assert signal_bars(low.generate(conflict)) == {}  # both sides reach 0.3: nothing


def test_output_is_edge_triggered() -> None:
    df = events_frame(open=[0, 1, 0, 0, 0, 0, 1, 0])
    out = composite(["open", "high"], "any", window=3).generate(df)
    # open's buy vote lasts bars 1..3, then 6..8: one event per stretch
    assert signal_bars(out) == {1: 1, 6: 1}


def test_details_list_every_vote() -> None:
    df = events_frame(open=[0, 1, 0], high=[0, 1, 0], low=[0, -1, 0])
    out = composite(["open", "high", "low"], "majority").generate(df)
    assert signal_bars(out) == {1: 1}
    details = out["details"].iloc[1]
    json.dumps(details)
    assert details == {
        "mode": "majority",
        "window": 1,
        "agreement": pytest.approx(2 / 3, abs=1e-6),
        "members": [
            {"ref": REFS["open"], "weight": 1.0, "vote": "buy"},
            {"ref": REFS["high"], "weight": 1.0, "vote": "buy"},
            {"ref": REFS["low"], "weight": 1.0, "vote": "sell"},
        ],
    }


def test_history_is_longest_member_plus_window() -> None:
    definition = {
        "schema_version": 1,
        "members": [{"ref": "rsi_reversal"}, {"ref": "macd_cross"}, {"ref": UUID_A}],
        "mode": "any",
        "window": 4,
    }
    strategy = ts.CompositeStrategy(definition, lambda r: ("builder", MA_CROSSOVER_REPLICA))
    longest = max(
        ts.get_strategy("rsi_reversal").history(),
        ts.get_strategy("macd_cross").history(),
        ts.BuilderStrategy(MA_CROSSOVER_REPLICA).history(),
    )
    assert strategy.history() == longest + 4
    assert strategy.inputs == ("high", "low", "close")
    names = [i["name"] for i in strategy.indicators({})]
    assert names == ["rsi", "macd", "ema", "ema"]


def test_composite_of_globals_matches_votes_on_real_data() -> None:
    df = synthetic_ohlcv(3000, seed=5)
    definition = {
        "schema_version": 1,
        "members": [
            {"ref": "rsi_reversal", "params": {"oversold": 40, "overbought": 60}},
            {"ref": "bollinger_reversion", "params": {"std": 1.5}},
        ],
        "mode": "all",
        "window": 5,
    }
    out = ts.CompositeStrategy(definition).generate(df)
    a = ts.run("rsi_reversal", df, oversold=40, overbought=60)["signal"].to_numpy()
    b = ts.run("bollinger_reversion", df, std=1.5)["signal"].to_numpy()
    (ab, _), (bb, _) = votes(a, 5), votes(b, 5)
    want = ab & bb
    expected_buys = np.flatnonzero(want & ~np.concatenate(([False], want[:-1])))
    assert np.flatnonzero(out["signal"].to_numpy() == 1).tolist() == expected_buys.tolist()
    assert len(expected_buys) > 5


def test_nested_composites_and_snapshots() -> None:
    inner = {
        "schema_version": 1,
        "members": [{"ref": "rsi_reversal"}, {"ref": UUID_C}],
        "mode": "any",
    }
    defs = {UUID_B: ("composite", inner), UUID_C: ("builder", MA_CROSSOVER_REPLICA)}
    outer = {
        "schema_version": 1,
        "members": [{"ref": "macd_cross"}, {"ref": UUID_B, "weight": 3}],
        "mode": "weighted",
        "window": 2,
        "threshold": 0.7,
    }
    strategy = ts.CompositeStrategy(outer, lambda r: defs[r], key=UUID_A)
    df = synthetic_ohlcv(2000, seed=8)
    out = strategy.generate(df)
    assert (out["signal"] != 0).sum() > 10
    snap = ts.snapshot("composite", outer, lambda r: defs[r])
    assert set(snap["members"]) == {UUID_B, UUID_C}
    rebuilt = ts.from_snapshot(snap)
    pd.testing.assert_frame_equal(rebuilt.generate(df), out)
    assert rebuilt.history() == strategy.history()
