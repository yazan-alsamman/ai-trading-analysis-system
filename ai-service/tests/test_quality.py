import json

import numpy as np
import pandas as pd
import pytest

from app.config import instruments
from app.data import quality
from app.data.sessions import is_open

XAU = instruments()["XAUUSD"]
NY = "America/New_York"


def _ny(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=NY).tz_convert("UTC")


def session_bars(start_ny: str, end_ny: str, seed: int = 0) -> pd.DataFrame:
    """Clean M1 bars over every configured XAUUSD trading minute between the two NY times."""
    grid = pd.date_range(_ny(start_ny), _ny(end_ny), freq="1min", inclusive="left")
    ts = grid[is_open(grid, XAU)]
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 0.05, len(ts)))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "ts_utc": ts.as_unit("ns"),
            "open": open_,
            "high": np.maximum(open_, close) + 0.05,
            "low": np.minimum(open_, close) - 0.05,
            "close": close,
            "tick_volume": pd.array(np.full(len(ts), 10), dtype="Int64"),
            "spread": np.full(len(ts), 0.25),
        }
    )


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> dict:
    # 2023-10-29 .. 2023-11-11: includes the US/EU DST mismatch week and NFP on Fri 2023-11-03.
    m1 = session_bars("2023-10-29 18:00", "2023-11-10 17:00")
    ts = m1["ts_utc"]
    hole = (ts >= _ny("2023-11-07 10:00")) & (ts < _ny("2023-11-07 10:30"))  # mid-session
    late = (ts >= _ny("2023-11-05 18:00")) & (ts < _ny("2023-11-05 19:00"))  # late weekly open
    m1 = m1[~(hole | late)].reset_index(drop=True)
    saturday = m1.iloc[[-1]].assign(ts_utc=_ny("2023-11-11 10:00"))  # a bar in closed hours
    m1 = pd.concat([m1, saturday], ignore_index=True)
    nfp = m1["ts_utc"] == _ny("2023-11-03 08:30")
    m1.loc[nfp, "high"] += 5.0  # the jobs-report spike, also a range jump
    jump = m1.index[m1["ts_utc"] == _ny("2023-11-08 11:00")][0]
    m1.loc[jump:, ["open", "high", "low", "close"]] += 30.0  # a one-minute price jump

    store = tmp_path_factory.mktemp("store")
    (store / "XAUUSD").mkdir()
    m1.to_parquet(store / "XAUUSD" / "m1.parquet", index=False)
    imported = {
        "input": {
            "file": "x.csv",
            "bytes_read": 1,
            "sha256_of_bytes_read": "0",
            "stopped_at_lockbox": True,
        },
        "parse": {"rejected_by_reason": {}},
        "frames": {"m1": {"content_sha256": "0"}},
    }
    (store / "XAUUSD" / "import.json").write_text(json.dumps(imported), encoding="utf-8")
    out = tmp_path_factory.mktemp("out")
    assert quality.main(["--store", str(store), "--out", str(out)]) == 0
    assert (out / "XAUUSD.md").read_text(encoding="utf-8").startswith("# Data quality: XAUUSD")
    return json.loads((out / "XAUUSD.json").read_text(encoding="utf-8"))


def test_missing_minutes_are_classed(report: dict) -> None:
    g = report["gaps"]["by_class"]
    assert g["mid_session"] == {"runs": 1, "minutes": 30}
    assert g["session_edge"] == {"runs": 1, "minutes": 60}
    assert report["gaps"]["longest_mid_session"][0]["start_ny"] == "2023-11-07 10:00"


def test_bars_in_closed_hours_are_counted(report: dict) -> None:
    assert report["closed_hour_bars"]["bars"] == 1
    assert report["closed_hour_bars"]["top_ny_slots"] == {"Sat 10:00": 1}


def test_week_boundaries(report: dict) -> None:
    # The data starts on a Sunday, so the only week open seen is the late one (planted at 19:00).
    assert report["week_boundaries"]["first_bar_ny"]["2023"] == "Sun 19:00"
    assert report["week_boundaries"]["last_bar_ny"]["2023"] == "Fri 16:59"


def test_jumps_are_flagged(report: dict) -> None:
    assert report["jumps"]["return"]["top"][0]["ts_ny"] == "2023-11-08 11:00"
    assert "2023-11-03 08:30" in [x["ts_ny"] for x in report["jumps"]["range"]["top"]]


def test_clock_check_sees_the_jobs_report_in_a_dst_mismatch_week(report: dict) -> None:
    c = report["clock_check"]
    assert (c["days"], c["peak_at_0830_share"]) == (1, 1.0)
    assert (c["dst_mismatch_days"], c["dst_mismatch_peak_at_0830"]) == (1, 1)


def test_spread_by_year(report: dict) -> None:
    y = report["spread"]["by_year"]["2023"]
    assert (y["median"], y["zero_share"], y["missing_share"]) == (0.25, 0.0, 0.0)
