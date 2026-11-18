"""Gold shadow candidates (``docs/strategies/GOLD_SHADOW.md``, registered 2026-11-07).

    python -m app research gold-shadow build                     # XAUUSD: tune, check, report
    python -m app research gold-shadow fxpro --export <GOLD M1>  # the same on FxPro's GOLD feed

**OPEN** is the opening candle, after SCUTA's "first 5-min candle vs 12 EMA". On a fixed New York
candle it goes with the candle's side of EMA(12) (or its colour). It enters at the next candle's
open, and the SL starts at the candle's other side. Under BAR the SL then follows each closed
candle's low (high); under M8 it is managed as v1. ``build`` tunes 36 settings on 2012-2021 and
checks the chosen one on 2022 to 2026-01-09.

**PIVW, ASIA, PWHL** are level breaks with LVL4H's frozen engine and settings (``gold_combo``),
at other levels: the daily pivots, the Asian range and the previous week's range.

``fxpro`` runs the chosen OPEN setting, SCUTA's own rules and the three level breaks on FxPro's
GOLD export, and gives the decision of section 4. Writes ``gold_shadow_xauusd.md`` and
``gold_shadow_fxpro.md``. The lockbox is not read."""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv

REPORT = gl.OUT_DIR / "gold_shadow_xauusd.md"  # not gold_shadow.md: GOLD_SHADOW.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_shadow_fxpro.md"
CHOICE = gl.STORE / "gold_shadow_choice.json"
TUNE_END = gc.TUNE_END  # 2021
CHECK_END = pd.Timestamp("2026-01-10", tz="UTC")

TIMES = {"08:20": 8 * 60 + 20, "08:30": 8 * 60 + 30, "09:30": 9 * 60 + 30}
DIRECTIONS = ("EMA", "COLOR")
MIN_RANGES = (0.0, 1.0, 2.0)
MANAGEMENT = ("BAR", "M8")
SCUTA = {"time": "09:30", "direction": "EMA", "min_range": 0.0, "mgmt": "BAR"}
MIN_TRADES = 300
EMA_LEN = 12


# --- OPEN ------------------------------------------------------------------------------------


def ema(x: np.ndarray, n: int = EMA_LEN) -> np.ndarray:
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def open_signals(cx: gl.Ctx, time: str, direction: str, min_range: float) -> pd.DataFrame:
    """The ``time`` candle of each weekday. Side: its close against EMA(12) or its open. Entry at
    the next bar's open (that bar must follow it at once). The SL is at the candle's other side.
    Kept when its range is at least ``min_range`` × ATR(14, 5m) of the bar before."""
    n = len(cx.c)
    i = np.flatnonzero((cx.ny_min == TIMES[time]) & (cx.weekday < 5))
    i = i[(i > 0) & (i < n - 1)]
    nxt = cx.m["ts_utc"].to_numpy()[i + 1] == cx.m["close_utc"].to_numpy()[i]
    i = i[nxt]
    ref = ema(cx.c)[i] if direction == "EMA" else cx.o[i]
    d = np.sign(cx.c[i] - ref)
    e = cx.o[i + 1]
    sl = np.where(d > 0, cx.lo[i], cx.h[i])
    risk = d * (e - sl)
    keep = (d != 0) & (risk > 0) & (cx.h[i] - cx.lo[i] >= min_range * cx.atr5[i - 1])
    keep &= cx.deadline[i] > i
    i, d, e, risk = i[keep], d[keep], e[keep], risk[keep]
    s = pd.DataFrame({"strategy": "OPEN", "i": i, "dir": d, "entry": e, "risk": risk,
                      "tp_r": np.nan, "end": cx.deadline[i]})  # fmt: skip
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[s["i"]], utc=True)
    return s[t >= gl.START].reset_index(drop=True)


