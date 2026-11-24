"""Stage D, family C (docs/strategies/PREREG.md, section 9): the windows, the selection on known
training trades only, the test trades and their exclusions, Holm over the three types, the
entry tables on a synthetic market and the command. Nothing here reads the research store."""

import numpy as np
import pandas as pd
import pytest

from app.research import decide
from app.research import management_eval as me
from tests.strategy_data import PRIMARY, market
from tests.test_strategy_eval import SWAPS, prereg

UTC = "UTC"


def hand_table(first: str = "2016-01-04", last: str = "2018-12-31", better: str = "M1"):
    """One entry a day of a scalp strategy; every bundle exits 2 hours later; ``better`` earns
    0.1 R a trade more than M0."""
    t = pd.date_range(first, last, freq="D", tz=UTC) + pd.Timedelta(hours=10)
    df = pd.DataFrame({"symbol": "X", "strategy": "S5", "type": "scalp", "entry_utc": t})
    for b in ("M0", "M1", "M2"):
        df[decide.exit_col(b)] = t + pd.Timedelta(hours=2)
        df[decide.r_col(b)] = 0.1 if b == better else 0.0
    return df


def test_thirteen_six_month_windows() -> None:
    w = me.windows()
    assert len(w) == 13
    assert w[0] == (pd.Timestamp("2018-01-01", tz=UTC), pd.Timestamp("2018-07-01", tz=UTC))
    assert w[-1][1] == pd.Timestamp("2024-07-01", tz=UTC)


def test_selection_uses_training_trades_and_the_test_uses_the_chosen_bundle() -> None:
    names = ["M0", "M1", "M2"]
    r = me.procedure(hand_table(), names, me.windows()[:2], 1, 500, 3)
    sel = r.selection.set_index("window")
    assert list(sel["chosen"]) == ["M1", "M1"]
    assert (r.test["delta"] == 0.1).all() and len(r.test) == sel["test"].sum()
    # an unresolved chosen-bundle outcome excludes the test trade; an unchosen one never does
    tab = hand_table()
    i = tab.index[tab["entry_utc"] >= pd.Timestamp("2018-02-01", tz=UTC)][0]
    tab.loc[i, decide.r_col("M2")] = np.nan
    tab.loc[i, decide.exit_col("M2")] = pd.NaT
    j = i + 1
    tab.loc[j, decide.r_col("M1")] = np.nan
    tab.loc[j, decide.exit_col("M1")] = pd.NaT
    r2 = me.procedure(tab, names, me.windows()[:1], 1, 500, 3)
    assert int(r2.selection["excluded"].iloc[0]) == 1
    assert len(r2.test) == len(r.test[r.test["window"] == "2018-01-01"]) - 1


def test_fewer_than_100_training_trades_choose_m0() -> None:
    names = ["M0", "M1", "M2"]
    r = me.procedure(hand_table(first="2017-10-01"), names, me.windows()[:1], 1, 500, 3)
    assert r.selection["training"].iloc[0] < 100
    assert r.selection["chosen"].iloc[0] == "M0" and (r.test["delta"] == 0.0).all()


def test_holm_over_the_three_types_and_untested_types_enter_with_p_1() -> None:
    names = ["M0", "M1", "M2"]
    res = me.evaluate(hand_table(last="2024-06-28"), names, 3, boot=500)
    assert set(res) == {"scalp"}
    r = res["scalp"]
    assert r.k >= 30 and r.p <= 1 / 400
    assert r.adjusted == pytest.approx(min(1.0, 3 * r.p))  # m = 3, the others at p = 1
    assert r.result == "passed (holdout check pending)" and r.served == "M1"


# --- on a synthetic market ------------------------------------------------------------------


@pytest.fixture(scope="module")
def tables():
    return me.entry_tables({"XAUUSD": market("XAUUSD", 7, *PRIMARY)}, SWAPS, ["M0", "M1", "M3"])


def test_entry_tables_have_every_bundles_own_columns_and_diagnostics(tables) -> None:
    table, diag = tables
    assert set(table["type"]) == {"scalp", "intraday", "swing"}
    for b in ("M0", "M1", "M3"):
        assert {decide.exit_col(b), decide.r_col(b), f"reason_{b}"} <= set(table.columns)
    assert set(diag["bundle"]) == {"M0", "M1", "M3"}
    m0 = diag[diag["bundle"] == "M0"]
    assert (m0["added"] == 0).all() and (m0["dropped"] == 0).all()


def test_bars_after_the_holdout_start_are_refused() -> None:
    with pytest.raises(ValueError, match="holdout"):
        me.entry_tables({"XAUUSD": market("XAUUSD")}, SWAPS, ["M0"])


def test_render(tables) -> None:
    table, diag = tables
    names = ["M0", "M1", "M3"]
    res = me.evaluate(table, names, 3, boot=200)
    md = me.render(res, table, diag, names, "a" * 40, "b" * 40, 3, 200, "2026-11-01")
    for text in ("trials 19-21", "## Decision", "Holm", "not activated", "Diagnostics"):
        assert text in md, text


def test_the_command_refuses_an_unapproved_preregistration(tmp_path, monkeypatch) -> None:
    from app.research import strategy_eval as ev

    draft = prereg(tmp_path / "PREREG.md", "b9ca2a8065513c832ff88deac3c697b7dd44edf5")
    real = ev.registered
    monkeypatch.setattr(me, "registered", lambda: real(draft))
    assert me.main([]) == 2


def test_main_writes_the_report(tmp_path, monkeypatch) -> None:
    store = tmp_path / "store" / "XAUUSD"
    store.mkdir(parents=True)
    for tf, fr in market("XAUUSD", 7, *PRIMARY).items():
        fr.to_parquet(store / f"{tf}.parquet", index=False)
    monkeypatch.setattr(me, "registered", lambda: ("a" * 40, "b" * 40, (11, 12)))
    monkeypatch.setattr(me, "BOOT", 100)
    out = tmp_path / "out"
    assert me.main(["--store", str(tmp_path / "store"), "--out", str(out)]) == 0
    assert "Stage D" in (out / "management.md").read_text(encoding="utf-8")
    assert (tmp_path / "store" / "stage_d_entries.parquet").exists()
