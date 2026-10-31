"""Stage C (docs/strategies/PREREG.md, sections 8 and 10) on synthetic markets of the primary
period: the registration guard, the M0 trades, the E0 matching, the test, Holm and the reports,
and the post-approval counts command. Nothing here reads the research store."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import bundles, instruments, rules, signal_specs
from app.data.sessions import MARKET_TZ
from app.management import counts as post
from app.management.book import manager, one_active
from app.research import post_counts
from app.research import strategy_eval as ev
from app.strategies import swap
from app.strategies.cli import load_swaps
from app.strategies.rules import candidates
from tests.strategy_data import PRIMARY, market
from tests.test_strategies_cli import git

XAU = instruments()["XAUUSD"]
RP, M0 = rules(), bundles()["M0"]
SPECS = signal_specs()
SWAPS = load_swaps(ev.SWAPS)
START = pd.Timestamp("2018-01-01", tz="UTC")


def primary():
    return market("XAUUSD", 7, *PRIMARY)


# --- registration ---------------------------------------------------------------------------


def prereg(path: Path, frozen: str, approved: str = "_(YYYY-MM-DD)_", seeds: str = "_(fixed)_"):
    path.write_text(
        "| Field | Value |\n| --- | --- |\n"
        f"| Rules frozen at commit | {frozen} |\n| Approval date | {approved} |\n"
        f"| Seeds (E0, bootstrap) | {seeds} |\n",
        encoding="utf-8",
    )
    return path


def test_the_commands_refuse_an_unapproved_preregistration(tmp_path, monkeypatch) -> None:
    draft = prereg(tmp_path / "PREREG.md", "b9ca2a8065513c832ff88deac3c697b7dd44edf5")
    real = ev.registered
    monkeypatch.setattr(ev, "registered", lambda: real(draft))
    monkeypatch.setattr(post_counts, "registered", lambda: real(draft))
    with pytest.raises(PermissionError):
        ev.registered()
    assert ev.main([]) == 2
    assert post_counts.main([]) == 2


def test_registration_needs_approval_seeds_and_unchanged_engine(tmp_path) -> None:
    repo = tmp_path / "repo"
    engine = repo / "ai-service" / "app" / "management" / "engine.py"
    engine.parent.mkdir(parents=True)
    engine.write_text("M0 = 1\n")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "rules")
    head = git(repo, "rev-parse", "HEAD")
    p = tmp_path / "PREREG.md"

    with pytest.raises(PermissionError):
        ev.registered(prereg(p, head), repo)
    with pytest.raises(ValueError, match="seeds"):
        ev.registered(prereg(p, head, "2026-11-02"), repo)
    ok = prereg(p, head, "2026-11-02", "20261102, 20261103")
    assert ev.registered(ok, repo) == (head, head, (20261102, 20261103))
    engine.write_text("M0 = 2\n")  # the management engine is a rule file for Stage C
    with pytest.raises(ValueError, match="differ"):
        ev.registered(ok, repo)


def test_delta_star_comes_from_the_counts_of_the_frozen_commit(tmp_path) -> None:
    md = tmp_path / "counts.md"
    md.write_text(
        "| Rules frozen at commit | `abc` |\n\n## Allowance a_S and delta*_S\n\n"
        "| strategy | armed_primary | a_S | delta_star |\n| --- | --- | --- | --- |\n"
        "| S1 | 10 | 0.025 | 0.050 |\n| S3 | 10 | 0.073 | 0.073 |\n| S9 | 0 |  |  |\n"
    )
    got = ev.deltas(md, "abc")
    assert (got["S1"], got["S3"]) == (0.05, 0.073)
    assert np.isnan(got["S9"])  # not computed: "unvalidated" cannot be reached (U_S < NaN)
    with pytest.raises(ValueError, match="frozen commit"):
        ev.deltas(md, "def")
    real = ev.deltas(ev.COUNTS, "b9ca2a8065513c832ff88deac3c697b7dd44edf5")
    assert set(real) == set(SPECS) and real["S3"] == pytest.approx(0.073)


# --- trades and E0 --------------------------------------------------------------------------


def test_trades_are_m0_under_one_active_trade_with_the_decision_swap() -> None:
    f, sp = primary(), SPECS["S3"]
    book, _ = ev.trades(f, XAU, sp, RP, M0, SWAPS["XAUUSD"], START)
    close = f[sp.frame]["close_utc"]
    run = manager(f, XAU, sp, RP, M0)
    arm = [c for c in candidates(f, XAU, sp) if c.state == "ARMED" and close.iloc[c.idx] >= START]
    want = [(c, o) for c, o in one_active(arm, run) if o is not None]
    assert list(book["idx"]) == [c.idx for c, _ in want] and len(book) >= 2  # S3 holds days
    price_at = swap.close_before(f[sp.frame])
    for (c, o), (_, row) in zip(want, book.iterrows(), strict=True):
        if o.state != "CLOSED":
            assert row["state"] == "unresolved" and np.isnan(row["x"])
            continue
        x = pd.Timestamp(o.exit_ns, tz="UTC")
        w1 = swap.swap_r(SWAPS["XAUUSD"], c.direction, row["entry_utc"], x, c.risk, c.entry,
                         price_at)  # fmt: skip
        assert row["x"] == pytest.approx(o.net_r() + w1)
        assert row["x_2x"] == pytest.approx(o.net_r(2) + w1)


def test_the_trades_equal_the_family_a_trades_of_the_post_approval_counts() -> None:
    f = primary()
    rows = post.instrument_rows(f, XAU, list(SPECS.values()), RP, M0)
    for name, sp in SPECS.items():
        book, _ = ev.trades(f, XAU, sp, RP, M0, SWAPS["XAUUSD"], START)
        a = rows[(rows["strategy"] == name) & rows["family_a"].isin(["resolved", "unresolved"])]
        assert list(book["idx"]) == list(a["idx"]), name
        assert (book["state"] == "resolved").sum() == (a["family_a"] == "resolved").sum()


def test_e0_matches_year_hour_risk_tp_cost_and_session_end(monkeypatch) -> None:
    f, sp = primary(), SPECS["S5"]
    p = ev.pool(f, sp, RP)
    seen = []
    real = ev.manage
    monkeypatch.setattr(ev, "manage", lambda *a, **k: seen.append(a[1]) or real(*a, **k))
    rng = np.random.default_rng(1)
    year, hour = next(iter(p.bars))
    xs = [ev.e0_draw(p, year, hour, 1.5, 1.5, rng, XAU, RP, M0, SWAPS["XAUUSD"], 0.15)
          for _ in range(60)]  # fmt: skip
    assert any(x is not None for x in xs) and seen
    for c in seen:
        t = c.ts_utc.tz_convert(MARKET_TZ)
        assert (t.year, t.hour) == (year, hour)
        assert c.risk == pytest.approx(1.5 * c.atr)
        assert c.sign * (c.tp - c.entry) == pytest.approx(1.5 * c.risk)
        assert (
            c.deadline is not None and c.deadline.tz_convert(MARKET_TZ).strftime("%H:%M") == "16:45"
        )
    assert {c.direction for c in seen} == {"buy", "sell"}
    assert ev.e0_draw(p, year, hour, 1.5, 1.5, rng, XAU, RP, M0, SWAPS["XAUUSD"], 0.0) is None
    assert ev.e0_draw(p, 1999, 3, 1.5, 1.5, rng, XAU, RP, M0, SWAPS["XAUUSD"], 0.15) is None


def test_first_friday_news() -> None:
    t = lambda s: pd.Timestamp(s, tz=MARKET_TZ).tz_convert("UTC")  # noqa: E731
    entry = pd.Series([t("2023-10-06 08:00"), t("2023-10-06 09:00"), t("2023-10-13 08:00")])
    exit_ = pd.Series([t("2023-10-06 09:00"), t("2023-10-06 10:00"), t("2023-10-13 09:00")])
    assert list(ev.first_friday_news(entry, exit_)) == [True, False, False]


# --- the whole evaluation -------------------------------------------------------------------


@pytest.fixture(scope="module")
def evaluated():
    return ev.evaluate(
        {"XAUUSD": primary()}, SWAPS, {n: 0.05 for n in SPECS}, (11, 12), reps=3, boot=200
    )


def test_evaluate_gives_every_strategy_a_result_with_holm_within_families(evaluated) -> None:
    results, book, draws = evaluated
    assert [r.name for r in results] == sorted(SPECS)
    assert draws.shape[1] == 3
    for r in results:
        g = r.primary
        assert (g["d"] == g["x"] - g["e"]).all()
        assert set(g["entry_utc"].dt.year) <= {2023}
        # eight weeks of data: K < 30, so the method condition fails, p = 1 and inconclusive
        if r.test is not None:
            assert not r.test.method_ok and r.test.p == 1.0
        assert r.adjusted == 1.0 and r.classification == "inconclusive"
    assert set(book["book"]) == {"primary", "from_2012"}


def test_classification_follows_the_registered_rule(evaluated, monkeypatch) -> None:
    from app.research import decide

    assert decide.classify(0.01, True, 0.2, 0.05) == "passed"
    assert decide.classify(0.5, True, 0.04, 0.05) == "unvalidated"
    assert decide.classify(0.5, True, 0.06, 0.05) == "inconclusive"
    assert decide.classify(0.01, False, 0.0, 0.05) == "inconclusive"


def test_bars_after_the_holdout_start_are_refused() -> None:
    with pytest.raises(ValueError, match="holdout"):
        ev.evaluate({"XAUUSD": market("XAUUSD")}, SWAPS, {}, (1, 2), reps=1, boot=10)


def test_reports(evaluated) -> None:
    results, _, _ = evaluated
    md = ev.strategy_report(results[4], "a" * 40, "b" * 40, (11, 12), 200, 3)
    want = ["Stage C: S5 (trial 15", "p_S (max of the four)", "Holm-adjusted p", "delta*_S"]
    want += ["Sensitivity 1", "Without first-Friday", "Deflated Sharpe", "**inconclusive**"]
    for text in want:
        assert text in md, text
    s = ev.summary_report(results, "a" * 40, "b" * 40, "2026-11-02")
    assert s.count("| inconclusive |") == len(SPECS) and "not validated yet" in s


def test_main_writes_the_reports(tmp_path, monkeypatch) -> None:
    store = tmp_path / "store" / "XAUUSD"
    store.mkdir(parents=True)
    for tf, fr in primary().items():
        fr.to_parquet(store / f"{tf}.parquet", index=False)
    monkeypatch.setattr(ev, "registered", lambda: ("a" * 40, "b" * 40, (11, 12)))
    monkeypatch.setattr(ev, "deltas", lambda path, commit: {n: 0.05 for n in SPECS})
    monkeypatch.setattr(ev, "REPS", 2)
    monkeypatch.setattr(ev, "BOOT", 100)
    out = tmp_path / "out"
    assert ev.main(["--store", str(tmp_path / "store"), "--out", str(out)]) == 0
    assert (out / "evaluation.md").exists() and (out / "eval_S1.md").exists()
    assert (tmp_path / "store" / "stage_c_trades.parquet").exists()


def test_post_counts_report_has_no_outcomes() -> None:
    tables = post.counts({"XAUUSD": primary()}, {n: 0.05 for n in SPECS})
    md = post_counts.render(tables, "a" * 40, "b" * 40, "2026-11-02")
    assert "## Power statements" in md and "n_unval" in md
    for word in ("net_r", "exit_", "pnl"):
        assert word not in md


# --- performance only: the precomputed rollovers give the same floats -------------------------


@pytest.mark.parametrize("mode", ["POINTS", "CURRENCY_SYMBOL", "INTEREST_CURRENT"])
def test_precomputed_rollovers_equal_swap_r_exactly(mode) -> None:
    from dataclasses import replace

    f = primary()
    sw = replace(SWAPS["XAUUSD"], mode=mode, long=-69.25, short=17.15)
    rng = np.random.default_rng(5)
    for tf in ("4h", "5m"):
        e = f[tf]
        roll = ev.Rollovers.of(e, sw)
        close = e["close_utc"]
        for _ in range(300):
            i = int(rng.integers(0, len(e) - 2))
            j = int(rng.integers(i + 1, min(len(e), i + 400)))
            d = "buy" if rng.random() < 0.5 else "sell"
            a, b = close.iloc[i], close.iloc[j]
            want = swap.swap_r(sw, d, a, b, 3.0, 2000.0, swap.close_before(e))
            assert roll.w1(d, a, b, 3.0, 2000.0) == want  # the same float, not approximately
        late = close.iloc[-1] + pd.Timedelta(days=40)  # outside the span: swap.swap_r itself
        assert roll.w1("buy", close.iloc[0], late, 3.0, 2000.0) == swap.swap_r(
            sw, "buy", close.iloc[0], late, 3.0, 2000.0, swap.close_before(e)
        )


def test_e0_draws_are_identical_with_and_without_the_precomputed_rollovers() -> None:
    f, rp = primary(), RP
    book = pd.concat(
        [ev.trades(f, XAU, SPECS[n], rp, M0, SWAPS["XAUUSD"], START)[0] for n in ("S3", "S5")]
    )
    book = book[book["state"] == "resolved"].head(40).reset_index(drop=True)
    sw = {"XAUUSD": SWAPS["XAUUSD"]}
    slow = {("XAUUSD", n): ev.pool(f, SPECS[n], rp) for n in ("S3", "S5")}
    fast = {("XAUUSD", n): ev.pool(f, SPECS[n], rp, sw["XAUUSD"]) for n in ("S3", "S5")}
    assert all(p.rollovers is None for p in slow.values())
    assert all(p.rollovers is not None for p in fast.values())
    a = ev.e0(book, slow, 3, np.random.default_rng(9), rp, M0, sw, 0.15)
    b = ev.e0(book, fast, 3, np.random.default_rng(9), rp, M0, sw, 0.15)
    assert np.array_equal(a, b, equal_nan=True) and np.isfinite(a).sum() > 50
