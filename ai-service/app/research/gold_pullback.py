"""Gold: the pullback inside a strong move, traded with the move (``docs/strategies/
GOLD_PULLBACK.md``, registered 2026-11-07).

    python -m app research gold-pullback build                      # XAUUSD: tune, check
    python -m app research gold-pullback fxpro --export <GOLD M1>   # FxPro GOLD, correlations

PBC takes the legs of ``gold_retrace`` (a strong move to a confirmed swing). After a pullback of
15% to 50% of the leg, it enters with the move when the pullback ends. SWING puts a stop above the
bars that confirm the pullback's swing low; BAR enters at the first close above the previous bar's
high. The SL is under the pullback's low. The target is the leg's end, the measured move, or none,
always with the trailing stop. The lockbox is not read."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn
from app.research import gold_retrace as gr
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_pullback_xauusd.md"  # not gold_pullback.md: GOLD_PULLBACK.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_pullback_fxpro.md"
CHOICE = gl.STORE / "gold_pullback_choice.json"
TUNE_END = gc.TUNE_END

KS = (0.5, 0.75)
TRIGGERS = ("SWING", "BAR")
TARGETS = ("HIGH", "ABCD", "NONE")
MIN_DEPTH, MAX_DEPTH = 0.15, 0.5
HOLD = 48  # TF bars a trade may live


def candidates(cx: gl.Ctx, fr: gr.Frame, lg: pd.DataFrame, trigger: str) -> pd.DataFrame:
    """One entry candidate per leg of at least 0.5 x ATR(D1): its 5m entry bar, direction, entry,
    SL, the pullback's extreme and whether it is a stop fill inside a bar."""
    h, lo = fr.h.tolist(), fr.lo.tolist()
    close = cx.c[fr.last5].tolist()
    atr_tf = fr.atr5[fr.last5].tolist()
    last5 = fr.last5.tolist()
    n, last = len(h), len(cx.c) - 1
    rows = []
    for r in lg[lg["ratio"] >= min(KS)].itertuples(index=False):
        d, top, big, j = int(r.dir), float(r.H), float(r.leg), int(r.j)
        ext, back = (h, lo) if d > 0 else (lo, h)
        b, stop_tf = j - gr.SWING_K, min(j + gr.LOOK, n - 1)
        pb = None
        for t in range(b + 1, stop_tf + 1):
            if d * (ext[t] - top) > 0:
                break  # a new extreme before the entry: the leg is over
            pb = back[t] if pb is None or d * (back[t] - pb) < 0 else pb
            depth = d * (top - pb) / big
            if depth > MAX_DEPTH:
                break
            if t < j or depth < MIN_DEPTH:
                continue
            if trigger == "BAR":
                if d * (close[t] - ext[t - 1]) > 0:
                    i = last5[t]
                    rows.append(
                        (i, d, close[t], pb - d * 0.1 * atr_tf[t], pb, top, big, False, r.ratio)
                    )
                    break
                continue
            p = (
                t - gr.SWING_K
            )  # SWING: is t the confirmation of a swing at p, the pullback's extreme?
            if p <= b or d * (back[p] - pb) != 0:
                continue
            win = back[p - gr.SWING_K : t + 1]
            if (min(win) if d > 0 else max(win)) != back[p]:
                continue
            level = max(ext[p : t + 1]) if d > 0 else min(ext[p : t + 1])
            f = fill(cx, d, last5[t] + 1, min(last5[stop_tf], last), level, back[p])
            if f >= 0:
                e = max(level, cx.o[f]) if d > 0 else min(level, cx.o[f])
                rows.append(
                    (f, d, e, back[p] - d * 0.1 * atr_tf[t], back[p], top, big, True, r.ratio)
                )
            break
    cols = ["i", "dir", "entry", "sl", "pb", "H", "leg", "touch", "ratio"]
    return pd.DataFrame(rows, columns=cols).sort_values("i", kind="stable").reset_index(drop=True)


def fill(cx: gl.Ctx, d: int, start: int, stop: int, level: float, floor: float) -> int:
    """The first 5m bar in [start, stop] reaching the stop ``level`` (with ``d``) before one trades
    beyond the pullback's extreme ``floor``; -1: none (a bar doing both counts as beyond)."""
    if start > stop:
        return -1
    hi, lo = cx.h[start : stop + 1], cx.lo[start : stop + 1]
    hit = (hi >= level) if d > 0 else (lo <= level)
    brk = (lo < floor) if d > 0 else (hi > floor)
    fh = int(np.argmax(hit)) if hit.any() else -1
    fb = int(np.argmax(brk)) if brk.any() else -1
    if fh < 0 or (0 <= fb <= fh):
        return -1
    return start + fh


