"""Gold combination (commercial track, exploratory; ``gold_lab.py`` has the rules and costs).

    python -m app research gold-combo build      # tune, combine, AI filter, MT5 trade file

The screen (``gold_lab_screen.md``) left one survivor: the level break at the first touch of the
day of PDH, PDL, 5DH and 5DL, with D = ATR(14, 4h), under M8 (LVL4H). The pivot version (PIVOT, M8)
shares the mechanism and is the only other candidate with net R > 0 in both halves.

1. **Tune** LVL4H on 2012-2021 only (the distance multiple, the entry window, a cost cap), keeping
   only settings with >= 60% of years positive; the best by mean net R. **Check** it on 2022 to
   2026-01-09, which the tuning did not use.
2. **Combine** the tuned LVL4H with PIVOT (fixed), each with one active trade.
3. **AI filter** (a LightGBM regressor of net R from the context at entry: level type, side,
   New York hour, weekday, cost in R, volatility ratios, the previous day's range, the gap at
   entry, the predicted range), walk-forward by year: trained on every earlier year, it keeps a
   trade when its predicted net R is above zero. Compared with taking every trade, per year.
4. **Trade file** for ``tools/mt5/GoldCombo.mq5``: every trade of the final combination with its
   entry, SL, TP, exit time and M8 SL moves, on the server clock. Written to MT5's Common Files.

Writes ``docs/strategies/gold_combo.md``. The lockbox is not read."""

from __future__ import annotations

import argparse
import itertools
import os
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_lab as gl

REPORT = gl.OUT_DIR / "gold_combo.md"
TUNE_END = 2021
WINDOWS = {"02-16": (120, 16 * 60), "07-16": (7 * 60, 16 * 60), "08-12": (8 * 60, 12 * 60)}
MULTS = (0.75, 1.0, 1.5)
CAPS = (None, 0.05)
LEVEL_KINDS = ("PDH", "PDL", "5DH", "5DL")


def levels(cx: gl.Ctx, name: str, lv_days: dict[str, np.ndarray], dist: np.ndarray,
           window: tuple[int, int], horizon: int, cap: float | None) -> pd.DataFrame:  # fmt: skip
    """First touch of the day of each level within the New York ``window``: a stop entry with the
    break (as ``gold_lab._level_trades``), with the level kind kept."""
    prev = np.r_[np.nan, cx.c[:-1]]
    ok = (cx.weekday < 5) & (cx.ny_min >= window[0]) & (cx.ny_min < window[1])
    ok &= np.isfinite(dist) & (dist > 0)
    out = []
    for kind, lv_day in lv_days.items():
        lv = lv_day[np.maximum(cx.day_idx, 0)]
        up = (prev < lv) & (cx.h >= lv)
        dn = (prev > lv) & (cx.lo <= lv)
        idx = np.flatnonzero(ok & (up | dn) & np.isfinite(lv))
        first = pd.Series(idx).groupby(cx.day_idx[idx]).min().to_numpy()
        d = np.where(up[first], 1.0, -1.0)
        entry = np.where(d > 0, np.maximum(lv[first], cx.o[first]), np.minimum(lv[first], cx.o[first]))
        out.append(pd.DataFrame({
            "strategy": name, "i": first, "dir": d, "entry": entry, "risk": dist[first], "tp_r": 1.0,
            "end": np.minimum(first + horizon, cx.deadline[first]), "kind": kind, "level": lv[first],
        }))  # fmt: skip
    s = pd.concat(out, ignore_index=True)
    s = s[(s["end"] > s["i"]) & (s["i"] > 5)]
    if cap is not None:
        s = s[(cx.spread[s["i"]] + gl.COMMISSION) / s["risk"] <= cap]
    t = pd.to_datetime(cx.m["close_utc"].to_numpy()[s["i"]], utc=True)
    return s[t >= gl.START].reset_index(drop=True)


def day_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    dh, dl = cx.d1["high"].to_numpy(), cx.d1["low"].to_numpy()
    return {"PDH": np.r_[np.nan, dh[:-1]], "PDL": np.r_[np.nan, dl[:-1]],
            "5DH": pd.Series(dh).rolling(5).max().shift(1).to_numpy(),
            "5DL": pd.Series(dl).rolling(5).min().shift(1).to_numpy()}  # fmt: skip


def pivot_levels(cx: gl.Ctx) -> dict[str, np.ndarray]:
    h, lo, c = (cx.d1[k].to_numpy() for k in ("high", "low", "close"))
    p = (h + lo + c) / 3
    return {"R1": np.r_[np.nan, (2 * p - lo)[:-1]], "S1": np.r_[np.nan, (2 * p - h)[:-1]]}


