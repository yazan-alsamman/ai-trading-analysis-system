"""Gold volatility forecast, part 1 (``docs/vol/VOL_FORECAST.md``, registered 2026-11-12).

    python -m app research vol-forecast

Forecasts log RV of the five's window (5m bars opening 02:00 to closing 16:45 New York) at 02:00
New York, walk-forward 2018-2025 with expanding train from 2012; M0 last, M1 ATR (the incumbent),
M2 HAR, M3 HAR + news, M4 LightGBM; QLIKE against M1, 4-week block bootstrap, Holm. No trade is
simulated. The calendar's scheduled time, currency and importance are the only calendar fields
read."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.discovery.events import TOP3
from app.research import decide as dc
from app.research import gold_lab as gl

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "data" / "processed" / "calendar.parquet"
REPORT = ROOT / "docs" / "vol" / "vol_forecast_result.md"  # not VOL_FORECAST.md (Windows case)
NY = "America/New_York"
W_FROM, W_END = 2 * 60, 16 * 60 + 45  # window: bar opens >= 02:00, closes <= 16:45 New York
W_BARS = (W_END - W_FROM) // 5  # 177
MIN_SHARE, MAX_GAP = 0.9, 30  # share of window bars, longest missing time (minutes)
EARLY = 8 * 60 + 30
FIRST, LAST = pd.Timestamp("2012-01-02"), pd.Timestamp("2026-01-09")
TEST_YEARS = tuple(range(2018, 2026))
HOLD_FROM = pd.Timestamp("2024-07-01")
BOOT, SEED, LGB_SEED = 10_000, 20261113, 20261112
FED = "Fed Interest Rate Decision"
MODELS = ("M0", "M1", "M2", "M3", "M4")
HAR = ["rv1", "rv5", "rv22", "on"]
NEWS = ["top3", "fed", "uh1", "uh2", "early"]
WEEK = ["tue", "wed", "thu", "fri"]
X = {"M1": ["atr"], "M2": HAR, "M3": HAR + NEWS + WEEK, "M4": HAR + NEWS + WEEK + ["atr"]}
LGB = dict(num_leaves=7, n_estimators=300, learning_rate=0.03, min_child_samples=50,
           subsample=0.8, subsample_freq=1, colsample_bytree=1.0, random_state=LGB_SEED,
           deterministic=True, force_row_wise=True, n_jobs=1, verbose=-1)  # fmt: skip


# --- the days ----------------------------------------------------------------------------------


def at_ny(days: pd.DatetimeIndex | pd.Series, minutes: int) -> pd.DatetimeIndex:
    """The UTC instant of ``minutes`` after New York midnight on each (naive) date."""
    d = pd.DatetimeIndex(days) + pd.Timedelta(minutes=minutes)
    return d.tz_localize(NY).tz_convert("UTC")


def days(m: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """One row per New York weekday with window bars (RV, bars, missing time, range, the price
    at 02:00, the bars closing by 02:00 and by 16:45) and the running sum of squared returns."""
    ny = m["ts_utc"].dt.tz_convert(NY)
    omin = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
    c = m["close"].to_numpy(float)
    r2 = np.r_[0.0, np.diff(np.log(c))] ** 2
    win = (omin >= W_FROM) & (omin + 5 <= W_END) & (ny.dt.day_of_week < 5).to_numpy()
    w = pd.DataFrame({"day": ny.dt.tz_localize(None).dt.normalize().to_numpy()[win],
                      "omin": omin[win], "r2": r2[win], "high": m["high"].to_numpy()[win],
                      "low": m["low"].to_numpy()[win]})  # fmt: skip
    prev = w.groupby("day")["omin"].shift(1).fillna(W_FROM - 5).to_numpy()
    w["miss"] = w["omin"].to_numpy() - prev - 5
    g = w.groupby("day")
    d = pd.DataFrame({"rv": g["r2"].sum(), "n": g["omin"].size(), "hi": g["high"].max(),
                      "lo": g["low"].min(), "miss": g["miss"].max(),
                      "last": g["omin"].max()})  # fmt: skip
    d["miss"] = np.maximum(d["miss"], W_END - 5 - d["last"])
    d["used"] = (d["n"] >= MIN_SHARE * W_BARS) & (d["miss"] <= MAX_GAP)
    # the price at 02:00: the last bar closing by then
    cu = m["close_utc"].to_numpy()
    k02 = np.searchsorted(cu, at_ny(d.index, W_FROM).to_numpy(), "right") - 1
    d["p02"] = np.where(k02 >= 0, c[np.maximum(k02, 0)], np.nan)
    d["k02"] = k02
    d["k1645"] = np.searchsorted(cu, at_ny(d.index, W_END).to_numpy(), "right") - 1
    return d.drop(columns=["last"]), np.cumsum(r2)


def news(cal: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Scheduled USD importance-3 releases inside each day's window (02:00-16:45 inclusive)."""
    u = cal[(cal["currency"] == "USD") & (cal["importance"] == 3)]
    t = u["ts_utc"].dt.tz_convert(NY)
    mins = (t.dt.hour * 60 + t.dt.minute).to_numpy()
    e = pd.DataFrame({"day": t.dt.tz_localize(None).dt.normalize().to_numpy(), "min": mins,
                      "event": u["event"].to_numpy()})  # fmt: skip
    e = e[(e["min"] >= W_FROM) & (e["min"] <= W_END)]
    e["top3"] = e["event"].isin(TOP3)
    e["fed"] = e["event"] == FED
    e["other"] = ~e["top3"]
    e["early"] = e["min"] <= EARLY
    g = e.groupby("day")[["top3", "fed", "other", "early"]].sum().reindex(index, fill_value=0)
    out = pd.DataFrame(index=index)
    out["top3"] = g["top3"] > 0
    out["fed"] = g["fed"] > 0
    out["uh1"] = g["other"] == 1
    out["uh2"] = g["other"] >= 2
    out["early"] = g["early"] > 0
    return out.astype(float)


