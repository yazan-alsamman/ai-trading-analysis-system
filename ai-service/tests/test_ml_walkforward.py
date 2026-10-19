import numpy as np
import pandas as pd

from app.ml.dataset import FEATURES
from app.ml.walkforward import (
    EMBARGO,
    closed_before,
    evaluate,
    fit_and_calibration,
    predict_window,
    render,
    walk_forward,
    windows,
)


def _synthetic(n=700, seed=0):
    """Setups from 2012 to 2024-06 whose label depends on one feature (fvg_atr)."""
    rng = np.random.default_rng(seed)
    start, end = pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2024-07-01", tz="UTC")
    decision = pd.to_datetime(np.sort(rng.uniform(start.value, end.value, n)), utc=True)
    x = rng.normal(size=(n, len(FEATURES)))
    signal = x[:, FEATURES.index("fvg_atr")]  # not overwritten below
    y = (rng.random(n) < 1 / (1 + np.exp(-(-1.0 + 1.5 * signal)))).astype(int)
    df = pd.DataFrame(x, columns=FEATURES)
    df["r_multiple"], df["cost_r"] = 2.0, 0.2
    df.insert(0, "decision_ts", decision)
    df.insert(1, "exit_ts", decision + pd.Timedelta(hours=6))
    df["y"] = y
    df["realized_r"] = np.where(y == 1, 2.0, -1.0)
    df["net_r"] = df["realized_r"] - df["cost_r"]
    return df


def test_windows_cover_2018_to_the_lockbox():
    w = windows()
    assert len(w) == 7
    assert w[0][0] == pd.Timestamp("2018-01-01", tz="UTC")
    assert w[-1] == (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-07-01", tz="UTC"))


def test_training_rows_closed_an_embargo_before_the_window():
    df = _synthetic()
    start = pd.Timestamp("2020-01-01", tz="UTC")
    train = closed_before(df, start)
    assert (train["exit_ts"] + EMBARGO <= start).all()
    near = df[(df["exit_ts"] < start) & (df["exit_ts"] + EMBARGO > start)]
    assert near.index.isin(train.index).sum() == 0


def test_calibration_slice_is_the_latest_and_fit_rows_close_before_it():
    train = closed_before(_synthetic(), pd.Timestamp("2020-01-01", tz="UTC"))
    fit, cal = fit_and_calibration(train)
    assert len(cal) == round(0.2 * len(train))
    assert fit["decision_ts"].max() < cal["decision_ts"].min()
    assert (fit["exit_ts"] + EMBARGO <= cal["decision_ts"].min()).all()


def test_predictions_ignore_everything_after_the_window():
    df = _synthetic()
    start, end = pd.Timestamp("2019-01-01", tz="UTC"), pd.Timestamp("2020-01-01", tz="UTC")
    before = predict_window(df, start, end)
    later = df.copy()
    future = later["decision_ts"] >= end
    later.loc[future, "y"] = 1 - later.loc[future, "y"]  # rewrite the future
    later.loc[future, FEATURES] = 0.0
    pd.testing.assert_frame_equal(before, predict_window(later, start, end))


def test_an_informative_feature_gives_positive_skill_and_a_report():
    pred = walk_forward(_synthetic(n=1500))
    assert pred["window"].nunique() == 7
    res = evaluate(pred)
    assert res["models"]["logistic"]["brier_skill"] > 0
    assert res["models"]["logistic"]["auc"] > 0.65
    assert abs(res["models"]["base_rate"]["brier_skill"]) < 1e-12
    assert "## By test window" in render(res)
