"""Post-approval counts (docs/strategies/PREREG.md, section 12) and the family C fixed entry set
(section 9) on synthetic markets of the primary period: exits stay inside the computation, the
served-signal rules, the guards, and independent per-bundle columns."""

import numpy as np
import pandas as pd
import pytest

from app.config import bundles, instruments, rules, signal_specs
from app.management import counts
from app.management.book import fixed_entry_table, manager, one_active, overlaps
from app.management.engine import Outcome
from app.research.decide import ALPHA, block_ids, exit_col, mde, n_unval, r_col
from app.strategies import swap
from app.strategies.base import BUY, SELL, Candidate
from app.strategies.rules import candidates
from tests.strategy_data import PRIMARY, market
from tests.test_strategies_swap import spec as swap_spec

XAU = instruments()["XAUUSD"]
RP, B = rules(), bundles()
SPECS = list(signal_specs().values())


def primary(symbol: str = "XAUUSD"):
    return market(symbol, 7, *PRIMARY)


# --- exits never leave the computation ------------------------------------------------------


def test_post_approval_counts_write_and_print_no_exit_detail_or_r(capsys, tmp_path) -> None:
    t = counts.counts({"XAUUSD": primary(), "EURUSD": primary("EURUSD")}, {"S5": 0.07})
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    assert set(t) == {"by_year", "power"}
    for name, df in t.items():
        cols = " ".join(df.columns).lower()
        for word in ("exit", "net_r", "gross", "pnl", "mfe", "mae", "reason", "price", "equity"):
            assert word not in cols, (name, word)
        assert not any(pd.api.types.is_datetime64_any_dtype(df[c]) for c in df), name
        assert all(df[c].dtype != object or c in ("strategy", "symbol", "family") for c in df)
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_bars_after_the_holdout_start_are_refused() -> None:
    with pytest.raises(ValueError, match="holdout"):
        counts.counts({"XAUUSD": market("XAUUSD")})  # 2024-09 to 2024-11


def test_run_is_refused_while_the_preregistration_is_a_draft(tmp_path, monkeypatch) -> None:
    p = tmp_path / "PREREG.md"
    p.write_text("| Field | Value |\n| Approval date | _(YYYY-MM-DD)_ |\n")
    real = counts.approved
    monkeypatch.setattr(counts, "approved", lambda prereg=p: real(prereg))
    with pytest.raises(PermissionError):
        counts.run(["XAUUSD"], store=tmp_path / "no-store")
    p.write_text("| Field | Value |\n| Approval date | _(YYYY-MM-DD; after ...)_ |\n")
    assert not counts.approved(p)
    p.write_text("| Field | Value |\n| Approval date | 2026-11-02 |\n")
    assert counts.approved(p)


# --- the counts ------------------------------------------------------------------------------


def test_family_a_states_match_the_one_active_book() -> None:
    f = primary()
    t = counts.counts({"XAUUSD": f})["by_year"].groupby("strategy").sum(numeric_only=True)
    for sp in SPECS:
        close = f[sp.frame]["close_utc"]
        armed = [c for c in candidates(f, XAU, sp) if c.state == "ARMED"]
        got = one_active(armed, manager(f, XAU, sp, RP, B["M0"]))
        trades = [o for _, o in got if o is not None]
        row = t.loc[sp.name] if sp.name in t.index else None
        assert len(armed) == (0 if row is None else row["armed"])
        if row is None:
            continue
        assert row["resolved"] == sum(o.state == "CLOSED" for o in trades)
        assert row["unresolved"] == sum(o.state != "CLOSED" for o in trades)
        assert row["armed"] == row["trades"] + row["position_open"] + row["undecided"]
        assert row["armed"] == (
            row["served"] + row["served_position_open"] + row["conflict"] + row["served_undecided"]
        )
        assert all(close.iloc[c.idx] >= pd.Timestamp("2018-01-01", tz="UTC") for c in armed)


