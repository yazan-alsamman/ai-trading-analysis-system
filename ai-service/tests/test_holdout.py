"""The single holdout reading (docs/strategies/PREREG.md, sections 9 and 10; Addendum 1): the
guards, the two registered checks on hand-built tables, the Addendum 1 details on a synthetic
market of the holdout period, and the report. Nothing here reads the research store."""

import subprocess

import numpy as np
import pandas as pd
import pytest

from app.research import decide
from app.research import holdout as hd
from tests.strategy_data import market
from tests.test_strategy_eval import SWAPS

UTC = "UTC"
CLOSED = "| Stage E (family D, AI) | closed by Fadi |\n"


def table(m8: float, m0: float = 0.0, strategy: str = "S1", kind: str = "scalp") -> pd.DataFrame:
    """One entry a day from 2016 to the lockbox start; M8 earns ``m8`` R a trade, M0 ``m0``."""
    t = pd.date_range("2016-01-04", "2026-01-08", freq="D", tz=UTC) + pd.Timedelta(hours=10)
    df = pd.DataFrame({"symbol": "X", "strategy": strategy, "type": kind, "entry_utc": t})
    for b, r in (("M0", m0), ("M8", m8)):
        df[decide.exit_col(b)] = t + pd.Timedelta(hours=2)
        df[decide.r_col(b)] = r
    return df


def test_the_reading_is_refused_a_second_time(tmp_path) -> None:
    done = tmp_path / "holdout.md"
    done.write_text("read")
    with pytest.raises(PermissionError, match="read once"):
        hd.preconditions(done)


def test_the_reading_waits_for_stage_e(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hd, "registered", lambda: ("a" * 40, "b" * 40, (1, 2)))
    p = tmp_path / "PREREG.md"
    p.write_text("| Field | Value |\n")
    with pytest.raises(PermissionError, match="Stage E"):
        hd.preconditions(tmp_path / "none.md", p)


def test_the_reading_needs_the_stage_reports_committed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hd, "registered", lambda: ("a" * 40, "b" * 40, (1, 2)))
    p = tmp_path / "PREREG.md"
    p.write_text(CLOSED)
    fail = subprocess.CompletedProcess([], 1, "", "")
    monkeypatch.setattr(hd, "_git", lambda *a: fail)
    with pytest.raises(PermissionError, match="committed"):
        hd.preconditions(tmp_path / "none.md", p)


def test_bars_after_the_lockbox_start_are_refused() -> None:
    f = {tf: df.assign(ts_utc=df["ts_utc"] + pd.Timedelta(days=500),
                       close_utc=df["close_utc"] + pd.Timedelta(days=500))
         for tf, df in market("XAUUSD").items()}  # fmt: skip
    with pytest.raises(ValueError, match="lockbox"):
        hd.entry_table({"XAUUSD": f}, SWAPS, ["M0"])


def test_the_scalp_check_uses_the_bundle_served_at_the_holdout_start() -> None:
    names = ["M0", "M8"]
    good = hd.scalp_check(table(0.1), names)
    assert good["served"] == "M8" and good["mean_delta"] == pytest.approx(0.1)
    assert good["result"].startswith("consistent") and good["n"] > 500
    bad = table(0.1)
    late = bad["entry_utc"] >= pd.Timestamp("2024-07-01", tz=UTC)
    bad.loc[late, decide.r_col("M8")] = -0.1  # better before, worse on the holdout
    out = hd.scalp_check(bad, names)
    assert out["served"] == "M8" and out["result"].startswith("not consistent")


def test_the_addendum_check_needs_both_conditions() -> None:
    assert hd.addendum_check(table(0.05, 0.0))["result"] == "consistent on the holdout"
    assert hd.addendum_check(table(0.05, 0.10))["result"].startswith("not")  # M8 below M0
    assert hd.addendum_check(table(-0.01, -0.05))["result"].startswith("not")  # negative net R
    other = hd.addendum_check(table(0.05, strategy="S2"))
    assert other["n"] == 0 and other["result"].startswith("not")


@pytest.fixture(scope="module")
def details():
    return hd.addendum_details({"XAUUSD": market("XAUUSD")}, SWAPS)  # 2024-09 to 2024-11


def test_addendum_details_on_the_holdout_period(details) -> None:
    d = details["detail"]
    assert len(d) > 0 and details["own_n"] > 0
    assert (d["gross"] >= d["w0"] - 1e-9).all()  # costs only lower net R
    assert np.allclose(d["x2"] - d["w1"], d["w0"] - d["gross"], atol=1e-6)  # the 2x stress


def test_render(details) -> None:
    md = hd.render(hd.scalp_check(table(0.1), ["M0", "M8"]), hd.addendum_check(table(0.05)),
                   details, "a" * 40, "b" * 40, "c" * 40, "2026-11-01")  # fmt: skip
    for text in ("read once", "Family C, scalp", "Addendum 1", "**consistent on the holdout",
                 "stays unvalidated", "Per instrument"):  # fmt: skip
        assert text in md, text


def test_main_refuses_without_the_preconditions(monkeypatch) -> None:
    def refuse():
        raise PermissionError("the holdout was read already")

    monkeypatch.setattr(hd, "preconditions", refuse)
    assert hd.main([]) == 2
