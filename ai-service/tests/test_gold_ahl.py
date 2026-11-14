"""Gold X1 large-leg exploration (app/research/gold_ahl.py) on synthetic bars; no market data."""

import numpy as np

from app.research import gold_ah as ah
from app.research import gold_ahf as ahf
from app.research import gold_ahl as ahl
from tests.test_gold_ahf import _bars


def test_explore_runs_and_reads_no_bar_after_2017(monkeypatch) -> None:
    m1 = _bars(30)
    monkeypatch.setattr(ahl, "load_d", lambda: m1)
    text = ahl.explore()
    assert "## 2. Exit grid" in text and "BIG+CHEAP" in text


def test_drift_is_signed_and_capped_at_the_day_end() -> None:
    m1 = _bars(10)
    cx = ah.context(m1)
    t = ahf.all_trades(cx, ah.raw_signals(cx))
    dr = ahl.drift(cx, t)
    i, d = t.i.to_numpy(), t.d.to_numpy()
    rr = d * (t.ext.to_numpy() - t.start.to_numpy())
    j = np.minimum(i + 360, cx.end[i])
    assert np.allclose(dr[360].to_numpy(), d * (cx.c[j] - cx.c[i]) / rr)
    assert (j <= cx.end[i]).all()