def test_power_statements() -> None:
    f = primary()
    t = counts.counts({"XAUUSD": f}, {"S5": 0.07})["power"].set_index("strategy")
    sp = signal_specs()["S5"]
    armed = [c for c in candidates(f, XAU, sp) if c.state == "ARMED"]
    got = one_active(armed, manager(f, XAU, sp, RP, B["M0"]))
    done = [c for c, o in got if o is not None and o.state == "CLOSED"]
    n = len(done)
    entry = [f["5m"]["close_utc"].iloc[c.idx] for c in done]
    row = t.loc["S5"]
    assert row["n"] == n and row["K"] == len(np.unique(block_ids(entry)))
    assert row["sigma"] == pytest.approx(np.sqrt(1.5)) and row["DE"] == 1.2
    assert row["mde_alpha_m"] == pytest.approx(mde(n, np.sqrt(1.5), 1.2, ALPHA / 6))
    assert row["mde_alpha"] == pytest.approx(mde(n, np.sqrt(1.5), 1.2, ALPHA))
    assert row["n_unval"] == n_unval(0.07, np.sqrt(1.5), 1.2)
    assert t.loc["S4", "DE"] == 1.5 and t.loc["S8", "DE"] == 1.5
    assert np.isnan(t.loc["S1", "n_unval"])  # no delta* given


def cand(name: str, idx: int, direction: str = BUY) -> Candidate:
    return Candidate(name, idx, pd.Timestamp("2024-01-01", tz="UTC"), direction, "ARMED", "",
                     100.0, 99.0, 101.0, 1.0, 1.0, 0.0, 1.0, 10, None)  # fmt: skip


def test_served_signal_rules() -> None:
    # time = idx (ns), one bar; outcomes: exit idx and exit time
    exits = {("A", 1): 5, ("C", 4): 9, ("B", 9): None}  # every other trade exits at 8

    def fake(c: Candidate) -> Outcome:
        x = exits.get((c.strategy, c.idx), 8)
        if x is None:
            return Outcome("PENDING", "active")
        return Outcome("CLOSED", "tp", x, exit_ns=x)

    armed = [
        cand("A", 1),
        cand("B", 2, SELL),  # B opposite to the open A trade: conflict
        cand("A", 3),  # A still open (exits at 5): position_open
        cand("C", 4),  # same direction as A: served
        cand("A", 5),
        cand("B", 6, SELL),  # A flat at 5: served; B opposite to C (to 9): conflict
        cand("B", 9, SELL),  # C left at 9 and A at 8: served, then unresolved
        cand("B", 10, SELL),
        cand("A", 11),  # B blocked: undecided; A opposite to open B: conflict
    ]
    got = counts.serve([(c, c.idx) for c in armed], dict.fromkeys("ABC", fake))
    assert [(c.strategy, c.idx, s) for c, s in got] == [
        ("A", 1, "served"), ("B", 2, "conflict"), ("A", 3, "position_open"), ("C", 4, "served"),
        ("A", 5, "served"), ("B", 6, "conflict"), ("B", 9, "served"), ("B", 10, "undecided"),
        ("A", 11, "conflict"),
    ]  # fmt: skip
    tie = counts.serve([(cand("B", 1, SELL), 1), (cand("A", 1), 1)], dict.fromkeys("AB", fake))
    assert [(c.strategy, s) for c, s in tie] == [("A", "served"), ("B", "conflict")]


# --- family C: the fixed entry set ------------------------------------------------------------


