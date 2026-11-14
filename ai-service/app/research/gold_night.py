"""Gold night reversion inside the Asian range (``docs/strategies/GOLD_NIGHT.md``, registered
2026-11-07).

    python -m app research gold-night build                      # XAUUSD: tune, check, report
    python -m app research gold-night fxpro --export <GOLD M1>   # FxPro GOLD, correlations

NIGHT fades the edges of a box drawn by the night's first bars, 19:00 to B New York. It enters at
an edge's touch (a limit at the edge) or at a bar that closes back inside after trading beyond
it. The target is the box middle or the other edge, with a fixed SL. Every trade is out by 02:00
New York, before the day strategies trade. ``build`` tunes 12 settings on 2012-2021 and checks
the choice on 2022 to 2026-01-09. ``fxpro`` runs it on FxPro's GOLD feed with the five day
strategies, for the correlations and the portfolio. The lockbox is not read."""

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
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_night_xauusd.md"  # not gold_night.md: GOLD_NIGHT.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_night_fxpro.md"
CHOICE = gl.STORE / "gold_night_choice.json"
TUNE_END = gc.TUNE_END

NIGHT_FROM, NIGHT_TO = 19 * 60, 120  # 19:00 to 02:00 New York
BOX_ENDS = {"20:00": 20 * 60, "21:00": 21 * 60}
ENTRIES = (("touch", 0.5), ("touch", 1.0), ("reclaim", 0.0))
TARGETS = ("mid", "far")
CAP = 0.10
MIN_TRADES = 300
MAX_CORR = 0.2


# --- signals ---------------------------------------------------------------------------------


def night_parts(cx: gl.Ctx, box_end: str) -> tuple[np.ndarray, ...]:
    """Per 5m bar: the night box of its trading day (H, L; NaN when incomplete), whether it is
    in the entry window, and the index of its night's last bar."""
    b = BOX_ENDS[box_end]
    night = (cx.ny_min >= NIGHT_FROM) | (cx.ny_min < NIGHT_TO)
    in_box = (cx.ny_min >= NIGHT_FROM) & (cx.ny_min < b)
    day = cx.day_idx
    g = pd.DataFrame({"d": day[in_box], "h": cx.h[in_box], "l": cx.lo[in_box]}).groupby("d")
    agg = g.agg(h=("h", "max"), l=("l", "min"), n=("h", "size"))
    agg = agg[agg["n"] >= 0.8 * (b - NIGHT_FROM) / 5]
    hi = pd.Series(agg["h"]).reindex(day).to_numpy()
    lo = pd.Series(agg["l"]).reindex(day).to_numpy()
    window = night & ((cx.ny_min >= b) | (cx.ny_min < NIGHT_TO))
    idx = np.arange(len(cx.c))
    last = pd.Series(np.where(night, idx, -1)).groupby(day).transform("max").to_numpy()
    return hi, lo, window, last


def signals(cx: gl.Ctx, box_end: str, entry: str, stop: float, target: str) -> pd.DataFrame:
    """The first touch (or reclaim) of each edge a night, with its entry, risk and target."""
    hi, lo, window, last = night_parts(cx, box_end)
    w, mid = hi - lo, (hi + lo) / 2
    prev = np.r_[np.nan, cx.c[:-1]]
    ok = window & np.isfinite(hi) & (w > 0) & (last > np.arange(len(cx.c)))
    out = []
    for d, edge, far in ((-1.0, hi, lo), (1.0, lo, hi)):  # sell the upper edge, buy the lower
        tp = mid if target == "mid" else far
        if entry == "touch":
            hit = (prev < edge) & (cx.h >= edge) if d < 0 else (prev > edge) & (cx.lo <= edge)
            e = np.maximum(edge, cx.o) if d < 0 else np.minimum(edge, cx.o)
            sl = edge - d * stop * w
        else:
            hit = (cx.h > edge) & (cx.c < edge) if d < 0 else (cx.lo < edge) & (cx.c > edge)
            e = cx.c
            sl = cx.h + 0.1 * cx.atr5 if d < 0 else cx.lo - 0.1 * cx.atr5
        risk = d * (e - sl)
        with np.errstate(divide="ignore", invalid="ignore"):
            tp_r = d * (tp - e) / risk
        i = np.flatnonzero(ok & hit)
        i = pd.Series(i).groupby(cx.day_idx[i]).min().to_numpy() if len(i) else i
        keep = (risk[i] > 0) & (tp_r[i] > 0) & ((cx.spread[i] + gl.COMMISSION) / risk[i] <= CAP)
        i = i[keep]
        kind = "H" if d < 0 else "L"
        out.append(pd.DataFrame({"strategy": "NIGHT", "i": i, "dir": d, "entry": e[i],
                                 "risk": risk[i], "tp_r": tp_r[i], "end": last[i], "kind": kind,
                                 "touch": entry == "touch"}))  # fmt: skip
    s = pd.concat(out, ignore_index=True).sort_values("i", kind="stable").reset_index(drop=True)
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[s["i"]], utc=True)
    return s[t >= gl.START].reset_index(drop=True)


