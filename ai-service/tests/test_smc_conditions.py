import dataclasses

import pandas as pd

from app.smc.conditions import CONDITIONS, check
from app.smc.params import FROZEN_V2, FROZEN_V3, StrategyParams
from tests.test_smc_engine import SETUP_BARS, WARMUP, _frame, _scan

AFTER = [
    (101.4, 101.5, 100.5, 100.8),
    (100.8, 100.9, 99.85, 100.3),
    (100.3, 102.1, 100.2, 102.0),
]


def _bars():
    return _frame(WARMUP + SETUP_BARS + AFTER)


def test_engine_setup_passes_every_condition():
    _, s = _scan(AFTER)
    res = check(s, _bars(), StrategyParams())
    assert all(res[c] is True for c in CONDITIONS), res


def test_tampered_setups_fail_the_matching_condition():
    _, s = _scan(AFTER)
    bars, p = _bars(), StrategyParams()
    assert check(dataclasses.replace(s, entry=99.7), bars, p)["plan"] is not True
    assert check(dataclasses.replace(s, ref_idx=21), bars, p)["choch"] is not True
    assert check(dataclasses.replace(s, fvg_idx=24), bars, p)["fvg"] is not True
    late = dataclasses.replace(
        s, level=dataclasses.replace(s.level, available_at=bars["ts_utc"][24])
    )
    assert check(late, bars, p)["level"] is not True


def test_fvg_window_is_enforced():
    _, s = _scan(AFTER)
    p = StrategyParams(fvg_max_bars_before_choch=0)
    moved = dataclasses.replace(s, choch_idx=s.fvg_idx + 1)
    assert "bars before the CHoCH" in str(check(moved, _bars(), p)["fvg"])


def test_bars_are_the_only_input():
    _, s = _scan(AFTER)
    bars = _bars()
    bars.loc[23, "close"] = 98.9  # the sweep bar now closes below the level
    assert check(s, bars, StrategyParams())["sweep"] == "sweep bar did not close back"
    assert isinstance(bars, pd.DataFrame)


def test_frozen_v3_is_v2_with_exactly_the_three_review_changes():
    v2, v3 = dataclasses.asdict(FROZEN_V2), dataclasses.asdict(FROZEN_V3)
    changed = {k: v3[k] for k in v3 if v3[k] != v2[k]}
    assert changed == {"min_fvg_atr": 0.25, "min_sweep_atr": 0.25, "k_ltf": 3}
