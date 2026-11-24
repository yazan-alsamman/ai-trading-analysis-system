"""Gold: the magnet to an untouched level (``docs/strategies/GOLD_MAGNET.md``, registered
2026-11-11).

    python -m app research gold-magnet build --export <GOLD M1>

A strong 5m move with the 1h trend (EMA 20 / 50) toward the nearest untouched level (day, week,
pivot, Asia, 1h swing, 1h FVG, $50) 1.5-4 R away: enter at the bar's close, SL at the move's
origin, target just before the level, exit 16:45 New York.

- **Part A** (descriptive): is a level reached more often than an arbitrary point at the same
  distance after the same kind of move? Hit = MFE before the SL >= m, against q(m), the share of
  all triggers whose MFE reaches m.
- **Part B**: the trade, M0 (target, SL, 16:45) and BE (also SL to entry + cost at +1 R)."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_c123 as g3
from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_magnet_result.md"  # not gold_magnet.md: GOLD_MAGNET.md on Windows
TUNE_END = gc.TUNE_END
WIN_FROM, WIN_TO = 2 * 60, 14 * 60  # bar opens 02:00-13:55 New York
ASIA_END, DAY_START = 2 * 60, 18 * 60
BODY_K, RUN_K, ORIGIN_PAD, TARGET_PAD = 0.6, 1.0, 0.1, 0.05
M_MIN, M_MAX, CAP = 1.5, 4.0, 0.10
SWING_K, FVG_MIN, LIFE = 3, 0.1, pd.Timedelta(days=5)
ROUND = 50.0
CELLS = ("M0", "BE")
MIN_TRADES, MAX_CORR = 300, 0.2
FAMILIES = ("DAY", "WEEK", "PIVOT", "ASIA", "SWING", "FVG", "ROUND")


# --- levels ---------------------------------------------------------------------------------------


def ns(s: pd.Series) -> np.ndarray:
    """Tz-aware timestamps as naive UTC datetime64[ns] (the stores differ in resolution)."""
    return s.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[ns]")


def day_extremes(cx: gl.Ctx) -> tuple[np.ndarray, ...]:
    """Per 5m bar: the high and low since the trading day began, and since 02:00 New York (the
    Asia range's end), through the bar itself."""
    k = pd.Series(cx.day_idx)
    hi = pd.Series(cx.h).groupby(k).cummax().to_numpy()
    lo = pd.Series(cx.lo).groupby(k).cummin().to_numpy()
    after = (cx.ny_min >= ASIA_END) & (cx.ny_min < DAY_START)
    hi2 = pd.Series(np.where(after, cx.h, -np.inf)).groupby(k).cummax().to_numpy()
    lo2 = pd.Series(np.where(after, cx.lo, np.inf)).groupby(k).cummin().to_numpy()
    return hi, lo, hi2, lo2


def day_families(cx: gl.Ctx) -> dict[str, dict[str, np.ndarray]]:
    """The day-indexed levels by family (by D1 bar)."""
    h, lo, c = (cx.d1[k].to_numpy() for k in ("high", "low", "close"))
    piv = gc.pivot_levels(cx)
    return {
        "DAY": {**gc.day_levels(cx), "PDC": np.r_[np.nan, c[:-1]]},
        "WEEK": gs.week_levels(cx),
        "PIVOT": {**piv, "P": np.r_[np.nan, ((h + lo + c) / 3)[:-1]]},
        "ASIA": gs.asia_levels(cx),
    }


def _first_touch(x: np.ndarray, level: float, side: int, a: int, b: int) -> int:
    """The first bar in [a, b] whose high (side +1) / low (side -1) reaches ``level``, or b + 1."""
    if b < a:
        return b + 1
    w = x[a : b + 1] >= level if side > 0 else x[a : b + 1] <= level
    k = int(np.argmax(w))
    return a + k if w[k] else b + 1


def event_levels(cx: gl.Ctx, h1: pd.DataFrame) -> pd.DataFrame:
    """1h swings and FVG near edges: price, side (+1 above: a buy's target), family, the first 5m
    bar it is known (start), the last bar of its life (expiry) and the first bar touching it
    (death; alive while start <= i < death and i <= expiry)."""
    hh, ll, cc = (h1[k].to_numpy() for k in ("high", "low", "close"))
    atr = gl.wilder(hh, ll, cc)
    ts, close = ns(h1["ts_utc"]), ns(h1["close_utc"])
    rows = []
    k = SWING_K
    for j in range(k, len(hh) - k):
        nb = np.r_[hh[j - k : j], hh[j + 1 : j + k + 1]]
        if hh[j] > nb.max():
            rows.append((hh[j], 1, "SWING", close[j + k], ts[j]))
        nb = np.r_[ll[j - k : j], ll[j + 1 : j + k + 1]]
        if ll[j] < nb.min():
            rows.append((ll[j], -1, "SWING", close[j + k], ts[j]))
    for j in range(2, len(hh)):
        if ll[j] - hh[j - 2] >= FVG_MIN * atr[j]:  # bullish gap below price: a sell's target
            rows.append((ll[j], -1, "FVG", close[j], ts[j]))
        if ll[j - 2] - hh[j] >= FVG_MIN * atr[j]:  # bearish gap above price: a buy's target
            rows.append((hh[j], 1, "FVG", close[j], ts[j]))
    cols = ["level", "side", "family", "known", "born"]
    ev = pd.DataFrame(rows, columns=cols)
    t5 = ns(cx.m["ts_utc"])
    known = ev["known"].to_numpy("datetime64[ns]")
    born = ev["born"].to_numpy("datetime64[ns]")
    ev["start"] = np.searchsorted(t5, known, "left")
    ev["expiry"] = np.searchsorted(t5, born + LIFE.to_timedelta64(), "left") - 1
    ev = ev[ev["start"] < len(t5)].sort_values("start", kind="stable").reset_index(drop=True)
    death = np.empty(len(ev), dtype=int)
    for q, r in enumerate(ev.itertuples(index=False)):
        x = cx.h if r.side > 0 else cx.lo
        death[q] = _first_touch(x, r.level, r.side, int(r.start), int(r.expiry))
    ev["death"] = death
    return ev[["level", "side", "family", "start", "expiry", "death"]]


def nearest_level(cx: gl.Ctx, i: int, s: int, fam_days: dict, ext: tuple, ev: pd.DataFrame,
                  ev_start: np.ndarray) -> tuple[float, str]:  # fmt: skip
    """The nearest alive level beyond bar i's close in direction s, and its family."""
    hi, lo, hi2, lo2 = (x[i] for x in ext)
    e = cx.c[i]
    d = int(cx.day_idx[i])
    best, fam = np.inf, ""

    def consider(level: float, family: str) -> None:
        nonlocal best, fam
        if np.isfinite(level) and 0 < s * (level - e) < best:
            best, fam = s * (level - e), family

    for family, lv in fam_days.items():
        top, bot = (hi2, lo2) if family == "ASIA" else (hi, lo)
        for arr in lv.values():
            x = arr[d] if 0 <= d < len(arr) else np.nan
            if (s > 0 and x > top) or (s < 0 and x < bot):
                consider(x, family)
    consider((np.floor(hi / ROUND) + 1) * ROUND if s > 0 else (np.ceil(lo / ROUND) - 1) * ROUND,
             "ROUND")  # fmt: skip
    a, b = np.searchsorted(ev_start, i - 1441, "left"), np.searchsorted(ev_start, i, "right")
    if b > a:
        w = ev.iloc[a:b]
        ok = (w["side"].to_numpy() == s) & (w["death"].to_numpy() > i)
        ok &= w["expiry"].to_numpy() >= i
        for level, family in zip(w["level"].to_numpy()[ok], w["family"].to_numpy()[ok],
                                 strict=True):  # fmt: skip
            consider(level, family)
    return (e + s * best if np.isfinite(best) else np.nan), fam


# --- triggers -------------------------------------------------------------------------------------


def trend_1h(cx: gl.Ctx, h1: pd.DataFrame) -> np.ndarray:
    c = h1["close"]
    diff = (c.ewm(span=20, adjust=False).mean() - c.ewm(span=50, adjust=False).mean()).to_numpy()
    return np.sign(gl.on_5m(cx.m, h1, diff))


def triggers(cx: gl.Ctx, h1: pd.DataFrame, rel: np.ndarray, start: pd.Timestamp) -> pd.DataFrame:
    """Every bar passing the trend, strength, window, release and cost rules (§2), with its
    direction, entry, SL and risk."""
    s = trend_1h(cx, h1)
    s = np.where(np.isfinite(s), s, 0.0)
    prev3 = np.r_[np.full(3, np.nan), cx.c[:-3]]
    strong = (s * (cx.c - cx.o) >= BODY_K * cx.atr5) | (s * (cx.c - prev3) >= RUN_K * cx.atr5)
    lo3 = pd.Series(cx.lo).rolling(3).min().to_numpy()
    hi3 = pd.Series(cx.h).rolling(3).max().to_numpy()
    sl = np.where(s > 0, lo3 - ORIGIN_PAD * cx.atr5, hi3 + ORIGIN_PAD * cx.atr5)
    risk = s * (cx.c - sl)
    ok = (s != 0) & strong & (cx.weekday < 5) & (cx.ny_min >= WIN_FROM) & (cx.ny_min < WIN_TO)
    ok &= np.isfinite(risk) & (risk > 0) & (cx.deadline > np.arange(len(cx.c)))
    ok &= (cx.spread + gl.COMMISSION) / np.where(risk > 0, risk, np.inf) <= CAP
    ok &= (cx.m["close_utc"] >= start).to_numpy()
    k = np.flatnonzero(ok)
    k = k[~g3.gated(cx, k, rel)]
    return pd.DataFrame({"i": k, "dir": s[k], "entry": cx.c[k], "sl": sl[k], "risk": risk[k]})


def mfe_before_sl(cx: gl.Ctx, tr: pd.DataFrame) -> np.ndarray:
    """The largest favourable move (R) before the SL bar or 16:45; a bar reaching the SL adds
    nothing."""
    out = np.zeros(len(tr))
    for q, r in enumerate(tr.itertuples(index=False)):
        i, end = int(r.i), int(cx.deadline[int(r.i)])
        if r.dir > 0:
            stop = _first_touch(cx.lo, r.sl, -1, i + 1, end)
            fav = cx.h[i + 1 : stop] - r.entry
        else:
            stop = _first_touch(cx.h, r.sl, 1, i + 1, end)
            fav = r.entry - cx.lo[i + 1 : stop]
        out[q] = max(fav.max(), 0.0) / r.risk if len(fav) else 0.0
    return out


def with_targets(cx: gl.Ctx, h1: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    """The triggers with the target (T, m, family); m NaN when no level is alive."""
    fam_days = day_families(cx)
    ext = day_extremes(cx)
    ev = event_levels(cx, h1)
    ev_start = ev["start"].to_numpy()
    lv, fam = np.full(len(tr), np.nan), np.full(len(tr), "", dtype=object)
    for q, r in enumerate(tr.itertuples(index=False)):
        lv[q], fam[q] = nearest_level(cx, int(r.i), int(r.dir), fam_days, ext, ev, ev_start)
    i = tr["i"].to_numpy()
    tgt = lv - tr["dir"].to_numpy() * TARGET_PAD * cx.atr5[i]
    m = tr["dir"].to_numpy() * (tgt - tr["entry"].to_numpy()) / tr["risk"].to_numpy()
    return tr.assign(level=lv, target=tgt, m=m, family=fam)


# --- part A ---------------------------------------------------------------------------------------


def clustered_t(x: np.ndarray, groups: np.ndarray) -> float:
    """Mean of x over its standard error with groups (trading days) as clusters."""
    n = len(x)
    if n < 2:
        return np.nan
    mu = x.mean()
    s = pd.Series(x - mu).groupby(groups).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s**2).sum() * g / max(g - 1, 1)) / n
    return float(mu / se) if se > 0 else np.nan


