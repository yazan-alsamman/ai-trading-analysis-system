from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.smc.engine import _LongScanner, _real_prices, run
from app.smc.params import CostParams, StrategyParams
from app.smc.primitives import Level

START = pd.Timestamp("2024-01-02 00:00", tz="UTC")
WARMUP = [(100.0, 100.5, 99.5, 100.0)] * 20
SETUP_BARS = [
    (100.0, 101.0, 99.6, 100.2),  # 20: the 15m swing high (101) the CHoCH must close above
    (100.2, 100.6, 99.5, 99.8),  # 21
    (99.8, 100.4, 99.3, 99.4),  # 22: confirms the swing high
    (99.4, 99.6, 98.8, 99.2),  # 23: sweeps the 99.0 low and closes back above it
    (99.2, 100.0, 99.1, 99.9),  # 24
    (99.9, 101.6, 99.9, 101.5),  # 25: CHoCH; FVG between high[23]=99.6 and low[25]=99.9
]


def _frame(rows):
    o, h, lo, c = (list(x) for x in zip(*rows, strict=True))
    return pd.DataFrame(
        {
            "ts_utc": pd.date_range(START, periods=len(rows), freq="15min"),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "spread": 0.0,
        }
    )


def _levels():
    day = np.datetime64("2024-01-02", "D")
    return [
        Level(99.0, "low", "1h", START, START, day),
        Level(102.0, "high", "1h", START, START, day),
    ]


def _scan(after, direction="buy", params=None):
    m15 = _frame(WARMUP + SETUP_BARS + after)
    sc = _LongScanner(m15, _levels(), params or StrategyParams(), CostParams(), direction)
    for j in range(len(m15)):
        sc.step(j)
    (setup,) = sc.finish()
    return sc, setup


def test_full_buy_setup_reaches_tp():
    after = [
        (101.4, 101.5, 100.5, 100.8),  # 26: no fill
        (100.8, 100.9, 99.85, 100.3),  # 27: fills at 99.9
        (100.3, 102.1, 100.2, 102.0),  # 28: TP
    ]
    sc, s = _scan(after)
    assert [e[1] for e in s.events] == ["DEVELOPING", "ARMED", "ACTIVE", "CLOSED"]
    assert (s.sweep_idx, s.extreme_idx, s.choch_idx, s.ref_idx, s.fvg_idx) == (23, 23, 25, 20, 25)
    assert s.entry == 99.9
    assert s.sl == pytest.approx(98.8 - 0.1 * sc.atr[23])
    assert s.tp == 102.0
    risk = s.entry - s.sl
    assert s.r_multiple == pytest.approx((102.0 - 99.9) / risk)
    assert (s.fill_idx, s.exit_idx, s.outcome) == (27, 28, "tp")
    cost = CostParams().round_trip(0.0) / risk
    assert s.net_r == pytest.approx(s.r_multiple - cost)


def test_new_extreme_discards_a_developing_setup():
    rows = WARMUP + SETUP_BARS[:4] + [(99.2, 99.4, 98.6, 99.0)]  # bar 24 makes a new low
    m15 = _frame(rows)
    sc = _LongScanner(m15, _levels(), StrategyParams(), CostParams(), "buy")
    for j in range(len(m15)):
        sc.step(j)
    (s,) = sc.finish()
    assert s.state == "DISCARDED"
    assert s.reason == "new extreme before the CHoCH"


def test_unfilled_setup_expires_after_the_entry_window():
    _, s = _scan([(101.4, 101.5, 100.5, 101.0)] * 10)
    assert s.state == "EXPIRED"
    assert s.events[-1][0] == 25 + 9


def test_tp_before_fill_invalidates():
    _, s = _scan([(101.5, 102.2, 101.0, 102.0)])
    assert s.state == "INVALIDATED"
    assert s.reason == "TP level reached before the fill"


def test_stop_loss_costs_slippage_and_spread():
    _, s = _scan([(100.5, 100.6, 99.85, 100.0), (100.0, 100.1, 98.0, 98.2)])
    assert s.outcome == "sl"
    risk = s.entry - s.sl
    assert s.realized_r == pytest.approx(-1 - CostParams().sl_slippage / risk)
    assert s.net_r < s.realized_r


def test_fill_bar_counts_only_the_stop():
    _, s = _scan([(100.5, 102.5, 99.85, 101.0), (101.0, 101.2, 100.5, 101.0)])
    assert s.state == "ACTIVE"  # TP touched on the fill bar is ignored


def test_horizon_closes_the_trade():
    params = StrategyParams(horizon=3)
    fill = [(100.5, 100.6, 99.85, 100.0)]
    flat = [(100.0, 100.5, 99.6, 100.1)] * 3
    _, s = _scan(fill + flat, params=params)
    assert s.outcome == "timeout"
    assert s.exit_idx == s.fill_idx + 2
    assert s.exit_price == 100.1


