"""Gold tighter SL (app/research/gold_sl.py)."""

import pandas as pd
import pytest

from app.research import gold_sl as gsl


def test_resize_changes_only_the_distance() -> None:
    sig = pd.DataFrame({"i": [5, 9], "dir": [1.0, -1.0], "entry": [100.0, 101.0],
                        "risk": [24.0, 30.0]})  # fmt: skip
    assert gsl.resize(sig, "BASE")["risk"].tolist() == [24.0, 30.0]
    assert gsl.resize(sig, "H50")["risk"].tolist() == [12.0, 15.0]
    assert gsl.resize(sig, "H67")["risk"].tolist() == pytest.approx([16.0, 20.0])
    assert gsl.resize(sig, "USD10")["risk"].tolist() == [10.0, 10.0]
    out = gsl.resize(sig, "USD15")
    assert out["risk"].tolist() == [15.0, 15.0]
    assert out[["i", "dir", "entry"]].equals(sig[["i", "dir", "entry"]])
    assert sig["risk"].tolist() == [24.0, 30.0]  # the input is not changed
