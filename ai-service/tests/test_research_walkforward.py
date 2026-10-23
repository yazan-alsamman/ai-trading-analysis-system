import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from app.research.walkforward import (
    choose_calibrator,
    ece,
    folds,
    predict,
    scores,
    split_calibration,
)


def _dataset(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    """Setups spread over 2012-2024 with a feature that drives the label."""
    rng = np.random.default_rng(seed)
    t0, t1 = pd.Timestamp("2012-01-02", tz="UTC"), pd.Timestamp("2024-06-28", tz="UTC")
    t = pd.to_datetime(np.sort(rng.integers(t0.value, t1.value, n)), utc=True)
    x = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(x - 1)))).astype(int)
    held = pd.to_timedelta(rng.integers(1, 60, n) * 15, unit="min")
    return pd.DataFrame(
        {"decision_utc": t, "exit_utc": t + held, "x": x, "noise": rng.normal(size=n), "y": y}
    )


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
            "y": [1],
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


def test_ece_is_zero_when_rates_match_and_the_gap_otherwise() -> None:
    p = np.array([0.25] * 4 + [0.75] * 4)
    y = np.array([1, 0, 0, 0, 1, 1, 1, 0])
    assert ece(p, y) == pytest.approx(0.0)
    assert ece(np.full(4, 0.9), np.array([1, 0, 1, 0])) == pytest.approx(0.4)


def test_calibrator_maps_a_shifted_score_back_to_the_hit_rate() -> None:
    rng = np.random.default_rng(1)
    true = rng.uniform(0.05, 0.6, 4000)
    y = (rng.random(4000) < true).astype(int)
    cal = choose_calibrator(np.clip(true + 0.3, 0, 1), y)
    assert ece(cal.predict(np.clip(true + 0.3, 0, 1)), y) < 0.05  # the P4 gate value


def test_walk_forward_learns_an_informative_feature_and_not_noise() -> None:
    df = _dataset()
    y = df["y"].to_numpy()
    good = scores(predict(df, ["x"], lambda: LogisticRegression()), y)
    noise = scores(predict(df, ["noise"], lambda: LogisticRegression()), y)
    assert good["bss"] > 0.05 and good["ece"] < 0.06
    assert noise["bss"] < 0.02
