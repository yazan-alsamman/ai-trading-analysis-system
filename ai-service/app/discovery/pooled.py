"""A model over all the tested strategies' trades (``docs/discovery/POOLED_MODEL.md``, registered
2026-11-14).

    python -m app discovery pooled build   # candidates, cells, features; counts only
    python -m app discovery pooled run     # validation, test, FxPro 2026 readout

``build`` reads outcomes only as the registration allows: the 2012-2019 gross means that pick the
cells, and labels stored for ``run``. Every feature of a candidate entering at 5m bar ``e`` reads
bars up to ``e - 1`` and trades that closed before ``e``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.levels import discover as ldisc
from app.levels import families as lfam
from app.levels import trades as ltr
from app.research import decide as dc
from app.research import exhaustion as exh
from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import vol_forecast as vf
from app.scoring import volatility as vs

ROOT = Path(__file__).resolve().parents[2]
STORE = gl.STORE / "pooled"
REPORT = ROOT / "docs" / "discovery" / "pooled_result.md"  # not POOLED_MODEL.md (Windows case)
COUNTS = ROOT / "docs" / "discovery" / "pooled_counts.md"
LAB = gl.STORE / "gold_lab_trades.parquet"
FX_EXPORT = Path("D:/GOLD_M1_201501020000_202611052359.csv")
FIVE = ("LVL4H", "PIVOT", "PIVW", "ASIA", "PWHL")
START, END = pd.Timestamp("2012-01-01", tz="UTC"), pd.Timestamp("2026-01-10", tz="UTC")
FX_FROM, FX_TO = 20260112, 20261105
FX_WARM = pd.Timestamp("2025-09-01", tz="UTC")
TRAIN_TO, VAL, TEST_FROM = 2019, (2020, 2021), 2022
MIN_TRADES, MIN_GROSS = 200, -0.02
WINDOW = 12  # 60 minutes of 5m bars
TAUS = (0.0, 0.02, 0.05, 0.10, 0.15)
BOOT, SEED_BOOT, RAND, SEED_RAND = 10_000, 20261121, 200, 20261122
GROUPS = ("lab", "levels", "six")
FEATURES = [
    "cell_code",
    "group_code",
    "dir",
    "minute",
    "weekday",
    "logF",
    "vratio",
    "u",
    "atr1h_4h",
    "atr4h_d",
    "cost_r",
    "same_lab",
    "opp_lab",
    "same_levels",
    "opp_levels",
    "same_six",
    "opp_six",
    "open_same",
    "open_opp",
    "fired_today",
    "cell_recent",
    "pool_recent5",
]
NUMERIC = [f for f in FEATURES if f not in ("cell_code", "group_code")]
LGB = dict(
    num_leaves=15,
    n_estimators=400,
    learning_rate=0.03,
    min_child_samples=200,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    random_state=20261120,
    deterministic=True,
    force_row_wise=True,
    n_jobs=2,
    verbose=-1,
)
RIDGE_ALPHA = 10.0


# --- the candidates ------------------------------------------------------------------------------


def lab_trades(cx: gl.Ctx, path: Path = LAB) -> pd.DataFrame:
    """The stored lab trades (``gold_lab.all_signals``, M0 and M8): entry bar ``i``; net R with
    the stop slip of ``gold_combo.run``."""
    t = pd.read_parquet(path)
    net = t["gross"] - t["cost"] - np.where(t["exit"] == "sl", gl.SL_SLIP / t["risk"], 0.0)
    return pd.DataFrame(
        {
            "cell": "lab:" + t["strategy"] + ":" + t["bundle"],
            "group": "lab",
            "e": t["i"],
            "j": t["j"],
            "dir": t["dir"],
            "risk": t["risk"],
            "gross": t["gross"],
            "net": net,
            "exit": t["exit"],
        }
    )


def lab_from_frames(fr: dict, cx: gl.Ctx) -> pd.DataFrame:
    """The lab trades made on other frames (FxPro): every lab signal but the dollar's lead (its
    driver feeds are sealed after 2026-01-09)."""
    parts = gl.frozen(fr, cx) + [
        gl.ny_momentum(cx),
        gl.news_830(cx),
        gl.extreme_bar(cx),
        gl.ema_cross(cx),
        gl.ema_cross(cx, reverse=True),
        gl.rsi2(cx, fr),
        gl.levels_4h(cx),
        gl.pivots(cx),
        gl.reopen_gap(cx),
        gl.spread_spike(cx),
    ]
    s = pd.concat(parts, ignore_index=True)
    s = pd.concat([s, gl.big_day(cx, s[s["strategy"].isin(gl.BREAKOUTS)])], ignore_index=True)
    s = s[(s["i"] > 5) & (s["end"] > s["i"]) & (s["end"] < len(cx.c) - 1) & (s["risk"] > 0)]
    t = pd.concat([gl.simulate(s, cx, b).assign(bundle=b) for b in ("M0", "M8")], ignore_index=True)
    path = STORE / "_fx_lab.parquet"
    t.to_parquet(path, index=False)
    return lab_trades(cx, path)


def level_trades(cx: gl.Ctx, fr: dict, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """The 24 level families x break / rejection (``levels discover``, real families only), entry
    at the open of bar ``k``."""
    fams = lfam.all_families(cx, fr)
    dl = ltr.deadline(cx)
    t = pd.to_datetime(cx.m["close_utc"].to_numpy(), utc=True)
    in_period = np.asarray((t >= start) & (t < end))
    r = ldisc.run_families(cx, fams, dl, in_period)
    return pd.DataFrame(
        {
            "cell": "levels:" + r["family"] + ":" + r["behaviour"],
            "group": "levels",
            "e": r["k"],
            "j": r["j"],
            "dir": r["dir"],
            "risk": r["risk"],
            "gross": r["gross"],
            "net": r["net"],
            "exit": r["exit"],
        }
    )


def six_trades(fr: dict, start: pd.Timestamp) -> pd.DataFrame:
    _, every, _, _ = gv.five_trades(fr, start=start, with_round=True)
    return pd.DataFrame(
        {
            "cell": "six:" + every["strategy"],
            "group": "six",
            "e": every["i"],
            "j": every["j"],
            "dir": every["dir"],
            "risk": every["risk"],
            "gross": every["gross"],
            "net": every["net_slip"],
            "exit": every["exit"],
        }
    )


def finish(c: pd.DataFrame, cx: gl.Ctx) -> pd.DataFrame:
    c = c[(c["e"] > WINDOW + 1) & (c["risk"] > 0)].copy()
    e = c["e"].to_numpy()
    c["ny_day"] = cx.ny_day[e]
    c["year"] = c["ny_day"] // 10000
    c["entry_utc"] = cx.m["close_utc"].to_numpy()[e - 1]  # the entry is after bar e - 1 closes
    c["exit_utc"] = cx.m["close_utc"].to_numpy()[c["j"].to_numpy()]
    return c.sort_values(["e", "cell"], kind="stable").reset_index(drop=True)


def select_cells(c: pd.DataFrame) -> pd.DataFrame:
    """§2: on 2012-2019, at least 200 trades and a gross mean of at least -0.02 R."""
    tr = c[c["year"] <= TRAIN_TO].groupby("cell")["gross"].agg(["size", "mean"])
    tr["kept"] = (tr["size"] >= MIN_TRADES) & (tr["mean"] >= MIN_GROSS)
    return tr


# --- the features --------------------------------------------------------------------------------


def day_volatility(
    fr: dict, cal: pd.DataFrame, fit_on: pd.DataFrame | None = None, years: range | None = None
) -> pd.DataFrame:
    """Per New York day: log F (M3) and the M3 / ATR ratio, each from a model fitted on earlier
    years only (yearly, expanding; 2012 has none), or, with ``fit_on``, from one fit on it."""
    u = vf.features(fr["5m"], fr["4h"], cal, pd.Timestamp("2012-01-02"), pd.Timestamp("2026-12-31"))
    out = []
    if fit_on is not None:
        groups = [(fit_on, u)]
    else:
        groups = [(u[u["year"] < y], u[u["year"] == y]) for y in (years or range(2013, 2027))]
    for tr, te in groups:
        if tr.empty or te.empty:
            continue
        b3, s3 = vf.ols(tr[vf.X["M3"]].to_numpy(), tr["y"].to_numpy())
        b1, _ = vf.ols(tr[vf.X["M1"]].to_numpy(), tr["y"].to_numpy())
        f3 = np.c_[np.ones(len(te)), te[vf.X["M3"]].to_numpy()] @ b3
        f1 = np.c_[np.ones(len(te)), te[vf.X["M1"]].to_numpy()] @ b1
        out.append(
            pd.DataFrame(
                {
                    "ny_day": exh.day_int(te.index),
                    "logF": f3 + s3 / 2,
                    "vratio": np.exp((f3 - f1) / 2),
                    "p02": te["p02"].to_numpy(),
                }
            )
        )
    return (
        pd.concat(out, ignore_index=True)
        if out
        else pd.DataFrame(columns=["ny_day", "logF", "vratio", "p02"])
    )


def window_counts(e: np.ndarray, n: int) -> np.ndarray:
    """Per bar: the number of entries in the ``WINDOW`` bars before it (not the bar itself)."""
    cs = np.r_[0, np.cumsum(np.bincount(e, minlength=n))]
    idx = np.arange(n)
    return cs[idx] - cs[np.maximum(idx - WINDOW, 0)]


def open_counts(e: np.ndarray, j: np.ndarray, n: int) -> np.ndarray:
    """Per bar b: trades with e < b <= j (entered earlier, still open at b)."""
    d = np.zeros(n + 2)
    np.add.at(d, e + 1, 1)
    np.add.at(d, np.minimum(j, n - 1) + 1, -1)
    return np.cumsum(d)[:n]


def recent_cell(c: pd.DataFrame) -> np.ndarray:
    """The mean net R of the cell's last 20 trades that closed before the entry bar."""
    out = np.full(len(c), np.nan)
    for _, g in c.groupby("cell", sort=False):
        order = np.argsort(g["j"].to_numpy(), kind="stable")
        js = g["j"].to_numpy()[order]
        cs = np.r_[0.0, np.cumsum(g["net"].to_numpy()[order])]
        n = np.searchsorted(js, g["e"].to_numpy(), side="left")  # exits strictly before e
        lo = np.maximum(n - 20, 0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[g.index.to_numpy()] = np.where(n > 0, (cs[n] - cs[lo]) / (n - lo), np.nan)
    return out


def recent_pool(c: pd.DataFrame, cx: gl.Ctx) -> np.ndarray:
    """The mean net R of every candidate that closed on the 5 trading days before the entry's
    day."""
    days = np.unique(cx.ny_day[cx.weekday < 5])
    pos = {d: k for k, d in enumerate(days)}
    exit_day = cx.ny_day[c["j"].to_numpy()]
    xi = np.array([pos.get(d, -1) for d in exit_day])
    s = np.bincount(xi[xi >= 0], c["net"].to_numpy()[xi >= 0], len(days))
    n = np.bincount(xi[xi >= 0], minlength=len(days)).astype(float)
    cs, cn = np.r_[0.0, np.cumsum(s)], np.r_[0.0, np.cumsum(n)]
    di = np.array([pos.get(d, -1) for d in c["ny_day"].to_numpy()])
    lo = np.maximum(di - 5, 0)
    tot, cnt = cs[di] - cs[lo], cn[di] - cn[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where((di >= 0) & (cnt > 0), tot / cnt, np.nan)


def features(c: pd.DataFrame, cx: gl.Ctx, vol: pd.DataFrame, cells: list[str]) -> pd.DataFrame:
    """The registered features (§3) of the kept cells' candidates."""
    c = c[c["cell"].isin(cells)].reset_index(drop=True)
    n = len(cx.c)
    e, d = c["e"].to_numpy(), c["dir"].to_numpy()
    p = e - 1
    out = c.copy()
    out["cell_code"] = c["cell"].map({k: i for i, k in enumerate(cells)}).astype(int)
    out["group_code"] = c["group"].map({g: i for i, g in enumerate(GROUPS)}).astype(int)
    out["minute"] = cx.ny_min[e]
    out["weekday"] = cx.weekday[e]
    v = vol.set_index("ny_day")
    known = out["minute"].to_numpy() >= vs.W_FROM  # the day's forecast is issued at 02:00
    out["logF"] = np.where(known, c["ny_day"].map(v["logF"]).to_numpy(), np.nan)
    out["vratio"] = np.where(known, c["ny_day"].map(v["vratio"]).to_numpy(), np.nan)
    scale = c["ny_day"].map(v["p02"] * np.sqrt(np.exp(v["logF"]))).to_numpy()
    out["u"] = np.where(known, exh.range_before(cx, e) / scale, np.nan)
    out["atr1h_4h"] = cx.atr1h[p] / cx.atr4h[p]
    out["atr4h_d"] = cx.atr4h[p] / cx.atrd[p]
    out["cost_r"] = (cx.spread[p] + gl.COMMISSION) / c["risk"].to_numpy()
    for g in GROUPS:
        m = (c["group"] == g).to_numpy()
        up = window_counts(e[m & (d > 0)], n)
        dn = window_counts(e[m & (d < 0)], n)
        out[f"same_{g}"] = np.where(d > 0, up[e], dn[e])
        out[f"opp_{g}"] = np.where(d > 0, dn[e], up[e])
    six = (c["group"] == "six").to_numpy()
    ou = open_counts(e[six & (d > 0)], c["j"].to_numpy()[six & (d > 0)], n)
    od = open_counts(e[six & (d < 0)], c["j"].to_numpy()[six & (d < 0)], n)
    out["open_same"] = np.where(d > 0, ou[e], od[e])
    out["open_opp"] = np.where(d > 0, od[e], ou[e])
    allc = np.r_[0, np.cumsum(np.bincount(e, minlength=n))]
    first = pd.Series(np.arange(n)).groupby(cx.ny_day).transform("min").to_numpy()
    out["fired_today"] = allc[e] - allc[first[e]]
    out["cell_recent"] = recent_cell(c)
    out["pool_recent5"] = recent_pool(c, cx)
    return out


# --- build ---------------------------------------------------------------------------------------


def build_store() -> dict:
    fr = gl.load()
    cx = gl.context(fr)
    cal = pd.read_parquet(vf.CAL)
    lv = level_trades(cx, fr, START, END)
    c = finish(pd.concat([lab_trades(cx), lv, six_trades(fr, START)], ignore_index=True), cx)
    c = c[c["entry_utc"] < END].reset_index(drop=True)
    sel = select_cells(c)
    cells = sorted(sel.index[sel["kept"]])
    vol = day_volatility(fr, cal)
    f = features(c, cx, vol, cells)
    STORE.mkdir(parents=True, exist_ok=True)
    f.to_parquet(STORE / "store.parquet", index=False)
    c[c["group"] == "six"].to_parquet(STORE / "six.parquet", index=False)
    sel.to_csv(STORE / "cells.csv")
    stored = pd.read_parquet(gl.STORE / "levels" / "discovery_trades.parquet")
    lv_old = lv[pd.to_datetime(cx.m["close_utc"].to_numpy()[lv["e"]], utc=True).year <= 2021]
    meta = {
        "cells": cells,
        "levels_regenerated_2012_2021": len(lv_old),
        "levels_stored_2012_2021": len(stored),
        "levels_same_net_sum": bool(np.isclose(lv_old["net"].sum(), stored["net"].sum())),
    }
    (STORE / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"c": c, "sel": sel, "f": f, "meta": meta}


def build_fx(export: Path, cells: list[str], store_vol_fit: pd.DataFrame) -> pd.DataFrame:
    """FxPro GOLD: every cell regenerated from 2025-09 (warm-up for the recent-results features),
    the readout days 2026-01-12 to 2026-11-05."""
    fr = ge.frames_from_lines(gv.fx_lines(export))
    cx = gl.context(fr)
    cal = pd.read_parquet(vf.CAL)
    end = pd.Timestamp("2026-11-07", tz="UTC")
    lab = lab_from_frames(fr, cx)
    parts = [lab, level_trades(cx, fr, FX_WARM, end), six_trades(fr, FX_WARM)]
    c = finish(pd.concat(parts, ignore_index=True), cx)
    c = c[c["entry_utc"] >= FX_WARM].reset_index(drop=True)
    vol = day_volatility(fr, cal, fit_on=store_vol_fit)
    f = features(c, cx, vol, cells)
    f = f[(f["ny_day"] >= FX_FROM) & (f["ny_day"] <= FX_TO)].reset_index(drop=True)
    f.to_parquet(STORE / "fx.parquet", index=False)
    return f


def counts_report(b: dict) -> str:
    c, sel, f, meta = b["c"], b["sel"], b["f"], b["meta"]
    days = f.groupby("year")["ny_day"].nunique()
    nd = f["ny_day"].nunique()
    lines = [
        "# The pooled candidates: counts (build, before any model)",
        "",
        "_`python -m app discovery pooled build`, `POOLED_MODEL.md` §2-3. XAUUSD 5m, 2012 to "
        "2026-01-09. Cells kept: at least 200 trades and a gross mean of at least -0.02 R on "
        "2012-2019._",
        "",
        f"Cells: {len(sel)}, kept {int(sel['kept'].sum())}. Candidates of kept cells: "
        f"{len(f):,} on {nd:,} days ({len(f) / nd:.1f} a day).",
        "",
        "Level families regenerated by today's code, 2012-2021: "
        f"{meta['levels_regenerated_2012_2021']:,} "
        f"trades (stored run: {meta['levels_stored_2012_2021']:,}; same net sum: "
        f"{'yes' if meta['levels_same_net_sum'] else 'no'}).",
        "",
        "| Cell | Trades 2012-2019 | Gross mean 2012-2019 | Kept |",
        "| --- | --- | --- | --- |",
    ]
    for cell, x in sel.sort_values("mean", ascending=False).iterrows():
        lines.append(
            f"| {cell} | {int(x['size']):,} | {x['mean']:+.4f} | {'yes' if x['kept'] else ''} |"
        )
    lines += [
        "",
        "| Year | Candidates | Days | A day | lab / levels / six |",
        "| --- | --- | --- | --- | --- |",
    ]
    for y, g in f.groupby("year"):
        gs = g.groupby("group").size()
        lines.append(
            f"| {y} | {len(g):,} | {days[y]} | {len(g) / days[y]:.1f} | "
            + " / ".join(f"{int(gs.get(k, 0)):,}" for k in GROUPS)
            + " |"
        )
    lines += ["", f"All candidates before selection: {len(c):,}.", ""]
    return "\n".join(lines)


# --- the models ----------------------------------------------------------------------------------


def purge(tr: pd.DataFrame, year: int) -> pd.DataFrame:
    """Training rows whose exit is before the predicted year's first day minus a 1-day embargo."""
    cut = pd.Timestamp(f"{year}-01-01", tz="UTC") - pd.Timedelta(days=1)
    return tr[pd.to_datetime(tr["exit_utc"], utc=True) < cut]


class RidgeModel:
    def __init__(self, cells: int):
        self.cells = cells

    def _x(self, d: pd.DataFrame, fit: bool) -> np.ndarray:
        x = d[NUMERIC].astype(float).copy()
        miss = x[["logF", "vratio", "u", "cell_recent", "pool_recent5"]].isna().astype(float)
        if fit:
            self.med = x.median()
        x = x.fillna(self.med)
        if fit:
            self.mu, self.sd = x.mean(), x.std().replace(0, 1.0)
        z = ((x - self.mu) / self.sd).to_numpy()
        onehot = np.zeros((len(d), self.cells))
        onehot[np.arange(len(d)), d["cell_code"].to_numpy()] = 1.0
        return np.c_[z, miss.to_numpy(), onehot]

    def fit(self, d: pd.DataFrame) -> RidgeModel:
        from sklearn.linear_model import Ridge

        self.m = Ridge(alpha=RIDGE_ALPHA).fit(self._x(d, True), d["net"].to_numpy())
        return self

    def predict(self, d: pd.DataFrame) -> np.ndarray:
        return self.m.predict(self._x(d, False))


class GbmModel:
    def __init__(self, cells: int):
        self.cells = cells

    def _x(self, d: pd.DataFrame) -> pd.DataFrame:
        x = d[FEATURES].copy()
        x["cell_code"] = pd.Categorical(x["cell_code"], categories=range(self.cells))
        x["group_code"] = pd.Categorical(x["group_code"], categories=range(len(GROUPS)))
        return x

    def fit(self, d: pd.DataFrame) -> GbmModel:
        from lightgbm import LGBMRegressor

        self.m = LGBMRegressor(**LGB).fit(self._x(d), d["net"].to_numpy())
        return self

    def predict(self, d: pd.DataFrame) -> np.ndarray:
        return self.m.predict(self._x(d))


MODELS = {"ridge": RidgeModel, "lgbm": GbmModel}


def walk(f: pd.DataFrame, cells: int, years: list[int]) -> pd.DataFrame:
    """Yearly expanding walk-forward predictions of both models (the last year also takes the
    days of the next one, 2026-01-02 to 2026-01-09)."""
    out = []
    for y in years:
        te = f[(f["year"] == y) | ((y == 2025) & (f["year"] == 2026))]
        tr = purge(f[f["year"] < y], y)
        p = te[["cell", "group", "e", "ny_day", "year", "net", "gross"]].copy()
        for name, cls in MODELS.items():
            p[f"pred_{name}"] = cls(cells).fit(tr).predict(te)
        out.append(p)
    return pd.concat(out, ignore_index=True)


def choose(v: pd.DataFrame) -> tuple[str, float, pd.DataFrame]:
    days = v["ny_day"].nunique()
    rows = []
    for name in MODELS:
        for tau in TAUS:
            s = v[v[f"pred_{name}"] > tau]
            rows.append(
                {
                    "model": name,
                    "tau": tau,
                    "trades": len(s),
                    "a_day": len(s) / days,
                    "mean": s["net"].mean() if len(s) else np.nan,
                }
            )
    g = pd.DataFrame(rows)
    ok = g[g["a_day"] >= 1.0].sort_values(["mean", "tau"], ascending=[False, True])
    if ok.empty:
        return "", np.nan, g
    best = ok.iloc[0]
    return str(best["model"]), float(best["tau"]), g


def block_boot(sel: pd.DataFrame) -> dict:
    ts = pd.to_datetime(sel["ny_day"].astype(str), format="%Y%m%d").dt.tz_localize("UTC")
    ids, inv = np.unique(dc.block_ids(ts), return_inverse=True)
    k = len(ids)
    s1 = np.bincount(inv, sel["net"].to_numpy(), k)
    n1 = np.bincount(inv, minlength=k).astype(float)
    draws = np.random.default_rng(SEED_BOOT).integers(0, k, size=(BOOT, k))
    star = s1[draws].sum(1) / n1[draws].sum(1)
    return {
        "mean": float(sel["net"].mean()),
        "lo": float(np.percentile(star, 2.5)),
        "hi": float(np.percentile(star, 97.5)),
        "p": float((1 + np.count_nonzero(star <= 0)) / (BOOT + 1)),
        "blocks": k,
    }


def random_selection(pool: pd.DataFrame, picked: pd.Series) -> np.ndarray:
    """``RAND`` means of selections taking, each day, as many candidates as the model at random."""
    rng = np.random.default_rng(SEED_RAND)
    sums, counts = np.zeros(RAND), 0
    for day, g in pool.groupby("ny_day", sort=True):
        n = int(picked.get(day, 0))
        if n == 0:
            continue
        x = g["net"].to_numpy()
        idx = np.argsort(rng.random((RAND, len(x))), axis=1)[:, :n]
        sums += x[idx].sum(axis=1)
        counts += n
    return sums / max(counts, 1)


def sharpe(x: np.ndarray) -> float:
    return float(np.mean(x) / np.std(x, ddof=1)) if len(x) > 1 and np.std(x) > 0 else np.nan


def max_dd(x: np.ndarray) -> float:
    c = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(np.r_[0.0, c])[1:] - c)) if len(c) else 0.0


