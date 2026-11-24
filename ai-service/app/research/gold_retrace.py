"""Gold: the 50% correction after a strong move (``docs/strategies/GOLD_RETRACE.md``, registered
2026-11-07).

    python -m app research gold-retrace build                     # XAUUSD: tune, check, report
    python -m app research gold-retrace fxpro --export <GOLD M1>  # FxPro GOLD, correlations

A leg is a move from the lowest low of the 24 timeframe (TF) bars before a confirmed swing high
to that high (or the mirror image), of at least K x ATR(14, D1).

- **CORR** trades against the leg at its confirmation, with the target at the leg's 50% level.
- **FIB50** waits for the 50% level with a limit, in the leg's direction, with the target at the
  leg's end and the SL at its 78.6% level.

FIXED keeps the SL; TRAIL moves it to break-even at +1 R, then to the last TF swing. All the
simulation is on the 5m bars. The lockbox is not read."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_retrace_xauusd.md"  # not gold_retrace.md: GOLD_RETRACE.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_retrace_fxpro.md"
CHOICE = gl.STORE / "gold_retrace_choice.json"
TUNE_END = gc.TUNE_END

TFS = {"5m": 1, "15m": 3, "30m": 6, "1h": 12}  # 5m bars a TF bar
KS = (0.5, 0.75, 1.0)
MGMT = ("FIXED", "TRAIL")
STRATS = ("CORR", "FIB50")
LOOK, HORIZON, SWING_K = 24, 24, 2
CAP, MIN_TP_R = 0.10, 0.5
SL_CORR, SL_FIB = 0.1, 0.786


# --- TF bars, swings and legs -----------------------------------------------------------------


@dataclass
class Frame:
    """TF bars from the 5m bars, and per 5m bar the TF series known at its close."""

    h: np.ndarray
    lo: np.ndarray
    last5: np.ndarray  # the 5m bar that closes each TF bar
    swl5: np.ndarray  # the last confirmed TF swing low, per 5m bar (NaN before the first)
    swh5: np.ndarray
    atr5: np.ndarray  # ATR(14, TF), per 5m bar


def frame(cx: gl.Ctx, tf: str) -> Frame:
    n5 = len(cx.c)
    key = cx.m["ts_utc"].dt.floor(f"{5 * TFS[tf]}min").to_numpy()
    d = pd.DataFrame({"k": key, "i": np.arange(n5), "o": cx.o, "h": cx.h, "l": cx.lo, "c": cx.c})
    g = d.groupby("k", sort=True).agg(h=("h", "max"), l=("l", "min"), c=("c", "last"),
                                      last=("i", "max"))  # fmt: skip
    h, lo, c, last = (g[k].to_numpy() for k in ("h", "l", "c", "last"))
    atr = gl.wilder(h, lo, c)
    swl, swh = swings(lo, -1), swings(h, 1)

    def per5(values: np.ndarray, lag: int) -> np.ndarray:
        """A TF series whose value at TF bar t is known at the close of TF bar t + lag."""
        out = np.full(n5, np.nan)
        known = np.arange(len(values)) + lag
        ok = known < len(values)
        out[last[known[ok]]] = values[ok]
        return pd.Series(out).ffill().to_numpy()

    return Frame(h, lo, last, per5(swl, SWING_K), per5(swh, SWING_K), per5(atr, 0))


def swings(x: np.ndarray, sign: int) -> np.ndarray:
    """At swing bar b: the value of the last swing (sign 1: high, -1: low) at or before b, its
    extreme over b - k .. b + k; known at b + k."""
    k = SWING_K
    w = np.lib.stride_tricks.sliding_window_view(sign * x, 2 * k + 1)
    is_sw = np.zeros(len(x), bool)
    is_sw[k : len(x) - k] = w[:, k] == w.max(axis=1)
    return pd.Series(np.where(is_sw, x, np.nan)).ffill().to_numpy()


def legs(cx: gl.Ctx, fr: Frame) -> pd.DataFrame:
    """Every leg ending at a confirmed TF swing: its direction (+1 up), end H, origin L, size, the
    5m bar of its confirmation (m) and its size against ATR(14, D1) known there."""
    h, lo, n = fr.h, fr.lo, len(fr.h)
    k = SWING_K
    rows = []
    for d, ext, org in ((1, h, lo), (-1, lo, h)):
        w = np.lib.stride_tricks.sliding_window_view(d * ext, 2 * k + 1)
        b = np.flatnonzero(w[:, k] == w.max(axis=1)) + k
        b = b[(b >= LOOK) & (b + k < n)]
        win = np.lib.stride_tricks.sliding_window_view(-d * org, LOOK + 1)  # window [b-LOOK, b]
        a = b - LOOK + np.argmax(win[b - LOOK], axis=1)
        for bb, aa in zip(b.tolist(), a.tolist(), strict=True):
            if d * ext[aa : bb + k + 1].max() > d * ext[bb] or aa >= bb:
                continue
            rows.append((d, float(ext[bb]), float(org[aa]), bb + k))
    lg = pd.DataFrame(rows, columns=["dir", "H", "L", "j"])
    lg["leg"] = (lg["H"] - lg["L"]).abs()
    lg["m"] = fr.last5[lg["j"].to_numpy()]
    m = lg["m"].to_numpy()
    lg["ratio"] = lg["leg"] / cx.atrd[m]
    ny = cx.ny_min[m] + 5  # the confirmation is at the bar's close
    ok = (cx.weekday[m] < 5) & ~((ny >= 17 * 60) & (ny < 18 * 60)) & np.isfinite(lg["ratio"])
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[m], utc=True)
    return lg[ok & (t >= gl.START)].sort_values("m", kind="stable").reset_index(drop=True)


def first_fill(cx: gl.Ctx, d: int, start: int, stop: int, level: float, ext: float) -> int:
    """The first 5m bar in [start, stop] that reaches ``level`` (against ``d``) before one trades
    beyond ``ext``; -1: none (a bar doing both counts as beyond)."""
    if start > stop:
        return -1
    hi, lo = cx.h[start : stop + 1], cx.lo[start : stop + 1]
    hit = (lo <= level) if d > 0 else (hi >= level)
    brk = (hi > ext) if d > 0 else (lo < ext)
    fh = int(np.argmax(hit)) if hit.any() else -1
    fb = int(np.argmax(brk)) if brk.any() else -1
    if fh < 0 or (0 <= fb <= fh):
        return -1
    return start + fh


# --- the two strategies ----------------------------------------------------------------------


def signals(cx: gl.Ctx, lg: pd.DataFrame, strat: str, tf: str, k: float) -> pd.DataFrame:
    span = HORIZON * TFS[tf]
    last = len(cx.c) - 1
    rows = []
    for r in lg[lg["ratio"] >= k].itertuples(index=False):
        d, big, m = int(r.dir), float(r.leg), int(r.m)
        p50 = r.H - d * 0.5 * big
        if strat == "CORR":
            s, i, e, touch = -d, m, float(cx.c[m]), False
            sl, tp = r.H + d * SL_CORR * big, p50
        else:
            f = first_fill(cx, d, m + 1, min(m + span, last), p50, r.H)
            if f < 0:
                continue
            s, i, touch = d, f, True
            e = min(p50, cx.o[f]) if d > 0 else max(p50, cx.o[f])
            sl, tp = r.H - d * SL_FIB * big, r.H
        risk = s * (e - sl)
        if risk <= 0:
            continue
        tp_r = s * (tp - e) / risk
        if tp_r < MIN_TP_R or (cx.spread[i] + gl.COMMISSION) / risk > CAP:
            continue
        rows.append((strat, i, float(s), e, risk, tp_r, min(i + span, last), touch))
    cols = ["strategy", "i", "dir", "entry", "risk", "tp_r", "end", "touch"]
    return pd.DataFrame(rows, columns=cols).sort_values("i", kind="stable").reset_index(drop=True)


def simulate(sig: pd.DataFrame, cx: gl.Ctx, fr: Frame, mgmt: str) -> pd.DataFrame:
    """One trade at a time. Each bar: the SL (at the bar's open when it gapped through), then the
    target; then under TRAIL the SL moves after the bar closes. A ``touch`` entry (a limit filled
    inside the bar) that reaches its SL on that bar is a full loss."""
    o, h, lo, c = (x.tolist() for x in (cx.o, cx.h, cx.lo, cx.c))
    swl, swh, atr = fr.swl5.tolist(), fr.swh5.tolist(), fr.atr5.tolist()
    out = []
    busy = -1
    for r in sig.itertuples(index=False):
        i, end = int(r.i), int(r.end)
        if i <= busy:
            continue
        s, e, risk = r.dir, r.entry, r.risk
        cost = cx.spread[i] + gl.COMMISSION
        sl, tp = e - s * risk, e + s * risk * r.tp_r
        armed = False
        exit_px, why, j = c[end], "time", end
        if r.touch and ((lo[i] <= sl) if s > 0 else (h[i] >= sl)):
            exit_px, why, j = sl, "sl", i
        else:
            for j in range(i + 1, end + 1):
                if (lo[j] <= sl) if s > 0 else (h[j] >= sl):
                    gap = (o[j] < sl) if s > 0 else (o[j] > sl)
                    exit_px, why = (o[j] if gap else sl), "sl"
                    break
                if (h[j] >= tp) if s > 0 else (lo[j] <= tp):
                    exit_px, why = tp, "tp"
                    break
                if mgmt == "TRAIL":
                    best = h[j] - e if s > 0 else e - lo[j]
                    if not armed and best >= risk:
                        armed = True
                        be = e + s * cost
                        sl = be if s * (be - sl) > 0 else sl
                    if armed:
                        sw = swl[j] - 0.1 * atr[j] if s > 0 else swh[j] + 0.1 * atr[j]
                        if sw == sw and s * (sw - sl) > 0 and s * (c[j] - sw) > 0:
                            sl = sw
            else:
                j = end
        busy = j
        out.append((r.strategy, i, j, s, risk, s * (exit_px - e) / risk, cost / risk, why))
    return pd.DataFrame(out, columns=["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit"])


def run(cx: gl.Ctx, cache: dict, strat: str, tf: str, k: float, mgmt: str) -> pd.DataFrame:
    if tf not in cache:
        fr = frame(cx, tf)
        cache[tf] = (fr, legs(cx, fr))
    fr, lg = cache[tf]
    t = simulate(signals(cx, lg, strat, tf, k), cx, fr, mgmt)
    return gn.with_day(gs.finish(t, cx), cx)


def settings() -> list[dict]:
    return [{"tf": a, "k": b, "mgmt": c} for a, b, c in itertools.product(TFS, KS, MGMT)]


def tune(cx: gl.Ctx, cache: dict, strat: str) -> pd.DataFrame:
    rows = []
    for st in settings():
        t = run(cx, cache, strat, **st)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{x}": v for x, v in a.items()},
                     **{f"check_{x}": v for x, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


def reached_half(cx: gl.Ctx, cache: dict) -> list[str]:
    """Descriptive: the share of legs whose price reached the 50% level before a new extreme
    within 24 TF bars, by TF and size (the baseline: 0.25 to 0.5 x ATR(D1))."""
    bands = [("0.25-0.5 (baseline)", 0.25, 0.5), (">= 0.5", 0.5, np.inf),
             (">= 0.75", 0.75, np.inf), (">= 1.0", 1.0, np.inf)]  # fmt: skip
    lines = ["| TF | " + " | ".join(b[0] for b in bands) + " |", "| --- |" + " --- |" * len(bands)]
    last = len(cx.c) - 1
    for tf in TFS:
        _, lg = cache[tf]
        cells = []
        for _, lo_, hi_ in bands:
            g = lg[(lg["ratio"] >= lo_) & (lg["ratio"] < hi_)]
            hit = [first_fill(cx, int(r.dir), int(r.m) + 1, min(int(r.m) + HORIZON * TFS[tf], last),
                              r.H - r.dir * 0.5 * r.leg, r.H) >= 0
                   for r in g.itertuples(index=False)]  # fmt: skip
            cells.append(f"{np.mean(hit):.0%} ({len(hit):,})" if hit else "-")
        lines.append(f"| {tf} | " + " | ".join(cells) + " |")
    return lines


# --- reports ---------------------------------------------------------------------------------


def _grid(g: pd.DataFrame) -> list[str]:
    return [
        "| TF | K | Management | Tune trades | Tune net | Tune years + | Tune cost R "
        "| Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.tf} | {r.k:g} | {r.mgmt} | {r.tune_trades:,} | {r.tune_net:+.3f} "
            f"| {r.tune_years_pos:.0%} | {r.tune_cost:.3f} | {r.check_trades:,} "
            f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {r.check_net_slip:+.3f} "
            f"| {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],
    ]


def _together(c: dict[str, pd.DataFrame], split: bool) -> list[str]:
    lines = ["| Set | Period | Trades | Mean (with slip) | Sum | Largest drawdown |",
             "| --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    sets = [
        *[(k, [t]) for k, t in c.items()],
        *([("Together", list(c.values()))] if len(c) > 1 else []),
    ]
    periods = [("all", None)]
    if split:
        periods = [("2012-2021", lambda t: t["year"] <= TUNE_END),
                   ("2022 to 2026-01-09", lambda t: t["year"] > TUNE_END)]  # fmt: skip
    for name, ts in sets:
        for pname, f in periods:
            p = gn.portfolio([t[f(t)] if f else t for t in ts])
            lines.append(f"| {name} | {pname} | {p['trades']:,} | {p['mean']:+.3f} "
                         f"| {p['sum']:+.1f} | {p['dd']:.1f} |")  # fmt: skip
    return lines


def build() -> str:
    cx = gl.context(gl.load())
    cache: dict = {}
    grids = {s: tune(cx, cache, s) for s in STRATS}
    choice, chosen = {}, {}
    lines = [
        "# Gold: the 50% correction after a strong move, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-retrace build`, registered in `GOLD_RETRACE.md` "
        "(2026-11-07). XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded "
        "spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to "
        "2026-01-09. Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. Does price reach the 50% level before a new extreme? (descriptive)",
        "",
        "Legs by size against ATR(14, D1), 2012 to 2026-01-09; share (legs):",
        "",
        *reached_half(cx, cache),
    ]
    for n, s in enumerate(STRATS, start=2):
        g = grids[s]
        ok = g[g["eligible"]]
        lines += ["", f"## {n}. {s}: the 24 settings (by net R on 2012-2021)", "", *_grid(g), ""]
        if len(ok):
            choice[s] = {"tf": ok.iloc[0]["tf"], "k": float(ok.iloc[0]["k"]),
                         "mgmt": ok.iloc[0]["mgmt"]}  # fmt: skip
            chosen[s] = run(cx, cache, s, **choice[s])
            lines.append(f"Chosen: {choice[s]}.")
        else:
            lines.append(f"**No setting qualifies: {s} is dropped.**")
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    if chosen:
        day = gn.day_strategies(cx)
        lines += ["", "## 4. Alone and together", "", *_together(chosen, split=True), ""]
        for s, t in chosen.items():
            corr = gn.correlations(t, day)
            lines += [f"{s}: daily net R correlation, 2012 to 2026-01-09 (decides nothing here): "
                      + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items()) + ".", ""]  # fmt: skip
            lines += [*gs.HEAD, gs._row(f"{s}, buys", t[t["dir"] > 0]),
                      gs._row(f"{s}, sells", t[t["dir"] < 0]), "", *gn._by_year(t), ""]  # fmt: skip
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if not choice:
        return "# Gold: the 50% correction on FxPro's GOLD feed\n\nBoth were dropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))

    def since(t: pd.DataFrame, when: pd.Timestamp) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= when]

    cache: dict = {}
    c = {s: since(run(cx, cache, s, **st), gv.FX_START) for s, st in choice.items()}
    day = {k: since(d, gv.FX_START) for k, d in gn.day_strategies(cx).items()}
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    lines = [
        "# Gold: the 50% correction after a strong move, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-retrace fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Settings chosen on XAUUSD 2012-2021: {choice}._",
        "",
        *gs.HEAD,
    ]
    for s, t in c.items():
        lines += [gs._row(f"{s}, all", t), gs._row(f"{s}, 2026-01-12 on", since(t, exam))]
    lines += ["", *_together(c, split=False), ""]
    for s, t in c.items():
        corr = gn.correlations(t, day)
        sm = gs.summary(t)
        met = sm["net_slip"] > 0 and all(abs(v) <= gn.MAX_CORR for v in corr.values())
        lines += [
            f"**{s}**: net with slip {sm['net_slip']:+.3f}; daily correlation "
            + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
            + f"; conditions 3 and 4: **{'met' if met else 'not met'}**.",
            "",
            *gn._by_year(t),
            "",
        ]
    five = gn.portfolio(list(day.values()))
    every = gn.portfolio([*day.values(), *c.values()])
    lines += [
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {n} | {p['trades']:,} | {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} |"
            for n, p in (("The five day strategies", five), ("With the chosen", every))
        ],  # fmt: skip
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-retrace")
    ap.add_argument("step", choices=("build", "fxpro"))
    ap.add_argument("--export", type=Path, help="fxpro: the GOLD M1 export")
    args = ap.parse_args(argv)
    if args.step == "build":
        REPORT.write_text(build(), encoding="utf-8", newline="\n")
        print(f"wrote {REPORT}")
    else:
        FX_REPORT.write_text(fxpro(args.export), encoding="utf-8", newline="\n")
        print(f"wrote {FX_REPORT}")
    return 0
