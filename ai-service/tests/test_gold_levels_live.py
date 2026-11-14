"""The live gold-levels engine (app/live/gold_levels.py) on synthetic bars: the same trades as
the research code, no look-ahead, the proposed payload, and the registry."""

import numpy as np
import pandas as pd
import pytest

from app.catalog import registry
from app.data.aggregate import aggregate
from app.data.mt5 import BAR_COLUMNS
from app.live import gold_levels as lv
from app.research import gold_live as gv

FRAMES = ("5m", "1h", "4h", "D1")


def frames(as_of: pd.Timestamp | None = None, days: int = 40, seed: int = 7) -> dict:
    """Gold-like 5m bars (weekdays, 23 hours a day) and the frames aggregated from them."""
    t = pd.date_range("2025-03-02 23:00", periods=days * 288, freq="5min", tz="UTC")
    ny = t.tz_convert(lv.NY)
    keep = (ny.day_of_week < 5) | ((ny.day_of_week == 6) & (ny.hour >= 18))
    keep &= ~((ny.hour == 17) & (ny.day_of_week < 5))  # the daily break
    keep &= ~((ny.day_of_week == 4) & (ny.hour >= 17))
    t = t[keep]
    rng = np.random.default_rng(seed)
    c = 2900 + np.cumsum(rng.normal(0, 1.2, len(t)))
    o = np.r_[c[0], c[:-1]]
    bars = pd.DataFrame(
        {
            "ts_utc": t,
            "open": o,
            "high": np.maximum(o, c) + rng.uniform(0, 1, len(t)),
            "low": np.minimum(o, c) - rng.uniform(0, 1, len(t)),
            "close": c,
            "tick_volume": 100.0,
            "spread": 0.25,
        }
    )[BAR_COLUMNS]
    step = pd.Timedelta(minutes=5)
    as_of = as_of or bars["ts_utc"].iloc[-1] + step
    out = {tf: aggregate(bars, tf, step, as_of) for tf in FRAMES}
    closed = out["D1"][out["D1"]["close_utc"] <= as_of].reset_index(drop=True)
    out["D1"] = lv.with_current_day(closed, out["5m"])
    return out


def day_at(day: int, hhmm: str) -> pd.Timestamp:
    h, m = map(int, hhmm.split(":"))
    return lv.at_ny(day, h * 60 + m)


def test_the_engine_gives_the_research_trades() -> None:
    full = frames()
    _, every, _, cx = gv.five_trades(
        full, start=pd.Timestamp("2025-03-20", tz="UTC"), with_round=True
    )
    every["ny_day"] = cx.ny_day[every["i"].to_numpy()]
    every["fill_at"] = cx.m["close_utc"].to_numpy()[every["i"].to_numpy()]
    days = sorted(d for d in every["ny_day"].unique() if d < 20250408)[:6]
    assert days
    for day in days:
        t = day_at(day, "16:55")
        got = [s for s in lv.scan_day(frames(t), t) if s.state == "CLOSED"]
        ref = every[every["ny_day"] == day]
        assert len(got) == len(ref), day
        for s in got:
            fill = next(p.at for p in s.path if p.state == "ACTIVE")
            r = ref[
                (ref["strategy"] == s.strategy) & (pd.to_datetime(ref["fill_at"], utc=True) == fill)
            ]
            assert len(r) == 1
            assert s.path[-1].realized_r == pytest.approx(float(r["net_slip"].iloc[0]))


def test_nothing_after_as_of_is_read() -> None:
    day = 20250402
    early = lv.scan_day(frames(day_at(day, "09:30")), day_at(day, "09:30"))
    late = {
        (s.strategy, s.kind): s
        for s in lv.scan_day(frames(day_at(day, "16:55")), day_at(day, "16:55"))
    }
    assert early
    for s in early:
        a = [(p.state, p.at) for p in s.path]
        b = [(p.state, p.at) for p in late[(s.strategy, s.kind)].path]
        assert b[: len(a)] == a


def test_states_by_time_of_day() -> None:
    day = 20250402
    assert lv.scan_day(frames(day_at(day, "01:55")), day_at(day, "01:55")) == []
    end = lv.scan_day(frames(day_at(day, "16:55")), day_at(day, "16:55"))
    assert {s.state for s in end} <= {"CLOSED", "EXPIRED", "INVALIDATED"}
    assert all(s.path[0].state == "ARMED" for s in end)


def test_payload_and_evidence_shape() -> None:
    day = 20250402
    s = lv.scan_day(frames(day_at(day, "16:55")), day_at(day, "16:55"))[0]
    p = lv.payload(s, "XAUUSD", "gold_levels")
    assert p["tp"] is None and p["exit_type"] == "trailing" and p["r_multiple"] is None
    assert p["setup_id"] == f"xauusd-gold_levels-{s.strategy.lower()}-{s.kind.lower()}-{day}"
    e = p["evidence"]
    assert {"strategy", "version", "entry_type", "exit_type", "d", "facts"} <= set(e)
    assert e["facts"][0]["key"] == "level_kind" and e["facts"][0]["label_ar"]


def test_registry_and_descriptions() -> None:
    reg = registry()
    assert list(reg) == list(lv.ORDER)
    for e in reg.values():
        assert e.description("ar") and e.description("en")
        assert e.exit_type == "trailing"


def test_with_current_day_adds_the_day_in_progress_once() -> None:
    f = frames(day_at(20250402, "10:00"))
    d1 = f["D1"]
    assert d1["ts_utc"].iloc[-1] == lv.at_ny(20250401, 17 * 60)
    assert len(lv.with_current_day(d1, f["5m"])) == len(d1)


def test_a_moved_stop_keeps_the_trade_active() -> None:
    t = day_at(20250402, "09:30")
    moved = [s for s in lv.scan_day(frames(t), t) if s.path[-1].state == "SL_MOVED"]
    assert moved
    for s in moved:
        assert s.state == "ACTIVE" and lv.payload(s, "XAUUSD", "gold_levels")["state"] == "ACTIVE"
        assert s.sl == s.path[-1].sl
