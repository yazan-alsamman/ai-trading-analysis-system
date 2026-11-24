"""The decision functions of docs/strategies/PREREG.md, sections 8-10, on made-up trade values
(no outcome of any strategy is involved)."""

import numpy as np
import pandas as pd
import pytest

from app.research import decide

B, SEED = 4000, 11


def T(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def trades(blocks: int, per_block: int, mean: float, sd: float, seed: int = 0):
    """``per_block`` trades in each of ``blocks`` 4-week blocks from 2018-01-01."""
    rng = np.random.default_rng(seed)
    n = blocks * per_block
    days = np.repeat(np.arange(blocks) * 28, per_block) + rng.integers(0, 28, n)
    ts = pd.DatetimeIndex(T("2018-01-01") + pd.to_timedelta(days, "D") + pd.Timedelta(hours=10))
    x = rng.normal(0, sd, n)
    x = x - x.mean() + mean  # the sample mean is exactly ``mean``
    return x, x - 0.0, ts  # d = x - e with e = 0 (E0 at zero)


def test_blocks_are_calendar_four_weeks_from_monday_2018_01_01() -> None:
    ts = [T("2018-01-01"), T("2018-01-28 23:59"), T("2018-01-29"), T("2017-12-31")]
    assert list(decide.block_ids(ts)) == [0, 0, 1, -1]
    assert list(decide.block_ids(ts, weeks=1)) == [0, 3, 4, -1]


def test_percentile_and_wald_p_values() -> None:
    assert decide.p_percentile(np.ones(99)) == pytest.approx(1 / 100)  # never below 1/(B+1)
    assert decide.p_percentile(-np.ones(99)) == 1.0
    assert decide.p_wald(0.1, np.zeros(10), 30) == 0.0
    star = np.random.default_rng(0).normal(0.1, 0.05, 20_000)
    assert decide.p_wald(0.1, star, 30) == pytest.approx(0.0275, abs=0.003)  # t(29) at 2.0


def test_bootstrap_is_trade_weighted_with_shared_draws() -> None:
    x = np.array([1.0, 1.0, 1.0, -2.0])
    blocks = np.array([0, 0, 0, 1])
    (xs, ys), k = decide.bootstrap([x, 2 * x], blocks, 2000, np.random.default_rng(1))
    assert k == 2
    assert set(np.round(xs, 6)) <= {1.0, -2.0, round(1 / 4, 6)}  # (3 - 2) / 4 when both drawn
    assert np.allclose(ys, 2 * xs)  # the same draws for every component


def test_holm_adjustment() -> None:
    adj = decide.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    assert decide.holm({"a": 0.6, "b": 0.7}) == {"a": 1.0, "b": 1.0}


def test_a_low_frequency_strategy_with_enough_evidence_can_pass() -> None:
    x, d, ts = trades(blocks=40, per_block=1, mean=0.8, sd=0.4)  # one trade a month
    t = decide.strategy_test(x, d, ts, B, SEED)
    assert t.method_ok and t.n == 40
    adj = decide.holm({"S": t.p, **{f"o{i}": 1.0 for i in range(5)}})["S"]
    result = decide.classify(adj, t.method_ok, t.upper, 0.05)
    assert result == "passed"
    assert decide.status("A", result, holdout_consistent=True) == "validated"
    assert decide.status("A", result, holdout_consistent=False) == "inconclusive"
    assert decide.status("B", result, holdout_consistent=True) == "exploratory"
    with pytest.raises(ValueError):
        decide.status("A", result, None)


def test_the_same_trades_spread_differently_over_days_give_the_same_status() -> None:
    x, d, ts = trades(blocks=36, per_block=3, mean=0.3, sd=1.0, seed=4)
    blocks = decide.block_ids(ts)
    moved = pd.DatetimeIndex(T("2018-01-01") + pd.to_timedelta(blocks * 28 + 27, "D"))
    a = decide.strategy_test(x, d, ts, B, SEED)
    b = decide.strategy_test(x, d, moved, B, SEED)  # every trade on the block's last day
    assert a == b


def test_weak_evidence_is_inconclusive_and_clear_absence_unvalidated() -> None:
    x, d, ts = trades(blocks=35, per_block=2, mean=0.05, sd=1.2, seed=5)
    t = decide.strategy_test(x, d, ts, B, SEED)
    assert decide.classify(1.0, t.method_ok, t.upper, 0.05) == "inconclusive"
    x, d, ts = trades(blocks=80, per_block=40, mean=-0.2, sd=0.8, seed=6)
    t = decide.strategy_test(x, d, ts, B, SEED)
    assert t.upper < 0.05
    assert decide.classify(1.0, t.method_ok, t.upper, 0.05) == "unvalidated"


def test_method_condition_needs_30_blocks() -> None:
    x, d, ts = trades(blocks=20, per_block=10, mean=1.0, sd=0.3)
    t = decide.strategy_test(x, d, ts, B, SEED)
    assert (t.k, t.method_ok, t.p) == (20, False, 1.0)
    assert decide.classify(0.0, t.method_ok, t.upper, 0.05) == "inconclusive"
    p, k = decide.paired_test(x, ts, B, SEED)
    assert (p, k) == (1.0, 20)


def test_power_statements_match_the_registered_reference_values() -> None:
    # PREREG section 8: sd 1.22, DE 1.2 -> n_unval 5,300 for 0.05 R and 1,325 for 0.10 R
    assert decide.n_unval(0.05, 1.22, 1.2) == pytest.approx(5300, rel=0.002)
    assert decide.n_unval(0.10, 1.22, 1.2) == pytest.approx(1325, rel=0.002)
    assert decide.mde(1000, 1.22, 1.2, 0.05) == pytest.approx(
        (1.6449 + 0.8416) * 1.22 * 1.2 / np.sqrt(1000), rel=1e-3
    )


def test_delta_star_is_the_median_assumed_cost_with_a_floor() -> None:
    a = decide.assumed_cost_r(
        spread=np.array([0.3, 0.3]), risk=np.array([2.0, 4.0]), extra_frac=0.5,
        extra_min=0.10, sl_slippage=0.10, swap_h=np.array([-0.05, 0.2]),
    )  # fmt: skip
    assert a == pytest.approx([(0.15 + 0.10) / 2 + 0.05, (0.15 + 0.10) / 4])  # credit counts 0
    assert decide.delta_star(a) == pytest.approx(np.median(a))
    assert decide.delta_star(np.array([0.01, 0.02])) == 0.05


BUNDLES = ["M0", "M1", "M2"]
START = T("2020-01-01")


def family_c(n: int = 120, r=(0.0, 0.1, 0.1)) -> pd.DataFrame:
    """``n`` training trades, one a day from 2019-01-01, each exiting a day later under every
    bundle, with net R ``r`` per bundle; then 40 trades in the test window [START, +6 months)."""
    entry = T("2019-01-01") + pd.to_timedelta(np.arange(n), "D")
    test = START + pd.to_timedelta(np.arange(40) * 4, "D")
    e = entry.append(test)
    df = pd.DataFrame({"entry_utc": e})
    for b, x in zip(BUNDLES, r, strict=True):
        df[decide.exit_col(b)] = e + pd.Timedelta(days=1)
        df[decide.r_col(b)] = x
    return df


def test_family_c_selection_ties_and_minimum() -> None:
    df = family_c()
    assert decide.select_bundle(df, BUNDLES, START) == "M1"  # tie -> lower index
    assert decide.select_bundle(family_c(99), BUNDLES, START) == "M0"  # < 100 training trades
    assert decide.training(df, BUNDLES, START).sum() == 120  # the test trades are not training


def test_a_missing_bundle_column_is_an_error() -> None:
    df = family_c().drop(columns=[decide.exit_col("M2")])
    with pytest.raises(KeyError, match="exit_utc_M2"):
        decide.select_bundle(df, BUNDLES, START)
    with pytest.raises(KeyError, match="net_r_M1"):
        decide.window_trades(
            family_c().drop(columns=[decide.r_col("M1")]), (START, T("2020-07-01")), "M1"
        )


def test_training_needs_every_bundle_resolved_and_known_by_the_window_start() -> None:
    df = family_c()
    last = df.index[119]
    # M0's exit is known, but M2 still holds the trade at the window start: not training
    late = df.copy()
    late.loc[last, decide.exit_col("M2")] = START
    assert not decide.training(late, BUNDLES, START)[last]
    assert decide.training(late, BUNDLES, START).sum() == 119
    # unresolved under one bundle (NaT exit or NaN R): not training
    for col, value in [(decide.exit_col("M1"), pd.NaT), (decide.r_col("M2"), np.nan)]:
        un = df.copy()
        un.loc[last, col] = value
        assert not decide.training(un, BUNDLES, START)[last]
    # exit + 1 day exactly at the window start is known
    edge = df.copy()
    edge.loc[last, [decide.exit_col(b) for b in BUNDLES]] = START - pd.Timedelta(days=1)
    assert decide.training(edge, BUNDLES, START)[last]


def test_selection_ignores_outcomes_not_known_by_the_window_start() -> None:
    df = family_c(150, r=(0.0, 0.1, 0.05))
    want = decide.select_bundle(df, BUNDLES, START)
    rng = np.random.default_rng(0)
    # the trades known by the start keep their values; every other outcome is scrambled: the test
    # window, and training-period trades still open under some bundle at the start
    df.loc[df.index[140:150], decide.exit_col("M2")] = START + pd.Timedelta(days=3)
    known = decide.training(df, BUNDLES, START)
    assert known.sum() == 140
    for _ in range(5):
        x = df.copy()
        for b in BUNDLES:
            x.loc[~known, decide.r_col(b)] = rng.normal(5 if b == "M2" else -5, 1, (~known).sum())
        assert decide.select_bundle(x, BUNDLES, START) == want == "M1"


def test_test_trades_never_depend_on_bundles_not_chosen() -> None:
    df = family_c()
    window = (START, T("2020-07-01"))
    got, excluded = decide.window_trades(df, window, "M1")
    assert (len(got), excluded) == (40, 0)
    assert np.allclose(got["delta"], 0.1)  # own columns: net R of M1 - net R of M0
    test = df["entry_utc"] >= START
    # unchosen bundle M2: unresolved, scrambled or open long after the window start: no effect
    x = df.copy()
    x.loc[test, decide.r_col("M2")] = np.nan
    x.loc[test, decide.exit_col("M2")] = pd.NaT
    pd.testing.assert_frame_equal(decide.window_trades(x, window, "M1")[0], got)
    x.loc[test, decide.r_col("M2")] = np.random.default_rng(1).normal(0, 9, test.sum())
    pd.testing.assert_frame_equal(decide.window_trades(x, window, "M1")[0], got)
    # unresolved under M0 or under the chosen bundle: excluded and counted
    y = df.copy()
    first, second = df.index[test][:2]
    y.loc[first, decide.r_col("M0")] = np.nan
    y.loc[second, decide.r_col("M1")] = np.nan
    got_y, excluded_y = decide.window_trades(y, window, "M1")
    assert (len(got_y), excluded_y) == (38, 2)
    # the set of test trades depends on the entry time only, never on an exit
    z = df.copy()
    z.loc[test, decide.exit_col("M1")] = T("2030-01-01")
    pd.testing.assert_frame_equal(decide.window_trades(z, window, "M1")[0], got)


def test_holdout_check() -> None:
    assert decide.holdout_consistent(np.array([0.1, 0.2]), np.array([0.05, 0.0]))
    assert not decide.holdout_consistent(np.array([0.1, 0.2]), np.array([-0.05, 0.0]))
