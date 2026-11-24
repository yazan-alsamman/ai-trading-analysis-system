from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.config import strategy
from app.smc.events import Side, detect_sweeps, find_choch, find_fvg
from app.smc.primitives import Level, previous_day_levels, swing_levels

P = strategy()  # k_entry 2, ATR 14, sweep 0.1-1.5 ATR, close back within 1 bar, CHoCH 8, FVG 0.1
START = pd.Timestamp("2024-01-16 01:00", tz="UTC")


def bars(
    rows: list[tuple[float, float, float, float]], gap_after: int | None = None
) -> pd.DataFrame:
    """15m bars from (open, high, low, close), after 20 quiet bars of range 2 (ATR = 2)."""
    quiet = [(101.0, 102.0, 100.0, 101.0)] * 20
    data = np.array(quiet + rows, float)
    ts = START + pd.to_timedelta(np.arange(len(data)) * 15, unit="min")
    if gap_after is not None:
        ts = ts.where(np.arange(len(data)) <= 20 + gap_after, ts + pd.Timedelta(hours=1))
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta("15min"),
            "open": data[:, 0],
            "high": data[:, 1],
            "low": data[:, 2],
            "close": data[:, 3],
        }
    )


def level(price: float, side: str) -> Level:
    return Level(price, side, "pd", START - pd.Timedelta(days=1), START, date(2024, 1, 16))


def sweeps(entry: pd.DataFrame, lv: Level) -> list:
    return [s for s in detect_sweeps(entry, [lv], P) if s.level == lv]


J = 20  # index of the first row after the quiet bars


# ---- sweep / breakout / shallow ----------------------------------------------------------------


def test_close_back_on_the_same_bar_is_a_sweep() -> None:
    (s,) = sweeps(bars([(100.5, 101, 99.5, 100.8)]), level(100, "low"))  # 0.5 below, ATR 2
    assert (s.direction, s.kind, s.first_idx, s.settled_idx) == ("buy", "sweep", J, J)
    assert s.extreme == 99.5 and s.depth_atr == pytest.approx(0.5 / s.atr, abs=1e-6)


def test_close_back_on_the_next_bar_is_a_sweep_settled_there() -> None:
    (s,) = sweeps(bars([(100.5, 101, 99.5, 99.8), (99.8, 100.9, 99.2, 100.6)]), level(100, "low"))
    assert (s.kind, s.settled_idx, s.extreme_idx, s.extreme) == ("sweep", J + 1, J + 1, 99.2)


def test_no_close_back_in_time_is_a_breakout() -> None:
    rows = [(100.5, 101, 99.5, 99.8), (99.8, 99.9, 99.3, 99.6), (99.6, 101, 99.5, 100.5)]
    (s,) = sweeps(bars(rows), level(100, "low"))
    assert (s.kind, s.reason, s.settled_idx) == ("breakout", "no_close_back", J + 1)


def test_deeper_than_the_breakout_limit_is_a_breakout_even_with_a_close_back() -> None:
    (s,) = sweeps(bars([(100.5, 101, 96.5, 100.5)]), level(100, "low"))  # 3.5 below = 1.75 ATR
    assert (s.kind, s.reason) == ("breakout", "too_deep")


def test_a_tick_beyond_is_shallow() -> None:
    (s,) = sweeps(bars([(100.5, 101, 99.9, 100.5)]), level(100, "low"))  # 0.05 ATR
    assert s.kind == "shallow"


def test_sell_side_is_the_mirror() -> None:
    (s,) = sweeps(bars([(101.5, 102.5, 101, 101.2)]), level(102, "high"))
    assert (s.direction, s.kind, s.extreme) == ("sell", "sweep", 102.5)


def test_a_sweep_that_needs_a_bar_not_there_yet_is_pending() -> None:
    assert sweeps(bars([(100.5, 101, 99.5, 99.8)]), level(100, "low")) == []


# ---- CHoCH ------------------------------------------------------------------------------------

# A swing high at 103.5 (k = 2) before the sweep, then the sweep of 100 and the bars after it.
SETUP = [
    (101, 102, 100.5, 101.5),
    (101.5, 103, 101, 102.5),
    (102.5, 103.5, 102, 103),  # swing high 103.5 at J + 2
    (103, 103.2, 101.5, 102),
    (102, 102.5, 100.8, 101),
    (101, 101.2, 99.4, 100.4),  # J + 5: sweep of 100, extreme 99.4, closes back
]


def _first_sweep(entry: pd.DataFrame):
    return sweeps(entry, level(100, "low"))[0]


def test_choch_is_the_close_above_the_last_swing_high_before_the_extreme() -> None:
    entry = bars(SETUP + [(100.4, 102, 100.2, 101.8), (101.8, 104.2, 101.6, 104)])
    s = _first_sweep(entry)
    ch, why = find_choch(Side.of(entry, "buy"), s, P.k_entry, P.choch_window_bars)
    assert why == "" and (ch.idx, ch.ref_idx, ch.ref_price) == (J + 7, J + 2, 103.5)


def test_a_lower_low_before_the_choch_ends_the_search() -> None:
    entry = bars(SETUP + [(100.4, 101, 99.0, 100.2)] + [(100.2, 104.5, 100, 104)] * 2)
    ch, why = find_choch(Side.of(entry, "buy"), _first_sweep(entry), P.k_entry, P.choch_window_bars)
    assert (ch, why) == (None, "new_extreme")