def magnet(tr: pd.DataFrame) -> dict:
    """Part A on one period: q(m) from every trigger, the level triggers' hits and excess."""
    srt = np.sort(tr["mfe"].to_numpy())
    lvl = tr[(tr["m"] >= M_MIN) & (tr["m"] <= M_MAX)]

    def q(m: np.ndarray) -> np.ndarray:
        return 1 - np.searchsorted(srt, m, "left") / len(srt)

    hit = (lvl["mfe"] >= lvl["m"]).to_numpy(float)
    qm = q(lvl["m"].to_numpy())
    rw = 1 / (1 + lvl["m"].to_numpy())
    ex = hit - qm
    out = {"triggers": len(tr), "level": len(lvl), "hit": hit.mean(), "q": qm.mean(),
           "rw": rw.mean(), "excess": ex.mean(), "t": clustered_t(ex, lvl["tday"].to_numpy()),
           "m": lvl["m"].mean(), "fam": {}}  # fmt: skip
    for f in FAMILIES:
        w = (lvl["family"] == f).to_numpy()
        if w.sum() >= 2:
            out["fam"][f] = (int(w.sum()), hit[w].mean(), qm[w].mean(), ex[w].mean(),
                             clustered_t(ex[w], lvl["tday"].to_numpy()[w]))  # fmt: skip
    return out