def run(sig: pd.DataFrame, cx: gl.Ctx, events: list | None = None) -> pd.DataFrame:
    """M8 trades of ``sig`` with the signal's columns and the year, net R and net with SL slip."""
    t = gl.simulate(sig, cx, "M8", events)
    keep = sig.drop_duplicates(["strategy", "i"]).drop(columns=["dir", "risk"])
    t = t.merge(keep, on=["strategy", "i"], how="left")
    t["year"] = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True).year
    t["net"] = t["gross"] - t["cost"]
    t["net_slip"] = t["net"] - np.where(t["exit"] == "sl", gl.SL_SLIP / t["risk"], 0.0)
    return t


def summary(t: pd.DataFrame) -> dict:
    yr = t.groupby("year")["net"].mean()
    return {"trades": len(t), "net": t["net"].mean(), "net_slip": t["net_slip"].mean(),
            "years_pos": (yr > 0).mean(), "se": t["net"].std(ddof=1) / np.sqrt(max(len(t), 2))}  # fmt: skip


def tune(cx: gl.Ctx) -> pd.DataFrame:
    rows = []
    for mult, (wname, win), cap in itertools.product(MULTS, WINDOWS.items(), CAPS):
        t = run(levels(cx, "LVL4H", day_levels(cx), mult * cx.atr4h, win, 200, cap), cx)
        a, b = t[t["year"] <= TUNE_END], t[t["year"] > TUNE_END]
        sa, sb = summary(a), summary(b)
        rows.append({"mult": mult, "window": wname, "cap": cap, "tune_trades": sa["trades"],
                     "tune_net": sa["net"], "tune_years_pos": sa["years_pos"],
                     "check_trades": sb["trades"], "check_net": sb["net"], "check_se": sb["se"]})  # fmt: skip
    g = pd.DataFrame(rows)
    g["eligible"] = g["tune_years_pos"] >= 0.6
    return g.sort_values("tune_net", ascending=False).reset_index(drop=True)


# --- AI filter -------------------------------------------------------------------------------

FEATURES = ["kind_code", "dir", "hour", "weekday", "cost", "atr1h_4h", "atr4h_d", "prev_range",
            "gap_at_entry", "pred_range"]  # fmt: skip


def features(t: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    i = t["i"].to_numpy()
    rng_d = (cx.d1["high"] - cx.d1["low"]).to_numpy()
    ad = gl.wilder(*(cx.d1[k].to_numpy() for k in ("high", "low", "close")))
    di = np.maximum(cx.day_idx[i], 1)
    # a simple range forecast: the mean 5m range of the last 12 bars against the last 288, both
    # known at the entry bar
    r5 = pd.Series(cx.h - cx.lo)
    pred = (r5.rolling(12).mean() / r5.rolling(288).mean()).to_numpy()
    kinds = {k: n for n, k in enumerate(sorted(t["kind"].dropna().unique()))}
    return pd.DataFrame({
        "kind_code": t["kind"].map(kinds).to_numpy(), "dir": t["dir"].to_numpy(),
        "hour": cx.ny_min[i] // 60, "weekday": cx.weekday[i], "cost": t["cost"].to_numpy(),
        "atr1h_4h": cx.atr1h[i] / cx.atr4h[i], "atr4h_d": cx.atr4h[i] / cx.atrd[i],
        "prev_range": rng_d[di - 1] / ad[di - 1],
        "gap_at_entry": t["dir"].to_numpy() * (t["entry"] - t["level"]).to_numpy() / t["risk"].to_numpy(),
        "pred_range": pred[i],
    })  # fmt: skip


def ai_filter(t: pd.DataFrame, cx: gl.Ctx, first_test: int = 2015) -> pd.DataFrame:
    """Walk-forward by year: the predicted net R of each trade from a model fitted on every
    earlier year; ``take`` when it is above zero (every trade before ``first_test``)."""
    import lightgbm as lgb

    x = features(t, cx)
    y = t["net"].to_numpy()
    pred = np.full(len(t), np.nan)
    for year in range(first_test, int(t["year"].max()) + 1):
        tr, te = (t["year"] < year).to_numpy(), (t["year"] == year).to_numpy()
        if te.sum() == 0 or tr.sum() < 500:
            continue
        m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15,
                              min_child_samples=80, subsample=0.8, subsample_freq=1,
                              colsample_bytree=0.8, random_state=20261104, verbose=-1)  # fmt: skip
        m.fit(x[tr], y[tr])
        pred[te] = m.predict(x[te])
    return t.assign(pred=pred, take=np.where(np.isnan(pred), True, pred > 0))