def signals(cx: gl.Ctx, cand: pd.DataFrame, tf: str, k: float, target: str) -> pd.DataFrame:
    c = cand[cand["ratio"] >= k]
    d = c["dir"].to_numpy(float)
    e, sl = c["entry"].to_numpy(), c["sl"].to_numpy()
    risk = d * (e - sl)
    if target == "HIGH":
        tp = c["H"].to_numpy()
    elif target == "ABCD":
        tp = c["pb"].to_numpy() + d * c["leg"].to_numpy()
    else:
        tp = e + d * np.inf
    with np.errstate(divide="ignore", invalid="ignore"):
        tp_r = np.where(np.isinf(tp), np.inf, d * (tp - e) / risk)
    i = c["i"].to_numpy()
    ok = (risk > 0) & (tp_r >= gr.MIN_TP_R) & ((cx.spread[i] + gl.COMMISSION) / risk <= gr.CAP)
    s = pd.DataFrame({"strategy": "PBC", "i": i, "dir": d, "entry": e, "risk": risk, "tp_r": tp_r,
                      "end": np.minimum(i + HOLD * gr.TFS[tf], len(cx.c) - 1),
                      "touch": c["touch"].to_numpy()})  # fmt: skip
    return s[ok].reset_index(drop=True)


def run(cx: gl.Ctx, cache: dict, tf: str, k: float, trigger: str, target: str) -> pd.DataFrame:
    if tf not in cache:
        fr = gr.frame(cx, tf)
        cache[tf] = (fr, gr.legs(cx, fr))
    fr, lg = cache[tf]
    if (tf, trigger) not in cache:
        cache[(tf, trigger)] = candidates(cx, fr, lg, trigger)
    t = gr.simulate(signals(cx, cache[(tf, trigger)], tf, k, target), cx, fr, "TRAIL")
    return gn.with_day(gs.finish(t, cx), cx)


def settings() -> list[dict]:
    grid = itertools.product(gr.TFS, KS, TRIGGERS, TARGETS)
    return [{"tf": a, "k": b, "trigger": c, "target": d} for a, b, c, d in grid]


def tune(cx: gl.Ctx, cache: dict) -> pd.DataFrame:
    rows = []
    for st in settings():
        t = run(cx, cache, **st)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{x}": v for x, v in a.items()},
                     **{f"check_{x}": v for x, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6)
    g["eligible"] &= g["tune_trades"] >= gn.MIN_TRADES
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


def _grid(g: pd.DataFrame) -> list[str]:
    return [
        "| TF | K | End | Target | Tune trades | Tune net | Tune years + | Tune cost R "
        "| Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.tf} | {r.k:g} | {r.trigger} | {r.target} | {r.tune_trades:,} "
            f"| {r.tune_net:+.3f} | {r.tune_years_pos:.0%} | {r.tune_cost:.3f} "
            f"| {r.check_trades:,} | {r.check_net:+.3f} ({r.check_se:.3f}) "
            f"| {r.check_net_slip:+.3f} | {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],
    ]


def build() -> str:
    cx = gl.context(gl.load())
    cache: dict = {}
    g = tune(cx, cache)
    ok = g[g["eligible"]]
    lines = [
        "# Gold: the pullback inside a strong move, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-pullback build`, registered in `GOLD_PULLBACK.md` "
        "(2026-11-07). XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded "
        "spread + $0.07 per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to "
        "2026-01-09. Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. The 48 settings (by net R on 2012-2021), all with the trailing stop",
        "",
        *_grid(g),
        "",
    ]
    if not len(ok):
        CHOICE.write_text(json.dumps(None) + "\n", encoding="utf-8")
        lines.append("**No setting qualifies: PBC is dropped.**")
        return "\n".join(lines) + "\n"
    choice = {"tf": ok.iloc[0]["tf"], "k": float(ok.iloc[0]["k"]),
              "trigger": ok.iloc[0]["trigger"], "target": ok.iloc[0]["target"]}  # fmt: skip
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    t = run(cx, cache, **choice)
    corr = gn.correlations(t, gn.day_strategies(cx))
    lines += [
        f"Chosen: {choice}.",
        "",
        "## 2. The chosen setting",
        "",
        *gs.HEAD,
        gs._row("2012-2021", t[t["year"] <= TUNE_END]),
        gs._row("2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END]),
        gs._row("Buys", t[t["dir"] > 0]),
        gs._row("Sells", t[t["dir"] < 0]),
        "",
        "Daily net R correlation, 2012 to 2026-01-09 (decides nothing here): "
        + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
        + ".",
        "",
        *gn._by_year(t),
    ]
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if choice is None:
        return "# Gold pullback on FxPro's GOLD feed\n\nPBC was dropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))

    def since(t: pd.DataFrame, when: pd.Timestamp) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= when]

    t = since(run(cx, {}, **choice), gv.FX_START)
    day = {k: since(d, gv.FX_START) for k, d in gn.day_strategies(cx).items()}
    corr = gn.correlations(t, day)
    s = gs.summary(t)
    met = s["net_slip"] > 0 and all(abs(v) <= gn.MAX_CORR for v in corr.values())
    five, six = gn.portfolio(list(day.values())), gn.portfolio([*day.values(), t])
    lines = [
        "# Gold: the pullback inside a strong move, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-pullback fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Setting chosen on XAUUSD 2012-2021: {choice}._",
        "",
        *gs.HEAD,
        gs._row("All", t),
        gs._row(
            "2026-01-12 on (used by no choice)", since(t, pd.Timestamp("2026-01-12", tz="UTC"))
        ),
        "",
        *gn._by_year(t),
        "",
        "Daily net R correlation: " + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items()) + ".",
        "",
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {n} | {p['trades']:,} | {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} |"
            for n, p in (("The five day strategies", five), ("With PBC", six))
        ],  # fmt: skip
        "",
        f"Conditions 3 and 4: **{'met' if met else 'not met'}**.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-pullback")
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
