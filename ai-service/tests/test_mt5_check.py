"""The MT5 cost-model check (app/research/mt5_check.py): the sample, its file for the EA, and the
comparison with hand-made tester results. Nothing here reads the research store."""

import numpy as np
import pandas as pd
import pytest

from app.research import mt5_check as mc

UTC = "UTC"


def book() -> pd.DataFrame:
    t = pd.to_datetime(["2024-01-15 10:00", "2024-03-12 14:00", "2024-05-06 09:30",
                        "2023-12-29 10:00", "2024-07-01 00:05"], utc=True)  # fmt: skip
    df = pd.DataFrame({
        "symbol": "EURUSD", "strategy": "S1", "type": "intraday", "direction": ["buy", "sell"] * 2
        + ["buy"], "entry_utc": t, "exit_utc": t + pd.Timedelta(hours=2), "state": "resolved",
        "book": "primary", "reason": ["tp", "sl", "timeout", "tp", "tp"], "k": 1.5, "risk": 0.002,
        "entry": 1.1, "net_w0": [1.45, -1.06, 0.2, 1.45, 1.45],
        "net_2x": [1.4, -1.12, 0.15, 1.4, 1.4],
        "x": [1.45, -1.06, 0.2, 1.45, 1.45],
    })  # fmt: skip
    extra = df.iloc[[0]].assign(book="from_2012")  # the sensitivity book repeats primary trades
    return pd.concat([df, extra], ignore_index=True)


def test_sample_keeps_the_primary_window_outside_dst_mismatch_weeks() -> None:
    s = mc.sample(book())
    # 2024-03-12: US daylight saving started 03-10, EU 03-31; 2023 and 2024-07-01 are outside
    assert list(s["entry_utc"].dt.strftime("%m-%d")) == ["01-15", "05-06"]
    assert list(s["id"]) == [1, 2]
    jan, may = s.iloc[0], s.iloc[1]
    assert jan["entry_server"] == pd.Timestamp("2024-01-15 12:00")  # UTC+2 in winter
    assert may["entry_server"] == pd.Timestamp("2024-05-06 12:30")  # UTC+3 in summer
    assert jan["sl"] == pytest.approx(1.098) and jan["tp"] == pytest.approx(1.103)
    assert may["sl"] == pytest.approx(1.098)  # the May trade is a buy too
    assert jan["gross"] == pytest.approx(1.5) and jan["cost"] == pytest.approx(0.05)


def test_the_sample_file_is_what_the_ea_reads(tmp_path) -> None:
    p = tmp_path / mc.SAMPLE_FILE
    mc.write_sample(mc.sample(book()), p)
    raw = p.read_bytes().decode()
    assert raw.startswith(",".join(mc.SAMPLE_COLUMNS) + "\r\n")
    first = raw.split("\r\n")[1].split(",")
    assert len(first) == 13 and first[5] == "2024.01.15 12:00:00" and first[4] == "buy"


def results(s: pd.DataFrame) -> pd.DataFrame:
    """A TP at the level with 0.2 pips of spread and $7 commission a lot, then a timeout."""
    return pd.DataFrame({
        "id": s["id"], "status": "closed", "note": np.nan, "open_bid": [1.1, 1.1],
        "open_ask": [1.10002, 1.10002], "m1_close": [1.1, 1.1001], "close_reason": ["tp", "time"],
        "profit": [298.0, 50.0], "commission": [-7.0, -7.0], "fee": 0.0, "swap": 0.0,
        "risk_money": [200.0, 200.0],
    })  # fmt: skip


def test_joined_measures_the_tester_cost_on_agreeing_exits() -> None:
    s = mc.sample(book())
    j = mc.joined(s, results(s))
    tp = j.iloc[0]
    assert tp["mt5_net"] == pytest.approx((298 - 7) / 200)
    assert tp["mt5_cost"] == pytest.approx(1.5 - 291 / 200)
    assert tp["mt5_commission"] == pytest.approx(7 / 200)
    assert tp["mt5_spread"] == pytest.approx(0.01)
    assert j["same_exit"].all()  # a research timeout is a tester "time" exit
    assert j.iloc[1]["entry_gap"] == pytest.approx(0.05)


def test_render() -> None:
    s = mc.sample(book())
    md = mc.render(mc.joined(s, results(s)), 1, "2026-11-03")
    for text in ("decides nothing", "## By instrument", "## By type", "## By exit",
                 "Clock alignment", "| EURUSD | 2 | 2 | 100% |"):  # fmt: skip
        assert text in md, text
