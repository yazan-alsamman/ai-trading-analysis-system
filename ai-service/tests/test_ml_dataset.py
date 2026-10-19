import numpy as np
import pandas as pd
import pytest

from app.ml.dataset import FEATURES, build
from app.smc.params import FROZEN_V4, StrategyParams
from tests.test_smc_engine import DATA, _random_walk, _resample


def _closed_by(df: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    return df[df["exit_ts"] <= end].reset_index(drop=True)


def _assert_no_lookahead(bars, h1, h4, params, cutoffs):
    full = build(bars, h1, h4, params)
    assert len(full) > 0
    tf = pd.Timedelta(minutes=params.entry_tf_minutes)
    for cut in cutoffs:
        end = bars["ts_utc"].iloc[cut - 1] + tf
        part = build(bars.iloc[:cut], h1, h4, params)
        pd.testing.assert_frame_equal(_closed_by(part, end), _closed_by(full, end))


def test_features_do_not_look_ahead_on_a_random_walk():
    m15 = _random_walk(n=6000, seed=3)
    h1, h4 = _resample(m15, "1h"), _resample(m15, "4h")
    _assert_no_lookahead(m15, h1, h4, StrategyParams(), [2500, 4100, 5999])


def test_rows_are_closed_setups_with_scale_free_features():
    m15 = _random_walk(n=6000, seed=3)
    df = build(m15, _resample(m15, "1h"), _resample(m15, "4h"), StrategyParams())
    assert set(df["y"]) <= {0, 1}
    assert (df["y"] == (df["outcome"] == "tp")).all()
    assert (df["decision_ts"] < df["exit_ts"]).all()
    assert list(df.columns[-len(FEATURES) - 2 : -2]) == FEATURES
    assert np.isclose(df["net_r"], df["realized_r"] - df["cost_r"]).all()
    sessions = df[["session_asia", "session_london", "session_ny"]].sum(axis=1)
    assert sessions.isin([0.0, 1.0]).all()  # 17:00-18:00 belongs to none


@pytest.mark.skipif(not (DATA / "5m.parquet").exists(), reason="research store not built")
def test_features_do_not_look_ahead_on_real_data():
    bars, h1, h4 = (pd.read_parquet(DATA / f"{tf}.parquet") for tf in ("5m", "1h", "4h"))
    start, end = pd.Timestamp("2016-01-01", tz="UTC"), pd.Timestamp("2016-07-01", tz="UTC")
    bars = bars[(bars["ts_utc"] >= start) & (bars["ts_utc"] < end)].reset_index(drop=True)
    _assert_no_lookahead(bars, h1, h4, FROZEN_V4, [12_000, 25_000, len(bars) - 1])