def features(m: pd.DataFrame, h4: pd.DataFrame, cal: pd.DataFrame,
             first: pd.Timestamp = FIRST, last: pd.Timestamp = LAST) -> pd.DataFrame:  # fmt: skip
    """Used days with the target (log RV) and every feature known at 02:00 New York."""
    d, cum = days(m)
    u = d[d["used"]].copy()
    rv = u["rv"]
    u["y"] = np.log(rv)
    u["rv1"] = np.log(rv.shift(1))
    u["rv5"] = np.log(rv.shift(1).rolling(5).mean())
    u["rv22"] = np.log(rv.shift(1).rolling(22).mean())
    prev_end = u["k1645"].shift(1).to_numpy()
    k02 = u["k02"].to_numpy()
    on = np.full(len(u), np.nan)
    ok = ~np.isnan(prev_end) & (k02 >= 0)
    on[ok] = cum[k02[ok]] - cum[prev_end[ok].astype(int)]
    u["on"] = np.log(np.maximum(on, 1e-12))
    a4 = gl.wilder(*(h4[k].to_numpy(float) for k in ("high", "low", "close")))
    k4 = np.searchsorted(h4["close_utc"].to_numpy(), at_ny(u.index, W_FROM).to_numpy(), "right") - 1
    u["atr"] = np.log(np.where(k4 >= 0, a4[np.maximum(k4, 0)], np.nan) / u["p02"].to_numpy())
    u = u.join(news(cal, u.index))
    wd = u.index.day_of_week
    for i, name in enumerate(WEEK, start=1):
        u[name] = (wd == i).astype(float)
    u["year"] = u.index.year
    u = u[(u.index >= first) & (u.index <= last)]
    return u.dropna(subset=["y", "atr", *HAR])


# --- models ------------------------------------------------------------------------------------