# --- MT5 trade file --------------------------------------------------------------------------


def trade_file(t: pd.DataFrame, events: list, cx: gl.Ctx, path: Path) -> None:
    """id, strategy, dir, place / expire / exit times (server), entry (the level: a stop order),
    sl, the M8 SL moves as "time@sl;time@sl", and take (1 when the AI filter keeps it)."""
    def server(idx, col="ts_utc"):  # the open (ts_utc) or the close (close_utc) of 5m bars
        u = pd.to_datetime(cx.m[col].to_numpy()[idx], utc=True)
        return u.tz_convert("Europe/Athens").tz_localize(None).strftime("%Y.%m.%d %H:%M:%S")

    ev = pd.DataFrame(events, columns=["strategy", "i", "k", "sl"])
    ev = ev.merge(t[["strategy", "i"]], on=["strategy", "i"])
    ev["when"] = server(ev["k"].to_numpy() - 1, "close_utc")  # in force after that bar
    moves = ev.groupby(["strategy", "i"]).apply(
        lambda g: ";".join(f"{w}@{s:.2f}" for w, s in zip(g["when"], g["sl"])), include_groups=False
    )
    i = t["i"].to_numpy()
    out = pd.DataFrame({
        "id": t["id"], "strategy": t["strategy"], "dir": np.where(t["dir"] > 0, "buy", "sell"),
        "place_server": server(i), "expire_server": server(i, "close_utc"),
        "exit_server": server(t["end"].to_numpy(), "close_utc"),
        "entry": t["level"].round(2), "sl": (t["level"] - t["dir"] * t["risk"]).round(2),
        "moves": [moves.get((s, k), "") for s, k in zip(t["strategy"], i)],
        "take": t["take"].astype(int).to_numpy(),
    })  # fmt: skip
    out.to_csv(path, index=False, lineterminator="\r\n")


def common_files() -> Path | None:
    appdata = os.environ.get("APPDATA")
    p = Path(appdata) / "MetaQuotes" / "Terminal" / "Common" / "Files" if appdata else None
    return p if p is not None and p.is_dir() else None


def _fmt(d: dict) -> str:
    return (f"{d['trades']:,} | {d['net']:+.3f} ({d['se']:.3f}) | {d['net_slip']:+.3f} "
            f"| {d['years_pos']:.0%}")  # fmt: skip


RANK = {"closed": 0, "expired": 1, "failed": 2, "skipped": 3, "open_at_end": 4,
        "pending_at_end": 5, "not_reached": 6}  # fmt: skip