def simulate(sig: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """Fixed SL and target, one trade at a time. A touch entry that reaches its SL on the touch
    bar itself is a full loss; a target there is not counted. Otherwise SL first, then target,
    bar by bar from the next bar; the exit at ``end``'s close."""
    h, lo, c = cx.h, cx.lo, cx.c
    out = []
    busy = -1
    for r in sig.itertuples(index=False):
        i, end = int(r.i), int(r.end)
        if i <= busy:
            continue
        s, e, risk = float(r.dir), float(r.entry), float(r.risk)
        sl, tp = e - s * risk, e + s * risk * float(r.tp_r)
        exit_px, why, j = c[end], "time", end
        if r.touch and ((lo[i] <= sl) if s > 0 else (h[i] >= sl)):
            exit_px, why, j = sl, "sl", i
        else:
            for j in range(i + 1, end + 1):
                if (lo[j] <= sl) if s > 0 else (h[j] >= sl):
                    exit_px, why = sl, "sl"
                    break
                if (h[j] >= tp) if s > 0 else (lo[j] <= tp):
                    exit_px, why = tp, "tp"
                    break
            else:
                j = end
        busy = j
        cost = (cx.spread[i] + gl.COMMISSION) / risk
        out.append((r.strategy, i, j, s, risk, s * (exit_px - e) / risk, cost, why))
    return pd.DataFrame(out, columns=["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit"])


def run_night(cx: gl.Ctx, box_end: str, entry: str, stop: float, target: str) -> pd.DataFrame:
    return with_day(gs.finish(simulate(signals(cx, box_end, entry, stop, target), cx), cx), cx)


def with_day(t: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """The trading day (D1 bar) of each trade's entry bar."""
    return t.assign(tday=cx.day_idx[t["i"].to_numpy()])


def settings() -> list[dict]:
    return [{"box_end": b, "entry": e, "stop": s, "target": t}
            for b, (e, s), t in itertools.product(BOX_ENDS, ENTRIES, TARGETS)]  # fmt: skip


def tune(cx: gl.Ctx) -> pd.DataFrame:
    rows = []
    for st in settings():
        t = run_night(cx, **st)
        a, b = gs.summary(t[t["year"] <= TUNE_END]), gs.summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_years_pos"] >= 0.6) & (g["tune_trades"] >= MIN_TRADES)
    g["eligible"] &= g["tune_net"] > 0
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


# --- the day strategies, correlations, portfolio ----------------------------------------------


def day_strategies(cx: gl.Ctx) -> dict[str, pd.DataFrame]:
    """v1 (LVL4H, PIVOT) and the shadow level breaks, as the EA trades them."""
    piv = gc.levels(cx, "PIVOT", gc.pivot_levels(cx), cx.atr1h, gc.WINDOWS[ge.PIV_WINDOW],
                    ge.PIV_HORIZON, None)  # fmt: skip
    out = {
        "LVL4H": gs.level_run(cx, "LVL4H", gc.day_levels(cx)),
        "PIVOT": gs.finish(gc.run(piv, cx).drop(columns=["year", "net", "net_slip"]), cx),
        **{k: gs.level_run(cx, k, lv) for k, lv in gs.shadow_levels(cx).items()},
    }
    return {k: with_day(t, cx) for k, t in out.items()}


def correlations(night: pd.DataFrame, day: dict[str, pd.DataFrame]) -> dict[str, float]:
    """Correlation of net R per trading day; days without a trade count as 0."""
    first = min(t["tday"].min() for t in [night, *day.values()])
    last = max(t["tday"].max() for t in [night, *day.values()])
    days = np.arange(first, last + 1)
    x = night.groupby("tday")["net"].sum().reindex(days, fill_value=0.0)
    return {k: float(x.corr(t.groupby("tday")["net"].sum().reindex(days, fill_value=0.0)))
            for k, t in day.items()}  # fmt: skip


def portfolio(trades: list[pd.DataFrame]) -> dict:
    """Every trade together, in exit order: mean net R with slippage, its sum and the largest
    drawdown of the cumulative sum, in R."""
    t = pd.concat(trades, ignore_index=True).sort_values(["j", "i"], kind="stable")
    cum = t["net_slip"].cumsum().to_numpy()
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, cum])[1:] - cum)) if len(cum) else 0.0
    return {"trades": len(t), "mean": t["net_slip"].mean(), "sum": cum[-1], "dd": dd}


# --- reports ---------------------------------------------------------------------------------


def _by_year(t: pd.DataFrame) -> list[str]:
    lines = ["| Year | Trades | Net R | With slip |", "| --- | --- | --- | --- |"]
    for y, g in t.groupby("year"):
        lines.append(f"| {y} | {len(g)} | {g['net'].mean():+.3f} | {g['net_slip'].mean():+.3f} |")
    return lines


