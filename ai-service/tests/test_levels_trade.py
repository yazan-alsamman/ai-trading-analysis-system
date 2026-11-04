"""Addendum 2, H_L2 (app/research/levels_trade.py): the trades of the real-level touches, the
server clock, the decision on hand-made tester results, and the report. Nothing here reads the
confirmation store."""

import numpy as np
import pandas as pd
import pytest

from app.research import levels_confirm as lc
from app.research import levels_trade as lt
from tests.strategy_data import market


def test_server_clock_is_athens() -> None:
    t = pd.Series(pd.to_datetime(["2024-01-15 10:00", "2024-07-15 10:00"], utc=True))
    expected = [pd.Timestamp("2024-01-15 12:00"), pd.Timestamp("2024-07-15 13:00")]
    assert list(lt.server(t)) == expected


@pytest.fixture(scope="module")
def trades():
    keep = lc.INSTRUMENTS, lc.STEP
    lc.INSTRUMENTS, lc.STEP = {"XAUUSD": None}, {"XAUUSD": 10.0}
    try:
        return lt.trades({"XAUUSD": market("XAUUSD", start="2023-09-25", end="2023-11-18")})
    finally:
        lc.INSTRUMENTS, lc.STEP = keep


def test_trades_follow_section_3(trades) -> None:
    t = trades
    assert len(t) > 0 and list(t["id"]) == list(range(1, len(t) + 1))
    buy = t["dir"] == "buy"
    assert (t.loc[buy, "sl"] < t.loc[buy, "level"]).all()
    assert (t.loc[buy, "tp"] > t.loc[buy, "level"]).all()
    assert (t.loc[~buy, "sl"] > t.loc[~buy, "level"]).all()
    assert np.allclose((t["tp"] - t["level"]).abs(), t["d"])
    assert np.allclose((t["level"] - t["sl"]).abs(), t["d"])
    assert ((t["expire_utc"] - t["place_utc"]) == pd.Timedelta(minutes=5)).all()
    assert (t["exit_utc"] - t["expire_utc"] >= pd.Timedelta(minutes=5 * lc.HZ)).all()


def results(t: pd.DataFrame, r: float) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    x = r + rng.normal(0, 0.1, len(t))
    return pd.DataFrame({"id": t["id"], "status": "closed", "close_reason": "tp",
                         "profit": 100 * x + 5, "commission": -5.0, "fee": 0.0, "swap": 0.0,
                         "risk_money": 100.0})  # fmt: skip


def test_the_decision_on_hand_made_results(trades) -> None:
    long = pd.concat([trades.assign(place_utc=trades["place_utc"] - pd.Timedelta(weeks=4 * k),
                                    id=trades["id"] + k * 10_000) for k in range(40)])  # fmt: skip
    good = lt.h_l2(lt.joined(long, results(long, 0.05)), boot=2000)
    assert good["method_ok"] and good["passed"] and good["mean"] == pytest.approx(0.05, abs=0.01)
    bad = lt.h_l2(lt.joined(long, results(long, -0.02)), boot=2000)
    assert not bad["passed"]
    short = lt.h_l2(lt.joined(trades, results(trades, 0.05)), boot=2000)
    assert not short["method_ok"] and not short["passed"]  # fewer than 30 blocks


def test_render(trades) -> None:
    j = lt.joined(trades, results(trades, 0.01))
    md = lt.render(j, lt.h_l2(j, boot=500), "2026-11-04")
    for text in ("once", "## Decision (section 5)", "Deflated Sharpe (N = 60)", "## Replay",
                 "At twice the commission"):  # fmt: skip
        assert text in md, text