def simulate_bar(sig: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """SCUTA's management. The SL starts at ``entry - dir * risk``. After each closed bar it moves
    to that bar's low (high for a sell) when better. A hit exits at the SL, or at the bar's open
    when it gapped through. Otherwise the exit is the close of ``end``. One trade at a time;
    columns as ``gold_lab.simulate``."""
    o, h, lo, c = cx.o, cx.h, cx.lo, cx.c
    out = []
    busy = -1
    for r in sig.sort_values("i").itertuples(index=False):
        i, end = int(r.i), int(r.end)
        if i <= busy:
            continue
        s, e, risk = float(r.dir), float(r.entry), float(r.risk)
        cost = cx.spread[i] + gl.COMMISSION
        sl = e - s * risk
        exit_px, why, j = c[end], "time", end
        for j in range(i + 1, end + 1):
            if (lo[j] <= sl) if s > 0 else (h[j] >= sl):
                gap = (o[j] < sl) if s > 0 else (o[j] > sl)
                exit_px, why = (o[j] if gap else sl), "sl"
                break
            sl = max(sl, lo[j]) if s > 0 else min(sl, h[j])
        else:
            j = end
        busy = j
        out.append((r.strategy, i, j, s, risk, s * (exit_px - e) / risk, cost / risk, why))
    return pd.DataFrame(out, columns=["strategy", "i", "j", "dir", "risk", "gross", "cost", "exit"])


def finish(t: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    """Year, New York day, net R and net with SL slip, as ``gold_combo.run``."""
    t = t.copy()
    t["year"] = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True).year
    t["ny_day"] = cx.ny_day[t["i"].to_numpy()]
    t["net"] = t["gross"] - t["cost"]
    t["net_slip"] = t["net"] - np.where(t["exit"] == "sl", gl.SL_SLIP / t["risk"], 0.0)
    return t


def run_open(cx: gl.Ctx, time: str, direction: str, min_range: float, mgmt: str,
             name: str = "OPEN") -> pd.DataFrame:  # fmt: skip
    sig = open_signals(cx, time, direction, min_range).assign(strategy=name)
    t = gl.simulate(sig, cx, "M8") if mgmt == "M8" else simulate_bar(sig, cx)
    return finish(t, cx)


def settings() -> list[dict]:
    grid = itertools.product(TIMES, DIRECTIONS, MIN_RANGES, MANAGEMENT)
    return [{"time": a, "direction": b, "min_range": c, "mgmt": d} for a, b, c, d in grid]


def summary(t: pd.DataFrame) -> dict:
    if len(t) == 0:
        return {"trades": 0, "net": np.nan, "se": np.nan, "net_slip": np.nan, "years_pos": np.nan,
                "cost": np.nan}  # fmt: skip
    yr = t.groupby("year")["net"].mean()
    return {"trades": len(t), "net": t["net"].mean(),
            "se": t["net"].std(ddof=1) / np.sqrt(max(len(t), 2)), "net_slip": t["net_slip"].mean(),
            "years_pos": (yr > 0).mean(), "cost": t["cost"].mean()}  # fmt: skip


def tune(cx: gl.Ctx) -> pd.DataFrame:
    rows = []
    for st in settings():
        t = run_open(cx, **st)
        a, b = summary(t[t["year"] <= TUNE_END]), summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (g["tune_years_pos"] >= 0.6) & (g["tune_trades"] >= MIN_TRADES)
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


# --- level breaks in LVL4H's family -----------------------------------------------------------


def asia_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    """The high and low of each trading day's 19:00-02:00 New York bars (known at 02:00, when the
    entry window opens), by D1 bar."""
    asia = (cx.ny_min >= 19 * 60) | (cx.ny_min < 120)
    k = cx.day_idx[asia]
    hi = pd.Series(cx.h[asia]).groupby(k).max()
    lo = pd.Series(cx.lo[asia]).groupby(k).min()
    n = len(cx.d1)
    out_h, out_l = np.full(n, np.nan), np.full(n, np.nan)
    ok = (hi.index >= 0) & (hi.index < n)
    out_h[hi.index[ok]] = hi.to_numpy()[ok]
    out_l[lo.index[ok]] = lo.to_numpy()[ok]
    return {"ASH": out_h, "ASL": out_l}


def week_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    """The previous week's high and low. Weeks are of trading days, by the New York date of each
    D1 bar's close."""
    days = cx.d1["close_utc"].dt.tz_convert(gl.NY).dt.tz_localize(None).dt.to_period("W-SUN")
    h = cx.d1["high"].groupby(days.to_numpy()).max()
    lo = cx.d1["low"].groupby(days.to_numpy()).min()
    prev_h, prev_l = h.shift(1), lo.shift(1)
    return {"PWH": prev_h.reindex(days.to_numpy()).to_numpy(),
            "PWL": prev_l.reindex(days.to_numpy()).to_numpy()}  # fmt: skip


def level_run(cx: gl.Ctx, name: str, lv: dict[str, np.ndarray],
              events: list | None = None) -> pd.DataFrame:  # fmt: skip
    """LVL4H's frozen settings (``gold_exam``) at other levels; ``events`` as ``gold_lab``."""
    sig = gc.levels(cx, name, lv, ge.LVL_MULT * cx.atr4h, gc.WINDOWS[ge.LVL_WINDOW],
                    ge.LVL_HORIZON, ge.LVL_CAP)  # fmt: skip
    return finish(gc.run(sig, cx, events).drop(columns=["year", "net", "net_slip"]), cx)


def shadow_levels(cx: gl.Ctx) -> dict[str, dict[str, np.ndarray]]:
    """The levels of the shadow level breaks, as ``GoldLive.mq5`` trades them."""
    return {"PIVW": gc.pivot_levels(cx), "ASIA": asia_levels(cx), "PWHL": week_levels(cx)}


def candidates(cx: gl.Ctx, choice: dict) -> dict[str, pd.DataFrame]:
    return {
        "OPEN": run_open(cx, **choice),
        "OPEN-SCUTA": run_open(cx, **SCUTA, name="OPEN-SCUTA"),
        **{k: level_run(cx, k, lv) for k, lv in shadow_levels(cx).items()},
        "LVL4H": level_run(cx, "LVL4H", gc.day_levels(cx)),
    }


# --- NFP days --------------------------------------------------------------------------------


def nfp_days(first: int, last: int) -> set[int]:
    """The BLS rule: the third Friday after the Saturday ending the week (Sunday to Saturday) that
    holds the 12th. It ignores shutdowns and holiday moves. As New York dates (yyyymmdd)."""
    out = set()
    for y in range(first, last + 1):
        for mth in range(1, 13):
            d12 = date(y, mth, 12)
            sat = d12 + timedelta(days=(5 - d12.weekday()) % 7)
            fri = sat + timedelta(days=6 + 14)
            out.add(fri.year * 10000 + fri.month * 100 + fri.day)
    return out


# --- report ----------------------------------------------------------------------------------


def _row(name: str, t: pd.DataFrame) -> str:
    s = summary(t)
    if s["trades"] == 0:
        return f"| {name} | 0 | - | - | - | - |"
    return (f"| {name} | {s['trades']:,} | {s['net']:+.3f} ({s['se']:.3f}) | {s['net_slip']:+.3f} "
            f"| {s['years_pos']:.0%} | {s['cost']:.3f} |")  # fmt: skip


HEAD = ["| Set | Trades | Net R (SE) | With slip | Years + | Cost R |",
        "| --- | --- | --- | --- | --- | --- |"]  # fmt: skip


def detail(c: dict[str, pd.DataFrame], nfp: set[int]) -> list[str]:
    """By year; buys and sells; NFP days; daily correlation with LVL4H and the two together."""
    names = [k for k in c if k != "LVL4H"]
    years = sorted(set().union(*[set(t["year"]) for t in c.values()]))
    lines = ["| Year | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for y in years:
        cells = []
        for k in names:
            g = c[k][c[k]["year"] == y]
            cells.append(f"{g['net'].mean():+.3f} ({len(g)})" if len(g) else "-")
        lines.append(f"| {y} | " + " | ".join(cells) + " |")
    lv = c["LVL4H"].groupby("ny_day")["net"].sum()
    lines += ["", *HEAD]
    for k in names:
        t = c[k]
        both = pd.concat([t, c["LVL4H"]], ignore_index=True)
        day = t.groupby("ny_day")["net"].sum()
        j = pd.concat([day, lv], axis=1, keys=["x", "lvl"]).fillna(0.0)
        lines += [
            _row(f"{k}, buys", t[t["dir"] > 0]),
            _row(f"{k}, sells", t[t["dir"] < 0]),
            _row(f"{k}, NFP days", t[t["ny_day"].isin(nfp)]),
            _row(f"{k}, other days", t[~t["ny_day"].isin(nfp)]),
            _row(f"{k} + LVL4H (daily R corr. {j['x'].corr(j['lvl']):+.2f})", both),
        ]
    return lines


def build() -> str:
    fr = gl.load()
    cx = gl.context(fr)
    grid = tune(cx)
    ok = grid[grid["eligible"]]
    choice = (ok.iloc[0] if len(ok) else grid.iloc[0])[["time", "direction", "min_range", "mgmt"]]
    choice = {k: (float(v) if k == "min_range" else str(v)) for k, v in choice.items()}
    CHOICE.write_text(json.dumps(choice, indent=2) + "\n", encoding="utf-8")
    c = candidates(cx, choice)
    nfp = nfp_days(2011, 2026)

    def fmt(r) -> str:
        return (f"| {r.time} | {r.direction} | {r.min_range:g} | {r.mgmt} | {r.tune_trades:,} "
                f"| {r.tune_net:+.3f} | {r.tune_years_pos:.0%} | {r.check_trades:,} "
                f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {r.check_net_slip:+.3f} "
                f"| {'yes' if r.eligible else ''} |")  # fmt: skip

    lines = [
        "# Gold shadow candidates on the XAUUSD feed (commercial track, exploratory)",
        "",
        "_`python -m app research gold-shadow build`, registered in `GOLD_SHADOW.md` (2026-11-07). "
        "XAUUSD 5m bars 2012-01 to 2026-01-09. Cost = the signal bar's recorded spread + $0.07 "
        "per oz; with slip adds $0.10 on every stop exit. Tune 2012-2021, check 2022 to "
        "2026-01-09. Seen data: optimistic. The lockbox was not read._",
        "",
        "## 1. OPEN: the 36 settings (by net R on 2012-2021)",
        "",
        "| Candle (NY) | Side | Min range (ATR 5m) | Management | Tune trades | Tune net | "
        "Tune years + | Check trades | Check net (SE) | Check with slip | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[fmt(r) for r in grid.itertuples()],
        "",
        f"Chosen: candle {choice['time']}, side {choice['direction']}, minimum range "
        f"{choice['min_range']:g} × ATR(5m), {choice['mgmt']}. "
        f"{'' if len(ok) else 'No setting was eligible; the best by tune net is shown. '}"
        "SCUTA's own rules: 09:30, EMA, no minimum, BAR (`OPEN-SCUTA`).",
        "",
        "## 2. The candidates",
        "",
        *HEAD,
    ]
    for k, t in c.items():
        lines += [_row(f"{k}, 2012-2021", t[t["year"] <= TUNE_END]),
                  _row(f"{k}, 2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END])]  # fmt: skip
    lines += ["", "## 3. Detail, 2012 to 2026-01-09 (decides nothing)", "",
              "Net R by year (trades):", "", *detail(c, nfp)]  # fmt: skip
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    """The candidates on FxPro's GOLD feed (``gold_live.fx_lines``), and the decision."""
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    fr = ge.frames_from_lines(gv.fx_lines(export))
    cx = gl.context(fr)
    c = {k: t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= gv.FX_START]
         for k, t in candidates(cx, choice).items()}  # fmt: skip
    exam = pd.Timestamp("2026-01-12", tz="UTC")
    lines = [
        "# Gold shadow candidates on FxPro's GOLD feed (commercial track, exploratory)",
        "",
        f"_`python -m app research gold-shadow fxpro`: `{export.name}`, bars from "
        f"{gv.FX_FIRST_DAY.decode()}, trades from {gv.FX_START.date()} to the export's end. Costs "
        "as `gold_shadow_xauusd.md`. OPEN's setting was chosen on XAUUSD 2012-2021: "
        f"{choice['time']}, {choice['direction']}, minimum {choice['min_range']:g} × ATR(5m), "
        f"{choice['mgmt']}._",
        "",
        "## 1. All, and 2026-01-12 on (used by no choice)",
        "",
        *HEAD,
    ]
    for k, t in c.items():
        placed = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True)
        lines += [_row(f"{k}, all", t), _row(f"{k}, 2026-01-12 on", t[placed >= exam])]
    lines += ["", "## 2. Detail (decides nothing)", "", "Net R by year (trades):", "",
              *detail(c, nfp_days(2015, 2026))]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-shadow")
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