def test_no_choch_within_the_window() -> None:
    entry = bars(SETUP + [(100.4, 101.5, 100, 101)] * 9)
    ch, why = find_choch(Side.of(entry, "buy"), _first_sweep(entry), P.k_entry, P.choch_window_bars)
    assert (ch, why) == (None, "window")


def test_choch_pending_while_the_window_is_open() -> None:
    entry = bars(SETUP + [(100.4, 101.5, 100, 101)] * 3)
    ch, why = find_choch(Side.of(entry, "buy"), _first_sweep(entry), P.k_entry, P.choch_window_bars)
    assert (ch, why) == (None, "pending")


# ---- FVG --------------------------------------------------------------------------------------

DISPLACEMENT = SETUP + [
    (100.4, 101.0, 100.2, 100.9),  # J + 6: high 101.0
    (100.9, 102.5, 100.8, 102.4),  # J + 7
    (102.4, 104.2, 101.6, 104.0),  # J + 8: low 101.6 > 101.0: gap 0.6 = 0.3 ATR; CHoCH
]


def test_fvg_is_the_first_gap_of_the_displacement() -> None:
    entry = bars(DISPLACEMENT)
    side = Side.of(entry, "buy")
    s = _first_sweep(entry)
    ch, _ = find_choch(side, s, P.k_entry, P.choch_window_bars)
    f = find_fvg(side, s, ch, P.fvg_min_size_atr)
    assert (f.idx, f.low, f.high) == (J + 8, 101.0, 101.6)
    assert f.size_atr == pytest.approx(0.6 / s.atr, abs=1e-6)


def test_bars_across_a_break_cannot_form_a_gap() -> None:
    entry = bars(DISPLACEMENT, gap_after=7)  # an hour of missing data before J + 8
    side = Side.of(entry, "buy")
    s = _first_sweep(entry)
    ch, _ = find_choch(side, s, P.k_entry, P.choch_window_bars)
    assert find_fvg(side, s, ch, P.fvg_min_size_atr) is None


def test_sell_side_fvg_and_choch_mirror_the_buy_side() -> None:
    flip = [(200 - o, 200 - lo, 200 - h, 200 - c) for o, h, lo, c in DISPLACEMENT]
    entry = bars(flip)
    entry.loc[: J - 1, ["open", "high", "low", "close"]] = [99.0, 100.0, 98.0, 99.0]
    (s,) = [x for x in detect_sweeps(entry, [level(100, "high")], P)]
    side = Side.of(entry, "sell")
    ch, _ = find_choch(side, s, P.k_entry, P.choch_window_bars)
    f = find_fvg(side, s, ch, P.fvg_min_size_atr)
    assert (s.direction, s.extreme, ch.ref_price) == ("sell", 100.6, 96.5)
    assert (f.low, f.high) == (98.4, 99.0)


# ---- no look-ahead ----------------------------------------------------------------------------


def _walk(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    open_ = np.r_[close[0], close[:-1]]
    ts = pd.date_range("2024-01-15 23:00", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta("15min"),
            "open": open_,
            "high": np.maximum(open_, close) + rng.uniform(0, 1.5, n),
            "low": np.minimum(open_, close) - rng.uniform(0, 1.5, n),
            "close": close,
        }
    )


@pytest.mark.parametrize("n", [300, 777, 1500])
def test_events_never_change_when_bars_are_appended(n: int) -> None:
    full = _walk(2000, seed=7)
    h1 = full.groupby(full["ts_utc"].dt.floor("1h")).agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    h1 = h1.rename_axis("ts_utc").reset_index()
    h1["close_utc"] = h1["ts_utc"] + pd.Timedelta("1h")
    h1 = h1[h1["close_utc"] <= full["close_utc"].iloc[-1]]
    part = full.iloc[:n]
    cut = part["close_utc"].iloc[-1]
    levels_full = swing_levels(h1, 3, "1h")
    levels_part = swing_levels(h1[h1["close_utc"] <= cut], 3, "1h")
    a = detect_sweeps(full, levels_full, P)
    b = detect_sweeps(part, levels_part, P)
    assert b == [s for s in a if s.settled_idx < n]
    assert len(a) > 30
    for s in b:
        for side_full, side_part in ((Side.of(full, s.direction), Side.of(part, s.direction)),):
            cf, wf = find_choch(side_full, s, P.k_entry, P.choch_window_bars)
            cp, wp = find_choch(side_part, s, P.k_entry, P.choch_window_bars)
            if wp != "pending":
                assert (cf, wf) == (cp, wp)
            if cp is not None:
                assert find_fvg(side_full, s, cf, P.fvg_min_size_atr) == find_fvg(
                    side_part, s, cp, P.fvg_min_size_atr
                )


def test_previous_day_levels_feed_the_sweeps() -> None:
    d1 = pd.DataFrame(
        {
            "ts_utc": [pd.Timestamp("2024-01-14 22:00", tz="UTC")],
            "close_utc": [pd.Timestamp("2024-01-15 22:00", tz="UTC")],
            "open": [100.0],
            "high": [104.0],
            "low": [100.0],
            "close": [101.0],
        }
    )
    entry = bars([(100.5, 101, 99.5, 100.8)])
    (s,) = [x for x in detect_sweeps(entry, previous_day_levels(d1), P) if x.direction == "buy"]
    assert (s.kind, s.level.source) == ("sweep", "pd")
