import numpy as np
import pandas as pd
import pytest

from app.smc import review


def patterns(n_per_cell: dict[tuple[int, str], int]) -> pd.DataFrame:
    rows = []
    for (year, direction), n in n_per_cell.items():
        for k in range(n):
            rows.append(
                {
                    "year": year,
                    "direction": direction,
                    "sweep_utc": pd.Timestamp(f"{year}-03-01", tz="UTC") + pd.Timedelta(hours=k),
                }
            )
    return pd.DataFrame(rows)


def test_sample_is_fixed_and_spread_over_years_and_directions() -> None:
    cells = {(y, d): 30 for y in range(2012, 2018) for d in ("buy", "sell")}
    df = patterns(cells)
    a, b = review.sample(df), review.sample(df)
    pd.testing.assert_frame_equal(a, b)  # same seed, same sample
    assert len(a) == 50
    counts = a.groupby(["year", "direction"]).size()
    assert counts.min() >= 4 and counts.max() <= 5
    assert a["sweep_utc"].is_monotonic_increasing


def test_small_cells_give_their_share_to_the_others() -> None:
    cells = {(2012, "buy"): 1, (2012, "sell"): 60, (2013, "buy"): 60, (2013, "sell"): 60}
    a = review.sample(patterns(cells), n=20)
    counts = a.groupby(["year", "direction"]).size().to_dict()
    assert counts[(2012, "buy")] == 1 and sum(counts.values()) == 20


def test_score_counts_yes_and_no_and_reports_blanks(tmp_path) -> None:
    header = review.CHECKLIST.format(
        symbol="X", n=3, total=9, years="2012-2017", spread="cells", seed=1, fvg_note=""
    )
    body = "\n".join(
        [
            "| 1 | [a](a) | `p1` | 2012-01-01 | buy | 1h 1.0 | yes |  |",
            "| 2 | [b](b) | `p2` | 2012-01-02 | sell | pd 2.0 | no | sweep is a breakout |",
            "| 3 | [c](c) | `p3` | 2012-01-03 | buy | 4h 3.0 |  |  |",
        ]
    )
    path = tmp_path / "REVIEW.md"
    path.write_text(header + body, encoding="utf-8")
    r = review.score(path)
    assert (r["rows"], r["yes"], r["no"], r["not_reviewed"], r["precision"]) == (3, 1, 1, 1, 0.5)
    assert r["passed"] is False  # a blank row means the review is not finished


def test_wilson_interval() -> None:
    lo, hi = review.wilson(45, 50)
    assert lo == pytest.approx(0.7864, abs=1e-3) and hi == pytest.approx(0.9565, abs=1e-3)


def test_a_chart_is_drawn(tmp_path) -> None:
    ts = pd.date_range("2016-03-01 10:00", periods=80, freq="15min", tz="UTC")
    close = 1200 + np.cumsum(np.random.default_rng(0).normal(0, 1, 80))
    entry = pd.DataFrame(
        {"ts_utc": ts, "open": close, "high": close + 1, "low": close - 1, "close": close + 0.2}
    )
    row = pd.Series(
        {
            "direction": "buy",
            "level_source": "1h",
            "level_price": close[45] - 0.5,
            "sweep_first_idx": 45,
            "extreme_idx": 45,
            "extreme": close[45] - 1,
            "choch_ref_idx": 40,
            "choch_ref_price": close[40] + 1,
            "choch_idx": 50,
            "fvg_idx": 49,
            "fvg_low": close[47],
            "fvg_high": close[47] + 0.5,
            "sweep_utc": ts[45],
            "depth_atr": 0.4,
            "fvg_size_atr": 0.3,
        }
    )
    review.draw(row, entry, tmp_path / "x.png", 1)
    assert (tmp_path / "x.png").stat().st_size > 10_000


def test_sample_can_spread_over_other_cells() -> None:
    rows = []
    for sym in ("XAUUSD", "EURUSD"):
        for has in (True, False):
            for k in range(20):
                t = pd.Timestamp("2016-03-01", tz="UTC") + pd.Timedelta(hours=k)
                rows.append({"symbol": sym, "has_fvg": has, "sweep_utc": t, "year": 2016})
    a = review.sample(pd.DataFrame(rows), n=20, seed=410733, by=("symbol", "has_fvg"))
    assert a.groupby(["symbol", "has_fvg"]).size().tolist() == [5, 5, 5, 5]


def test_a_chart_without_fvg_is_drawn(tmp_path) -> None:
    ts = pd.date_range("2016-03-01 10:00", periods=80, freq="15min", tz="UTC")
    close = 1.1 + np.cumsum(np.random.default_rng(0).normal(0, 1e-4, 80))
    entry = pd.DataFrame(
        {"ts_utc": ts, "open": close, "high": close + 2e-4, "low": close - 2e-4, "close": close}
    )
    row = pd.Series(
        {
            "symbol": "EURUSD",
            "direction": "sell",
            "level_source": "1h",
            "level_price": close[45] + 1e-4,
            "sweep_first_idx": 45,
            "extreme_idx": 45,
            "extreme": close[45] + 2e-4,
            "choch_ref_idx": 40,
            "choch_ref_price": close[40] - 2e-4,
            "choch_idx": 50,
            "fvg_idx": -1,
            "fvg_low": np.nan,
            "fvg_high": np.nan,
            "sweep_utc": ts[45],
            "depth_atr": 0.4,
            "fvg_size_atr": np.nan,
        }
    )
    review.draw(row, entry, tmp_path / "x.png", 1, decimals=5)
    assert (tmp_path / "x.png").stat().st_size > 10_000
