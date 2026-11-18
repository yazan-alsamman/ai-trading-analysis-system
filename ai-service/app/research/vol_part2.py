"""Gold volatility forecast, part 2 (``docs/vol/VOL_PART2.md``, registered 2026-11-12).

    python -m app research vol-part2 --export <GOLD M1 export>

VOL: the five's D (0.75 x ATR(4h); PIVOT ATR(1h)) times ratio(d) = exp((f_M3 - f_M1) / 2),
clipped to [0.67, 1.5], from part 1's out-of-sample forecasts; BASE: ratio 1. Per New York day,
the sum of the five's net R with slip; the difference VOL - BASE by a 4-week block bootstrap on
the research store 2018-01-02 to 2026-01-09, and a readout on FxPro 2026-01-12 to 2026-11-05 (M3
and M1 fitted on every research-store day). ROUND is reported, not tested."""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import decide as dc
from app.research import gold_combo as gc
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_round as gr
from app.research import gold_shadow as gs
from app.research import vol_forecast as vf

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "vol" / "vol_part2_result.md"  # not VOL_PART2.md (Windows case)
DEFAULT_EXPORT = Path("D:/GOLD_M1_201501020000_202611052359.csv")
CLIP = (0.67, 1.5)
FIVE = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
STORE_FROM = pd.Timestamp("2018-01-01", tz="UTC")
SPLIT = 20220101  # segments: before / from this New York day
FX_FROM, FX_LAST = pd.Timestamp("2026-01-12"), pd.Timestamp("2026-11-05")
BOOT, SEED = 10_000, 20261114


def ratio(f1: np.ndarray, f3: np.ndarray) -> np.ndarray:
    return np.clip(np.exp((np.asarray(f3) - np.asarray(f1)) / 2), *CLIP)


def day_int(index: pd.DatetimeIndex) -> np.ndarray:
    return (index.year * 10000 + index.month * 100 + index.day).to_numpy()


def bar_scale(ny_day: np.ndarray, days: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Each bar's ratio from its New York day; 1 where the day has no forecast."""
    m = pd.Series(r, index=days)
    return pd.Series(ny_day).map(m).fillna(1.0).to_numpy()


def trades(cx0: gl.Ctx, scale: np.ndarray, start: pd.Timestamp) -> pd.DataFrame:
    """The five and ROUND as ``gold_live.five_trades`` with every D times ``scale`` (per bar)."""
    cx = dataclasses.replace(cx0, atr4h=cx0.atr4h * scale, atr1h=cx0.atr1h * scale)
    events: list = []
    lvl = gc.levels(
        cx,
        "LVL4H",
        gc.day_levels(cx),
        ge.LVL_MULT * cx.atr4h,
        gc.WINDOWS[ge.LVL_WINDOW],
        ge.LVL_HORIZON,
        ge.LVL_CAP,
    )
    piv = gc.levels(
        cx, "PIVOT", gc.pivot_levels(cx), cx.atr1h, gc.WINDOWS[ge.PIV_WINDOW], ge.PIV_HORIZON, None
    )
    parts = [gc.run(lvl, cx, events), gc.run(piv, cx, events)]
    parts += [gs.level_run(cx, k, lv, events) for k, lv in gs.shadow_levels(cx).items()]
    parts.append(gs.level_run(cx, "ROUND", gr.round_levels(cx, gr.SHADOW_STEP), events))
    t = pd.concat(parts, ignore_index=True)
    placed = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True)
    t = t[placed >= start].copy()
    t["ny_day"] = cx.ny_day[t["i"].to_numpy()]
    return t[["strategy", "i", "ny_day", "risk", "exit", "net", "net_slip"]].reset_index(drop=True)