def compare(folder: Path) -> str:
    """The MT5 replay (gold_combo_replay*.csv, parts merged) against the Python simulation."""
    t = pd.read_parquet(gl.STORE / "gold_combo_trades.parquet")
    res = pd.concat([pd.read_csv(f) for f in sorted(folder.glob("gold_combo_replay*.csv"))])
    res = res.assign(rank=res["status"].map(RANK).fillna(9)).sort_values(["id", "rank"])
    res = res.drop_duplicates("id").drop(columns=["rank", "strategy"])
    j = t.merge(res, on="id", how="left")
    done = j["status"] == "closed"
    money = j["risk_money"].where(j["risk_money"] > 0)
    j["mt5"] = ((j["profit"] + j["commission"] + j["fee"] + j["swap"]) / money).where(done)
    c = j[done]
    status = j["status"].fillna("missing").value_counts().to_dict()
    lines = [
        "# Gold combination in the MT5 Strategy Tester (commercial track, exploratory)",
        "",
        '_`tools/mt5/GoldCombo.mq5`, "Every tick based on real ticks" (where the broker has no '
        "real ticks, MT5 generates them from M1 bars: the tester log says which); parts merged. "
        f"Statuses: {status}. Net R = "
        "(profit + commission + fee + swap) / the money risk of the level and SL. Python = the "
        "simulation of `gold_combo.md` on the same trades._",
        "",
        "| Set | Trades | MT5 net R | Python net R | Python net with slip |",
        "| --- | --- | --- | --- | --- |",
    ]
    sets = [("All replayed", c), ("AI filter kept", c[c["take"]]),
            *[(f"{k}", g) for k, g in c.groupby("strategy")]]  # fmt: skip
    for name, g in sets:
        lines.append(f"| {name} | {len(g):,} | {g['mt5'].mean():+.3f} | {g['net'].mean():+.3f} "
                     f"| {g['net_slip'].mean():+.3f} |")  # fmt: skip
    lines += ["", "| Year | Trades | MT5 net R | Python net R |", "| --- | --- | --- | --- |"]
    lines += [f"| {y} | {len(g):,} | {g['mt5'].mean():+.3f} | {g['net'].mean():+.3f} |"
              for y, g in c.groupby("year")]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-combo")
    ap.add_argument("step", choices=("build", "compare"))
    args = ap.parse_args(argv)
    if args.step == "compare":
        out = gl.OUT_DIR / "gold_combo_mt5.md"
        out.write_text(compare(common_files()), encoding="utf-8", newline="\n")
        print(f"wrote {out}")
        return 0
    fr = gl.load()
    cx = gl.context(fr)
    grid = tune(cx)
    best = grid[grid["eligible"]].iloc[0]
    win = WINDOWS[best["window"]]
    cap = None if pd.isna(best["cap"]) else float(best["cap"])
    events: list = []
    lvl = run(levels(cx, "LVL4H", day_levels(cx), best["mult"] * cx.atr4h, win, 200, cap), cx, events)
    piv = run(levels(cx, "PIVOT", pivot_levels(cx), cx.atr1h, WINDOWS["02-16"], 48, None), cx, events)
    combo = pd.concat([lvl, piv], ignore_index=True)
    ai = ai_filter(combo, cx).sort_values(["i", "strategy"], kind="stable").reset_index(drop=True)
    ai["id"] = np.arange(1, len(ai) + 1)
    taken = ai[ai["take"]]
    lines = [
        "# Gold combination (commercial track, exploratory)",
        "",
        "_XAUUSD 2012-01 to 2026-01-09, M8, real costs (recorded spread + $0.07 per oz); net with "
        "slip adds $0.10 on stop exits. Tuned on 2012-2021 only; 2022-2026 is the check. Seen data:"
        " optimistic. The lockbox was not read._",
        "",
        "## 1. LVL4H tuning (2012-2021) and its check (2022-2026)",
        "",
        "| D x ATR(4h) | Window (NY) | Cost cap | Tune trades | Tune net | Tune years + | Check trades "
        "| Check net (SE) | Eligible |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[f"| {r.mult} | {r.window} | {r.cap if r.cap == r.cap else '-'} | {r.tune_trades:,} "
          f"| {r.tune_net:+.3f} | {r.tune_years_pos:.0%} | {r.check_trades:,} "
          f"| {r.check_net:+.3f} ({r.check_se:.3f}) | {'yes' if r.eligible else ''} |"
          for r in grid.itertuples()],  # fmt: skip
        "",
        f"Chosen: D = {best['mult']} x ATR(4h), window {best['window']}, cost cap {cap or '-'}.",
        "",
        "## 2. The combination",
        "",
        "| Set | Trades | Net R (SE) | Net with slip | Years + |",
        "| --- | --- | --- | --- | --- |",
        f"| LVL4H, all years | {_fmt(summary(lvl))} |",
        f"| PIVOT, all years | {_fmt(summary(piv))} |",
        f"| Combination, all years | {_fmt(summary(combo))} |",
        f"| Combination, 2022-2026 (check) | {_fmt(summary(combo[combo['year'] > TUNE_END]))} |",
        "",
        "## 3. AI filter (walk-forward by year from 2015)",
        "",
        "| Set | Trades | Net R (SE) | Net with slip | Years + |",
        "| --- | --- | --- | --- | --- |",
        f"| Every trade, 2015-2026 | {_fmt(summary(ai[ai['year'] >= 2015]))} |",
        f"| Taken by the filter, 2015-2026 | {_fmt(summary(taken[taken['year'] >= 2015]))} |",
        f"| Every trade, 2022-2026 | {_fmt(summary(ai[ai['year'] > TUNE_END]))} |",
        f"| Taken by the filter, 2022-2026 | {_fmt(summary(taken[taken['year'] > TUNE_END]))} |",
        "",
        "| Year | Trades | Net R, every trade | Taken | Net R, taken |",
        "| --- | --- | --- | --- | --- |",
    ]
    for y, g in ai.groupby("year"):
        k = g[g["take"]]
        lines.append(f"| {y} | {len(g)} | {g['net'].mean():+.3f} | {len(k)} | {k['net'].mean():+.3f} |")
    days = len(np.unique(cx.ny_day[(cx.m["close_utc"] >= gl.START).to_numpy()]))
    lines += ["", f"Trades a trading day: every trade {len(combo) / days:.2f}, taken {len(taken) / days:.2f}."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    ai.to_parquet(gl.STORE / "gold_combo_trades.parquet", index=False)
    common = common_files()
    for target in [gl.STORE / "gold_combo_trades.csv", *([common / "gold_combo_trades.csv"] if common else [])]:
        trade_file(ai, events, cx, target)
    print(f"wrote {REPORT}")
    return 0
