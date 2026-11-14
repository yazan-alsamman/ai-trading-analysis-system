"""The 24 level families of ``docs/levels/SPEC.md`` §2, from closed bars only.

Two shapes:

- **Lattice** (the grids): at 5m bar i the levels are origin[i] + k x step[i] for every integer k,
  in price, or in log price for the percent grids. NaN origin: no levels at that bar.
- **Discrete** (the real families): records (level, start, end): the level is live on the 5m bars
  start <= i < end. start is the first 5m bar opening at or after the moment the level is known."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.research import gold_lab as gl

B_ATR, TAU_ATR = 0.25, 0.05  # SPEC §3 (D5)
LIFE_DAYS = 5  # SPEC §2.1 (D2)
SWING_K = 3
FVG_MIN = 0.1
LIQ_TOL = 0.1
RND_STEPS = (10.0, 25.0, 50.0, 100.0)
PCT_STEPS = (0.0025, 0.005, 0.01)
PCT_REF = 1000.0
ANC_MULTS = (0.5, 1.0)
ASIA, LONDON_FROM, LONDON_TO, NY_OPEN = (19 * 60, 2 * 60), 2 * 60, 7 * 60, 9 * 60 + 30


@dataclass
class Lattice:
    name: str
    kind: str  # "round", "percent", "anchored"
    origin: np.ndarray
    step: np.ndarray
    log: bool = False


@dataclass
class Discrete:
    name: str
    recs: pd.DataFrame  # level, start, end
    kind: str = "real"


# --- helpers --------------------------------------------------------------------------------------


def day_bounds(cx: gl.Ctx) -> tuple[np.ndarray, np.ndarray]:
    """First and one-past-last 5m bar of each D1 bar (trading day); -1 / -1 when it has none."""
    n = max(len(cx.d1), int(cx.day_idx.max()) + 1 if len(cx.day_idx) else 0)
    first, end = np.full(n, -1), np.full(n, -1)
    ok = (cx.day_idx >= 0) & (cx.day_idx < n)
    idx = np.arange(len(cx.c))[ok]
    d = cx.day_idx[ok]
    g = pd.Series(idx).groupby(d)
    first[g.min().index.to_numpy()] = g.min().to_numpy()
    end[g.max().index.to_numpy()] = g.max().to_numpy() + 1
    return first, end


def b_of(cx: gl.Ctx) -> np.ndarray:
    return B_ATR * cx.atr5


def bar_at(cx: gl.Ctx, when: np.ndarray) -> np.ndarray:
    """The first 5m bar opening at or after each time (datetime64[ns] UTC, naive)."""
    t = cx.m["ts_utc"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")
    return np.searchsorted(t, when, "left")


def expiry(cx: gl.Ctx, start: np.ndarray) -> np.ndarray:
    """One past the last bar of the 5th trading day after the start bar's day."""
    first, end = day_bounds(cx)
    d = cx.day_idx[np.minimum(start, len(cx.c) - 1)] + LIFE_DAYS
    d = np.minimum(d, len(end) - 1)
    out = end[d]
    return np.where(out > 0, out, len(cx.c))


def first_close_beyond(cx: gl.Ctx, level: float, side: int, a: int, b: int,
                       bb: np.ndarray | None = None) -> int:  # fmt: skip
    """The first bar in [a, b) whose close is beyond ``level`` by b (side +1: above), else b.
    ``bb``: b per bar, precomputed (``b_of``) when called in a loop."""
    if b <= a:
        return b
    x = cx.c[a:b] - level if side > 0 else level - cx.c[a:b]
    hit = x > (b_of(cx) if bb is None else bb)[a:b]
    k = int(np.argmax(hit))
    return a + k if hit[k] else b


def _recs(level, start, end) -> pd.DataFrame:
    r = pd.DataFrame(
        {
            "level": np.asarray(level, float),
            "start": np.asarray(start, int),
            "end": np.asarray(end, int),
        }
    )
    r = r[np.isfinite(r["level"]) & (r["end"] > r["start"]) & (r["start"] >= 0)]
    return r.sort_values("start", kind="stable").reset_index(drop=True)


