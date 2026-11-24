import numpy as np
import pandas as pd
import pytest

from app.config import strategy
from app.smc import detector
from app.smc.events import Side, detect_sweeps, find_choch, sweep_allowed
from app.smc.primitives import Level

V1, V5 = strategy(), strategy("V5-S")


def ny_bars(start_ny: str, rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """15m bars from (open, high, low, close) after 20 quiet bars (ATR 2), times in New York."""
    data = np.array([(101.0, 102.0, 100.0, 101.0)] * 20 + rows, float)
    ts = pd.date_range(
        pd.Timestamp(start_ny, tz="America/New_York"), periods=len(data), freq="15min"
    )
    ts = ts.tz_convert("UTC")
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


def level(entry: pd.DataFrame) -> Level:
    t = entry["ts_utc"].iloc[0]
    return Level(100.0, "low", "pd", t - pd.Timedelta(days=1), t, t.date())


SWEEP = [(100.5, 101.0, 99.5, 100.8)]  # 0.5 below the level and back: a sweep in v1


def test_rule_sets_load_and_unknown_ones_are_refused() -> None:
    assert (V1.rule_set, V1.break_is_gap, V1.sweep_session) == ("v1", False, None)
    assert (V5.rule_set, V5.break_is_gap, V5.sweep_session, V5.skip_us_holidays) == (
        "V5-S",
        True,
        ("02:00", "16:00"),
        True,
    )
    assert V5.k_entry == V1.k_entry and V5.min_depth_atr == V1.min_depth_atr
    with pytest.raises(KeyError):
        strategy("nope")


@pytest.mark.parametrize(
    "start_ny, allowed",
    [
        # the sweep bar is the 21st bar, 5 h after the start
        ("2024-01-16 04:00", True),  # 09:00 New York, Tuesday
        ("2024-01-16 10:45", True),  # 15:45: the last bar inside 02:00-16:00
        ("2024-01-16 11:00", False),  # 16:00: the window has ended
        ("2024-01-16 14:00", False),  # 19:00: evening session
        ("2024-01-13 21:00", False),  # Sunday 02:00: not a weekday
        ("2024-07-03 04:00", False),  # 09:00 on 2024-07-03, in the US holiday calendar
    ],
)
def test_a_sweep_counts_only_in_the_session_window(start_ny: str, allowed: bool) -> None:
    entry = ny_bars(start_ny, SWEEP)
    (s,) = detect_sweeps(entry, [level(entry)], V5)
    assert s.kind == ("sweep" if allowed else "off_session")
    (v1,) = detect_sweeps(entry, [level(entry)], V1)
    assert v1.kind == "sweep"  # v1 is unchanged


def test_the_first_bar_after_a_gap_is_not_a_sweep_bar() -> None:
    entry = ny_bars("2024-01-16 04:00", SWEEP)
    entry.loc[20:, ["ts_utc", "close_utc"]] += pd.Timedelta(hours=1)  # a hole before the sweep
    after_gap = Side.of(entry, "buy").after_gap
    assert after_gap[0] and after_gap[20] and not after_gap[1:20].any()
    assert not sweep_allowed(entry, after_gap, V5)[20]
    (s,) = detect_sweeps(entry, [level(entry)], V5)
    assert s.kind == "off_session"


def test_the_first_bar_after_a_gap_cannot_be_the_choch_reference() -> None:
    rows = [
        (101, 102, 100.5, 101.5),
        (101.5, 103, 101, 102.5),
        (102.5, 103.5, 102, 103),  # swing high 103.5 at index 22
        (103, 103.2, 101.5, 102),
        (102, 102.5, 100.8, 101),
        (101, 101.2, 99.4, 100.4),  # sweep of 100 at index 25
        (100.4, 102, 100.2, 101.8),
        (101.8, 104.2, 101.6, 104),  # close above 103.5 at index 27
    ]
    entry = ny_bars("2024-01-16 04:00", rows)
    lv = level(entry)
    (s,) = [x for x in detect_sweeps(entry, [lv], V1) if x.kind == "sweep"]
    side = Side.of(entry, "buy")
    ch, _ = find_choch(side, s, 2, 8)
    assert ch.ref_idx == 22
    gapped = entry.copy()
    gapped.loc[22:, ["ts_utc", "close_utc"]] += pd.Timedelta(hours=1)  # bar 22 opens after a gap
    side = Side.of(gapped, "buy")
    ch, why = find_choch(side, s, 2, 8, no_swing_after_gap=True)
    assert ch is None or ch.ref_idx != 22


def test_development_frames_drop_gold_daily_break_bars_for_v5(tmp_path) -> None:
    ts = pd.date_range("2016-03-01 21:00", periods=12, freq="15min", tz="UTC")  # 16:00-18:45 NY
    f = pd.DataFrame(
        {
            "ts_utc": ts,
            "close_utc": ts + pd.Timedelta("15min"),
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
        }
    )
    (tmp_path / "XAUUSD").mkdir()
    for tf in ("15m", "1h", "4h", "D1"):
        f.to_parquet(tmp_path / "XAUUSD" / f"{tf}.parquet", index=False)
    v1 = detector.development_frames("XAUUSD", tmp_path, V1)["15m"]
    v5 = detector.development_frames("XAUUSD", tmp_path, V5)["15m"]
    assert len(v1) == 12 and len(v5) == 8  # the four bars of 17:00-17:45 New York are removed
    ny = v5["ts_utc"].dt.tz_convert("America/New_York")
    assert not (ny.dt.hour == 17).any()
