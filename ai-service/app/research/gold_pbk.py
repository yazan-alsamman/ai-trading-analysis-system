"""Gold: buy the pullback before the break (PBK) and re-enter a strong move (RTB)
(``docs/strategies/GOLD_PBK.md``, registered 2026-11-10; Fadi's idea).

    python -m app research gold-pbk build       # XAUUSD 2012 to 2026-01-09: tune, check, report

- **PBK.** A 5m swing level (or PDH / PDL) is touched for the first time, price pulls back a
  little without breaking or bouncing far, and the first bar closing back toward the level is the
  entry, in the break's direction.
- **RTB.** After a strong 5m leg (>= 0.75 x ATR(14, D1)), a limit at its 20% or 30% retracement,
  in the leg's direction, SL at its 50% level.

Both: optional 1h + 4h market-structure filter, target 2 R or the next live level, M8 with the
target, 16:45 New York exit. The lockbox is not read."""

from __future__ import annotations

import argparse
import itertools

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_lab as gl
from app.research import gold_night as gn
from app.research import gold_retrace as gr
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_pbk_xauusd.md"  # not gold_pbk.md: GOLD_PBK.md on Windows
TUNE_END = gc.TUNE_END

LEVEL_K, LEVEL_LIFE = 3, 288  # 5m swing levels: bars a side; life in bars
TREND_K = 2  # 1h / 4h swings: bars a side
AWAY, MIN_GAP, NEAR = 1.0, 6, 0.1  # x ATR(5m); bars after the level's bar; touch tolerance
WAIT, PULL, BOUNCE, SL_PAD, MIN_RISK = 12, 0.5, 1.5, 0.1, 1.0
BIG, RS, SL_RTB, FILL_WAIT = 0.75, (0.20, 0.30), 0.5, 24
CAP = 0.10
FROM_MIN, TO_MIN = 2 * 60, 16 * 60  # entries 02:00 to 16:00 New York
TARGETS, FILTERS = ("R2", "LIQ"), ("STRUCT", "NONE")


# --- trend: 1h / 4h market structure ----------------------------------------------------------


def structure(h: np.ndarray, lo: np.ndarray, k: int = TREND_K) -> np.ndarray:
    """Per TF bar t (at its close): +1 when the last two confirmed swing highs and lows both rise,
    -1 when both fall, else 0. A swing at bar b is known at the close of b + k."""
    n = len(h)

    def last_prev(x: np.ndarray, sign: int) -> tuple[np.ndarray, np.ndarray]:
        if n < 2 * k + 1:
            return np.full(n, np.nan), np.full(n, np.nan)
        w = np.lib.stride_tricks.sliding_window_view(sign * x, 2 * k + 1)
        b = np.flatnonzero(w[:, k] == w.max(axis=1)) + k
        b = b[b + k < n]
        last, prev = np.full(n, np.nan), np.full(n, np.nan)
        last[b + k] = x[b]
        prev[b + k] = np.r_[np.nan, x[b][:-1]]
        return pd.Series(last).ffill().to_numpy(), pd.Series(prev).ffill().to_numpy()

    hl, hp = last_prev(h, 1)
    ll, lp = last_prev(lo, -1)
    up = (hl > hp) & (ll > lp)
    down = (hl < hp) & (ll < lp)
    return np.where(up, 1, np.where(down, -1, 0))


def trends(cx: gl.Ctx, fr: dict[str, pd.DataFrame]) -> tuple[np.ndarray, np.ndarray]:
    """The 1h and 4h structure known at each 5m bar's close."""
    out = []
    for tf in ("1h", "4h"):
        f = fr[tf]
        st = structure(f["high"].to_numpy(), f["low"].to_numpy()).astype(float)
        out.append(np.nan_to_num(gl.on_5m(cx.m, f, st)).astype(int))
    return out[0], out[1]


# --- levels -----------------------------------------------------------------------------------


