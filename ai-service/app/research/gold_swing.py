"""Gold: the daily trend swing (``docs/strategies/GOLD_SWING.md``, registered 2026-11-08).

    python -m app research gold-swing build                      # XAUUSD: tune, check
    python -m app research gold-swing fxpro --export <GOLD M1>   # FxPro GOLD, the decision

SWING buys a daily close above the N-day high (sells one below the N-day low) at the next open,
with an SL of 2 x ATR(20, D1). It exits at the SL or after a close beyond the M-day channel, at
the next open. The swap is an estimated scenario: longs pay 3% a year of the price a night.
The lockbox is not read."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_night as gn

REPORT = gl.OUT_DIR / "gold_swing_xauusd.md"  # not gold_swing.md: GOLD_SWING.md on Windows
FX_REPORT = gl.OUT_DIR / "gold_swing_fxpro.md"
CHOICE = gl.STORE / "gold_swing_choice.json"
TUNE_END = gc.TUNE_END
SETTINGS = [{"n": 20, "m": 10, "shorts": True}, {"n": 20, "m": 10, "shorts": False},
            {"n": 55, "m": 20, "shorts": True}, {"n": 55, "m": 20, "shorts": False}]  # fmt: skip
ATR_N, SL_ATR, SWAP_LONG, MIN_TRADES = 20, 2.0, 0.03, 40
DEMO_RISK = {"LVL4H": 0.5, "PIVOT": 0.5, "PIVW": 0.25, "ASIA": 0.25, "PWHL": 0.25, "SWING": 0.5}


def simulate(d1: pd.DataFrame, n: int, m: int, shorts: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The trades, and the daily marked-to-market R of the open trade (gross, by D1 bar)."""
    o, h, lo, c = (d1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    spread = d1["spread_mean"].to_numpy(float)
    day = pd.to_datetime(d1["close_utc"]).dt.tz_convert(gl.NY).dt.normalize().to_numpy()
    atr = gl.wilder(h, lo, c, ATR_N)
    hi_n = pd.Series(h).rolling(n).max().shift(1).to_numpy()
    lo_n = pd.Series(lo).rolling(n).min().shift(1).to_numpy()
    hi_m = pd.Series(h).rolling(m).max().shift(1).to_numpy()
    lo_m = pd.Series(lo).rolling(m).min().shift(1).to_numpy()
    trades, mtm = [], []
    pos, e, sl, risk, k_in, ref, cost, leave = 0, 0.0, 0.0, 0.0, 0, 0.0, 0.0, False
    for t in range(len(c)):
        if pos and leave:  # the channel exit, at this open
            mtm.append((t, pos * (o[t] - ref) / risk))
            trades.append((k_in, t, pos, e, o[t], risk, cost, "channel"))
            pos, leave = 0, False
        if pos:
            hit = lo[t] <= sl if pos > 0 else h[t] >= sl
            if hit:
                gap = o[t] < sl if pos > 0 else o[t] > sl
                px = o[t] if gap else sl
                mtm.append((t, pos * (px - ref) / risk))
                trades.append((k_in, t, pos, e, px, risk, cost, "sl"))
                pos = 0
            else:
                mtm.append((t, pos * (c[t] - ref) / risk))
                ref = c[t]
                leave = (c[t] < lo_m[t]) if pos > 0 else (c[t] > hi_m[t])
                if leave and t + 1 >= len(c):
                    leave = False
        if pos == 0 and t + 1 < len(c) and np.isfinite(hi_n[t]) and atr[t] > 0:
            d = 1 if c[t] > hi_n[t] else (-1 if shorts and c[t] < lo_n[t] else 0)
            if d:
                pos, e, risk, k_in = d, o[t + 1], SL_ATR * atr[t], t + 1
                sl, ref, cost, leave = e - d * risk, e, spread[t + 1] + gl.COMMISSION, False
                # the entry day itself: the SL is checked from that day's bar on (next loop)
    t = pd.DataFrame(trades, columns=["i", "j", "dir", "entry", "exit", "risk", "cost_px", "why"])
    t["gross"] = t["dir"] * (t["exit"] - t["entry"]) / t["risk"]
    nights = (day[t["j"]] - day[t["i"]]).astype("timedelta64[D]").astype(int)  # rollovers crossed
    t["days"] = nights
    t["swap"] = np.where(t["dir"] > 0, SWAP_LONG * t["entry"] * nights / 365, 0.0) / t["risk"]
    t["net_noswap"] = (
        t["gross"]
        - t["cost_px"] / t["risk"]
        - np.where(t["why"] == "sl", gl.SL_SLIP / t["risk"], 0)
    )
    t["net"] = t["net_noswap"] - t["swap"]
    t["year"] = pd.to_datetime(d1["close_utc"].to_numpy()[t["i"]], utc=True).year
    t["tday"] = t["i"]
    mt = pd.DataFrame(mtm, columns=["tday", "net"])
    for r in t.itertuples():  # the costs and the swap on the exit day
        mt.loc[len(mt)] = (r.j, (r.net_noswap - r.gross) - r.swap)
    mt["tday"] = mt["tday"].astype(int)
    return t, mt.groupby("tday", as_index=False)["net"].sum()


def summary(t: pd.DataFrame) -> dict:
    if not len(t):
        return {"trades": 0, "net": np.nan, "noswap": np.nan, "se": np.nan, "years_pos": np.nan}
    yr = t.groupby("year")["net"].mean()
    return {"trades": len(t), "net": t["net"].mean(), "noswap": t["net_noswap"].mean(),
            "se": t["net"].std(ddof=1) / np.sqrt(max(len(t), 2)),
            "years_pos": (yr > 0).mean()}  # fmt: skip


def _row(name: str, t: pd.DataFrame) -> str:
    s = summary(t)
    if not s["trades"]:
        return f"| {name} | 0 | - | - | - | - |"
    return (f"| {name} | {s['trades']} | {s['net']:+.3f} ({s['se']:.3f}) | {s['noswap']:+.3f} "
            f"| {s['years_pos']:.0%} | {t['days'].median():.0f} |")  # fmt: skip


HEAD = ["| Set | Trades | Net R with swap (SE) | Without swap | Years + | Days held (median) |",
        "| --- | --- | --- | --- | --- | --- |"]  # fmt: skip


def five_daily(cx: gl.Ctx, since: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The five day strategies' net R (with slip) per trading day, in R and in account % at the
    demo risks."""
    rows = []
    for k, t in gn.day_strategies(cx).items():
        if since is not None:
            t = t[pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True) >= since]
        rows.append(t.assign(pct=t["net_slip"] * DEMO_RISK[k]))
    a = pd.concat(rows)
    r = a.groupby("tday", as_index=False)["net_slip"].sum().rename(columns={"net_slip": "net"})
    return r, a.groupby("tday", as_index=False)["pct"].sum()


def account(five_pct: pd.DataFrame, swing_mt: pd.DataFrame | None) -> dict:
    x = five_pct.set_index("tday")["pct"]
    if swing_mt is not None:
        x = x.add(swing_mt.set_index("tday")["net"] * DEMO_RISK["SWING"], fill_value=0.0)
    cum = x.sort_index().cumsum().to_numpy()
    dd = float(np.max(np.maximum.accumulate(np.r_[0.0, cum])[1:] - cum))
    return {"total": float(cum[-1]), "dd": dd}


def extras(cx: gl.Ctx, t: pd.DataFrame, mt: pd.DataFrame, since: pd.Timestamp | None) -> list[str]:
    five_r, five_pct = five_daily(cx, since)
    corr = gn.correlations(mt, {"FIVE": five_r})["FIVE"]
    a, b = account(five_pct, None), account(five_pct, mt)
    return [
        f"Daily marked-to-market R correlation with the five together: **{corr:+.3f}**.",
        "",
        "| Account at demo risk | Total % | Largest drawdown % |",
        "| --- | --- | --- |",
        f"| The five | {a['total']:+.1f} | {a['dd']:.1f} |",
        f"| The five + SWING at 0.5% | {b['total']:+.1f} | {b['dd']:.1f} |",
        "",
        *HEAD,
        _row("Longs", t[t["dir"] > 0]),
        _row("Shorts", t[t["dir"] < 0]),
        "",
        "| Year | Trades | Net R with swap | Sum |",
        "| --- | --- | --- | --- |",
        *[
            f"| {y} | {len(g)} | {g['net'].mean():+.3f} | {g['net'].sum():+.2f} |"
            for y, g in t.groupby("year")
        ],
    ], corr  # type: ignore[return-value]


def build() -> str:
    cx = gl.context(gl.load())
    d1 = cx.d1
    rows = []
    for st in SETTINGS:
        t, _ = simulate(d1, **st)
        t = t[pd.to_datetime(d1["close_utc"].to_numpy()[t["i"]], utc=True) >= gl.START]
        a, b = summary(t[t["year"] <= TUNE_END]), summary(t[t["year"] > TUNE_END])
        rows.append({**st, **{f"tune_{k}": v for k, v in a.items()},
                     **{f"check_{k}": v for k, v in b.items()}})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = (
        (g["tune_net"] > 0) & (g["tune_years_pos"] >= 0.6) & (g["tune_trades"] >= MIN_TRADES)
    )
    g = g.sort_values("tune_net", ascending=False).reset_index(drop=True)
    lines = [
        "# Gold: the daily trend swing, XAUUSD feed (exploratory)",
        "",
        "_`python -m app research gold-swing build`, registered in `GOLD_SWING.md` (2026-11-08). "
        "XAUUSD D1 bars 2012 to 2026-01-09; cost = the entry day's mean spread + $0.07 per oz, "
        "$0.10 on stop exits; swap scenario: longs 3% a year. Seen data: optimistic._",
        "",
        "| N / M | Shorts | Tune trades | Tune net (swap) | Without swap | Tune years + "
        "| Check trades | Check net (swap) | Without swap | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.n} / {r.m} | {'yes' if r.shorts else 'no'} | {r.tune_trades} "
            f"| {r.tune_net:+.3f} | {r.tune_noswap:+.3f} | {r.tune_years_pos:.0%} "
            f"| {r.check_trades} | {r.check_net:+.3f} | {r.check_noswap:+.3f} "
            f"| {'yes' if r.eligible else ''} |"
            for r in g.itertuples()
        ],  # fmt: skip
        "",
    ]
    ok = g[g["eligible"]]
    if not len(ok):
        CHOICE.write_text("null\n", encoding="utf-8")
        return "\n".join([*lines, "**No setting qualifies: SWING is dropped.**"]) + "\n"
    choice = {
        "n": int(ok.iloc[0]["n"]),
        "m": int(ok.iloc[0]["m"]),
        "shorts": bool(ok.iloc[0]["shorts"]),
    }
    CHOICE.write_text(json.dumps(choice) + "\n", encoding="utf-8")
    t, mt = simulate(d1, **choice)
    keep = pd.to_datetime(d1["close_utc"].to_numpy()[t["i"]], utc=True) >= gl.START
    t = t[keep]
    ex, _ = extras(cx, t, mt[mt["tday"] >= (t["i"].min() if len(t) else 0)], None)
    lines += [f"Chosen: {choice}.", "", *HEAD, _row("2012-2021", t[t["year"] <= TUNE_END]),
              _row("2022 to 2026-01-09 (check)", t[t["year"] > TUNE_END]), "", *ex]  # fmt: skip
    return "\n".join(lines) + "\n"


def fxpro(export: Path) -> str:
    choice = json.loads(CHOICE.read_text(encoding="utf-8"))
    if choice is None:
        return "# Gold daily swing on FxPro's GOLD feed\n\nSWING was dropped on XAUUSD.\n"
    cx = gl.context(ge.frames_from_lines(gv.fx_lines(export)))
    t, mt = simulate(cx.d1, **choice)
    start = pd.to_datetime(cx.d1["close_utc"].to_numpy()[t["i"]], utc=True) >= gv.FX_START
    t = t[start]
    mt = mt[mt["tday"] >= t["i"].min()]
    ex, corr = extras(cx, t, mt, gv.FX_START)
    s = summary(t)
    met = s["net"] > 0 and abs(corr) <= gn.MAX_CORR
    since26 = pd.to_datetime(cx.d1["close_utc"].to_numpy()[t["i"]], utc=True) >= pd.Timestamp(
        "2026-01-12", tz="UTC"
    )
    lines = [
        "# Gold: the daily trend swing, FxPro's GOLD feed (exploratory)",
        "",
        f"_`python -m app research gold-swing fxpro`: `{export.name}`, trades from "
        f"{gv.FX_START.date()}. Setting chosen on XAUUSD 2012-2021: {choice}._",
        "",
        *HEAD,
        _row("All", t),
        _row("2026-01-12 on", t[since26]),
        "",
        *ex,
        "",
        f"Conditions 3 and 4: **{'met' if met else 'not met'}**.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-swing")
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
