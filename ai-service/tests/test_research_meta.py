import numpy as np
import pandas as pd
import pytest

from app.config import instruments, strategy
from app.features.setup_features import CONTEXT, FEATURES, PATTERN, context_features, features
from app.research.baselines import market, random_trade
from app.research.meta import (
    C_GRID,
    E2,
    MIN_ACCEPTED,
    accept,
    deflated_sharpe,
    h2,
    inner_folds,
    main,
    run,
    scored_rows,
    sign_test,
    top_counts,
    uniqueness,
)
from app.research.walkforward import folds, predict, target
from app.setups.labels import label_all
from tests.test_features_setup import _frames

L1 = strategy("L1")
XAU = instruments()["XAUUSD"]


def _dataset(n: int = 1800, seed: int = 0) -> pd.DataFrame:
    """Setups of two instruments over 2012-2024 whose net R depends on ``x``."""
    rng = np.random.default_rng(seed)
    t0, t1 = pd.Timestamp("2012-01-02", tz="UTC"), pd.Timestamp("2024-06-28", tz="UTC")
    t = pd.to_datetime(np.sort(rng.integers(t0.value, t1.value, n)), utc=True)
    x = rng.normal(size=n)
    win = rng.random(n) < 1 / (1 + np.exp(-(1.5 * x - 0.3)))
    net_r = np.where(win, rng.uniform(0.1, 2.5, n), -rng.uniform(0.1, 1.1, n))
    held = pd.to_timedelta(rng.integers(1, 49, n) * 15, unit="min")
    return pd.DataFrame(
        {
            "symbol": rng.choice(["XAUUSD", "EURUSD"], n),
            "decision_utc": t,
            "exit_utc": t + held,
            "x": x,
            "noise": rng.normal(size=n),
            "gap": np.where(rng.random(n) < 0.1, np.nan, rng.normal(size=n)),
            "net_r": net_r,
            "net_r_2x": net_r - 0.05,
            "y": (net_r > 1.5).astype(int),
        }
    )