def ols(xtr: np.ndarray, ytr: np.ndarray):
    a = np.c_[np.ones(len(xtr)), xtr]
    beta, *_ = np.linalg.lstsq(a, ytr, rcond=None)
    res = ytr - a @ beta
    s2 = float(res @ res / max(len(ytr) - a.shape[1], 1))
    return beta, s2


def qlike(rv: np.ndarray, f: np.ndarray, s2: float | np.ndarray) -> np.ndarray:
    z = rv / np.exp(f + s2 / 2)
    return z - np.log(z) - 1


def walk(u: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Forecasts on every test day; the last window's fits for the report."""
    from lightgbm import LGBMRegressor

    rows, last = [], {}
    for year in TEST_YEARS:
        tr, te = u[u["year"] < year], u[u["year"] == year]
        if year == TEST_YEARS[-1]:
            te = u[u["year"] >= year]
        ytr = tr["y"].to_numpy()
        out = pd.DataFrame({"y": te["y"], "rv": te["rv"], "year": year, "top3": te["top3"],
                            "hi": te["hi"], "lo": te["lo"], "p02": te["p02"]})  # fmt: skip
        out["f_M0"] = te["rv1"].to_numpy()
        out["s2_M0"] = float(np.var(ytr - tr["rv1"].to_numpy(), ddof=1))
        for name in ("M1", "M2", "M3"):
            beta, s2 = ols(tr[X[name]].to_numpy(), ytr)
            out[f"f_{name}"] = np.c_[np.ones(len(te)), te[X[name]].to_numpy()] @ beta
            out[f"s2_{name}"] = s2
            if year == TEST_YEARS[-1]:
                last[name] = pd.Series(beta, index=["const", *X[name]])
        gbm = LGBMRegressor(**LGB).fit(tr[X["M4"]].to_numpy(), ytr)
        out["f_M4"] = gbm.predict(te[X["M4"]].to_numpy())
        out["s2_M4"] = float(np.var(ytr - gbm.predict(tr[X["M4"]].to_numpy()), ddof=1))
        if year == TEST_YEARS[-1]:
            imp = gbm.booster_.feature_importance("gain")
            last["M4"] = pd.Series(imp / imp.sum(), index=X["M4"]).sort_values(ascending=False)
            last["train_days"] = len(tr)
        rows.append(out)
    f = pd.concat(rows)
    for name in MODELS:
        f[f"L_{name}"] = qlike(
            f["rv"].to_numpy(), f[f"f_{name}"].to_numpy(), f[f"s2_{name}"].to_numpy()
        )
    return f, last


# --- decision ----------------------------------------------------------------------------------


def holm(p: dict[str, float]) -> dict[str, float]:
    order = sorted(p, key=p.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * p[k]))
        out[k] = run
    return out


def compare(f: pd.DataFrame) -> pd.DataFrame:
    blocks = dc.block_ids(at_ny(f.index, W_FROM))
    rows = {}
    for name in ("M2", "M3", "M4"):
        d = (f[f"L_{name}"] - f["L_M1"]).to_numpy()
        (star,), k = dc.bootstrap([d], blocks, BOOT, np.random.default_rng(SEED))
        yearly = f.groupby("year")[[f"L_{name}", "L_M1"]].mean()
        hold = f[f.index >= HOLD_FROM]
        rows[name] = {
            "diff": d.mean(), "lo": np.percentile(star, 2.5), "hi": np.percentile(star, 97.5),
            "p": (1 + np.count_nonzero(star >= 0)) / (BOOT + 1), "blocks": k,
            "years": int((yearly[f"L_{name}"] < yearly["L_M1"]).sum()),
            "hold": hold[f"L_{name}"].mean() - hold["L_M1"].mean(),
        }  # fmt: skip
    r = pd.DataFrame(rows).T
    r["holm"] = pd.Series(holm(r["p"].to_dict()))
    r["beats"] = (r["diff"] < 0) & (r["holm"] < 0.05) & (r["years"] >= 6) & (r["hold"] < 0)
    return r