def _extras(t: pd.DataFrame, day: dict[str, pd.DataFrame]) -> list[str]:
    corr = correlations(t, day)
    five, six = portfolio(list(day.values())), portfolio([*day.values(), t])
    exits = t["exit"].value_counts(normalize=True)
    return [
        "| Strategy | Daily net R correlation with NIGHT |",
        "| --- | --- |",
        *[f"| {k} | {v:+.3f} |" for k, v in corr.items()],
        "",
        "| Portfolio (net R with slip) | Trades | Mean | Sum | Largest drawdown |",
        "| --- | --- | --- | --- | --- |",
        *[
            f"| {n} | {p['trades']:,} | {p['mean']:+.3f} | {p['sum']:+.1f} | {p['dd']:.1f} |"
            for n, p in (("The five day strategies", five), ("With NIGHT", six))
        ],  # fmt: skip
        "",
        f"Exits: {', '.join(f'{k} {v:.0%}' for k, v in exits.items())}.",
        "",
        *gs.HEAD,
        gs._row("Buys", t[t["dir"] > 0]),
        gs._row("Sells", t[t["dir"] < 0]),
    ]


def build() -> str:
    cx = gl.context(gl.load())
    grid = tune(cx)
    ok = grid[grid["eligible"]]
    lines = [
        "# Gold night reversion on the XAUUSD feed (commercial track, exploratory)",
        "",
        "_`python -m app research gold-night build`, registered in `GOLD_NIGHT.md` (2026-11-07). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09; cost = the signal bar's recorded spread + $0.07 "
        "per oz; with slip adds $0.10 on stop exits. Tune 2012-2021, check 2022 to 2026-01-09. "
        "Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. The 12 settings (by net R on 2012-2021)",
        "",
        "| Box end | Entry | SL (x W) | Target | Tune trades | Tune net | Tune years + "
        "| Tune cost R | Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.box_end} | {r.entry} | {r.stop:g} | {r.target} | {r.tune_trades:,} "
            f"| {r.tune_net:+.3f} | {r.tune_years_pos:.0%} | {r.tune_cost:.3f} "
            f"| {r.check_trades:,} | {r.check_net:+.3f} ({r.check_se:.3f}) "
            f"| {r.check_net_slip:+.3f} | {'yes' if r.eligible else ''} |"
            for r in grid.itertuples()
        ],  # fmt: skip
        "",
    ]
    if not len(ok):
        CHOICE.write_text(json.dumps(None) + "\n", encoding="utf-8")
        lines.append("**No setting qualifies (section 2 of the registration): NIGHT is dropped.**")
        return "\n".join(lines) + "\n"
    choice = {k: ok.iloc[0][k] for k in ("box_end", "entry", "stop", "target")}
    choice["stop"] = float(choice["stop"])
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    t = run_night(cx, **choice)
    day = day_strategies(cx)
    sl_text = f" (SL {choice['stop']:g} x W)" if choice["entry"] == "touch" else ""
    lines += [
        f"Chosen: box to {choice['box_end']}, {choice['entry']}{sl_text}, target "
        f"{choice['target']}.",
        "",
        "## 2. The chosen setting",
        "",
        *gs.HEAD,
        gs._row("2012-2021", t[t["year"] <= TUNE_END]),
        gs._row("2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END]),
        "",
        *_by_year(t),
        "",
        "## 3. Beside the day strategies, 2012 to 2026-01-09 (decides nothing here)",
        "",
        *_extras(t, day),
    ]
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if choice is None:
        return "# Gold night reversion on FxPro's GOLD feed\n\nNIGHT was dropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))

    def since(t: pd.DataFrame, when: pd.Timestamp) -> pd.DataFrame:
        return t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= when]

    t = since(run_night(cx, **choice), gv.FX_START)
    day = {k: since(d, gv.FX_START) for k, d in day_strategies(cx).items()}
    corr = correlations(t, day)
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    s = gs.summary(t)
    passed = s["net_slip"] > 0 and all(abs(v) <= MAX_CORR for v in corr.values())
    lines = [
        "# Gold night reversion on FxPro's GOLD feed (commercial track, exploratory)",
        "",
        f"_`python -m app research gold-night fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Setting chosen on XAUUSD 2012-2021: {choice}. Costs as "
        "`gold_night_xauusd.md`._",
        "",
        *gs.HEAD,
        gs._row("All", t),
        gs._row("2026-01-12 on (used by no choice)", since(t, exam)),
        "",
        *_by_year(t),
        "",
        *_extras(t, day),
        "",
        f"Decision conditions 3 and 4 on this feed: net with slip {s['net_slip']:+.3f}, largest "
        f"|correlation| {max(abs(v) for v in corr.values()):.3f}: "
        f"**{'met' if passed else 'not met'}**.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-night")
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