def test_sell_side_maps_back_to_real_prices():
    _, buy = _scan([])
    m15 = _frame(WARMUP + SETUP_BARS)
    sc = _LongScanner(m15, _levels(), StrategyParams(), CostParams(), "sell")
    for j in range(len(m15)):
        sc.step(j)
    (sell,) = (_real_prices(s) for s in sc.finish())
    assert (sell.entry, sell.sl, sell.tp) == (-buy.entry, -buy.sl, -buy.tp)
    assert (sell.fvg_low, sell.fvg_high) == (-buy.fvg_high, -buy.fvg_low)
    assert sell.level.kind == "high" and sell.level.price == -99.0


# ---- no look-ahead ------------------------------------------------------------------------------


def _random_walk(n=4000, seed=7):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2023-01-02 00:00", periods=n, freq="15min", tz="UTC")
    c = 1900 + rng.normal(0, 1.2, n).cumsum()
    o = np.concatenate(([c[0]], c[:-1]))
    h = np.maximum(o, c) + rng.exponential(0.6, n)
    lo = np.minimum(o, c) - rng.exponential(0.6, n)
    return pd.DataFrame({"ts_utc": ts, "open": o, "high": h, "low": lo, "close": c, "spread": 0.2})


def _resample(m15, rule):
    g = m15.set_index("ts_utc").resample(rule, label="left", closed="left")
    out = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "spread": "min"})
    return out.dropna().reset_index()


def _snapshot(setups, cutoff):
    """What was known about each setup by the close of bar ``cutoff - 1``."""
    out = {}
    for s in setups:
        if s.sweep_idx >= cutoff:
            continue
        events = [e for e in s.events if e[0] < cutoff]
        armed = any(e[1] == "ARMED" for e in events)
        levels = (s.entry, s.sl, s.tp) if armed else None
        out[s.setup_id] = (events, levels)
    return out


def _assert_no_lookahead(m15, h1, h4, cutoffs):
    full = run(m15, h1, h4)
    assert len(full) > 0
    for cut in cutoffs:
        part = run(m15.iloc[:cut], h1, h4)
        assert _snapshot(part, cut) == _snapshot(full, cut), cut


def test_no_lookahead_on_a_random_walk():
    m15 = _random_walk()
    _assert_no_lookahead(m15, _resample(m15, "1h"), _resample(m15, "4h"), [900, 1777, 2600, 3999])


DATA = Path(__file__).resolve().parents[1] / "data" / "processed" / "XAUUSD"


@pytest.mark.skipif(not (DATA / "15m.parquet").exists(), reason="research store not built")
def test_no_lookahead_on_real_data():
    m15, h1, h4 = (pd.read_parquet(DATA / f"{tf}.parquet") for tf in ("15m", "1h", "4h"))
    end = pd.Timestamp("2013-07-01", tz="UTC")
    m15 = m15[m15["ts_utc"] < end].reset_index(drop=True)
    _assert_no_lookahead(m15, h1, h4, [3_000, 11_111, 17_500, len(m15) - 1])


def test_extend_sweep_keeps_a_developing_setup_within_max_depth():
    rows = WARMUP + SETUP_BARS[:4] + [(99.2, 99.4, 98.6, 99.0)]  # new low 98.6, depth 0.4
    m15 = _frame(rows)
    sc = _LongScanner(m15, _levels(), StrategyParams(extend_sweep=True), CostParams(), "buy")
    for j in range(len(m15)):
        sc.step(j)
    (s,) = sc.finish()
    assert s.state == "DEVELOPING"
    assert (s.extreme, s.extreme_idx, s.extensions) == (98.6, 24, 1)


def test_extend_sweep_still_discards_beyond_max_depth():
    rows = WARMUP + SETUP_BARS[:4] + [(99.2, 99.4, 96.0, 96.5)]  # 3.0 below the level
    m15 = _frame(rows)
    sc = _LongScanner(m15, _levels(), StrategyParams(extend_sweep=True), CostParams(), "buy")
    for j in range(len(m15)):
        sc.step(j)
    (s,) = sc.finish()
    assert s.state == "DISCARDED"


def test_no_lookahead_with_all_variant_options():
    m15 = _random_walk(seed=11)
    h1, h4 = _resample(m15, "1h"), _resample(m15, "4h")
    params = StrategyParams(extend_sweep=True, session_levels=True)
    full = run(m15, h1, h4, params)
    for cut in (1500, 3333):
        part = run(m15.iloc[:cut], h1, h4, params)
        assert _snapshot(part, cut) == _snapshot(full, cut)
