import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from app.research.walkforward import (
    Platt,
    calibration_line,
    ece,
    ece_debiased,
    ece_debiased_ci,
    fit_weights,
    folds,
    mass_bins,
    predict,
    reliability,
    scores,
    split_calibration,
    target,
)


def _dataset(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    """Setups spread over 2012-2024 with a feature that drives the outcome."""
    rng = np.random.default_rng(seed)
    t0, t1 = pd.Timestamp("2012-01-02", tz="UTC"), pd.Timestamp("2024-06-28", tz="UTC")
    t = pd.to_datetime(np.sort(rng.integers(t0.value, t1.value, n)), utc=True)
    x = rng.normal(size=n)
    win = rng.random(n) < 1 / (1 + np.exp(-(x - 1)))
    net_r = np.where(win, rng.uniform(0.1, 2.5, n), -rng.uniform(0.1, 1.1, n))
    held = pd.to_timedelta(rng.integers(1, 60, n) * 15, unit="min")
    return pd.DataFrame(
        {
            "decision_utc": t,
            "exit_utc": t + held,
            "x": x,
            "noise": rng.normal(size=n),
            "net_r": net_r,
            "y": (net_r > 1.5).astype(int),  # the design label: TP first
        }
    )


class _LR:
    """The model interface of ``predict``: a plain weighted logistic regression."""

    def __init__(self) -> None:
        self.seen: dict = {}

    def fit(self, x, y, sample_weight, rows):
        self.seen = {"w": sample_weight, "rows": rows}
        self.m = LogisticRegression().fit(x, y, sample_weight=sample_weight)
        return self

    def predict_proba(self, x):
        return self.m.predict_proba(x)

    def info(self, x_test):
        return {"w": self.seen["w"], "rows": self.seen["rows"]}


def test_thirteen_six_month_windows_with_purge_and_embargo() -> None:
    df = _dataset()
    fs = folds(df)
    assert len(fs) == 13
    assert fs[0].start == pd.Timestamp("2018-01-01", tz="UTC")
    assert fs[-1].end == pd.Timestamp("2024-07-01", tz="UTC")
    for f in fs:
        tr, te = df.iloc[f.train], df.iloc[f.test]
        assert (tr["exit_utc"] + pd.Timedelta(days=1) <= f.start).all()
        assert ((te["decision_utc"] >= f.start) & (te["decision_utc"] < f.end)).all()
    assert len(fs[1].train) > len(fs[0].train)  # expanding


def test_a_setup_whose_outcome_reaches_into_the_embargo_is_not_trained_on() -> None:
    df = _dataset()
    start = pd.Timestamp("2018-01-01", tz="UTC")
    late = pd.DataFrame(
        {
            "decision_utc": [start - pd.Timedelta(hours=30)],
            "exit_utc": [start - pd.Timedelta(hours=20)],  # known 20 h before: inside the day
            "x": [0.0],
            "noise": [0.0],
            "net_r": [1.0],
            "y": [0],
        }
    )
    df = pd.concat([df, late], ignore_index=True).sort_values("decision_utc")
    df = df.reset_index(drop=True)
    row = int(np.flatnonzero(df["exit_utc"] == start - pd.Timedelta(hours=20))[0])
    assert row not in folds(df)[0].train


def test_calibration_slice_is_the_latest_quarter_and_purged_from_the_fit_rows() -> None:
    df = _dataset()
    train = folds(df)[3].train
    fit, cal = split_calibration(df, train)
    assert len(cal) == round(len(train) * 0.25)
    first = df["decision_utc"].iloc[cal].min()
    assert df["decision_utc"].iloc[fit].max() < first
    assert (df["exit_utc"].iloc[fit] + pd.Timedelta(days=1) <= first).all()


def test_the_label_is_net_r_above_zero_and_the_design_label_on_request() -> None:
    df = pd.DataFrame({"net_r": [0.4, 0.0, -1.0, 2.0], "y": [0, 0, 0, 1]})
    assert list(target(df)) == [1, 0, 0, 1]  # a zero R trade is not a win
    assert list(target(df, "tp")) == [0, 0, 0, 1]
    with pytest.raises(ValueError):
        target(df, "sharpe")


def test_weights_are_abs_net_r_with_mean_one() -> None:
    w = fit_weights(np.array([2.0, -1.0, 0.0, 1.0]))
    assert w.mean() == pytest.approx(1.0)
    assert list(w) == pytest.approx([2.0, 1.0, 0.0, 1.0])
    assert list(fit_weights(np.zeros(3))) == [1.0, 1.0, 1.0]


def test_each_fit_set_gets_its_own_weights_and_rows() -> None:
    df = _dataset()
    info: list = []
    predict(df, ["x"], _LR, info=info)
    fs = folds(df)
    for d in info:
        fit, _ = split_calibration(df, fs[d["fold"]].train)
        assert d["w"].mean() == pytest.approx(1.0)
        assert d["w"] == pytest.approx(np.abs(df["net_r"].to_numpy()[fit]) / np.abs(
            df["net_r"].to_numpy()[fit]).mean())  # fmt: skip
        assert list(d["rows"].index) == list(fit)


def test_platt_maps_a_shifted_score_back_to_the_hit_rate() -> None:
    rng = np.random.default_rng(1)
    true = rng.uniform(0.05, 0.6, 4000)
    y = (rng.random(4000) < true).astype(int)
    shifted = np.clip(true + 0.3, 0, 1)
    assert ece(shifted, y) > 0.2
    assert ece(Platt().fit(shifted, y).predict(shifted), y) < 0.05  # the P4 gate value


def test_equal_mass_bins_hold_the_same_number_of_predictions() -> None:
    p = np.random.default_rng(2).random(1003)
    sizes = [len(b) for b in mass_bins(p)]
    assert len(sizes) == 10 and sum(sizes) == 1003 and max(sizes) - min(sizes) <= 1
    edges = [p[b].max() for b in mass_bins(p)]
    assert edges == sorted(edges)


def test_ece_is_zero_when_rates_match_and_the_gap_otherwise() -> None:
    levels = np.linspace(0.05, 0.95, 10)
    p = np.repeat(levels, 100)
    y = np.concatenate([(np.arange(100) < round(100 * q)).astype(int) for q in levels])
    assert ece(p, y) == pytest.approx(0.0)
    assert ece(np.full(400, 0.9), np.tile([1, 0], 200)) == pytest.approx(0.4)


def test_debiased_ece_removes_the_noise_of_a_calibrated_model() -> None:
    rng = np.random.default_rng(3)
    p = rng.uniform(0.2, 0.7, 1000)
    y = (rng.random(1000) < p).astype(int)
    raw = ece(p, y)
    deb = ece_debiased(p, y, np.random.default_rng(4))
    assert raw > 0.01  # a calibrated model still shows ECE by noise on 1,000 trades
    assert abs(deb) < 0.015
    off = np.clip(p + 0.15, 0, 1)
    floor = raw - deb  # the noise floor of 1,000 trades in 10 bins
    assert ece_debiased(off, y, np.random.default_rng(4)) == pytest.approx(
        ece(off, y) - floor, abs=0.01
    )
    assert ece_debiased(off, y, np.random.default_rng(4)) > 0.05  # fails the gate


def test_debiased_ece_interval_resamples_whole_weeks() -> None:
    rng = np.random.default_rng(5)
    p = rng.uniform(0.2, 0.7, 600)
    y = (rng.random(600) < p).astype(int)
    weeks = np.repeat(np.arange(60), 10)
    lo, hi = ece_debiased_ci(p, y, weeks, np.random.default_rng(6), boot=50, sims=100)
    assert lo < ece_debiased(p, y, np.random.default_rng(6), sims=100) < hi


def test_calibration_line_is_zero_and_one_for_calibrated_predictions() -> None:
    rng = np.random.default_rng(7)
    p = rng.uniform(0.05, 0.95, 20000)
    y = (rng.random(20000) < p).astype(int)
    a, b = calibration_line(p, y)
    assert a == pytest.approx(0.0, abs=0.06) and b == pytest.approx(1.0, abs=0.06)
    rel = reliability(p, y)
    assert len(rel) == 10 and (rel["rate"] - rel["mean_p"]).abs().max() < 0.03


def test_walk_forward_learns_an_informative_feature_and_not_noise() -> None:
    df = _dataset()
    y = target(df)
    good = scores(predict(df, ["x"], _LR), y)
    noise = scores(predict(df, ["noise"], _LR), y)
    assert good["bss"] > 0.05 and good["ece_debiased"] < 0.03
    assert noise["bss"] < 0.02
    assert {"intercept", "slope", "ece"} <= set(good)
