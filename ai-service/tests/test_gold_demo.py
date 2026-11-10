"""Gold demo check (app/research/gold_demo.py) on a hand-built MT5 history report."""

import numpy as np
import pandas as pd
import pytest

from app.research import gold_demo as gd

HEAD = "<html><body><table>"
TAIL = "</table></body></html>"


def row(*cells: str, hidden: dict[int, str] | None = None) -> str:
    out = []
    for k, c in enumerate(cells):
        if hidden and k in hidden:
            out.append(f'<td class="hidden" colspan="8">{hidden[k]}</td>')
        out.append(f"<td>{c}</td>")
    return "<tr>" + "".join(out) + "</tr>"


def report() -> bytes:
    """A sell filled at a stop order (LVL4H PDL) that hits its SL, a buy at market (PIVOT R1)
    closed by the EA, and a position of another program."""
    html = [
        HEAD,
        row("Trade History Report"),
        row("Positions"),
        row(
            "Time",
            "Position",
            "Symbol",
            "Type",
            "Volume",
            "Price",
            "S / L",
            "T / P",
            "Time",
            "Price",
            "Commission",
            "Swap",
            "Profit",
        ),  # fmt: skip
        row(
            "2026.11.10 12:18:07",
            "101",
            "GOLD",
            "sell",
            "0.03",
            "4080.10",
            "4096.27",
            "",
            "2026.11.10 13:01:00",
            "4096.37",
            "-0.21",
            "0.00",
            "-48.81",
            hidden={4: "LVL4H PDL"},
        ),  # fmt: skip
        row(
            "2026.11.10 15:00:02",
            "102",
            "GOLD",
            "buy",
            "0.01",
            "4100.50",
            "4090.00",
            "",
            "2026.11.10 23:45:00",
            "4110.50",
            "-0.07",
            "0.00",
            "10.00",
            hidden={4: "PIVOT R1"},
        ),  # fmt: skip
        row(
            "2026.11.10 16:00:00",
            "103",
            "GOLD",
            "buy",
            "0.10",
            "4100.00",
            "4090.00",
            "",
            "2026.11.10 16:30:00",
            "4101.00",
            "0.00",
            "0.00",
            "10.00",
            hidden={4: "other bot"},
        ),  # fmt: skip
        row(""),
        row("Orders"),
        row(
            "Open Time",
            "Order",
            "Symbol",
            "Type",
            "Volume",
            "Price",
            "S / L",
            "T / P",
            "Time",
            "State",
            "Comment",
        ),  # fmt: skip
        row(
            "2026.11.10 12:15:00",
            "101",
            "GOLD",
            "sell stop",
            "0.03 / 0.03",
            "4080.17",
            "4096.27",
            "",
            "2026.11.10 12:18:07",
            "filled",
            "LVL4H PDL",
        ),  # fmt: skip
        row(
            "2026.11.10 15:00:01",
            "102",
            "GOLD",
            "buy",
            "0.01 / 0.01",
            "market",
            "4089.00",
            "",
            "2026.11.10 15:00:02",
            "filled",
            "PIVOT R1",
        ),  # fmt: skip
        row(
            "2026.11.10 16:00:00",
            "103",
            "GOLD",
            "buy",
            "0.10 / 0.10",
            "market",
            "4090.00",
            "",
            "2026.11.10 16:00:00",
            "filled",
            "other bot",
        ),  # fmt: skip
        row(""),
        row("Deals"),
        row(
            "Time",
            "Deal",
            "Symbol",
            "Type",
            "Direction",
            "Volume",
            "Price",
            "Order",
            "Commission",
            "Fee",
            "Swap",
            "Profit",
            "Balance",
            "Comment",
        ),  # fmt: skip
        row(
            "2026.11.10 13:01:00",
            "9",
            "GOLD",
            "buy",
            "out",
            "0.03",
            "4096.37",
            "201",
            "0.00",
            "0.00",
            "0.00",
            "-48.81",
            "9 951.19",
            "[sl 4096.27]",
        ),  # fmt: skip
        row(
            "2026.11.10 23:45:00",
            "10",
            "GOLD",
            "sell",
            "out",
            "0.01",
            "4110.50",
            "202",
            "0.00",
            "0.00",
            "0.00",
            "10.00",
            "9 961.19",
            "",
        ),  # fmt: skip
        row(""),
        TAIL,
    ]
    return "".join(html).encode("utf-16")


def test_the_report_gives_the_eas_trades() -> None:
    t = gd.demo_trades(gd.report_tables(gd._decode(report())))
    assert t["strategy"].tolist() == ["LVL4H", "PIVOT"]  # the other program's trade is left out
    s, b = t.iloc[0], t.iloc[1]
    assert (s["kind"], s["dir"], s["bar_server"], s["exit"]) == (
        "PDL",
        -1,
        "2026.11.10 12:15:00",
        "sl",
    )
    assert s["level"] == pytest.approx(4080.17)
    assert s["risk"] == pytest.approx(16.10)  # the stop order's level to its first SL
    assert s["gross"] == pytest.approx(-(4096.37 - 4080.17) / 16.10)
    assert s["net"] == pytest.approx((-48.81 - 0.21) / (16.10 * 0.03 * 100))
    assert s["slip"] == pytest.approx(0.07)  # filled $0.07 below a sell stop
    assert np.isnan(b["level"])  # a market entry: D from the fill
    assert b["risk"] == pytest.approx(4100.50 - 4089.00)
    assert b["exit"] == "ea"


def test_match_and_the_stop_rules() -> None:
    demo = gd.demo_trades(gd.report_tables(gd._decode(report())))
    py = pd.DataFrame({
        "strategy": ["LVL4H", "ASIA"],
        "bar_server": ["2026.11.10 12:15:00", "2026.11.10 10:00:00"],
        "dir": [-1.0, 1.0], "level": [4080.17, 4070.0], "risk": [16.10, 15.0],
        "gross": [-1.0, 0.5], "net": [-1.02, 0.48], "net_slip": [-1.03, 0.48],
        "exit": ["sl", "time"],
    })  # fmt: skip
    j = gd.match(py, demo)
    assert sorted(j["_merge"].astype(str)) == ["both", "left_only", "right_only"]
    st = {n: (c, s) for n, c, _, s in gd.stop_status(demo)}
    assert st["LVL4H"][0] == 1 and st["LVL4H"][1].startswith("first check at 100")
    many = pd.DataFrame({"strategy": "ASIA", "net": [-0.2] * 120})
    st = {n: s for n, _, _, s in gd.stop_status(many)}
    assert "checked at 100" in st["ASIA"] and "stop" in st["ASIA"]
