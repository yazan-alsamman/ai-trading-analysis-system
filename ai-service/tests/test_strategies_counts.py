"""Pre-approval candidate counts (docs/strategies/PREREG.md, section 12) on synthetic markets: no
outcome logic is reachable, the tables carry no outcome, the holdout is labelled, the lockbox is
refused, and a_S uses signal-time information only."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import instruments, signal_specs
from app.strategies import counts
from app.strategies.counts import HOLDOUT_LABEL, REASONS
from app.strategies.rules import candidates
from tests.strategy_data import PRIMARY, market
from tests.test_strategies_swap import spec as swap_spec

ROOT = Path(__file__).resolve().parents[1]
XAU = instruments()["XAUUSD"]
SPECS = list(signal_specs().values())
FORBIDDEN = ("app.setups.labels", "app.management", "app.research.baselines")


def tables(frames=None, sw=None):
    f = market("XAUUSD") if frames is None else frames
    rows = counts.candidate_rows(f, XAU, SPECS, sw)
    return rows, counts.report(rows, counts.trading_days(f, XAU, SPECS), SPECS)


def test_the_counting_module_never_imports_outcome_code() -> None:
    """The whole import graph, not only the module's own import lines."""
    code = "import sys, app.strategies.counts; print('\\n'.join(sorted(sys.modules)))"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "app.strategies.counts" in out
    loaded = [m for m in out if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)]
    assert loaded == []


def test_counts_run_with_resolve_and_management_replaced_by_raising_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.management.book as book
    import app.management.engine as engine
    import app.research.baselines as baselines
    import app.setups.labels as labels

    def boom(*a, **k):
        raise AssertionError("outcome logic called by a pre-approval count")

    stubs = [
        (labels, "resolve"),
        (labels, "label_all"),
        (engine, "manage"),
        (book, "one_active"),
        (book, "manager"),
        (book, "fixed_entry_table"),
    ]
    for mod, name in stubs:
        monkeypatch.setattr(mod, name, boom)
    for name in dir(baselines):
        if callable(getattr(baselines, name)) and not name.startswith("_"):
            monkeypatch.setattr(baselines, name, boom, raising=False)
    rows, t = tables(market("XAUUSD", 7, *PRIMARY), swap_spec())
    assert t["by_year"]["candidates"].sum() == len(rows) > 0
    assert t["allowance"]["armed_primary"].sum() > 0


def test_count_tables_have_no_outcome_fields() -> None:
    _, t = tables()
    assert set(t) == {"by_year", "summary", "by_type", "allowance"}
    for name, df in t.items():
        assert counts.check_no_outcomes(df) is df, name
        cols = " ".join(df.columns).lower()
        for word in ("exit", "net_r", "gross", "pnl", "mfe", "mae", "win", "equity", "price"):
            assert word not in cols.replace("window", ""), (name, word)
    for bad in ("exit_utc", "net_r", "R", "exit_price", "mfe", "hit_rate", "realized_r"):
        with pytest.raises(ValueError):
            counts.check_no_outcomes(pd.DataFrame({bad: [1.0]}))
    with pytest.raises(ValueError):  # no timestamps either (an exit time could hide there)
        counts.check_no_outcomes(pd.DataFrame({"when": pd.to_datetime(["2024-01-01"], utc=True)}))


def test_an_end_past_the_lockbox_start_is_refused_before_anything_is_read(tmp_path) -> None:
    lockbox = pd.Timestamp("2026-01-10", tz="UTC")
    start = pd.Timestamp("2012-01-01", tz="UTC")
    for end in (lockbox + pd.Timedelta(minutes=1), pd.Timestamp("2026-10-21", tz="UTC")):
        with pytest.raises(ValueError, match="lockbox"):
            counts.run(["XAUUSD"], start, end, store=tmp_path / "no-store")


def test_every_candidate_is_counted_once_armed_or_by_its_reason() -> None:
    rows, t = tables()
    assert set(rows.loc[rows["state"] == "REJECTED", "reason"]) <= set(REASONS)
    y = t["by_year"]
    rejected = y[[f"rejected_{r}" for r in REASONS]].sum(axis=1)
    assert (y["armed"] + rejected == y["candidates"]).all()
    assert y["candidates"].sum() == len(rows)
    s = t["summary"]
    for name in signal_specs():
        per_symbol = s[(s["strategy"] == name) & (s["symbol"] != "all")]["candidates"].sum()
        assert (
            per_symbol == s[(s["strategy"] == name) & (s["symbol"] == "all")]["candidates"].item()
        )


def test_holdout_rows_carry_the_candidate_only_label() -> None:
    _, t = tables()  # the synthetic market lies in 2024-09 to 2024-11: holdout period
    assert set(t["by_year"]["period"]) == {"holdout"}
    for name in ("by_year", "summary", "by_type"):
        assert (t[name]["note"] == HOLDOUT_LABEL).all(), name
    _, p = tables(market("XAUUSD", 7, *PRIMARY))
    assert set(p["by_year"]["period"]) == {"primary"} and (p["by_year"]["note"] == "").all()


