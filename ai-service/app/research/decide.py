"""The decision functions of docs/strategies/PREREG.md, sections 8-10, as pure functions of trade
values: blocks, the block bootstrap, the two tests, Holm, the classification, the status, delta*,
the power statements and the family C selection. Nothing here reads data or outcomes; callers
pass arrays. Seeds and B are arguments (fixed at approval).

* **Blocks:** calendar blocks of ``weeks`` weeks from Monday 2018-01-01, the same for every
  instrument; a trade belongs to the block of its entry time (UTC).
* **Bootstrap:** the K non-empty blocks drawn with replacement, B times; each resample gives the
  trade-weighted means of x and d from the same draws.
* **T1 (percentile):** p1 = (1 + #{c* <= 0}) / (B + 1). **T2 (Wald, bootstrap SE):**
  p2 = 1 - F_(K-1)(mean(c) / sd(c*)). p_S = max(p1_x, p2_x, p1_d, p2_d) (intersection-union).
* **Method condition:** K >= 30, else p = 1 and inconclusive.
* **Holm** within a family, one-sided alpha 0.05.
* **Unvalidated:** not passed and U_S = max(q95(x*), mean(x) + t_(K-1, 0.95) sd(x*)) < delta*_S.
* **Status:** validated (family A passed, consistent on the holdout), exploratory (family B passed,
  consistent on the holdout), inconclusive, unvalidated.
* **Family C:** each bundle's outcome on an entry is its own (exit time, net R); training trades
  need every bundle's outcome known by the window start, test trades are the fixed entry set in
  the window, excluded only when the M0 or the chosen bundle's outcome is unresolved."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

ORIGIN = pd.Timestamp("2018-01-01", tz="UTC")  # a Monday
ALPHA = 0.05
MIN_BLOCKS = 30
DELTA_FLOOR = 0.05  # R: an economic judgement (0.05% of equity per trade at 1% risk)
Z_POWER = stats.norm.ppf(0.8)


def block_ids(entry_utc: pd.Series | pd.DatetimeIndex, weeks: int = 4) -> np.ndarray:
    """The calendar block of each entry time: ``weeks``-week steps from ``ORIGIN``."""
    t = pd.DatetimeIndex(entry_utc).tz_convert("UTC")
    return np.floor((t - ORIGIN) / pd.Timedelta(weeks=weeks)).astype("int64").to_numpy()


def bootstrap(
    values: list[np.ndarray], blocks: np.ndarray, boot: int, rng: np.random.Generator
) -> tuple[list[np.ndarray], int]:
    """Trade-weighted resample means of each array in ``values`` (same draws for all) and K."""
    ids, inv = np.unique(blocks, return_inverse=True)
    k = len(ids)
    counts = np.bincount(inv, minlength=k).astype(float)
    sums = [np.bincount(inv, weights=np.asarray(v, float), minlength=k) for v in values]
    draws = rng.integers(0, k, size=(boot, k))
    n = counts[draws].sum(axis=1)
    return [s[draws].sum(axis=1) / n for s in sums], k


def p_percentile(star: np.ndarray) -> float:
    return float((1 + np.count_nonzero(star <= 0)) / (len(star) + 1))


def p_wald(mean: float, star: np.ndarray, k: int) -> float:
    sd = float(np.std(star, ddof=1))
    if sd == 0:
        return 0.0 if mean > 0 else 1.0
    return float(stats.t.sf(mean / sd, k - 1))


@dataclass(frozen=True)
class StrategyTest:
    n: int
    k: int
    method_ok: bool
    mean_x: float
    mean_d: float
    p1_x: float
    p2_x: float
    p1_d: float
    p2_d: float
    p: float  # p_S, 1 when the method condition fails
    upper: float  # U_S
    ci_x: tuple[float, float]  # two-sided 95% percentile intervals (reported, not decided on)
    ci_d: tuple[float, float]


def strategy_test(
    x: np.ndarray,
    d: np.ndarray,
    entry_utc: pd.Series | pd.DatetimeIndex,
    boot: int,
    seed: int,
    weeks: int = 4,
) -> StrategyTest:
    """Section 8 for one strategy: x = net R, d = x - e (its matched E0 mean)."""
    x, d = np.asarray(x, float), np.asarray(d, float)
    blocks = block_ids(entry_utc, weeks)
    (xs, ds), k = bootstrap([x, d], blocks, boot, np.random.default_rng(seed))
    mx, md = float(x.mean()), float(d.mean())
    p1x, p2x, p1d, p2d = p_percentile(xs), p_wald(mx, xs, k), p_percentile(ds), p_wald(md, ds, k)
    ok = k >= MIN_BLOCKS
    upper = max(
        float(np.quantile(xs, 0.95)),
        mx + float(stats.t.ppf(0.95, k - 1)) * float(np.std(xs, ddof=1)),
    )
    return StrategyTest(
        n=len(x),
        k=k,
        method_ok=ok,
        mean_x=mx,
        mean_d=md,
        p1_x=p1x,
        p2_x=p2x,
        p1_d=p1d,
        p2_d=p2d,
        p=max(p1x, p2x, p1d, p2d) if ok else 1.0,
        upper=upper,
        ci_x=(float(np.quantile(xs, 0.025)), float(np.quantile(xs, 0.975))),
        ci_d=(float(np.quantile(ds, 0.025)), float(np.quantile(ds, 0.975))),
    )


def paired_test(
    delta: np.ndarray,
    entry_utc: pd.Series | pd.DatetimeIndex,
    boot: int,
    seed: int,
    weeks: int = 4,
) -> tuple[float, int]:
    """Families C and D: one component, p = max(p1, p2); 1 when the method condition fails.
    Returns (p, K)."""
    delta = np.asarray(delta, float)
    (ds,), k = bootstrap([delta], block_ids(entry_utc, weeks), boot, np.random.default_rng(seed))
    if k < MIN_BLOCKS:
        return 1.0, k
    m = float(delta.mean())
    return max(p_percentile(ds), p_wald(m, ds, k)), k


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-adjusted p-values: p_(j) = max over k <= j of min(1, (m - k + 1) p_(k))."""
    order = sorted(pvalues, key=lambda h: (pvalues[h], h))
    m = len(order)
    out, running = {}, 0.0
    for i, h in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[h]))
        out[h] = running
    return out