# --- part B ---------------------------------------------------------------------------------------


def simulate(cx: gl.Ctx, sig: pd.DataFrame, cell: str) -> pd.DataFrame:
    """One open trade at a time: target, SL, 16:45; BE also moves the SL to entry + cost from the
    bar after the favourable extreme first reaches +1 R."""
    out, busy = [], -1
    for r in sig.itertuples(index=False):
        i = int(r.i)
        if i <= busy:
            continue
        s, e, risk, tgt = int(r.dir), float(r.entry), float(r.risk), float(r.target)
        end = int(cx.deadline[i])
        cost = cx.spread[i] + gl.COMMISSION
        fav, adv = (cx.h, cx.lo) if s > 0 else (cx.lo, cx.h)
        sl = e - s * risk
        j_sl = _first_touch(adv, sl, -s, i + 1, end)
        j_tp = _first_touch(fav, tgt, s, i + 1, end)
        j, px, why = end, cx.c[end], "time"
        if cell == "BE":
            j_be = _first_touch(fav, e + s * risk, s, i + 1, end)
            if j_be < min(j_sl, j_tp):  # +1 R reached first, without the SL on that bar
                be = e + s * cost
                j_sl = _first_touch(adv, be, -s, j_be + 1, end)
                sl = be
        if j_sl <= end and j_sl <= j_tp:
            j, px, why = j_sl, sl, "sl"
        elif j_tp <= end:
            j, px, why = j_tp, tgt, "tp"
        busy = j
        out.append(("MAGNET-" + cell, i, j, float(s), risk, s * (px - e) / risk, cost / risk, why,
                    r.family))  # fmt: skip
    cols = ["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit", "family"]
    return pd.DataFrame(out, columns=cols)