def test_per_day_and_per_week_shares() -> None:
    days = pd.date_range("2024-06-10", "2024-06-21", freq="B")  # two weeks, ten trading days
    when = ["2024-06-10"] * 3 + ["2024-06-11"] + ["2024-06-17"] * 12
    rows = pd.DataFrame({"ny_date": pd.to_datetime(when), "state": "ARMED", "reason": ""})
    s = counts._stats(rows, days)
    assert (s["days"], s["armed"]) == (10, 16)
    assert s["per_day_mean"] == pytest.approx(1.6) and s["per_day_median"] == 0.0
    assert (s["days_0"], s["days_1"], s["days_2plus"]) == (0.7, 0.1, 0.2)
    assert (s["weeks"], s["weeks_0"], s["weeks_1_to_9"], s["weeks_10plus"]) == (2, 0.0, 0.5, 0.5)


def test_rows_and_a_s_use_no_price_after_the_signal_bar() -> None:
    """Prices after a time t scrambled in every frame (times kept): every candidate whose signal
    bar closed by t has the same state, reason and assumed cost, a_S's swap term included."""
    full = market("XAUUSD", 7, *PRIMARY)
    t = full["5m"]["close_utc"].iloc[len(full["5m"]) // 2]
    rng = np.random.default_rng(3)
    scrambled = {}
    for tf, f in full.items():
        f = f.copy()
        late = f["ts_utc"] >= t
        for col in ("open", "high", "low", "close"):
            f.loc[late, col] = f.loc[late, col].to_numpy() * rng.uniform(0.9, 1.1, late.sum())
        f.loc[late, "high"] = f.loc[late, ["open", "high", "low", "close"]].max(axis=1)
        f.loc[late, "low"] = f.loc[late, ["open", "high", "low", "close"]].min(axis=1)
        scrambled[tf] = f
    a = counts.candidate_rows(full, XAU, SPECS, swap_spec())
    b = counts.candidate_rows(scrambled, XAU, SPECS, swap_spec())
    keep = ["strategy", "entry_utc", "state", "reason", "assumed_r"]
    a, b = (x[x["entry_utc"] <= t][keep].reset_index(drop=True) for x in (a, b))
    assert len(a) > 100
    pd.testing.assert_frame_equal(a, b)


def test_a_s_is_the_median_assumed_cost_of_armed_primary_candidates() -> None:
    rows, t = tables(market("XAUUSD", 7, *PRIMARY), swap_spec())
    al = t["allowance"].set_index("strategy")
    for name in ("S4", "S5"):
        a = rows[(rows["strategy"] == name) & (rows["state"] == "ARMED")]["assumed_r"]
        assert al.loc[name, "a_S"] == pytest.approx(np.median(a))
        assert al.loc[name, "delta_star"] == pytest.approx(max(0.05, np.median(a)))
    # without a swap export: scalp and intraday need none (s_h = 0 by construction), the same
    # values; the swing strategy's a_S is not computed
    no_swap = counts.candidate_rows(market("XAUUSD", 7, *PRIMARY), XAU, SPECS, None)
    armed = (rows["state"] == "ARMED") & (rows["type"] != "swing")
    assert armed.sum() > 100
    pd.testing.assert_series_equal(no_swap["assumed_r"][armed], rows["assumed_r"][armed])
    swing = (no_swap["state"] == "ARMED") & (no_swap["type"] == "swing")
    assert swing.sum() > 0 and no_swap["assumed_r"][swing].isna().all()
    al = counts.report(no_swap, counts.trading_days(market("XAUUSD", 7, *PRIMARY), XAU, SPECS),
                       SPECS)["allowance"].set_index("strategy")  # fmt: skip
    assert np.isnan(al.loc["S3", "delta_star"]) and al.drop("S3")["delta_star"].notna().all()


def test_the_swap_term_of_a_s_comes_from_the_registered_horizon_only() -> None:
    f = market("XAUUSD", 7, *PRIMARY)
    charge = swap_spec(long=-50.0, short=-50.0)  # both sides charged
    extra = {}
    for name in ("S5", "S3"):
        sp = signal_specs()[name]
        close = f[sp.frame]["close_utc"]
        for c in candidates(f, XAU, sp):
            if c.state != "ARMED":
                continue
            cost = max(XAU.cost_extra_frac * c.spread, XAU.cost_extra_min) + XAU.sl_slippage
            extra.setdefault(name, []).append(
                counts.assumed_r(c, close, XAU, sp, charge) - cost / c.risk
            )
    assert np.allclose(extra["S5"], 0.0)  # scalp: the horizon ends by 16:45, before a rollover
    assert min(extra["S3"]) > 0  # swing: 60 4h bars always span a rollover