def classify(adjusted_p: float, method_ok: bool, upper: float, delta: float) -> str:
    """``passed``, ``unvalidated`` or ``inconclusive`` (section 8)."""
    if method_ok and adjusted_p <= ALPHA:
        return "passed"
    if method_ok and upper < delta:
        return "unvalidated"
    return "inconclusive"


def status(family: str, result: str, holdout_consistent: bool | None) -> str:
    """The status served with every signal (section 10). A passed strategy needs its holdout
    check first."""
    if result != "passed":
        return result
    if holdout_consistent is None:
        raise ValueError("a passed strategy is classified only after its holdout check")
    if not holdout_consistent:
        return "inconclusive"
    return {"A": "validated", "B": "exploratory"}[family]


def holdout_consistent(x: np.ndarray, d: np.ndarray) -> bool:
    return bool(np.mean(x) > 0 and np.mean(d) > 0)


def assumed_cost_r(
    spread: np.ndarray,
    risk: np.ndarray,
    extra_frac: float,
    extra_min: float,
    sl_slippage: float,
    swap_h: np.ndarray,
) -> np.ndarray:
    """The assumed part of the cost model per signal, in R: the extra term, the SL slippage
    (counted on every trade) and max(0, -s_h). The recorded spread is excluded."""
    spread, risk = np.asarray(spread, float), np.asarray(risk, float)
    extra = np.maximum(extra_frac * spread, extra_min)
    return (extra + sl_slippage) / risk + np.maximum(0.0, -np.asarray(swap_h, float))