# --- grids ----------------------------------------------------------------------------------------


def rnd(cx: gl.Ctx, d: float) -> Lattice:
    n = len(cx.c)
    return Lattice(f"RND-{d:g}", "round", np.zeros(n), np.full(n, d))


def pct(cx: gl.Ctx, p: float) -> Lattice:
    n = len(cx.c)
    return Lattice(
        f"PCT-{p * 100:g}",
        "percent",
        np.full(n, np.log(PCT_REF)),
        np.full(n, np.log1p(p)),
        log=True,
    )


def anc(cx: gl.Ctx, anchor: str, mult: float) -> Lattice:
    """The day's open (18:00 New York) or the New York open (09:30) +/- k x mult x the previous
    day's ATR(14, D1); levels from the anchor bar to the day's end."""
    first, end = day_bounds(cx)
    n = len(cx.c)
    origin = np.full(n, np.nan)
    for d in range(len(first)):
        a, e = first[d], end[d]
        if a < 0:
            continue
        if anchor == "NY":
            k = np.flatnonzero(cx.ny_min[a:e] == NY_OPEN)
            if not len(k):
                continue
            a = a + int(k[0])
        origin[a:e] = cx.o[a]
    return Lattice(f"ANC-{anchor}-{mult:g}", "anchored", origin, mult * cx.atrd)


def grids(cx: gl.Ctx, with_round: bool = True) -> list[Lattice]:
    out = [rnd(cx, d) for d in RND_STEPS] if with_round else []
    out += [pct(cx, p) for p in PCT_STEPS]
    out += [anc(cx, a, m) for a in ("D", "NY") for m in ANC_MULTS]
    return out


# --- real families: day and week ------------------------------------------------------------------


def _per_day(
    cx: gl.Ctx, values: dict[str, np.ndarray], from_min: int | None = None
) -> pd.DataFrame:
    """Levels per trading day (arrays by D1 bar), live from the day's first bar (or its first bar
    at New York minute ``from_min``) to the day's end."""
    first, end = day_bounds(cx)
    lv, st, en = [], [], []
    for d in range(len(first)):
        a, e = first[d], end[d]
        if a < 0:
            continue
        if from_min is not None:
            k = np.flatnonzero((cx.ny_min[a:e] >= from_min) & (cx.ny_min[a:e] < 17 * 60))
            if not len(k):
                continue
            a = a + int(k[0])
        for v in values.values():
            if np.isfinite(v[d]):
                lv.append(v[d])
                st.append(a)
                en.append(e)
    return _recs(lv, st, en)


def projected(h: np.ndarray, lo: np.ndarray, **levels: np.ndarray) -> dict[str, np.ndarray]:
    """A range's levels with its projections (SPEC addendum 1): high + 1 and 2 ranges, low - 1
    and 2 ranges."""
    r = h - lo
    return {**levels, "H+1": h + r, "H+2": h + 2 * r, "L-1": lo - r, "L-2": lo - 2 * r}


def prev_day(cx: gl.Ctx) -> Discrete:
    h, lo, c = (np.r_[np.nan, cx.d1[k].to_numpy()[:-1]] for k in ("high", "low", "close"))
    return Discrete("PREV-D", _per_day(cx, projected(h, lo, H=h, L=lo, C=c)))


def prev_week(cx: gl.Ctx) -> Discrete:
    wk = cx.d1["close_utc"].dt.tz_convert(gl.NY).dt.tz_localize(None).dt.to_period("W-SUN")
    g = cx.d1.groupby(wk.to_numpy())
    h, lo, c = g["high"].max().shift(1), g["low"].min().shift(1), g["close"].last().shift(1)
    key = wk.to_numpy()
    return Discrete(
        "PREV-W",
        _per_day(
            cx,
            projected(
                h.reindex(key).to_numpy(),
                lo.reindex(key).to_numpy(),
                H=h.reindex(key).to_numpy(),
                L=lo.reindex(key).to_numpy(),
                C=c.reindex(key).to_numpy(),
            ),
        ),
    )


