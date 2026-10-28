"""The management engine (docs/strategies/PREREG.md, section 7): each rule on hand-built bars, M0
against ``labels.resolve``, the one-active-trade book, and an append-future-bars test for every
bundle."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.config import SignalSpec, bundles, instruments, rules, signal_specs, strategy
from app.data.sessions import MARKET_TZ
from app.management.book import one_active
from app.management.engine import Market, Outcome, manage
from app.setups.builder import Plan
from app.setups.labels import Bars, resolve, round_trip
from app.strategies.base import BUY, SELL, STEP, Candidate, Thesis, Trigger, at_time, finish
from app.strategies.rules import STRATEGIES, candidates, thesis
from tests.strategy_data import cut, market

RP = rules()
B = bundles()
XAU = instruments()["XAUUSD"]
FREE = replace(XAU, cost_extra_frac=0.0, cost_extra_min=0.0, sl_slippage=0.0)
D = 30  # the signal bar of the hand-built trades
QUIET = (100.0, 100.2, 99.8, 100.0)


def frame(after: list[tuple], before: int = D + 1) -> pd.DataFrame:
    """``before`` quiet 15m bars (the last is the signal bar, closing at 100), then ``after``."""
    data = np.asarray([QUIET] * before + after, float)
    ts = pd.date_range("2024-06-12 00:00", periods=len(data), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "ts_utc": ts.as_unit("ns"),
            "close_utc": (ts + pd.Timedelta(minutes=15)).as_unit("ns"),
            "open": data[:, 0],
            "high": data[:, 1],
            "low": data[:, 2],
            "close": data[:, 3],
        }
    )


def cand(direction=BUY, entry=100.0, sl=98.0, tp=104.0, h=8, spread=0.0, deadline=None,
         level=None, idx=D) -> Candidate:  # fmt: skip
    s = 1.0 if direction == BUY else -1.0
    risk = s * (entry - sl)
    return Candidate("S0", idx, pd.Timestamp("2024-06-12", tz="UTC"), direction, "ARMED", "",
                     entry, sl, tp, risk, None if tp is None else s * (tp - entry) / risk, spread,
                     1.0, h, deadline, level)  # fmt: skip


def run(after, bundle="M0", inst=FREE, l5=None, th=None, **kw) -> Outcome:
    c = cand(**kw)
    m = Market.of(frame(after), c.direction, "15m", RP)
    return manage(m, c, B[bundle], RP, inst, l5, th)


def test_m0_tp_sl_timeout_and_gap() -> None:
    assert run([QUIET, (100, 104.1, 99.9, 104)]).reason == "tp"
    sl = run([(100, 100.1, 97.9, 98.5)], inst=XAU, spread=0.3)
    assert (sl.reason, sl.exit_price, sl.gross_r) == ("sl", pytest.approx(97.9), -1.0)
    assert sl.net_r() == pytest.approx(-1.0 - 0.10 / 2 - round_trip(0.3, XAU) / 2)
    assert run([(100, 104.5, 97.5, 101)]).reason == "sl"  # ambiguous bar
    gap = run([(97.0, 97.2, 96.8, 97.0)])
    assert (gap.reason, gap.exit_price, gap.gross_r) == ("sl", 97.0, -1.5)
    out = run([QUIET] * 8)
    assert (out.reason, out.exit_idx) == ("timeout", D + 8)
    assert run([QUIET] * 3).state == "PENDING"


def test_session_end_exits_at_the_last_bar_that_closes_by_the_deadline() -> None:
    deadline = pd.Timestamp("2024-06-12", tz="UTC") + pd.Timedelta(minutes=15 * (D + 4))
    out = run([QUIET] * 8, deadline=deadline)  # bar D + 3 closes at the deadline
    assert (out.reason, out.exit_idx) == ("session_end", D + 3)


# The session end at 16:45 New York on every intraday frame, in winter, summer and both weeks a
# year when US and EU daylight saving differ (the rollover is then at 18:00 New York).
DAYS = ("2024-01-10", "2024-03-13", "2024-06-12", "2024-10-30")
EXIT_AT = {"5m": "16:45", "15m": "16:45", "1h": "16:00"}  # New York close of the exit bar


def grid(day: str, tf: str, drop: tuple[str, str] | None = None) -> pd.DataFrame:
    """Quiet bars of ``tf`` from 08:00 to 22:00 New York on ``day`` (bars opening in ``drop``,
    New York times, left out)."""
    start, end = (at_time(np.datetime64(day), t, MARKET_TZ) for t in ("08:00", "22:00"))
    ts = pd.date_range(start, end, freq=STEP[tf], inclusive="left").as_unit("ns")
    if drop is not None:
        lo, hi = (at_time(np.datetime64(day), t, MARKET_TZ) for t in drop)
        ts = ts[(ts < lo) | (ts >= hi)]
    n = len(ts)
    return pd.DataFrame({"ts_utc": ts, "close_utc": ts + STEP[tf], "open": [100.0] * n,
                         "high": [100.2] * n, "low": [99.8] * n, "close": [100.0] * n})  # fmt: skip


def opening(frame: pd.DataFrame, day: str, hhmm: str) -> int:
    t = at_time(np.datetime64(day), hhmm, MARKET_TZ)
    return int(np.flatnonzero(frame["ts_utc"] == t)[0])


@pytest.mark.parametrize("day", DAYS)
@pytest.mark.parametrize("tf", sorted(EXIT_AT))
def test_session_end_boundary_on_every_intraday_frame(day: str, tf: str) -> None:
    e = grid(day, tf)
    deadline = at_time(np.datetime64(day), "16:45", MARKET_TZ)
    c = cand(idx=opening(e, day, "13:00"), h=500, deadline=deadline)
    out = manage(Market.of(e, BUY, tf, RP), c, B["M0"], RP, FREE)
    exit_ny = pd.Timestamp(out.exit_ns, tz="UTC").tz_convert(MARKET_TZ).strftime("%H:%M")
    assert (out.reason, exit_ny) == ("session_end", EXIT_AT[tf])
    assert out.slip_r == 0.0  # an exit at a close, as the timeout


@pytest.mark.parametrize("day", DAYS)
@pytest.mark.parametrize("tf", sorted(EXIT_AT))
def test_no_time_left_boundary_on_every_intraday_frame(day: str, tf: str) -> None:
    """The last signal bar of the liquid window (opening before 16:00) has time left on 5m and
    15m; on 1h the bar opening 15:00 has none (its next bar would close 17:00), 14:00 has."""
    e = grid(day, tf)
    spec = replace(signal_specs()["S2"], frame=tf)  # intraday: the 16:45 session end
    last = {"5m": "15:55", "15m": "15:45", "1h": "14:00"}[tf]
    states = {}
    for hhmm in sorted({last, "15:00"}):
        j = opening(e, day, hhmm)
        (c,) = finish(e, [Trigger(j, BUY, 90.0, tp_r=1.5)], spec, FREE, np.ones(len(e)))
        states[hhmm] = c.reason
    assert states[last] == ""
    assert states["15:00"] == ("no_time_left" if tf == "1h" else "")


def test_no_session_end_on_a_4h_or_d1_frame() -> None:
    for tf in ("4h", "D1"):
        with pytest.raises(ValueError, match="session end"):
            SignalSpec("SX", "A", "intraday", tf, 10, True, "16:45", {})
    SignalSpec("SX", "A", "swing", "4h", 10, False, None, {})  # swing: horizon only


def test_bars_missing_before_the_session_end_exit_at_the_next_open() -> None:
    day = "2024-06-12"
    e = grid(day, "5m", drop=("16:30", "17:30"))  # nothing from 16:30 to 17:30 New York
    e.loc[opening(e, day, "17:30"), ["open", "high", "low", "close"]] = (100.5, 100.6, 100.4, 100.5)
    deadline = at_time(np.datetime64(day), "16:45", MARKET_TZ)
    c = cand(idx=opening(e, day, "13:00"), h=500, deadline=deadline)
    out = manage(Market.of(e, BUY, "5m", RP), c, B["M0"], RP, XAU)
    j = opening(e, day, "17:30")
    assert (out.reason, out.exit_idx) == ("session_end_gap", j)
    assert out.exit_price == pytest.approx(100.5 - XAU.sl_slippage)  # the open, minus slippage
    assert out.exit_ns == e["ts_utc"].iloc[j].value  # exit time: the bar's open (for swap)
    e.loc[j, ["open", "high", "low", "close"]] = (104.5, 104.6, 104.4, 104.5)  # opens past the TP
    tp = manage(Market.of(e, BUY, "5m", RP), c, B["M0"], RP, XAU)
    assert (tp.reason, tp.exit_price, tp.slip_r) == ("tp", 104.0, 0.0)


def test_t1_profit_lock_after_half_the_horizon() -> None:
    near = (100, 103.4, 99.9, 103.3)  # progress 3.3 / 4 >= 80%
    early = run([near, near, near, (103.3, 103.5, 103.1, 103.4)], "M1")
    assert early.state == "PENDING"  # at D + 3 only 3 of 8 bars elapsed
    out = run([QUIET, QUIET, QUIET, near, (103.0, 103.5, 102.9, 103.2)], "M1", inst=XAU)
    assert (out.reason, out.exit_idx) == ("profit_lock", D + 5)
    assert out.exit_price == pytest.approx(103.0 - 0.10)  # next open, minus the slippage


def test_t2_scale_out_then_tp_or_breakeven() -> None:
    up = (100, 102.1, 99.9, 101.5)
    out = run([up, (101.5, 104.2, 101.4, 104)], "M4")
    assert (out.reason, out.scaled, out.gross_r) == ("scale_out_tp", True, 1.5)
    be = run([up, (101.5, 101.6, 99.9, 100.2)], "M4")  # L1 moved the rest's SL to entry
    assert (be.reason, be.gross_r) == ("breakeven", 0.5)
    low_tp = run([(100, 101.6, 99.9, 101.5)], "M4", tp=101.5)  # TP below +1 R: no scale-out
    assert (low_tp.reason, low_tp.scaled) == ("tp", False)


def test_l1_breakeven_at_the_round_trip_cost() -> None:
    out = run([(100, 102.1, 99.9, 101), (101, 101.1, 100.3, 100.5)], "M2", inst=XAU, spread=0.3)
    assert out.reason == "breakeven"
    assert out.exit_price == pytest.approx(100 + round_trip(0.3, XAU) - 0.10)


def test_t3_dead_trade_and_t4_fade() -> None:
    dead = run([QUIET] * 5, "M5")
    assert (dead.reason, dead.exit_idx) == ("dead_trade", D + 5)
    arm = (100, 101.3, 99.9, 101.2)  # open profit 0.6 R at the close
    engulf = (101.3, 101.4, 99.8, 99.9)  # body covers the previous body, against
    fade = run([arm, engulf, QUIET], "M5")
    assert (fade.reason, fade.exit_idx) == ("fade", D + 3)
    up, below_ema = (101.2, 101.5, 101.0, 101.4), (100.5, 100.6, 99.9, 99.95)  # no engulfing
    fade = run([arm, up, below_ema, QUIET], "M5")
    assert (fade.reason, fade.exit_idx) == ("fade", D + 4)
    same_bar = run([(100, 101.3, 99.9, 99.9), QUIET], "M5")  # arms only at a close
    assert same_bar.state == "PENDING"


def test_l2_atr_trail_moves_up_only() -> None:
    rise = [(100 + i, 101 + i, 99.9 + i, 101 + i) for i in range(4)]  # high 104 -> trailing
    out = run([*rise, (103.5, 103.6, 101.0, 101.5)], "M3", h=20)
    assert out.reason == "trail" and out.exit_idx == D + 5
    m = Market.of(frame(rise), BUY, "15m", RP)
    assert out.exit_price == pytest.approx(104 - 2 * m.atr[D + 4])


def test_l3_structure_trail_to_the_last_confirmed_swing_low() -> None:
    after = [(101.5, 102.2, 101.4, 102), (102, 102.6, 101.8, 102.4), (102.4, 102.5, 101.0, 101.5),
             (101.5, 103, 101.4, 102.8), (102.8, 103.5, 102.5, 103.2),
             (103.2, 103.4, 100.5, 101)]  # fmt: skip
    out = run(after, "M8", h=20)  # swing low 101.0 at D + 3, confirmed at the close of D + 5
    m = Market.of(frame(after), BUY, "15m", RP)
    assert (out.reason, out.exit_idx) == ("trail", D + 6)
    assert out.exit_price == pytest.approx(101.0 - 0.1 * m.atr[D + 5])


def test_l4_time_tightening_and_l5_level() -> None:
    tight = run([QUIET] * 6 + [(100, 100.1, 98.9, 99.5)], "M6")  # SL -0.5 R from 6 of 8 bars
    assert (tight.reason, tight.exit_price) == ("time_tighten", 99.0)
    back = (99.6, 99.7, 99.3, 99.4)  # closes back below the broken level 99.5
    out = run([back, back, QUIET], "M6", l5="level", level=99.5)
    assert (out.reason, out.exit_idx) == ("invalidation", D + 3)
    reset = run([back, QUIET, back, QUIET], "M6", l5="level", level=99.5)
    assert reset.state == "PENDING"


def test_l5_series_only_from_source_bars_after_the_entry() -> None:
    n = D + 6
    entry_close = frame([]).close_utc.iloc[D].value
    against = np.zeros(n, bool)
    against[D + 2] = True
    stale = Thesis(against, np.full(n, entry_close))  # its source closed at the entry
    assert run([QUIET] * 5, "M6", l5="series", th=stale).state == "PENDING"
    fresh = Thesis(against, np.full(n, entry_close + 1))
    out = run([QUIET] * 5, "M6", l5="series", th=fresh)
    assert (out.reason, out.exit_idx) == ("invalidation", D + 3)
    with pytest.raises(ValueError):
        run([QUIET], "M6", l5="series")


def test_a_sell_is_the_mirror_of_a_buy() -> None:
    after = [(100, 102.1, 99.9, 101.5), (101.5, 101.6, 99.9, 100.2)]
    buy = run(after, "M4")
    mirrored = [(200 - o, 200 - lo, 200 - h, 200 - c) for o, h, lo, c in after]  # QUIET is 100
    c = cand(SELL, 100.0, 102.0, 96.0)
    sell = manage(Market.of(frame(mirrored), SELL, "15m", RP), c, B["M4"], RP, FREE)
    assert (sell.reason, sell.gross_r) == (buy.reason, buy.gross_r)


# --- M0 equals labels.resolve ----------------------------------------------------------------


def _same(lab, out: Outcome) -> None:
    if lab.state == "PENDING":
        assert out.state == "PENDING"
        return
    assert (out.reason, out.exit_idx) == (lab.reason, lab.exit_idx)
    assert out.exit_price == lab.exit_price
    assert (out.gross_r, out.net_r(), out.net_r(2)) == (lab.gross_r, lab.net_r, lab.net_r_2x)


def test_m0_equals_resolve_on_random_plans() -> None:
    p = strategy("L1")
    e = market("XAUUSD")["15m"]
    rng = np.random.default_rng(3)
    markets = {d: Market.of(e, d, "15m", RP) for d in (BUY, SELL)}
    sides = {d: Bars.of(e, d) for d in (BUY, SELL)}
    close = e["close"].to_numpy()
    for _ in range(400):
        d = int(rng.integers(30, len(e) - 1))
        direction = BUY if rng.random() < 0.5 else SELL
        s = 1.0 if direction == BUY else -1.0
        risk, k = float(rng.uniform(1, 6)), float(rng.uniform(1.5, 4))
        spread = float(rng.uniform(0.1, 0.5))
        c = cand(direction, close[d], close[d] - s * risk, close[d] + s * k * risk, 48, spread,
                 idx=d)  # fmt: skip
        plan = Plan("ARMED", "", c.entry, c.sl, c.tp, c.risk, k, None)
        lab = resolve(sides[direction], d, plan, spread, p, XAU)
        _same(lab, manage(markets[direction], c, B["M0"], RP, XAU))


STORE = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.mark.skipif(not (STORE / "XAUUSD" / "15m.parquet").exists(), reason="no research store")
@pytest.mark.parametrize("symbol", ["XAUUSD", "EURUSD"])
def test_m0_equals_resolve_on_the_l1_store(symbol: str) -> None:
    """Every armed L1 setup of the development period: the engine's M0 and ``resolve`` agree to
    the last digit. Nothing is printed or written."""
    from app.setups.builder import build
    from app.smc.detector import detect, development_frames

    p = strategy("L1")
    inst = instruments()[symbol]
    frames = development_frames(symbol, STORE, p)
    e = frames[p.entry_timeframe]
    markets = {d: Market.of(e, d, p.entry_timeframe, RP) for d in (BUY, SELL)}
    sides = {d: Bars.of(e, d) for d in (BUY, SELL)}
    n = 0
    for st in build(frames, detect(frames, p), p):
        if st.plan.state != "ARMED":
            continue
        pl, direction = st.plan, st.pattern.direction
        c = cand(direction, pl.entry, pl.sl, pl.tp, p.horizon_bars, st.spread,
                 idx=st.decision_idx)  # fmt: skip
        lab = resolve(sides[direction], st.decision_idx, pl, st.spread, p, inst)
        _same(lab, manage(markets[direction], c, B["M0"], RP, inst))
        n += 1
    assert n > 30


# --- one active trade ------------------------------------------------------------------------


def test_one_active_trade_rejects_until_the_exit_bar() -> None:
    cs = [cand(idx=10), cand(idx=12), cand(idx=15), cand(idx=20)]
    exits = {10: 15, 15: 18, 20: None}

    def fake(c):
        x = exits[c.idx]
        return Outcome("PENDING", "active") if x is None else Outcome("CLOSED", "tp", x)

    out = one_active([*cs, replace(cs[0], idx=30)], fake)
    assert [(c.idx, c.state, c.reason) for c, _ in out] == [
        (10, "ARMED", ""),
        (12, "REJECTED", "position_open"),
        (15, "ARMED", ""),  # the trade left at bar 15: flat at its close
        (20, "ARMED", ""),
        (30, "ARMED", ""),
    ]
    assert out[3][1].state == "PENDING" and out[4][1] is None  # nothing after it is decided


# --- no look-ahead ---------------------------------------------------------------------------


@pytest.mark.parametrize("bundle", sorted(B))
def test_append_future_bars_changes_no_outcome(bundle: str) -> None:
    full = market("XAUUSD")
    checked = 0
    for name, (_, l5) in sorted(STRATEGIES.items()):
        spec = signal_specs()[name]
        e = full[spec.frame]
        th_full = thesis(full, spec, RP.L5_adx_max)
        arm = [c for c in candidates(full, XAU, spec) if c.state == "ARMED"][:25]
        outs = {}
        for c in arm:
            m = Market.of(e, c.direction, spec.frame, RP)
            th = th_full[c.direction] if th_full else None
            outs[c.idx, c.direction] = manage(m, c, B[bundle], RP, XAU, l5, th)
        for t in e["close_utc"].iloc[[len(e) // 3, 2 * len(e) // 3]]:
            part = cut(full, t)
            pe = part[spec.frame]
            th_part = thesis(part, spec, RP.L5_adx_max)
            for c in arm:
                if c.idx >= len(pe):
                    continue
                m = Market.of(pe, c.direction, spec.frame, RP)
                th = th_part[c.direction] if th_part else None
                got = manage(m, c, B[bundle], RP, XAU, l5, th)
                if got.state == "CLOSED":
                    assert got == outs[c.idx, c.direction]
                    checked += 1
    assert checked > 20