def r2(y: np.ndarray, f: np.ndarray, ref: np.ndarray | None = None) -> float:
    base = np.full_like(y, y.mean()) if ref is None else ref
    return float(1 - ((y - f) ** 2).sum() / ((y - base) ** 2).sum())


# --- report ------------------------------------------------------------------------------------


def report(u: pd.DataFrame, f: pd.DataFrame, last: dict, all_days: pd.DataFrame) -> str:
    cmp = compare(f)
    best = min(MODELS, key=lambda k: f[f"L_{k}"].mean())
    passed = cmp[cmp["beats"]]
    go = min(passed.index, key=lambda k: f[f"L_{k}"].mean()) if len(passed) else None
    y = f["y"].to_numpy()
    lines = [
        "# Gold volatility forecast, part 1: result",
        "",
        "_`python -m app research vol-forecast`, registered in `VOL_FORECAST.md` (with addendum 1)"
        f". XAUUSD 5m, window 02:00-16:45 New York. {len(u):,} used days 2012-01-02 to "
        f"2026-01-09; test days {len(f):,} ({f.index.min():%Y-%m-%d} to {f.index.max():%Y-%m-%d})"
        f". QLIKE (lower is better); 4-week block bootstrap, {BOOT:,} resamples, seed {SEED}. No "
        "trade simulated._",
        "",
        "## Decision",
        "",
    ]
    if go is not None:
        lines.append(
            f"**Part 1 passes: {', '.join(passed.index)} beat the ATR.** {go} has the "
            "lowest mean QLIKE and goes to part 2 (a separate registration)."
        )
    else:
        lines.append(
            "**Part 1 does not pass: no model beats the ATR on all three conditions.** "
            "Part 2 is not registered; the five keep the ATR."
        )
    lines += [
        "",
        "## Primary comparisons (model minus M1, per test day)",
        "",
        "| Model | Mean QLIKE diff | 95% | p (one-sided) | Holm p | Years below M1 (of 8) "
        "| 2024-07 to 2026-01-09 diff | Beats the ATR |",
        "|" + " --- |" * 8,
    ]
    for k, x in cmp.iterrows():
        lines.append(
            f"| {k} | {x['diff']:+.4f} | {x['lo']:+.4f} to {x['hi']:+.4f} | {x['p']:.4f} "
            f"| {x['holm']:.4f} | {int(x['years'])} | {x['hold']:+.4f} | "
            f"{'yes' if x['beats'] else 'no'} |"
        )
    lines += [
        "",
        f"Blocks: {int(cmp['blocks'].iloc[0])}. Lowest mean QLIKE over all test days: {best}.",
        "",
        "## Every model, all test days",
        "",
        "| Model | Mean QLIKE | MSE log RV | R^2 log RV | R^2 vs M1 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for k in MODELS:
        fk = f[f"f_{k}"].to_numpy()
        lines.append(
            f"| {k} | {f[f'L_{k}'].mean():.4f} | {np.mean((y - fk) ** 2):.4f} | {r2(y, fk):.3f} "
            f"| {r2(y, fk, f['f_M1'].to_numpy()):+.3f} |"
        )
    lines += [
        "",
        "## Per test year (mean QLIKE / R^2 of log RV)",
        "",
        "| Year | Days | " + " | ".join(MODELS) + " |",
        "|" + " --- |" * (2 + len(MODELS)),
    ]
    for yr, g in f.groupby("year"):
        gy = g["y"].to_numpy()
        cells = " | ".join(f"{g[f'L_{k}'].mean():.3f} / {r2(gy, g[f'f_{k}'].to_numpy()):.2f}"
                           for k in MODELS)  # fmt: skip
        lines.append(f"| {yr}{'+' if yr == TEST_YEARS[-1] else ''} | {len(g)} | {cells} |")
    lines += ["", "2025+ holds 2026-01-02 to 2026-01-09 too.", ""]
    # news days
    lines += [
        "## News days (TOP3 in the window) against the others",
        "",
        "| Days | n | Median window move % (100 x sqrt RV) | "
        + " | ".join(f"QLIKE {k}" for k in MODELS)
        + " |",
        "|" + " --- |" * (3 + len(MODELS)),
    ]
    for flag, g in f.groupby("top3"):
        lines.append(
            f"| {'TOP3' if flag else 'other'} | {len(g):,} "
            f"| {np.median(np.sqrt(g['rv'])) * 100:.2f}"
            " | " + " | ".join(f"{g[f'L_{k}'].mean():.3f}" for k in MODELS) + " |"
        )
    # coefficients
    lines += ["", f"## Last window fits (train 2012-2024, {last['train_days']:,} days)", ""]
    for k in ("M1", "M2", "M3"):
        lines.append(f"- **{k}:** " + ", ".join(f"{n} {v:+.3f}" for n, v in last[k].items()))
    lines.append("- **M4 gain share:** " + ", ".join(f"{n} {v:.2f}" for n, v in last["M4"].items()))
    # calibration
    lines += ["", "## Calibration (test days in deciles of the forecast; RV x 1e4)", ""]
    for k in dict.fromkeys(["M1", best]):
        lev = np.exp(f[f"f_{k}"] + f[f"s2_{k}"] / 2)
        dec = pd.qcut(lev, 10, labels=False)
        t = pd.DataFrame({"F": lev, "rv": f["rv"]}).groupby(dec).mean() * 1e4
        lines += [
            f"**{k}**",
            "",
            "| Decile | Mean forecast | Mean realised |",
            "| --- | --- | --- |",
        ]
        lines += [f"| {i + 1} | {x['F']:.3f} | {x['rv']:.3f} |" for i, x in t.iterrows()]
        lines.append("")
    # product readout
    lev = np.exp(f[f"f_{best}"] + f[f"s2_{best}"] / 2)
    dec = pd.qcut(lev, 10, labels=False)
    rng_usd = f["hi"] - f["lo"]
    rng_pct = rng_usd / f["p02"] * 100
    lines += [
        f"## Product readout: the window's range by forecast decile ({best})",
        "",
        "| Decile | Days | Range $ median (p20 to p80) | Range % median (p20 to p80) |",
        "| --- | --- | --- | --- |",
    ]
    for i in range(10):
        s = dec == i
        a, b = rng_usd[s], rng_pct[s]
        lines.append(
            f"| {i + 1} | {int(s.sum())} | {a.median():.1f} ({a.quantile(0.2):.1f} to "
            f"{a.quantile(0.8):.1f}) | {b.median():.2f} ({b.quantile(0.2):.2f} to "
            f"{b.quantile(0.8):.2f}) |"
        )
    # dropped days
    wk = pd.bdate_range(FIRST, LAST)
    used = set(u.index)
    present = all_days.reindex(wk)
    lines += [
        "",
        "## Weekdays not used (§2), per year",
        "",
        "| Year | Weekdays | No window bars | Failed the bar / gap rule | Used |",
        "| --- | --- | --- | --- | --- |",
    ]
    for yr in sorted(set(wk.year)):
        s = wk.year == yr
        none = int(present.loc[s, "n"].isna().sum())
        n_used = sum(1 for d in wk[s] if d in used)
        lines.append(
            f"| {yr} | {int(s.sum())} | {none} | {int(s.sum()) - none - n_used} | {n_used} |"
        )
    lines += [
        "",
        "Used days also need 22 earlier used days (from 2011-09) for `rv22`.",
        "",
        "## Notes",
        "",
        "- `usd_high` enters M3 and M4 as two dummies (1, 2 or more).",
        "- M4's s^2 is its in-sample residual variance, as registered; a LightGBM fits its "
        "train days closer than OLS, so its level forecast may be biased low.",
        "- The calendar's importance labels are MT5's current ones (a small look-ahead).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    fr = gl.load()
    cal = pd.read_parquet(CAL)
    u = features(fr["5m"], fr["4h"], cal)
    f, last = walk(u)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report(u, f, last, days(fr["5m"])[0]), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