# --- run -----------------------------------------------------------------------------------------


def five_daily(six: pd.DataFrame, days: np.ndarray) -> pd.Series:
    five = six[six["cell"].isin([f"six:{k}" for k in FIVE])]
    return five.groupby("ny_day")["net"].sum().reindex(days, fill_value=0.0)


def run(export: Path) -> str:
    f = pd.read_parquet(STORE / "store.parquet")
    meta = json.loads((STORE / "meta.json").read_text(encoding="utf-8"))
    cells = meta["cells"]
    nc = len(cells)
    val = walk(f, nc, list(VAL))
    model, tau, grid = choose(val)
    lines = [
        "# A model over all the tested strategies' trades: result",
        "",
        "_`python -m app discovery pooled run`, registered in `POOLED_MODEL.md`. XAUUSD 5m; "
        f"{len(cells)} cells; walk-forward yearly, purge + 1-day embargo. Intervals by 4-week "
        f"blocks of days ({BOOT:,} resamples)._",
        "",
        "## Validation (2020-2021)",
        "",
        "| Model | tau | Trades | A day | Mean net R |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {r.model} | {r.tau:.2f} | {r.trades:,} | {r.a_day:.2f} | {r.mean:+.4f} |"
        for r in grid.itertuples()
    ]
    lines += [
        "",
        f"All candidates 2020-2021: {len(val):,}, mean net R {val['net'].mean():+.4f}.",
        "",
    ]
    if not model:
        lines += ["**No model x tau selects one trade a day on average: nothing to test. Fails.**"]
        return "\n".join(lines) + "\n"
    lines += [f"Chosen: **{model}, tau {tau:.2f}**.", ""]
    test = walk(f, nc, [2022, 2023, 2024, 2025])
    sel = test[test[f"pred_{model}"] > tau]
    b = block_boot(sel)
    picked = sel.groupby("ny_day").size()
    rand = random_selection(test, picked)
    p95 = float(np.quantile(rand, 0.95))
    days = np.sort(test["ny_day"].unique())
    six = pd.read_parquet(STORE / "six.parquet")
    fd = five_daily(six, days)
    md = sel.groupby("ny_day")["net"].sum().reindex(days, fill_value=0.0)
    corr = float(np.corrcoef(fd, md)[0, 1]) if md.std() > 0 else np.nan
    sh5, sh5m = sharpe(fd.to_numpy()), sharpe((fd + md).to_numpy())
    # FxPro 2026 (unseen): the chosen model fitted on every store candidate
    fx_path = STORE / "fx.parquet"
    if not fx_path.exists():
        fr = gl.load()
        cal = pd.read_parquet(vf.CAL)
        u = vf.features(fr["5m"], fr["4h"], cal)
        build_fx(export, cells, u)
    fx = pd.read_parquet(fx_path)
    fx_pred = MODELS[model](nc).fit(f).predict(fx) if len(fx) else np.array([])
    fx_sel = fx[fx_pred > tau] if len(fx) else fx
    fx_mean = float(fx_sel["net"].mean()) if len(fx_sel) else np.nan
    c1 = b["mean"] > 0 and b["p"] < 0.05
    c2 = b["mean"] > p95
    c3 = (corr < 0.2) or (sh5m > sh5)
    c4 = bool(fx_mean > 0)
    ok = c1 and c2 and c3 and c4
    lines += [
        "## Decision (test 2022-01-01 to 2026-01-09)",
        "",
        f"1. Edge: mean net R per selected trade {b['mean']:+.4f} (95% {b['lo']:+.4f} to "
        f"{b['hi']:+.4f}), p {b['p']:.4f}, {b['blocks']} blocks: **{'yes' if c1 else 'no'}**",
        f"2. Above the 95th percentile of {RAND} random selections ({p95:+.4f}; their median "
        f"{np.median(rand):+.4f}): **{'yes' if c2 else 'no'}**",
        f"3. Useful: correlation with the five's days {corr:+.3f}; daily Sharpe five "
        f"{sh5:.4f}, five + selection {sh5m:.4f}: **{'yes' if c3 else 'no'}**",
        f"4. FxPro 2026-01-12 to 2026-11-05: {len(fx_sel):,} selected of {len(fx):,}, mean net "
        f"R {fx_mean:+.4f}: **{'yes' if c4 else 'no'}**",
        "",
        "**It passes.** Any live use needs its own registration."
        if ok
        else "**It does not pass.** The search for an edge in gold's intraday trades ends here.",
        "",
        "## Test detail",
        "",
        f"Selected {len(sel):,} of {len(test):,} candidates on {len(days):,} days "
        f"({len(sel) / len(days):.2f} a day); all candidates' mean net R "
        f"{test['net'].mean():+.4f}; "
        f"largest drawdown of the selection {max_dd(md.to_numpy()):.1f} R.",
        "",
        "| Year | Candidates | Selected | Mean net R selected | Mean net R all |",
        "| --- | --- | --- | --- | --- |",
    ]
    for y, g in test.groupby("year"):
        s_ = g[g[f"pred_{model}"] > tau]
        lines.append(
            f"| {y} | {len(g):,} | {len(s_):,} | {s_['net'].mean():+.4f} | {g['net'].mean():+.4f} |"
        )
    lines += ["", "| Group | Selected | Mean net R |", "| --- | --- | --- |"]
    for g_, s_ in sel.groupby("group"):
        lines.append(f"| {g_} | {len(s_):,} | {s_['net'].mean():+.4f} |")
    gb = GbmModel(nc).fit(purge(f[f["year"] < 2025], 2025))
    imp = gb.m.booster_.feature_importance("gain")
    imp = pd.Series(imp / imp.sum(), index=FEATURES).sort_values(ascending=False)
    lines += [
        "",
        "## LightGBM gain by feature (fit on 2012-2024)",
        "",
        ", ".join(f"{k} {v:.2f}" for k, v in imp.items()),
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pooled")
    ap.add_argument("step", choices=("build", "run"))
    ap.add_argument("--export", type=Path, default=FX_EXPORT)
    a = ap.parse_args(argv or [])
    if a.step == "build":
        b = build_store()
        COUNTS.write_text(counts_report(b), encoding="utf-8", newline="\n")
        print(f"wrote {COUNTS}")
        return 0
    REPORT.write_text(run(a.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
