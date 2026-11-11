"""Gold losing-trade screen (app/research/gold_loss.py): the greedy filter and the buckets."""

import numpy as np
import pandas as pd

from app.research import gold_loss as gl_


def test_greedy_removes_the_planted_bad_bucket() -> None:
    rng = np.random.default_rng(1)
    n = 2000
    b = pd.DataFrame({"hour": rng.choice(["a", "b", "c", "d"], n),
                      "side": rng.choice(["buy", "sell"], n)})  # fmt: skip
    y = rng.normal(0.05, 1.0, n)
    y[b["hour"].to_numpy() == "c"] -= 1.0  # planted
    chosen, gain = gl_.greedy(b, y)
    assert chosen[0] == ("hour", "c")
    assert gain > 0.2
    keep = gl_.apply(b, chosen)
    assert not (b["hour"].to_numpy()[keep] == "c").any()


def test_bucketize_uses_the_tune_edges() -> None:
    f = pd.DataFrame({k: np.arange(10.0) for k in gl_.QUANT})
    tune = np.r_[np.ones(5, bool), np.zeros(5, bool)]  # edges from 0..4 only
    b = gl_.bucketize(f, gl_.edges(f, tune))
    assert b["moved"].tolist()[:5] == ["q1", "q2", "q3", "q4", "q5"]
    assert set(b["moved"].tolist()[5:]) == {"q5"}  # later values above the tune edges


def test_greedy_keeps_at_least_sixty_percent() -> None:
    n = 1000
    b = pd.DataFrame({"fill": ["stop"] * 990 + ["market"] * 10})
    y = np.r_[np.zeros(990), np.full(10, 5.0)]
    chosen, _ = gl_.greedy(b, y)
    assert chosen == []  # removing "stop" would keep 1%
    assert len(y) == n
