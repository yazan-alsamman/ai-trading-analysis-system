"""Gold value area (app/research/gold_vp.py) on hand-built bars."""

import numpy as np
import pytest

from app.research import gold_vp as vp


def test_value_area_holds_70_percent_around_the_poc() -> None:
    # range 100-110; heavy volume between 104 and 106, light elsewhere
    h = np.array([110.0, 106.0, 106.0, 102.0])
    lo = np.array([109.0, 104.0, 104.0, 100.0])
    v = np.array([10.0, 400.0, 400.0, 10.0])
    vah, val = vp.value_area(h, lo, v)
    # 70% of 820 is 574: about 14.4 of the 20 heavy bins (40 each), inside 104-106
    assert 104.0 - 1e-9 <= val < vah <= 106.0 + 1e-9
    assert vah - val == pytest.approx(1.5, abs=0.11)


def test_flat_or_empty_days_have_no_area() -> None:
    assert np.isnan(vp.value_area(np.array([1.0]), np.array([1.0]), np.array([5.0]))[0])
    assert np.isnan(vp.value_area(np.array([2.0]), np.array([1.0]), np.array([0.0]))[0])