def trades(cx: gl.Ctx, sig: pd.DataFrame, cell: str) -> pd.DataFrame:
    return gn.with_day(gs.finish(simulate(cx, sig, cell), cx), cx)


# --- report ---------------------------------------------------------------------------------------


def prepare(fr: dict[str, pd.DataFrame], rel: np.ndarray, start: pd.Timestamp) -> tuple:
    cx = gl.context(fr)
    tr = triggers(cx, fr["1h"], rel, start)
    tr = with_targets(cx, fr["1h"], tr)
    tr["mfe"] = mfe_before_sl(cx, tr)
    tr["tday"] = cx.day_idx[tr["i"].to_numpy()]
    tr["year"] = pd.to_datetime(cx.m["close_utc"].to_numpy()[tr["i"]], utc=True).year
    sig = tr[(tr["m"] >= M_MIN) & (tr["m"] <= M_MAX)].sort_values("i").reset_index(drop=True)
    return cx, tr, sig


def _a_rows(name: str, a: dict) -> list[str]:
    return [f"| {name} | {a['triggers']:,} | {a['level']:,} | {a['m']:.2f} | {a['hit']:.1%} "
            f"| {a['q']:.1%} | {a['rw']:.1%} | {a['excess']:+.1%} | {a['t']:+.2f} |"]  # fmt: skip