def levels(cx: gl.Ctx, with_days: bool = True) -> pd.DataFrame:
    """Every level: side d (+1 a high, -1 a low), value v, its bar b, the bar it is known
    (known), its last bar (end), the first bar a touch may come (mint) and the first bar from
    ``known`` that closes beyond it (brk; a large number when none)."""
    h, lo, c, n = cx.h, cx.lo, cx.c, len(cx.c)
    k = LEVEL_K
    rows = []
    for d, x in ((1, h), (-1, lo)):
        if n < 2 * k + 1:
            break
        w = np.lib.stride_tricks.sliding_window_view(d * x, 2 * k + 1)
        b = np.flatnonzero(w[:, k] == w.max(axis=1)) + k
        b = b[b + k + 1 < n]
        rows.append(pd.DataFrame({"d": d, "v": x[b], "b": b, "known": b + k + 1,
                                  "end": np.minimum(b + LEVEL_LIFE, n - 1),
                                  "mint": np.maximum(b + MIN_GAP, b + k + 1)}))  # fmt: skip
    if with_days and len(cx.d1):
        dl = gc.day_levels(cx)
        idx = np.arange(n)
        g = pd.DataFrame({"day": cx.day_idx, "i": idx}).groupby("day")["i"].agg(["min", "max"])
        for d, key in ((1, "PDH"), (-1, "PDL")):
            v = dl[key][g.index.to_numpy()]
            ok = np.isfinite(v)
            first, last = g["min"].to_numpy()[ok], g["max"].to_numpy()[ok]
            rows.append(pd.DataFrame({"d": d, "v": v[ok], "b": first, "known": first,
                                      "end": last, "mint": first}))  # fmt: skip
    lv = pd.concat(rows, ignore_index=True)
    brk = np.full(len(lv), np.iinfo(np.int64).max // 4, dtype=np.int64)
    for q, (d, v, a, e) in enumerate(lv[["d", "v", "known", "end"]].itertuples(index=False)):
        seg = d * (c[a : e + 1] - v) > 0
        if seg.any():
            brk[q] = a + int(np.argmax(seg))
    lv["brk"] = brk
    return lv.sort_values(["known", "d"], kind="stable").reset_index(drop=True)


class Liq:
    """The nearest live level beyond a reference price, at a bar."""

    def __init__(self, lv: pd.DataFrame) -> None:
        self.known = lv["known"].to_numpy()
        self.d, self.v = lv["d"].to_numpy(), lv["v"].to_numpy()
        self.end, self.brk = lv["end"].to_numpy(), lv["brk"].to_numpy()

    def target_r(self, d: int, j: int, ref: float, e: float, risk: float) -> float:
        """TP in R: the nearest level of side d live at bar j, beyond ``ref`` and at least 1 R
        from the entry ``e``; inf when none."""
        a = np.searchsorted(self.known, j - LEVEL_LIFE - 12)
        z = np.searchsorted(self.known, j, "right")
        v = self.v[a:z]
        ok = (self.d[a:z] == d) & (self.end[a:z] >= j) & (self.brk[a:z] > j)
        ok &= (d * (v - ref) > 0) & (d * (v - e) >= risk)
        if not ok.any():
            return np.inf
        return float(np.min(d * (v[ok] - e)) / risk)


def in_window(cx: gl.Ctx, j: int) -> bool:
    return cx.weekday[j] < 5 and FROM_MIN <= cx.ny_min[j] < TO_MIN and cx.deadline[j] > j


# --- PBK ------------------------------------------------------------------------------------------


def first_touches(cx: gl.Ctx, lv: pd.DataFrame):
    """Per level with a first touch (§2 rules 1-2): (d, v, t, brk)."""
    h, lo, c, atr = cx.h, cx.lo, cx.c, cx.atr5
    for d, v, b, known, end, mint, brk in lv[
        ["d", "v", "b", "known", "end", "mint", "brk"]
    ].itertuples(index=False):
        a = atr[b]
        if not np.isfinite(a) or a <= 0 or known > end:
            continue
        seg = slice(known, end + 1)
        far = (lo[seg] <= v - AWAY * a) if d > 0 else (h[seg] >= v + AWAY * a)
        if not far.any():
            continue
        start = max(mint, known + int(np.argmax(far)) + 1)
        if start > end:
            continue
        s2 = slice(start, end + 1)
        if d > 0:
            near = (h[s2] >= v - NEAR * atr[s2]) & (c[s2] <= v)
        else:
            near = (lo[s2] <= v + NEAR * atr[s2]) & (c[s2] >= v)
        if not near.any():
            continue
        t = start + int(np.argmax(near))
        if brk <= t:
            continue
        yield int(d), float(v), t, int(brk)


def pbk_candidates(cx: gl.Ctx, lv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Entries (before the trend filter and the target) and, per first touch, whether a pullback
    came and whether the level broke within 24 bars (descriptive)."""
    o, h, lo, c, atr = cx.o, cx.h, cx.lo, cx.c, cx.atr5
    n = len(c)
    ent, touches = [], []
    for d, v, t, brk in first_touches(cx, lv):
        at = atr[t]
        mx, ext = (h[t], c[t]) if d > 0 else (lo[t], c[t])
        pulled, entry = False, -1
        for j in range(t, min(t + WAIT, n - 1) + 1):
            if j > t:
                if d * (c[j] - v) > 0:
                    break
                mx = max(mx, h[j]) if d > 0 else min(mx, lo[j])
                ext = min(ext, lo[j]) if d > 0 else max(ext, h[j])
            if d * (v - ext) > BOUNCE * at:
                break
            if not pulled and d * (mx - ext) >= PULL * at:
                pulled = True
            if pulled and j > t and d * (c[j] - o[j]) > 0:
                entry = j
                break
        touches.append((d, t, pulled, brk <= t + 24))
        if entry < 0 or not in_window(cx, entry):
            continue
        j = entry
        e = float(c[j])
        far_px = lo[t : j + 1].min() if d > 0 else h[t : j + 1].max()
        sl = far_px - d * SL_PAD * at
        sl = min(sl, e - MIN_RISK * at) if d > 0 else max(sl, e + MIN_RISK * at)
        ent.append((j, d, e, d * (e - sl), float(v), t))
    e_cols = ["i", "dir", "entry", "risk", "ref", "touch_bar"]
    return pd.DataFrame(ent, columns=e_cols), pd.DataFrame(
        touches, columns=["dir", "t", "pulled", "broke24"]
    )


# --- PBK-M1 (Addendum 1): entry on M1, fixed $10 SL and TP -------------------------------------

SL_USD = TP_USD = 10.0  # "1000 pips": 1,000 points of $0.01
M1_REPORT = gl.OUT_DIR / "gold_pbk_m1_xauusd.md"
FIVE = np.timedelta64(5, "m")


def _ns(s: pd.Series) -> np.ndarray:
    return s.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")


def pbk_m1_candidates(cx: gl.Ctx, lv: pd.DataFrame, m1: pd.DataFrame) -> pd.DataFrame:
    """Addendum 1 entries: the 5m pullback (§2 rules 1-3, without entering on 5m), then the
    first M1 up close. Columns: k (M1 bar), i (its 5m bar), dir, entry, spread, end (last M1 bar
    of the day's 16:45 exit), ref (the level), touch_bar."""
    h, lo, c, atr = cx.h, cx.lo, cx.c, cx.atr5
    n = len(c)
    ts5, cl5 = _ns(cx.m["ts_utc"]), _ns(cx.m["close_utc"])
    ts1 = _ns(m1["ts_utc"])
    o1, h1, l1, c1 = (m1[k].to_numpy() for k in ("open", "high", "low", "close"))
    sp1 = m1["spread"].to_numpy()
    rows = []
    for d, v, t, _ in first_touches(cx, lv):
        at = atr[t]
        last5 = min(t + WAIT, n - 1)
        mx, ext = (h[t], c[t]) if d > 0 else (lo[t], c[t])
        p = -1
        for j in range(t, last5 + 1):
            if j > t:
                if d * (c[j] - v) > 0:
                    break
                mx = max(mx, h[j]) if d > 0 else min(mx, lo[j])
                ext = min(ext, lo[j]) if d > 0 else max(ext, h[j])
            if d * (v - ext) > BOUNCE * at:
                break
            if d * (mx - ext) >= PULL * at:
                p = j
                break
        if p < 0 or p >= last5:
            continue
        k0 = int(np.searchsorted(ts1, ts5[p] + FIVE))
        k1 = int(np.searchsorted(ts1, ts5[last5] + FIVE))
        entry = -1
        for k in range(k0, k1):
            if d * (c1[k] - v) > 0:
                break
            ext = min(ext, l1[k]) if d > 0 else max(ext, h1[k])
            if d * (v - ext) > BOUNCE * at:
                break
            if d * (c1[k] - o1[k]) > 0:
                entry = k
                break
        if entry < 0:
            continue
        j5 = int(np.searchsorted(ts5, ts1[entry], "right")) - 1
        if j5 < 0 or not in_window(cx, j5):
            continue
        end = int(np.searchsorted(ts1, cl5[cx.deadline[j5]])) - 1
        if end <= entry:
            continue
        rows.append((entry, j5, d, float(c1[entry]), float(sp1[entry]), end, v, t))
    cols = ["k", "i", "dir", "entry", "spread", "end", "ref", "touch_bar"]
    return pd.DataFrame(rows, columns=cols).sort_values("k", kind="stable").reset_index(drop=True)


def simulate_m1(cand: pd.DataFrame, m1: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """Fixed SL / TP on M1 bars, one trade at a time; a bar reaching both is the SL."""
    o1, h1, l1, c1 = (m1[k].to_numpy() for k in ("open", "high", "low", "close"))
    ts1, ts5 = _ns(m1["ts_utc"]), _ns(cx.m["ts_utc"])
    out, busy = [], -1
    for x in cand.itertuples(index=False):
        k, end, s, e = int(x.k), int(x.end), int(x.dir), float(x.entry)
        if k <= busy:
            continue
        sl, tp = e - s * SL_USD, e + s * TP_USD
        exit_px, why, q = c1[end], "time", end
        for q in range(k + 1, end + 1):
            if (l1[q] <= sl) if s > 0 else (h1[q] >= sl):
                gap = (o1[q] < sl) if s > 0 else (o1[q] > sl)
                exit_px, why = (o1[q] if gap else sl), "sl"
                break
            if (h1[q] >= tp) if s > 0 else (l1[q] <= tp):
                gap = (o1[q] > tp) if s > 0 else (o1[q] < tp)
                exit_px, why = (o1[q] if gap else tp), "tp"
                break
        else:
            q = end
        busy = q
        j5 = int(np.searchsorted(ts5, ts1[q], "right")) - 1
        cost = (x.spread + gl.COMMISSION) / SL_USD
        gross = s * (exit_px - e) / SL_USD
        out.append(("PBK-M1", int(x.i), j5, float(s), SL_USD, gross, cost, why))
    cols = ["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit"]
    t = pd.DataFrame(out, columns=cols)
    return gn.with_day(gs.finish(t, cx), cx)


def build_m1() -> str:
    from app.research import gold_ah as ah

    fr = gl.load()
    cx = gl.context(fr)
    m1 = ah.load_store()
    t = simulate_m1(pbk_m1_candidates(cx, levels(cx), m1), m1, cx)
    t = t[t["year"] >= gl.START.year].reset_index(drop=True)  # 2011 is warm-up
    a, b = t[t["year"] <= TUNE_END], t[t["year"] > TUNE_END]
    sa, sb = gs.summary(a), gs.summary(b)
    ok1 = sa["net"] > 0 and sa["years_pos"] >= 0.6 and sa["trades"] >= gn.MIN_TRADES
    ok2 = sb["net_slip"] > 0
    verdict = "passes" if ok1 and ok2 else "is dropped"
    lines = [
        "# Gold: PBK-M1, fixed $10 SL and TP, entry on M1, XAUUSD (Addendum 1)",
        "",
        "_`python -m app research gold-pbk m1`, registered in `GOLD_PBK.md` §10 (2026-11-10). "
        "XAUUSD 5m levels and M1 entries and exits, 2012-01 to 2026-01-09; cost = the entry M1 "
        "bar's recorded spread + $0.07 per oz; with slip adds $0.10 on stop exits. Seen data: "
        "optimistic. The lockbox was not read._",
        "",
        *gs.HEAD,
        gs._row("2012-2021", a),
        gs._row("2022 to 2026-01-09", b),
        gs._row("Buys", t[t["dir"] > 0]),
        gs._row("Sells", t[t["dir"] < 0]),
        "",
        "| Period | Gross R (SE) | TP | SL | Time |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, g in (("2012-2021", a), ("2022 to 2026-01-09", b)):
        ex = g["exit"].value_counts(normalize=True)
        se = g["gross"].std(ddof=1) / np.sqrt(max(len(g), 2))
        lines.append(
            f"| {name} | {g['gross'].mean():+.3f} ({se:.3f}) | {ex.get('tp', 0):.1%} "
            f"| {ex.get('sl', 0):.1%} | {ex.get('time', 0):.1%} |"
        )
    lines += ["", *gn._by_year(t), "", f"**Decision (§10): PBK-M1 {verdict}.**"]
    return "\n".join(lines) + "\n"


# --- RTB ------------------------------------------------------------------------------------------


def rtb_candidates(cx: gl.Ctx, lg: pd.DataFrame, r: float) -> pd.DataFrame:
    """Limit fills at the r retracement of every strong leg (the trend filter reads bar m)."""
    last = len(cx.c) - 1
    rows = []
    for x in lg[lg["ratio"] >= BIG].itertuples(index=False):
        d, big, m, top = int(x.dir), float(x.leg), int(x.m), float(x.H)
        p = top - d * r * big
        f = gr.first_fill(cx, d, m + 1, min(m + FILL_WAIT, last), p, top)
        if f < 0 or not in_window(cx, f):
            continue
        e = min(p, cx.o[f]) if d > 0 else max(p, cx.o[f])
        sl = top - d * SL_RTB * big
        risk = d * (e - sl)
        if risk <= 0:
            continue
        rows.append((f, d, float(e), float(risk), top, m))
    return pd.DataFrame(rows, columns=["i", "dir", "entry", "risk", "ref", "m"])


# --- settings and runs ------------------------------------------------------------------------


def finalize(cx: gl.Ctx, cand: pd.DataFrame, liq: Liq, tr: tuple[np.ndarray, np.ndarray],
             name: str, target: str, filt: str, at: str, touch: bool) -> pd.DataFrame:  # fmt: skip
    """The trend filter (read at column ``at``), the target, the cost cap: simulator signals."""
    rows = []
    t1, t4 = tr
    for x in cand.itertuples(index=False):
        i, d, e, risk = int(x.i), int(x.dir), float(x.entry), float(x.risk)
        k = int(getattr(x, at))
        if filt == "STRUCT" and not (t1[k] == d and t4[k] == d):
            continue
        if (cx.spread[i] + gl.COMMISSION) / risk > CAP:
            continue
        tp_r = 2.0 if target == "R2" else liq.target_r(d, i, float(x.ref), e, risk)
        rows.append((name, i, float(d), e, risk, tp_r, int(cx.deadline[i]), touch))
    cols = ["strategy", "i", "dir", "entry", "risk", "tp_r", "end", "touch"]
    return pd.DataFrame(rows, columns=cols).sort_values("i", kind="stable").reset_index(drop=True)


def simulate(sig: pd.DataFrame, cx: gl.Ctx, fr5: gr.Frame) -> pd.DataFrame:
    t = gr.simulate(sig, cx, fr5, "TRAIL")
    return gn.with_day(gs.finish(t, cx), cx)


def settings(strategy: str) -> list[dict]:
    if strategy == "PBK":
        return [{"target": a, "filt": b} for a, b in itertools.product(TARGETS, FILTERS)]
    return [{"r": r, "target": a, "filt": b} for r, a, b in itertools.product(RS, TARGETS, FILTERS)]


class Lab:
    """Everything computed once: context, frames, trends, levels, legs and candidates."""

    def __init__(self, cx: gl.Ctx, tr: tuple[np.ndarray, np.ndarray], lv: pd.DataFrame) -> None:
        self.cx, self.tr, self.lv = cx, tr, lv
        self.fr5 = gr.frame(cx, "5m")
        self.liq = Liq(lv)
        self.pbk, self.touches = pbk_candidates(cx, lv)
        self.legs = gr.legs(cx, self.fr5)
        self.rtb = {r: rtb_candidates(cx, self.legs, r) for r in RS}

    def run(self, strategy: str, target: str, filt: str, r: float | None = None) -> pd.DataFrame:
        if strategy == "PBK":
            sig = finalize(self.cx, self.pbk, self.liq, self.tr, "PBK", target, filt, "i", False)
        else:
            sig = finalize(self.cx, self.rtb[r], self.liq, self.tr, "RTB", target, filt, "m", True)
        return simulate(sig, self.cx, self.fr5)


def tune(lab: Lab, strategy: str) -> pd.DataFrame:
    rows = []
    for st in settings(strategy):
        t = lab.run(strategy, **st)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


# --- report -----------------------------------------------------------------------------------


def _grid(g: pd.DataFrame) -> list[str]:
    keys = [k for k in ("r", "target", "filt") if k in g]
    head = " | ".join(k for k in keys)
    lines = [
        f"| {head} | Tune trades | Tune net | Tune years + | Tune cost R | Check trades "
        "| Check net (SE) | Check with slip | Eligible |",
        "|" + " --- |" * (len(keys) + 8),
    ]
    for r in g.itertuples():
        ks = " | ".join(f"{getattr(r, k):g}" if k == "r" else str(getattr(r, k)) for k in keys)
        lines.append(
            f"| {ks} | {r.tune_trades:,} | {r.tune_net:+.3f} | {r.tune_years_pos:.0%} "
            f"| {r.tune_cost:.3f} | {r.check_trades:,} | {r.check_net:+.3f} ({r.check_se:.3f}) "
            f"| {r.check_net_slip:+.3f} | {'yes' if r.eligible else ''} |"
        )
    return lines


def describe(lab: Lab) -> list[str]:
    tch = lab.touches
    lines = [
        "| First touches | Count | Closed beyond within 24 bars |",
        "| --- | --- | --- |",
    ]
    for name, g in (("All", tch), ("With a pullback (rule 3)", tch[tch["pulled"]]),
                    ("Without", tch[~tch["pulled"]])):  # fmt: skip
        lines.append(f"| {name} | {len(g):,} | {g['broke24'].mean():.1%} |")
    big = lab.legs[lab.legs["ratio"] >= BIG]
    last = len(lab.cx.c) - 1
    lines += ["", "| Strong legs (>= 0.75 x ATR(D1)) | Count | Reach 20% | Reach 30% |",
              "| --- | --- | --- | --- |"]  # fmt: skip
    hits = {
        r: np.mean(
            [
                gr.first_fill(
                    lab.cx,
                    int(x.dir),
                    int(x.m) + 1,
                    min(int(x.m) + FILL_WAIT, last),
                    x.H - x.dir * r * x.leg,
                    x.H,
                )
                >= 0
                for x in big.itertuples(index=False)
            ]
        )  # fmt: skip
        for r in RS
    }
    lines.append(f"| 5m | {len(big):,} | {hits[0.2]:.0%} | {hits[0.3]:.0%} |")
    return lines


def build() -> str:
    fr = gl.load()
    cx = gl.context(fr)
    lab = Lab(cx, trends(cx, fr), levels(cx))
    lines = [
        "# Gold: PBK (pullback before the break) and RTB (re-enter a strong move), XAUUSD",
        "",
        "_`python -m app research gold-pbk build`, registered in `GOLD_PBK.md` (2026-11-10). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the entry bar's recorded spread + $0.07 "
        "per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to 2026-01-09. "
        "Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. Descriptive (decides nothing)",
        "",
        *describe(lab),
    ]
    chosen = {}
    for n, s in enumerate(("PBK", "RTB"), start=2):
        g = tune(lab, s)
        ok = g[g["eligible"]]
        lines += ["", f"## {n}. {s}: the settings (by net R on 2012-2021)", "", *_grid(g), ""]
        if len(ok):
            st = {k: ok.iloc[0][k] for k in ("r", "target", "filt") if k in ok}
            if "r" in st:
                st["r"] = float(st["r"])
            chosen[s] = lab.run(s, **st)
            lines.append(f"Chosen: {st}.")
        else:
            lines.append(f"**No setting qualifies: {s} is dropped.**")
    if chosen:
        day = gn.day_strategies(cx)
        lines += ["", "## 4. The chosen settings", ""]
        for s, t in chosen.items():
            corr = gn.correlations(t, day)
            lines += [
                *gs.HEAD,
                gs._row(f"{s}, 2012-2021", t[t["year"] <= TUNE_END]),
                gs._row(f"{s}, check", t[t["year"] > TUNE_END]),
                gs._row(f"{s}, buys", t[t["dir"] > 0]),
                gs._row(f"{s}, sells", t[t["dir"] < 0]),
                "",
                f"Exits: {t['exit'].value_counts(normalize=True).round(3).to_dict()}.",
                "",
                f"{s}: daily net R correlation with the five, 2012 to 2026-01-09 (decides "
                "nothing here): " + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items()) + ".",
                "",
                *gn._by_year(t),
                "",
            ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-pbk")
    ap.add_argument("step", choices=("build", "m1"))
    args = ap.parse_args(argv)
    path, text = (REPORT, build) if args.step == "build" else (M1_REPORT, build_m1)
    path.write_text(text(), encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return 0