def _tests(n_acc: int, acc_r: float, all_r: float, seed: int = 0) -> pd.DataFrame:
    """Test rows over 2018-2024: ``n_acc`` accepted at ``acc_r``, the rest at ``all_r``."""
    rng = np.random.default_rng(seed)
    n = 700
    t = pd.date_range("2018-01-02", "2024-06-20", periods=n, tz="UTC")
    accepted = np.zeros(n, bool)
    accepted[rng.choice(n, n_acc, replace=False)] = True
    r = np.where(accepted, acc_r, all_r) + rng.normal(0, 0.01, n)
    fold = np.minimum(((t - pd.Timestamp("2018-01-01", tz="UTC")).days // 182).to_numpy(), 12)
    return pd.DataFrame(
        {"decision_utc": t, "net_r": r, "net_r_2x": r - 0.05, "accepted": accepted, "fold": fold}
    )


def test_pattern_and_context_split_the_38_features() -> None:
    assert len(FEATURES) == 38 and len(PATTERN) == 9 and len(CONTEXT) == 29
    assert set(PATTERN) | set(CONTEXT) == set(FEATURES) and not set(PATTERN) & set(CONTEXT)


def test_ev_rule_uses_the_training_means_only() -> None:
    df = _dataset()
    pred = predict(df, ["x"], E2)
    a = accept(df, pred)
    fs = folds(df)
    y, r = target(df), df["net_r"].to_numpy()
    for k, g in a.groupby("fold"):
        tr = fs[k].train
        assert g["m1"].iloc[0] == pytest.approx(r[tr][y[tr] == 1].mean())
        assert g["m0"].iloc[0] == pytest.approx(r[tr][y[tr] == 0].mean())
    assert ((a["p"] * a["m1"] + (1 - a["p"]) * a["m0"] > 0) == a["accepted"]).all()
    moved = df.copy()
    last = fs[-1].test  # trained on by no window
    moved.loc[last, "net_r"] = moved.loc[last, "net_r"] * 10
    b = accept(moved, pred)
    assert np.allclose(a["m1"], b["m1"]) and np.allclose(a["m0"], b["m0"])
    assert (a["accepted"] == b["accepted"]).all()


def test_h2_below_the_minimum_is_insufficient() -> None:
    assert h2(_tests(MIN_ACCEPTED - 1, 1.0, -0.1), boot=500)["status"] == "insufficient"


def test_h2_is_supported_by_a_clear_gain_in_most_years() -> None:
    h = h2(_tests(200, 0.5, -0.2), boot=2000)
    assert h["accepted"] == 200 and h["lower"] > 0
    assert h["years_ok"] >= 4 and h["status"] == "supported"
    assert h["precision"] == pytest.approx(1.0)


def test_h2_without_a_gain_is_not_supported() -> None:
    h = h2(_tests(200, -0.2, -0.2), boot=2000)
    assert h["lower"] < 0 and h["status"] == "not supported"


def test_h2_needs_the_yearly_condition_too() -> None:
    t = _tests(60, 0.6, 0.0)
    year = t["decision_utc"].dt.year
    t.loc[year < 2021, "accepted"] = False  # accepted trades only in 2021-2024
    t.loc[(year < 2021), "net_r"] = 0.5  # and the other years are good for every trade
    h = h2(t, boot=2000)
    assert h["years_ok"] < 4 and h["status"] == "not supported"


def test_sign_test() -> None:
    assert sign_test(np.array([1.0] * 13)) == (13, 13, pytest.approx(2 / 2**13))
    assert sign_test(np.array([1.0, -1.0, np.nan, 0.0]))[:2] == (1, 2)


def test_inner_folds_expand_in_time_and_are_purged_and_embargoed() -> None:
    rows = _dataset().iloc[:900].reset_index(drop=True)
    fs = inner_folds(rows)
    assert len(fs) == 3
    for i, (tr, va) in enumerate(fs):
        first = rows["decision_utc"].iloc[va].min()
        assert (rows["exit_utc"].iloc[tr] + pd.Timedelta(days=1) <= first).all()
        if i:
            assert len(tr) > len(fs[i - 1][0])
            assert first > rows["decision_utc"].iloc[fs[i - 1][1]].max()


def test_e2_picks_c_from_the_grid_and_learns_the_feature() -> None:
    df = _dataset()
    y, w = target(df), np.abs(df["net_r"].to_numpy())
    m = E2().fit(df[["x", "noise"]].to_numpy(), y, w / w.mean(), df)
    assert m.c in C_GRID and len(m.losses) == len(C_GRID)
    coef = m.info(None)["importance"]
    assert coef[0] > 0.5 and abs(coef[1]) < abs(coef[0]) / 5


@pytest.mark.parametrize("model", ["lr", "lgbm", "mlp"])
def test_each_family_runs_the_protocol_and_finds_the_edge(model: str) -> None:
    df = _dataset()
    pred, info = run(df, model, ["x", "noise", "gap"])
    t = scored_rows(df, pred)
    assert len(t) == sum(len(f.test) for f in folds(df)) and len(info) == 13
    assert t["p"].between(0, 1).all()
    acc = t[t["accepted"]]
    assert len(acc) >= MIN_ACCEPTED and acc["net_r"].mean() > t["net_r"].mean()


def test_the_design_label_runs_with_its_own_means() -> None:
    df = _dataset()
    pred, _ = run(df, "lr", ["x"], "tp")
    a = accept(df, pred, "tp")
    tr = folds(df)[0].train
    assert a.loc[a["fold"] == 0, "m1"].iloc[0] == pytest.approx(
        df["net_r"].to_numpy()[tr][df["y"].to_numpy()[tr] == 1].mean()
    )


def test_deflated_sharpe_falls_with_the_number_of_trials() -> None:
    r = np.random.default_rng(0).normal(0.1, 1.0, 400)
    one, ten = deflated_sharpe(r, 1), deflated_sharpe(r, 10)
    assert one["sr0"] == 0 and ten["sr0"] > 0
    assert ten["dsr"] < one["dsr"]
    assert deflated_sharpe(np.random.default_rng(1).normal(1.0, 1.0, 400), 10)["dsr"] > 0.99
    assert np.isnan(deflated_sharpe(np.ones(5))["dsr"])


def test_top_counts_never_rank_zero_coefficients() -> None:
    m = np.array([[0.0, 0.0, 0.0], [0.0, -0.5, 0.2], [0.3, 0.0, 0.0]])
    assert list(top_counts(m, k=2)) == [1, 1, 1]
    assert list(top_counts(np.zeros((13, 38)))) == [0] * 38


def test_uniqueness_of_disjoint_and_identical_labels() -> None:
    t = pd.to_datetime(["2020-01-06 10:00", "2020-01-06 12:00"], utc=True)
    apart = pd.DataFrame({"decision_utc": t, "exit_utc": t + pd.Timedelta(hours=1)})
    assert list(uniqueness(apart)) == [1.0, 1.0]
    same = pd.DataFrame({"decision_utc": t[[0, 0]], "exit_utc": t[[0, 0]] + pd.Timedelta("1h")})
    assert list(uniqueness(same)) == [0.5, 0.5]
    half = pd.DataFrame(  # 4 bars each, 2 shared: (2 * 1 + 2 * 0.5) / 4
        {"decision_utc": t[[0, 0]] + pd.to_timedelta([0, 30], "min"),
         "exit_utc": t[[0, 0]] + pd.to_timedelta([45, 75], "min")}
    )  # fmt: skip
    assert list(uniqueness(half)) == [0.75, 0.75]


def test_the_design_label_is_refused_outside_trial_10(tmp_path) -> None:
    assert main(["--model", "lgbm", "--label", "tp", "--store", str(tmp_path)]) == 2
    assert main(["--model", "lr", "--label", "tp", "--arm", "e0", "--store", str(tmp_path)]) == 2


def _e1_setups(frames: dict) -> pd.DataFrame:
    df = label_all(frames, "XAUUSD", L1)
    return df[df["state"] == "CLOSED"].reset_index(drop=True)


def test_context_features_of_a_setup_are_its_full_features_without_the_pattern() -> None:
    frames = _frames()
    e1 = _e1_setups(frames)
    assert len(e1) >= 3
    full = features(frames, e1, "XAUUSD", L1)
    pd.testing.assert_frame_equal(context_features(frames, e1, "XAUUSD", L1), full[CONTEXT])


def _random_trades(frames: dict, n: int = 40) -> pd.DataFrame:
    m = market(frames, L1)
    rng = np.random.default_rng(3)
    keys = sorted(m.pool, key=lambda k: -len(m.pool[k]))[:4]
    rows = [random_trade(m, y, h, 1.2, rng, L1, XAU) for y, h in keys for _ in range(n // 4)]
    return pd.DataFrame([r for r in rows if r is not None])


def test_random_entries_carry_what_their_features_and_purge_need() -> None:
    frames = _frames()
    t = _random_trades(frames)
    assert len(t) >= 5
    assert (t["exit_idx"] > t["decision_idx"]).all()
    assert np.allclose(t["risk"], 1.2 * t["atr"])
    assert t["r_multiple"].between(L1.min_r, L1.max_r).all() and t["target_source"].notna().all()
    f = context_features(frames, t, "XAUUSD", L1)
    assert list(f.columns) == CONTEXT
    assert np.allclose(f["risk_atr"], 1.2) and np.allclose(f["r_multiple"], t["r_multiple"])


def test_context_features_of_random_entries_never_change_when_bars_are_appended() -> None:
    full = _frames()
    t = _random_trades(full)
    whole = context_features(full, t, "XAUUSD", L1)
    cut_bar = int(t["decision_idx"].median()) + 1
    cut = full["15m"]["close_utc"].iloc[cut_bar]
    part = {k: v[v["close_utc"] <= cut].reset_index(drop=True) for k, v in full.items()}
    early = t[t["decision_idx"] < cut_bar]
    assert len(early) >= 1
    got = context_features(part, early, "XAUUSD", L1)
    pd.testing.assert_frame_equal(got, whole.loc[early.index])