def delta_star(assumed: np.ndarray, floor: float = DELTA_FLOOR) -> float:
    """delta*_S = max(floor, a_S), a_S the median assumed cost in R."""
    return max(floor, float(np.median(assumed)))


def mde(n: int, sigma: float, de: float, a: float, power: float = 0.8) -> float:
    """MDE(n) = (z_(1-a) + z_power) sigma DE / sqrt(n)."""
    return float((stats.norm.ppf(1 - a) + stats.norm.ppf(power)) * sigma * de / np.sqrt(n))


def n_unval(delta: float, sigma: float, de: float, a: float = ALPHA, power: float = 0.8) -> int:
    """The count at which a zero-edge strategy reaches "unvalidated" with probability ``power``:
    U ~ mean + z_(1-a) SE < delta with P = power when SE = delta / (z_(1-a) + z_power)."""
    z = stats.norm.ppf(1 - a) + stats.norm.ppf(power)
    return int(np.ceil((z * sigma * de / delta) ** 2))


def exit_col(bundle: str) -> str:
    return f"exit_utc_{bundle}"


def r_col(bundle: str) -> str:
    return f"net_r_{bundle}"


def _need(trades: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in trades]
    if missing:
        raise KeyError(f"family C trades lack the columns {missing}")


def training(
    trades: pd.DataFrame, bundles: list[str], window_start: pd.Timestamp, embargo_days: int = 1
) -> pd.Series:
    """Family C training trades of one test window: entry before the window start and, under
    **every** bundle, a resolved outcome whose own exit + embargo is at or before it, so every
    bundle's net R is known by the window start and all bundles are compared on the same trades.
    A trade unresolved, or still open at the window start, under any bundle is left out. Only
    training membership reads the other bundles' exits; test trades never do (``window_trades``).
    """
    _need(trades, [c for b in bundles for c in (exit_col(b), r_col(b))])
    embargo = pd.Timedelta(days=embargo_days)
    ok = trades["entry_utc"] < window_start
    for b in bundles:
        ex = trades[exit_col(b)]
        ok &= ex.notna() & trades[r_col(b)].notna() & (ex + embargo <= window_start)
    return ok


def select_bundle(
    trades: pd.DataFrame,
    bundles: list[str],
    window_start: pd.Timestamp,
    embargo_days: int = 1,
    min_trades: int = 100,
) -> str:
    """Family C selection for one test window: the bundle with the highest mean net R over the
    training trades (``training``); ties to the lower index; fewer than ``min_trades`` training
    trades: the first bundle (M0). ``trades`` has ``entry_utc`` and, per bundle b, its own
    ``exit_utc_<b>`` and ``net_r_<b>`` from that bundle's own management of the entry (NaT / NaN
    when unresolved)."""
    train = trades[training(trades, bundles, window_start, embargo_days)]
    if len(train) < min_trades:
        return bundles[0]
    means = [train[r_col(b)].mean() for b in bundles]
    return bundles[int(np.argmax(means))]  # argmax returns the first of equal maxima


def window_trades(
    trades: pd.DataFrame,
    window: tuple[pd.Timestamp, pd.Timestamp],
    chosen: str,
    base: str = "M0",
) -> tuple[pd.DataFrame, int]:
    """Family C test trades of the window ``[start, end)``: every trade of the fixed entry set with
    entry in it, with delta = net R under the chosen bundle - net R under M0. A trade is excluded,
    and counted, only when its M0 or chosen-bundle outcome is unresolved (NaN) at the load limit;
    the columns of the other bundles are never read. Returns the trades (``entry_utc``,
    ``delta``) and the number excluded."""
    _need(trades, [r_col(base), r_col(chosen)])
    start, end = window
    inw = trades[(trades["entry_utc"] >= start) & (trades["entry_utc"] < end)]
    r0, rc = inw[r_col(base)], inw[r_col(chosen)]
    ok = r0.notna() & rc.notna()
    out = pd.DataFrame({"entry_utc": inw["entry_utc"][ok], "delta": (rc - r0)[ok]})
    return out.reset_index(drop=True), int((~ok).sum())