def pivots(cx: gl.Ctx) -> Discrete:
    h, lo, c = (np.r_[np.nan, cx.d1[k].to_numpy()[:-1]] for k in ("high", "low", "close"))
    p = (h + lo + c) / 3
    rng = h - lo
    lv = {
        "P": p,
        "R1": 2 * p - lo,
        "S1": 2 * p - h,
        "R2": p + rng,
        "S2": p - rng,
        "R3": h + 2 * (p - lo),
        "S3": lo - 2 * (h - p),
    }
    return Discrete("PIVOT", _per_day(cx, lv))


def fib(cx: gl.Ctx) -> Discrete:
    h, lo = (np.r_[np.nan, cx.d1[k].to_numpy()[:-1]] for k in ("high", "low"))
    fibs = {f"F{r}": lo + r * (h - lo) for r in (0.0, 0.382, 0.5, 0.618, 1.0)}
    return Discrete("FIB", _per_day(cx, projected(h, lo, **fibs)))


def _session(cx: gl.Ctx, inside: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    k = cx.day_idx[inside]
    n = len(cx.d1)
    hi, lo = np.full(n, np.nan), np.full(n, np.nan)
    gh = pd.Series(cx.h[inside]).groupby(k).max()
    gl_ = pd.Series(cx.lo[inside]).groupby(k).min()
    ok = (gh.index >= 0) & (gh.index < n)
    hi[gh.index[ok]] = gh.to_numpy()[ok]
    lo[gl_.index[ok]] = gl_.to_numpy()[ok]
    return hi, lo


def sess_asia(cx: gl.Ctx) -> Discrete:
    inside = (cx.ny_min >= ASIA[0]) | (cx.ny_min < ASIA[1])
    hi, lo = _session(cx, inside)
    return Discrete("SESS-A", _per_day(cx, projected(hi, lo, H=hi, L=lo), from_min=ASIA[1]))


def sess_london(cx: gl.Ctx) -> Discrete:
    inside = (cx.ny_min >= LONDON_FROM) & (cx.ny_min < LONDON_TO)
    hi, lo = _session(cx, inside)
    return Discrete("SESS-L", _per_day(cx, projected(hi, lo, H=hi, L=lo), from_min=LONDON_TO))


# --- real families: swings, liquidity, FVG --------------------------------------------------------


def _naive(s: pd.Series) -> np.ndarray:
    return s.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")


def swing_points(frame: pd.DataFrame, k: int = SWING_K) -> pd.DataFrame:
    """Swing highs (side +1) and lows (-1): beyond every one of the k bars on each side; known at
    the close of the k-th bar after."""
    h, lo = frame["high"].to_numpy(), frame["low"].to_numpy()
    close = _naive(frame["close_utc"])
    rows = []
    for j in range(k, len(h) - k):
        if h[j] > max(h[j - k : j].max(), h[j + 1 : j + k + 1].max()):
            rows.append((h[j], 1, close[j + k], j))
        if lo[j] < min(lo[j - k : j].min(), lo[j + 1 : j + k + 1].min()):
            rows.append((lo[j], -1, close[j + k], j))
    return pd.DataFrame(rows, columns=["level", "side", "known", "j"])


def _ends(cx: gl.Ctx, pts: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Per point (side = the direction of the close that breaks it): its first live bar and one
    past its last (a close beyond it by b ends it after that bar; else 5 trading days)."""
    if pts.empty:
        return pts, np.array([], int), np.array([], int)
    start = bar_at(cx, pts["known"].to_numpy("datetime64[ns]"))
    keep = start < len(cx.c)
    pts, start = pts[keep].reset_index(drop=True), start[keep]
    exp = expiry(cx, start)
    bb = b_of(cx)
    end = np.empty(len(pts), int)
    for q, (lv, side, a, b) in enumerate(zip(pts["level"], pts["side"], start, exp, strict=True)):
        k = first_close_beyond(cx, lv, side, a, b, bb)
        end[q] = k + 1 if k < b else b
    return pts, start, end


def swings(cx: gl.Ctx, frame: pd.DataFrame, name: str) -> Discrete:
    pts, start, end = _ends(cx, swing_points(frame))
    return Discrete(name, _recs(pts["level"].to_numpy(), start, end))


def liquidity(cx: gl.Ctx, h1: pd.DataFrame) -> Discrete:
    """Equal highs / lows: a 1h swing point within 0.1 x ATR(14, 1h) of an earlier one of the
    same side still live when it is confirmed; the level is the outer of the two."""
    pts, start, end = _ends(cx, swing_points(h1))
    atr = gl.wilder(*(h1[k].to_numpy() for k in ("high", "low", "close")))
    lv, sd, j = pts["level"].to_numpy(), pts["side"].to_numpy(), pts["j"].to_numpy()
    rows = []
    for side in (1, -1):
        idx = np.flatnonzero(sd == side)
        for q, a in enumerate(idx):
            for b_ in idx[max(0, q - 30) : q][::-1]:
                if start[b_] <= start[a] < end[b_] and abs(lv[a] - lv[b_]) <= LIQ_TOL * atr[j[a]]:
                    out = max(lv[a], lv[b_]) if side > 0 else min(lv[a], lv[b_])
                    rows.append((out, side, pts["known"].iloc[a], j[a]))
                    break
    liq, s2, e2 = _ends(cx, pd.DataFrame(rows, columns=["level", "side", "known", "j"]))
    return Discrete("LIQ", _recs(liq["level"].to_numpy() if len(liq) else [], s2, e2))


def fvg_points(frame: pd.DataFrame) -> pd.DataFrame:
    """Proximal edges: bullish (low of bar j above the high of j-2; the edge is low[j], price above
    it: side -1, broken by a close below) and bearish (mirrored, side +1); gap >= 0.1 x ATR."""
    h, lo, c = (frame[k].to_numpy() for k in ("high", "low", "close"))
    atr = gl.wilder(h, lo, c)
    close = _naive(frame["close_utc"])
    rows = []
    for j in range(2, len(h)):
        if lo[j] - h[j - 2] >= FVG_MIN * atr[j]:
            rows.append((lo[j], -1, close[j], j))
        if lo[j - 2] - h[j] >= FVG_MIN * atr[j]:
            rows.append((h[j], 1, close[j], j))
    return pd.DataFrame(rows, columns=["level", "side", "known", "j"])


def fvg_and_ifvg(cx: gl.Ctx, frame: pd.DataFrame, tf: str) -> tuple[Discrete, Discrete]:
    """FVG edges live until a close through them by b (then an IFVG from the next bar for 5
    trading days) or 5 trading days."""
    pts, start, end = _ends(cx, fvg_points(frame))
    lv = pts["level"].to_numpy() if len(pts) else np.array([])
    exp = expiry(cx, start) if len(start) else start
    broke = end < exp  # ended by a close through it, not by age
    i_st = end[broke]
    i_end = expiry(cx, np.minimum(i_st, len(cx.c) - 1)) if len(i_st) else i_st
    return (
        Discrete(f"FVG-{tf}", _recs(lv, start, end)),
        Discrete(f"IFVG-{tf}", _recs(lv[broke], i_st, i_end)),
    )


OB_DISP_ATR = 1.0  # ORDER_BLOCKS.md §1
OB_SPANS = (2, 3)


def last_confirmed(frame: pd.DataFrame, k: int = SWING_K) -> tuple[np.ndarray, np.ndarray]:
    """Per frame bar: the last swing high and swing low confirmed by that bar (NaN before)."""
    n = len(frame)
    sh, sl = np.full(n, np.nan), np.full(n, np.nan)
    pts = swing_points(frame, k)
    for side, out in ((1, sh), (-1, sl)):
        p = pts[pts["side"] == side]
        conf = p["j"].to_numpy() + k
        val = pd.Series(np.nan, index=range(n))
        val.iloc[conf[conf < n]] = p["level"].to_numpy()[conf < n]
        out[:] = val.ffill().to_numpy()
    return sh, sl


def order_block_points(frame: pd.DataFrame) -> pd.DataFrame:
    """Order blocks (ORDER_BLOCKS.md §1): bar j, the last opposite candle before a displacement
    of 2-3 bars that closes >= 1 ATR beyond it, breaks the last confirmed swing and leaves a gap.
    One row per block: proximal and distal edges, side (+1 bullish), known (close of j+m), j."""
    o, h, lo, c = (frame[k].to_numpy() for k in ("open", "high", "low", "close"))
    atr = gl.wilder(h, lo, c)
    close = _naive(frame["close_utc"])
    sh, sl = last_confirmed(frame)
    n = len(c)
    rows = []
    for j in range(n - 2):
        for side in (1, -1):
            if (side > 0 and not c[j] < o[j]) or (side < 0 and not c[j] > o[j]):
                continue
            for m in OB_SPANS:
                t = j + m
                if t >= n:
                    break
                if side > 0:
                    disp = c[t] - h[j] >= OB_DISP_ATR * atr[j]
                    bos = np.isfinite(sh[j]) and c[t] > sh[j]
                    gap = any(lo[q] > h[q - 2] for q in range(j + 2, t + 1))
                else:
                    disp = lo[j] - c[t] >= OB_DISP_ATR * atr[j]
                    bos = np.isfinite(sl[j]) and c[t] < sl[j]
                    gap = any(h[q] < lo[q - 2] for q in range(j + 2, t + 1))
                if disp and bos and gap:
                    prox, dist = (h[j], lo[j]) if side > 0 else (lo[j], h[j])
                    rows.append((prox, dist, side, close[t], j))
                    break
    return pd.DataFrame(rows, columns=["proximal", "distal", "side", "known", "j"])


def order_blocks(cx: gl.Ctx, frame: pd.DataFrame, tf: str) -> Discrete:
    """Both edges of each block, live until a close beyond the distal edge by b or 5 days."""
    ob = order_block_points(frame)
    if ob.empty:
        return Discrete(f"OB-{tf}", _recs([], [], []), kind="ob")
    pts = pd.DataFrame(
        {"level": ob["distal"], "side": -ob["side"], "known": ob["known"], "j": ob["j"]}
    )  # the distal edge breaks against the block's side
    pts2, start, end = _ends(cx, pts)
    keep = bar_at(cx, ob["known"].to_numpy("datetime64[ns]")) < len(cx.c)
    prox = ob["proximal"].to_numpy()[keep]
    lv = np.r_[pts2["level"].to_numpy(), prox]
    return Discrete(f"OB-{tf}", _recs(lv, np.r_[start, start], np.r_[end, end]), kind="ob")


def real(cx: gl.Ctx, fr: dict[str, pd.DataFrame]) -> list[Discrete]:
    out = [
        prev_day(cx),
        prev_week(cx),
        sess_asia(cx),
        sess_london(cx),
        swings(cx, fr["15m"], "SWING-15"),
        swings(cx, fr["1h"], "SWING-1H"),
        liquidity(cx, fr["1h"]),
    ]
    for tf, key in (("15", "15m"), ("1H", "1h")):
        out += list(fvg_and_ifvg(cx, fr[key], tf))
    out += [pivots(cx), fib(cx)]
    return out


def all_families(
    cx: gl.Ctx, fr: dict[str, pd.DataFrame], with_round: bool = True
) -> list[Lattice | Discrete]:
    return [*real(cx, fr), *grids(cx, with_round)]
