"""Gold round numbers (app/research/gold_round.py)."""

from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.research import gold_round as gr


def test_round_levels_bracket_the_previous_close() -> None:
    cx = SimpleNamespace(d1=pd.DataFrame({"close": [4093.2, 4150.0, 4101.0]}))
    lv = gr.round_levels(cx, 50.0)
    assert np.isnan(lv["RU"][0]) and np.isnan(lv["RD"][0])  # no previous day
    assert lv["RD"][1:].tolist() == [4050.0, 4150.0]  # a close on a multiple is its RD
    assert lv["RU"][1:].tolist() == [4100.0, 4200.0]
    assert gr.round_levels(cx, 10.0)["RU"][1] == 4100.0
