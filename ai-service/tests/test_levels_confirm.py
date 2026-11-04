"""Addendum 2 confirmation (app/research/levels_confirm.py): the first-passage rule on hand-built
bars, the touches on a synthetic market, the decision rule, the report and the guards. Nothing
here reads the confirmation store."""

import numpy as np
import pandas as pd
import pytest

from app.research import levels_confirm as lc
from tests.strategy_data import market


def bars(path: list[tuple[float, float]], n: int = 120) -> tuple[np.ndarray, np.ndarray]:
    """Highs and lows: the given bars, then flat bars at 100 (long enough for the windows)."""
    hi, lo = np.full(n, 100.0), np.full(n, 100.0)
    for j, (h, low) in enumerate(path):
        hi[j], lo[j] = h, low
    return hi, lo


def passage(path, up=True, lv=100.0, d=1.0):
    hi, lo = bars(path)
    out, cont = lc.first_passage(hi, lo, np.array([0]), np.array([lv]), np.array([d]),
                                 np.array([up]))  # fmt: skip
    return out[0], cont[0]


def test_first_passage_on_hand_built_bars() -> None:
    # touched from below at bar 0; then down 1 before up 1: a bounce
    assert passage([(100.0, 99.5), (100.2, 98.9)])[0] == "bounce"
    # then up 1 first: a break, then 2 through before back to 100: continuation
    assert passage([(100.0, 99.5), (101.1, 100.4), (102.1, 101.5)]) == ("break", 1.0)
    # a break that comes back to the level first: no continuation
    assert passage([(100.0, 99.5), (101.1, 100.4), (100.8, 99.9)]) == ("break", 0.0)
    # the touch bar itself reaching D through counts as a break; its low does not count
    assert passage([(101.2, 98.0), (100.5, 100.1)])[0] == "break"
    # one bar reaching both: ambiguous
    assert passage([(100.0, 99.5), (101.5, 98.5)])[0] == "ambiguous"
    # nothing within 48 bars
    assert passage([(100.0, 99.5)])[0] == "none"
    # approached from above: mirrored
    assert passage([(100.5, 100.0), (101.1, 99.8)], up=False)[0] == "bounce"


@pytest.fixture(scope="module")
def synthetic():
    rng = np.random.default_rng(lc.SEED)
    fr = market("XAUUSD", start="2023-09-25", end="2023-11-18")
    return lc.outcomes(lc.touches(fr, "XAUUSD", 10.0, rng))


def test_touches_on_a_synthetic_market(synthetic) -> None:
    d = synthetic
    assert set(d.kind) == {"PDH", "PDL", "5DH", "5DL", "ROUND"}
    assert d.placebo.any() and (~d.placebo).any()
    assert set(d.outcome) <= {"break", "bounce", "none", "ambiguous"}
    assert d.t.min() >= lc.START
    ny = d.t.dt.tz_convert("America/New_York")
    assert ny.dt.hour.between(2, 15).all() and (ny.dt.day_of_week < 5).all()
    # at most one first touch per day and day level
    day = ny.dt.date
    days = d[d.kind != "ROUND"].assign(day=day)
    assert not days.duplicated(["symbol", "kind", "placebo", "day"]).any()


def test_the_decision_needs_both_conditions() -> None:
    def diff(v, p=0.01):
        return lc.Diff(100, 0.45, 100, 0.45 - v, v, v - 0.01, v + 0.01, p)

    four = {f"I{k}": diff(-0.02) for k in range(4)} | {"I4": diff(0.01), "I5": diff(0.01)}
    assert lc.decide(diff(-0.03), four) == "H_L1 passed"
    three = {f"I{k}": diff(-0.02) for k in range(3)} | {f"I{k}": diff(0.01) for k in (3, 4, 5)}
    assert lc.decide(diff(-0.03), three) == "H_L1 not passed"
    assert lc.decide(diff(-0.03, p=0.2), four) == "H_L1 not passed"


def test_render(synthetic) -> None:
    rng = np.random.default_rng(1)
    d = pd.concat([synthetic, synthetic.assign(symbol="XAGUSD")], ignore_index=True)
    md = lc.render(d, rng, "a" * 40, "b" * 40, "2026-11-04", boot=200)
    for text in ("once", "## Decision (section 5)", "All six, pooled", "H_L1", "## Per instrument",
                 "Continuation", "lockbox was not read"):  # fmt: skip
        assert text in md, text


def test_the_reading_is_refused_a_second_time(tmp_path) -> None:
    done = tmp_path / "levels_confirm.md"
    done.write_text("read")
    with pytest.raises(PermissionError, match="once only"):
        lc.preconditions(done)


def test_the_reading_needs_an_approved_addendum(tmp_path) -> None:
    a = tmp_path / "ADDENDUM.md"
    a.write_text("| Approval date | (date) |\n")
    with pytest.raises(PermissionError, match="not approved"):
        lc.preconditions(tmp_path / "none.md", a)


def test_specs_cover_the_registered_instruments() -> None:
    assert list(lc.INSTRUMENTS) == ["NZDUSD", "USDCHF", "EURJPY", "GBPJPY", "EURGBP", "XAGUSD"]
    assert set(lc.STEP) == set(lc.INSTRUMENTS)
    assert lc.INSTRUMENTS["XAGUSD"].contract_size == 5000