def test_each_bundle_has_its_own_exit_and_r_columns() -> None:
    f, sp = primary(), signal_specs()["S5"]
    tab = fixed_entry_table(f, XAU, sp, RP, B)
    assert len(tab) > 100
    for b in B:
        assert {exit_col(b), r_col(b), f"reason_{b}"} <= set(tab.columns)
    differ = (tab[exit_col("M3")] != tab[exit_col("M0")]) & (tab[r_col("M3")] != tab[r_col("M0")])
    assert differ.sum() > 10
    # each bundle's columns come from its own management: computed alone, or in another order,
    # or with M0's columns overwritten, they do not change
    alone = fixed_entry_table(f, XAU, sp, RP, {"M0": B["M0"], "M3": B["M3"]})
    rev = fixed_entry_table(f, XAU, sp, RP, dict(reversed(list(B.items()))))
    for b in ("M0", "M3"):
        pd.testing.assert_series_equal(tab[exit_col(b)], alone[exit_col(b)])
        pd.testing.assert_series_equal(tab[r_col(b)], alone[r_col(b)])
    pd.testing.assert_frame_equal(tab, rev[tab.columns])
    run = manager(f, XAU, sp, RP, B["M3"])
    first = one_active(candidates(f, XAU, sp), manager(f, XAU, sp, RP, B["M0"]))
    entries = [c for c, o in first if o is not None]
    assert [c.idx for c in entries] == list(tab["idx"])
    for c, x, r in zip(entries, tab[exit_col("M3")], tab[r_col("M3")], strict=True):
        o = run(c)
        assert (pd.Timestamp(o.exit_ns, tz="UTC"), o.net_r()) == (x, r)


def test_fixed_entry_swap_uses_the_price_at_each_rollover() -> None:
    f, sp = primary(), signal_specs()["S3"]
    s = swap_spec("INTEREST_CURRENT", long=-2.0, short=-2.0)
    one = {"M0": B["M0"]}
    tab, bare = fixed_entry_table(f, XAU, sp, RP, one, s), fixed_entry_table(f, XAU, sp, RP, one)
    price_at = swap.close_before(f[sp.frame])
    by = {(c.idx, c.direction): c for c in candidates(f, XAU, sp)}
    ok = tab[r_col("M0")].notna()
    assert ok.sum() >= 2  # S3 holds for days: few trades in eight weeks
    for _, row in tab[ok].iterrows():
        c = by[row["idx"], row["direction"]]
        w1 = swap.swap_r(s, c.direction, row["entry_utc"], row[exit_col("M0")], c.risk, c.entry,
                         price_at)  # fmt: skip
        r0 = bare.loc[bare["idx"] == row["idx"], r_col("M0")].item()
        assert row[r_col("M0")] == pytest.approx(r0 + w1)


def test_unresolved_outcomes_are_missing_not_invented() -> None:
    f, sp = primary(), signal_specs()["S3"]
    tab = fixed_entry_table(f, XAU, sp, RP, B)
    last = tab.iloc[-1]
    assert pd.isna(last[exit_col("M0")]) and np.isnan(last[r_col("M0")])  # open at the data end


def test_overlaps_under_a_later_exiting_bundle() -> None:
    t = pd.to_datetime(["2024-01-01 10:00", "2024-01-01 11:00", "2024-01-01 13:00"], utc=True)
    tab = pd.DataFrame(
        {"symbol": "X", "strategy": "S5", "entry_utc": t,
         exit_col("M0"): t + pd.Timedelta(minutes=30),
         exit_col("M3"): [t[0] + pd.Timedelta(hours=2), t[1] + pd.Timedelta(minutes=30), pd.NaT]}
    )  # fmt: skip
    assert overlaps(tab, "M0") == 0
    assert overlaps(tab, "M3") == 1  # the 11:00 entry starts while the 10:00 one runs to 12:00
    late = tab.copy()
    late.loc[0, exit_col("M3")] = pd.NaT  # unresolved: open to the end
    assert overlaps(late, "M3") == 2
    assert overlaps(replace_symbol(tab), "M3") == 0  # another instrument does not overlap


def replace_symbol(tab: pd.DataFrame) -> pd.DataFrame:
    out = tab.copy()
    out["symbol"] = ["X", "Y", "Z"]
    return out
