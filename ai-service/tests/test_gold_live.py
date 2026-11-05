"""Gold v1 live check (app/research/gold_live.py): matching the EA's log with Python's trades."""

# ruff: noqa: E501 (log lines as the EA writes them)

import io

import pandas as pd
import pytest

from app.research import gold_live as gv

LOG = """time_server,event,strategy,kind,dir,bar_server,level,entry,sl,risk,lots,ticket,price,note
2026.01.13 16:45:10,FILL,LVL4H,PDH,1,2026.01.13 16:45:00,4630.21,4630.21,4604.41,25.80,1.00,11,4630.40,stop
2026.01.13 18:00:00,EXIT,LVL4H,PDH,1,2026.01.13 16:45:00,4630.21,4630.21,0,25.80,0.00,11,4604.41,sl
2026.01.13 18:00:00,DEAL,LVL4H,,0,,0,0,0,0,1.00,11,-2600.00,net money
2026.01.14 09:05:00,TOUCH,PIVOT,R1,1,2026.01.14 09:00:00,4700.00,0,0,9.00,0.00,0,0,busy
2026.01.15 10:00:30,FILL,PIVOT,S1,-1,2026.01.15 10:00:00,4500.00,4500.00,4509.00,9.00,1.00,12,4499.9,stop
2026.01.15 11:00:00,EXIT,PIVOT,S1,-1,2026.01.15 10:00:00,4500.00,4500.00,0,9.00,0.00,12,4491.00,16:45
2026.01.15 11:00:00,DEAL,PIVOT,,0,,0,0,0,0,1.00,12,893.00,net money
"""


def py() -> pd.DataFrame:
    return pd.DataFrame({
        "strategy": ["LVL4H", "PIVOT"], "dir": [1.0, 1.0], "level": [4630.21, 4700.0],
        "risk": [25.80, 9.0], "gross": [-1.0, 0.5], "net": [-1.02, 0.48],
        "bar_server": ["2026.01.13 16:45:00", "2026.01.14 09:00:00"],
    })  # fmt: skip


def test_trades_are_matched_on_strategy_and_signal_bar() -> None:
    j, n = gv.check(gv.read_log(io.StringIO(LOG)), py())
    assert (n["python"], n["ea"], n["matched"], n["dir_agree"]) == (2, 2, 1, 1)
    assert n["gross_ea"] == pytest.approx(-1.0)
    assert n["net_ea_all"] == pytest.approx((-2600 / 2580 + 893 / 900) / 2)
    only_py = j[j["_merge"] == "left_only"]
    assert only_py["ea_reason"].tolist() == ["busy"]
    assert "EA only (1)" in gv.render(j, n)