def build(export: Path) -> str:
    cal = pd.read_parquet(g3.CAL)
    rel = g3.release_times(cal)
    cx, tr, sig = prepare(gl.load(), rel, gl.START)
    fx_fr = ge.frames_from_lines(gv.fx_lines(export))  # without the summary bars
    fx, ftr, fsig = prepare(fx_fr, rel, gv.FX_START)
    tune, chk = tr[tr["year"] <= TUNE_END], tr[tr["year"] > TUNE_END]
    parts = {"2012-2021": magnet(tune), "2022 to 2026-01-09": magnet(chk),
             "FxPro 2016-2026": magnet(ftr)}  # fmt: skip
    lines = [
        "# Gold: the magnet to an untouched level, XAUUSD and FxPro",
        "",
        "_`python -m app research gold-magnet build`, registered in `GOLD_MAGNET.md` (2026-11-11). "
        "XAUUSD 5m 2012 to 2026-01-09, then FxPro GOLD from 2016-02; cost = spread + $0.07, slip "
        "$0.10 on SL exits. FxPro: the export's summary bars are dropped (`gold_live.fx_lines`)._",
        "",
        "## Part A: is a level reached more often than any point at the same distance?",
        "",
        "Hit = the move reaches the target before the SL (or 16:45). q(m) = the share of all "
        "triggers reaching the same distance m. RW = 1 / (1 + m). t from trading-day clusters.",
        "",
        "| Period | Triggers | With a level 1.5-4 R | Mean m | Hit | q(m) | RW | Excess over q "
        "| t |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, a in parts.items():
        lines += _a_rows(name, a)
    present = parts["2012-2021"]["excess"] > 0 and parts["2012-2021"]["t"] >= 2
    present &= parts["2022 to 2026-01-09"]["excess"] > 0
    lines += ["", f"**Magnet (registered reading): {'present' if present else 'not present'}.**",
              "", "By family of the nearest level (trades, hit, q(m), excess, t):", "",
              "| Family | " + " | ".join(parts) + " |",
              "| --- |" + " --- |" * len(parts)]  # fmt: skip
    for f in FAMILIES:
        row = []
        for a in parts.values():
            v = a["fam"].get(f)
            row.append(
                f"{v[0]:,}: {v[1]:.0%} vs {v[2]:.0%}, {v[3]:+.1%} (t {v[4]:+.1f})" if v else "-"
            )
        lines.append(f"| {f} | " + " | ".join(row) + " |")

    days = len(np.unique(cx.day_idx[(cx.m["close_utc"] >= gl.START).to_numpy()]))
    cells = {c: trades(cx, sig, c) for c in CELLS}
    lines += ["", "## Part B: the trade", "",
              "| Cell | Trades a day | Tune trades | Tune net (with slip) | Tune years + "
              "| Check trades | Check net (with slip) | TP / SL / time | Eligible |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    chosen, best = None, -np.inf
    for name, t in cells.items():
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        elig = a["net"] > 0 and a["years_pos"] >= 0.6 and a["trades"] >= MIN_TRADES
        mix = " / ".join(f"{(t['exit'] == x).mean():.0%}" for x in ("tp", "sl", "time"))
        lines.append(f"| {name} | {len(t) / days:.2f} | {a['trades']:,} | {a['net']:+.3f} "
                     f"({a['net_slip']:+.3f}) | {a['years_pos']:.0%} | {b['trades']:,} "
                     f"| {b['net']:+.3f} ({b['net_slip']:+.3f}) | {mix} "
                     f"| {'yes' if elig else ''} |")  # fmt: skip
        if elig and a["net_slip"] > best:
            chosen, best = name, a["net_slip"]
    fcells = {c: trades(fx, fsig, c) for c in CELLS}
    lines += ["", "FxPro 2016-02 to 2026-11-05 (net R with slip, t): "
              + "; ".join(f"{c} {t['net_slip'].mean():+.3f} (t {g3.t_stat(t):+.2f}, {len(t):,})"
                          for c, t in fcells.items()) + "."]  # fmt: skip
    if chosen is None:
        lines += ["", "**No cell qualifies on 2012-2021: dropped.**"]
    else:
        t = cells[chosen]
        chk_t = t[t["year"] > TUNE_END]
        f = fcells[chosen]
        since = pd.to_datetime(fx.m["close_utc"], utc=True).dt.tz_convert(None).to_numpy()
        start = np.datetime64(gv.FX_START.tz_convert(None))
        day = {k: v[since[v["i"]] >= start] for k, v in gn.day_strategies(fx).items()}
        corr = gn.correlations(f.assign(net=f["net_slip"]), day)
        ok = [chk_t["net_slip"].mean() > 0, f["net_slip"].mean() > 0,
              all(v < MAX_CORR for v in corr.values())]  # fmt: skip
        verdict = "passes 1-4" if all(ok) else "dropped"
        lines += ["", f"**Chosen {chosen}.** Check {chk_t['net_slip'].mean():+.3f} (t "
                  f"{g3.t_stat(chk_t):+.2f}, {len(chk_t):,}); FxPro {f['net_slip'].mean():+.3f} "
                  f"(t {g3.t_stat(f):+.2f}); daily correlation with the five "
                  + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
                  + f". Conditions 2-4: {'/'.join('yes' if x else 'no' for x in ok)}. "
                  f"**{verdict}.**"]  # fmt: skip
    lines += ["", "By year (net R with slip, trades):", "",
              "| Year | " + " | ".join(cells) + " |",
              "| --- |" + " --- |" * len(cells)]  # fmt: skip
    for y in sorted(set().union(*[set(t["year"]) for t in cells.values()])):
        row = []
        for t in cells.values():
            g = t[t["year"] == y]
            row.append(f"{g['net_slip'].mean():+.3f} ({len(g)})" if len(g) else "-")
        lines.append(f"| {y} | " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-magnet")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