def day_sums(base: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """Per New York day with a trade of the five in either: S_BASE, S_VOL, x = S_VOL - S_BASE."""
    b = base[base["strategy"].isin(FIVE)].groupby("ny_day")["net_slip"].sum()
    v = vol[vol["strategy"].isin(FIVE)].groupby("ny_day")["net_slip"].sum()
    d = pd.DataFrame({"base": b, "vol": v}).fillna(0.0).sort_index()
    d["x"] = d["vol"] - d["base"]
    return d


def boot(d: pd.DataFrame) -> dict:
    ts = pd.to_datetime(d.index.astype(str), format="%Y%m%d")
    blocks = dc.block_ids(vf.at_ny(ts, vf.W_FROM))
    (star,), k = dc.bootstrap([d["x"].to_numpy()], blocks, BOOT, np.random.default_rng(SEED))
    return {
        "mean": d["x"].mean(),
        "lo": np.percentile(star, 2.5),
        "hi": np.percentile(star, 97.5),
        "p": (1 + np.count_nonzero(star <= 0)) / (BOOT + 1),
        "k": k,
        "days": len(d),
    }


def per_trade(t: pd.DataFrame) -> tuple[int, float]:
    f = t[t["strategy"].isin(FIVE)]
    return len(f), float(f["net_slip"].mean())


# --- the report ---------------------------------------------------------------------------------


def side_table(name: str, base: pd.DataFrame, vol: pd.DataFrame, d: pd.DataFrame) -> list[str]:
    nb, mb = per_trade(base)
    nv, mv = per_trade(vol)
    return [
        f"| {name} | {len(d):,} | {nb:,} / {nv:,} | {mb:+.4f} / {mv:+.4f} "
        f"| {d['base'].sum():+.1f} / {d['vol'].sum():+.1f} | {d['x'].mean():+.4f} |"
    ]


def quintiles(base: pd.DataFrame, key: pd.Series, label: str) -> list[str]:
    f = base[base["strategy"].isin(FIVE)].copy()
    f["key"] = f["ny_day"].map(key)
    f = f.dropna(subset=["key"])
    f["q"] = pd.qcut(f["key"].rank(method="first"), 5, labels=False)
    out = [
        f"| {label} quintile | Trades | Mean net R with slip (SE) | Win share |",
        "| --- | --- | --- | --- |",
    ]
    for q, g in f.groupby("q"):
        se = g["net_slip"].std(ddof=1) / np.sqrt(len(g))
        out.append(
            f"| {q + 1} | {len(g):,} | {g['net_slip'].mean():+.4f} ({se:.4f}) "
            f"| {(g['net_slip'] > 0).mean():.1%} |"
        )
    return out


def report(st: dict, fx: dict) -> str:
    d, base, vol, fc = st["d"], st["base"], st["vol"], st["fc"]
    b = boot(d)
    seg = {"2018-2021": d[d.index < SPLIT], "2022 to 2026-01-09": d[d.index >= SPLIT]}
    nb, mb = per_trade(base)
    nv, mv = per_trade(vol)
    c1 = b["mean"] > 0 and b["p"] < 0.05
    c2 = all(g["x"].mean() > 0 for g in seg.values())
    c3 = mv >= mb
    passed = c1 and c2 and c3
    fx_x = fx["d"]["x"].mean()
    lines = [
        "# Gold volatility forecast, part 2: result",
        "",
        "_`python -m app research vol-part2`, registered in `VOL_PART2.md`. VOL = the five's D x "
        f"ratio(d), ratio = exp((f_M3 - f_M1) / 2) clipped to {CLIP}; BASE = the five as they "
        "trade."
        f" Per New York day: the sum of the five's net R with slip. 4-week block bootstrap, "
        f"{BOOT:,} resamples, seed {SEED}._",
        "",
        "## Decision",
        "",
        f"1. mean x > 0 with p < 0.05: **{'yes' if c1 else 'no'}** ({b['mean']:+.4f} R a day, "
        f"95% {b['lo']:+.4f} to {b['hi']:+.4f}, p {b['p']:.4f}, {b['k']} blocks)",
        "2. mean x > 0 in both segments: **"
        + ("yes" if c2 else "no")
        + "** ("
        + ", ".join(f"{k} {g['x'].mean():+.4f}" for k, g in seg.items())
        + ")",
        f"3. mean net R a trade VOL >= BASE: **{'yes' if c3 else 'no'}** ({mv:+.4f} vs {mb:+.4f})",
        "",
    ]
    if passed:
        lines.append(
            f"**VOL passes.** FxPro 2026-01-12 to 2026-11-05 (unseen): mean x {fx_x:+.4f}"
            + (
                " >= 0: it may go to the EA (a separate step)."
                if fx_x >= 0
                else " < 0: the change stops here."
            )
        )
    else:
        lines.append(
            "**VOL does not pass.** The five keep the ATR; the forecast serves the "
            'product\'s "expected range today" only. '
            f"(FxPro 2026, reported: mean x {fx_x:+.4f} R a day.)"
        )
    lines += [
        "",
        "## Both sides",
        "",
        "| Data | Days | Trades BASE / VOL | Net R a trade BASE / VOL | Total R BASE / VOL "
        "| Mean x (R a day) |",
        "|" + " --- |" * 6,
        *side_table("Store 2018 to 2026-01-09", base, vol, d),
        *[
            side_table(k, base[base["ny_day"].isin(g.index)], vol[vol["ny_day"].isin(g.index)], g)[
                0
            ]
            for k, g in seg.items()
        ],
        *side_table("FxPro 2026-01-12 to 2026-11-05", fx["base"], fx["vol"], fx["d"]),
        "",
        "## Per strategy (store 2018 to 2026-01-09; ROUND not in the test)",
        "",
        "| Strategy | Trades BASE / VOL | Net R a trade BASE / VOL | Total R BASE / VOL |",
        "| --- | --- | --- | --- |",
    ]
    for k in (*FIVE, "ROUND"):
        gb, gv_ = base[base["strategy"] == k], vol[vol["strategy"] == k]
        lines.append(
            f"| {k} | {len(gb):,} / {len(gv_):,} | {gb['net_slip'].mean():+.4f} / "
            f"{gv_['net_slip'].mean():+.4f} | {gb['net_slip'].sum():+.1f} / "
            f"{gv_['net_slip'].sum():+.1f} |"
        )
    lines += [
        "",
        "## Per year (store)",
        "",
        "| Year | Days | Total R BASE | Total R VOL | Mean x |",
        "| --- | --- | --- | --- | --- |",
    ]
    for y, g in d.groupby(d.index // 10000):
        lines.append(
            f"| {y} | {len(g)} | {g['base'].sum():+.1f} | {g['vol'].sum():+.1f} "
            f"| {g['x'].mean():+.4f} |"
        )
    r = fc["ratio"]
    lines += [
        "",
        "## The ratio (store test days)",
        "",
        "Deciles 10% ... 90%: "
        + ", ".join(f"{q:.2f}" for q in r.quantile(np.arange(1, 10) / 10))
        + f"; clipped low {(r <= CLIP[0]).mean():.1%}, high {(r >= CLIP[1]).mean():.1%}.",
        "",
        f"Mean ratio on TOP3 news days {r[fc['top3'] > 0].mean():.2f}, other days "
        f"{r[fc['top3'] == 0].mean():.2f}.",
        "",
        "## The five's BASE trades by the day's forecast (description only)",
        "",
    ]
    lines += quintiles(base, fc["f_M3"], "M3 forecast (low to high)")
    lines += [""] + quintiles(base, fc["ratio"], "Ratio M3 / ATR (low to high)")
    lines += ["", "Any filter these suggest needs its own registration.", ""]
    return "\n".join(lines)


def store_side() -> dict:
    fr = gl.load()
    cal = pd.read_parquet(vf.CAL)
    u = vf.features(fr["5m"], fr["4h"], cal)
    f, _ = vf.walk(u)
    f["ratio"] = ratio(f["f_M1"], f["f_M3"])
    cx = gl.context(fr)
    scale = bar_scale(cx.ny_day, day_int(f.index), f["ratio"].to_numpy())
    base = trades(cx, np.ones(len(scale)), STORE_FROM)
    vol = trades(cx, scale, STORE_FROM)
    fc = f.set_index(pd.Index(day_int(f.index)))
    return {"u": u, "cal": cal, "base": base, "vol": vol, "d": day_sums(base, vol), "fc": fc}


def fx_side(export: Path, u: pd.DataFrame, cal: pd.DataFrame) -> dict:
    fr = ge.frames_from_lines(gv.fx_lines(export))  # FxPro's own GOLD feed, as gold_live.fxpro
    y = u["y"].to_numpy()
    b1, _ = vf.ols(u[vf.X["M1"]].to_numpy(), y)
    b3, _ = vf.ols(u[vf.X["M3"]].to_numpy(), y)
    w = vf.features(fr["5m"], fr["4h"], cal, FX_FROM, FX_LAST)

    def fit(beta, cols):
        return np.c_[np.ones(len(w)), w[cols].to_numpy()] @ beta

    r = ratio(fit(b1, vf.X["M1"]), fit(b3, vf.X["M3"]))
    cx = gl.context(fr)
    scale = bar_scale(cx.ny_day, day_int(w.index), r)
    start = vf.at_ny(pd.DatetimeIndex([FX_FROM]), 0)[0]
    base = trades(cx, np.ones(len(scale)), start)
    vol = trades(cx, scale, start)
    last = int(FX_LAST.strftime("%Y%m%d"))
    base, vol = base[base["ny_day"] <= last], vol[vol["ny_day"] <= last]
    return {"base": base, "vol": vol, "d": day_sums(base, vol)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vol-part2")
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    a = ap.parse_args(argv or [])
    st = store_side()
    fx = fx_side(a.export, st["u"], st["cal"])
    REPORT.write_text(report(st, fx), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
