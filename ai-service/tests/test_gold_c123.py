"""Gold candidates C1-C3 (app/research/gold_c123.py): the helpers on hand-built data."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_c123 as g
from tests.test_gold_pbk import ctx


def test_zscore_uses_only_earlier_values() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 200)
    x[[5, 50]] = np.nan
    z = g.zscore(x, look=20)
    z_cut = g.zscore(x[:120], look=20)
    np.testing.assert_allclose(z[:120], z_cut, equal_nan=True)  # no future value used
    valid = pd.Series(x).dropna()
    sd = valid.iloc[:20].std()  # the first z is at the 21st valid value
    first = valid.index[20]
    assert z[first] == pytest.approx(x[first] / sd)
    assert np.isnan(z[: valid.index[20]]).all()


def test_at_local_follows_london_dst() -> None:
    n = 12 * 24 * 2
    cx = ctx(*(np.full(n, 100.0),) * 4)
    ts = pd.date_range("2024-07-01 00:00", periods=n, freq="5min", tz="UTC")
    cx.m = pd.DataFrame({"ts_utc": ts, "close_utc": ts + pd.Timedelta("5min")})
    k = g.at_local(cx, pd.Series(["2024-07-01", "2024-07-02", ""]), "08:00", g.LONDON)
    # 08:00 London in summer is 07:00 UTC: the bar opening 06:55 closes then
    assert cx.m["close_utc"].iloc[k[0]] == pd.Timestamp("2024-07-01 07:00", tz="UTC")
    assert k[1] == k[0] + 288 and k[2] == -1


def test_the_release_gate() -> None:
    n = 40
    cx = ctx(*(np.full(n, 100.0),) * 4)
    rel = np.array([cx.m["close_utc"].iloc[20].tz_convert(None).to_datetime64()],
                   dtype="datetime64[ns]")  # fmt: skip
    near = g.gated(cx, np.arange(n), rel)
    assert near[17:24].all() and not near[16] and not near[24]  # +/- 15 minutes = 3 bars
