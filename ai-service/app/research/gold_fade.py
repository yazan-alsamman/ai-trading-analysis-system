"""Gold: trade against the five's trades a model expects to fail (``docs/strategies/
GOLD_FADE.md``, registered 2026-11-10; Fadi's idea).

    python -m app research gold-fade build --export <GOLD M1>

Each trade of the five gets a fade: the same bar and price, the other side, D the same, M8 or a
1 D target. A model trained on earlier fades (LR or LightGBM, Platt, EV rule) says which fades to
take. Walk-forward 2015-2021, then the check (XAUUSD 2022 to 2026-01-09) and FxPro 2022 on."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from app.research import gold_exam as ge
from app.research import gold_lab as gl
from app.research import gold_live as gv
from app.research import gold_loss as gls
from app.research import gold_night as gn
from app.research import gold_shadow as gs

REPORT = gl.OUT_DIR / "gold_fade_xauusd.md"  # not gold_fade.md: GOLD_FADE.md on Windows
CAT = ["strategy", "kind", "side", "hour", "weekday", "news", "with_day", "structure", "earlier"]
NUM = ["d_atr", "vol_regime", "moved", "prev_bar", "yday_range", "cost_q", "minute"]
MODELS, EXITS = ("lr", "lgbm"), ("M8", "TP1")
WF_YEARS = range(2015, 2022)
CHECK_START = pd.Timestamp("2022-01-01", tz="UTC")
RANDOM_RUNS, MIN_ACCEPTED, MAX_CORR = 20, 300, 0.2


def fades(cx: gl.Ctx, t: pd.DataFrame, exit_: str) -> pd.DataFrame:
    """The fade of each trade in ``t`` (the five's), simulated; aligned with ``t`` by row."""
    sig = pd.DataFrame({
        "strategy": "F-" + t["strategy"], "i": t["i"], "dir": -t["dir"], "entry": t["entry"],
        "risk": t["risk"], "tp_r": 1.0 if exit_ == "TP1" else np.nan, "end": t["end"],
        "row": np.arange(len(t)),
    })  # fmt: skip
    f = gs.finish(gl.simulate(sig, cx, "M8" if exit_ == "M8" else "M0"), cx)
    f = f.merge(sig[["strategy", "i", "row"]], on=["strategy", "i"], how="left")
    return f.drop_duplicates("row").set_index("row").reindex(np.arange(len(t)))


def dataset(cx: gl.Ctx, fr: dict, exit_: str) -> pd.DataFrame:
    t = gls.trades(cx)
    x = gls.features(cx, fr, t)
    x["minute"] = cx.ny_min[t["i"].to_numpy()].astype(float)
    f = fades(cx, t, exit_)
    ts = pd.to_datetime(cx.m["close_utc"].to_numpy()[t["i"]], utc=True)
    te = pd.to_datetime(cx.m["close_utc"].to_numpy()[f["j"].fillna(t["i"]).astype(int)], utc=True)
    cols = ["net", "net_slip", "gross", "exit", "year"]
    d = pd.concat([x.reset_index(drop=True), f[cols].reset_index(drop=True)], axis=1)
    d["ts"], d["exit_ts"], d["tday"] = ts, te, t["tday"].to_numpy()
    d["orig_net"] = t["net_slip"].to_numpy()
    return d[d["net"].notna()].reset_index(drop=True)


class Design:
    """One-hot categories, median-imputed scaled numbers (fitted on the fit rows)."""

    def fit(self, x: pd.DataFrame) -> Design:
        self.levels = {k: np.unique(x[k].astype(str)) for k in CAT}
        self.med = x[NUM].median()
        z = self._raw(x)
        self.mu, self.sd = z.mean(0), z.std(0)
        self.sd[self.sd == 0] = 1.0
        return self

    def _raw(self, x: pd.DataFrame) -> np.ndarray:
        parts = [x[NUM].fillna(self.med).to_numpy(float)]
        for k, lv in self.levels.items():
            parts.append((x[k].astype(str).to_numpy()[:, None] == lv[None, :]).astype(float))
        return np.hstack(parts)

    def transform(self, x: pd.DataFrame) -> np.ndarray:
        return (self._raw(x) - self.mu) / self.sd


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, model: str) -> tuple[np.ndarray, dict]:
    """p for ``test`` (fit on the first 75% of train by time, Platt on the rest), and m1, m0."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss

    from app.research import gold_ahf as ahf
    from app.research import meta

    train = train.sort_values("ts")
    cut = int(0.75 * len(train))
    fit, cal = train.iloc[:cut], train.iloc[cut:]
    y, w = (fit["net"] > 0).to_numpy(int), fit["net"].abs().to_numpy()
    if model == "lr":
        des = Design().fit(fit)
        xf = des.transform(fit)
        folds = np.array_split(np.arange(len(fit)), meta.INNER_FOLDS + 1)
        best_c, best_l = meta.C_GRID[0], np.inf
        for c_ in meta.C_GRID:
            loss = 0.0
            for j in range(1, len(folds)):
                tr_, va = np.concatenate(folds[:j]), folds[j]
                m = LogisticRegression(C=c_, max_iter=2000).fit(xf[tr_], y[tr_],
                                                                sample_weight=w[tr_])  # fmt: skip
                loss += log_loss(y[va], m.predict_proba(xf[va])[:, 1], labels=[0, 1],
                                 sample_weight=w[va])  # fmt: skip
            if loss < best_l:
                best_c, best_l = c_, loss
        m = LogisticRegression(C=best_c, max_iter=2000).fit(xf, y, sample_weight=w)

        def raw(x: pd.DataFrame) -> np.ndarray:
            return m.predict_proba(des.transform(x))[:, 1]
    else:
        import lightgbm as lgb

        cats = {k: np.unique(train[k].astype(str)) for k in CAT}

        def mat(x: pd.DataFrame) -> pd.DataFrame:
            z = x[NUM].copy()
            for k in CAT:
                z[k] = pd.Categorical(x[k].astype(str), categories=cats[k])
            return z

        ds = lgb.Dataset(mat(fit), y, weight=w, categorical_feature=CAT)
        b = lgb.train({**meta.LGBM_PARAMS, "verbosity": -1}, ds,
                      num_boost_round=meta.LGBM_ROUNDS)  # fmt: skip

        def raw(x: pd.DataFrame) -> np.ndarray:
            return b.predict(mat(x))

    cal_f = ahf._platt(raw(cal), (cal["net"] > 0).to_numpy(int))
    stats = {"m1": train.loc[train["net"] > 0, "net"].mean(),
             "m0": train.loc[train["net"] <= 0, "net"].mean(),
             "base": (train["net"] > 0).mean()}  # fmt: skip
    return cal_f(raw(test)), stats


def accept(p: np.ndarray, s: dict) -> np.ndarray:
    return p * s["m1"] + (1 - p) * s["m0"] > 0


def walk_forward(d: pd.DataFrame, model: str) -> pd.DataFrame:
    out = []
    for y in WF_YEARS:
        a = pd.Timestamp(f"{y}-01-01", tz="UTC")
        train = d[(d["exit_ts"] < a - pd.Timedelta(days=1))]
        test = d[(d["ts"] >= a) & (d["ts"] < a + pd.DateOffset(years=1))]
        if len(train) < 300 or not len(test):
            continue
        p, s = fit_predict(train, test, model)
        r = test[["ts", "year", "tday", "net", "net_slip", "orig_net"]].copy()
        r["p"], r["base"], r["accept"] = p, s["base"], accept(p, s)
        out.append(r)
    return pd.concat(out)


def random_p95(r: pd.DataFrame) -> float:
    res = []
    for s in range(1, RANDOM_RUNS + 1):
        rng = np.random.default_rng(s)
        acc = []
        for _, g in r.groupby("year"):
            k = int(g["accept"].sum())
            if k:
                acc.append(g["net_slip"].to_numpy()[rng.choice(len(g), k, replace=False)])
        res.append(np.concatenate(acc).mean() if acc else np.nan)
    return float(np.nanquantile(res, 0.95))


def brier_skill(r: pd.DataFrame) -> float:
    y = (r["net"] > 0).to_numpy(float)
    return 1 - np.mean((r["p"] - y) ** 2) / np.mean((r["base"] - y) ** 2)


def daily_corr(acc: pd.DataFrame, day: dict[str, pd.DataFrame]) -> dict[str, float]:
    a = acc.rename(columns={"net_slip": "net"})[["tday", "net"]]
    return gn.correlations(a, day)


def build(export: Path) -> str:
    fr = gl.load()
    cx = gl.context(fr)
    fx_fr = ge.frames_from_lines(gv.fx_lines(export))
    fx = gl.context(fx_fr)
    rows, wf = [], {}
    data = {e: dataset(cx, fr, e) for e in EXITS}
    for model, e in itertools.product(MODELS, EXITS):
        d = data[e]
        r = walk_forward(d, model)
        acc = r[r["accept"]]
        p95 = random_p95(r)
        mu = acc["net_slip"].mean() if len(acc) else np.nan
        gate1 = len(acc) >= MIN_ACCEPTED and mu > 0 and mu > p95
        wf[(model, e)] = r
        rows.append({"model": model, "exit": e, "fades": len(r), "all": r["net_slip"].mean(),
                     "accepted": len(acc), "acc": acc["net_slip"].mean() if len(acc) else np.nan,
                     "p95": p95, "bss": brier_skill(r), "gate1": gate1})  # fmt: skip
    g = pd.DataFrame(rows)
    lines = [
        "# Gold: trade against the five's trades a model expects to fail",
        "",
        "_`python -m app research gold-fade build`, registered in `GOLD_FADE.md` (2026-11-10). "
        "Fades of the five's own trades (M8 or a 1 D target); LR / LightGBM with Platt and the EV "
        "rule; net R with slip. XAUUSD walk-forward 2015-2021, check 2022 to 2026-01-09; FxPro "
        f"(`{export.name}`) 2022 on._",
        "",
        "## 1. Walk-forward 2015-2021",
        "",
        "| Model | Exit | Fades | All fades | Accepted | Accepted mean | Random 95th | BSS "
        "| Gate 1 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *[
            f"| {r.model} | {r.exit} | {r.fades:,} | {r.all:+.3f} | {r.accepted:,} "
            f"| {r.acc:+.3f} | {r.p95:+.3f} | {r.bss:+.3f} | {'yes' if r.gate1 else 'no'} |"
            for r in g.itertuples()
        ],
        "",
        "By year (accepted fades, mean net R with slip):",
        "",
        "| Year | " + " | ".join(f"{m} {e}" for m, e in wf) + " |",
        "| --- |" + " --- |" * len(wf),
    ]
    for y in WF_YEARS:
        cells = []
        for r in wf.values():
            a = r[(r["year"] == y) & r["accept"]]
            cells.append(f"{a['net_slip'].mean():+.3f} ({len(a)})" if len(a) else "-")
        lines.append(f"| {y} | " + " | ".join(cells) + " |")
    ok = g[g["gate1"]]
    if not len(ok):
        lines += ["", "**No setting passes gate 1: the fade is dropped.**"]
        return "\n".join(lines) + "\n"
    best = ok.sort_values("acc", ascending=False).iloc[0]
    model, e = best["model"], best["exit"]
    d = data[e]
    train = d[d["exit_ts"] < CHECK_START - pd.Timedelta(days=1)]
    test = d[d["ts"] >= CHECK_START]
    p, s = fit_predict(train, test, model)
    acc2 = test[accept(p, s)]
    fd = dataset(fx, fx_fr, e)
    fd = fd[fd["ts"] >= CHECK_START]
    pf, _ = fit_predict(train, fd, model)
    accf = fd[accept(pf, s)]
    acc26 = accf[accf["ts"].dt.year == 2026]
    corr = daily_corr(accf, {k: v for k, v in gn.day_strategies(fx).items()})
    gates = [True, acc2["net_slip"].mean() > 0 if len(acc2) else False,
             accf["net_slip"].mean() > 0 if len(accf) else False,
             all(v < MAX_CORR for v in corr.values())]  # fmt: skip

    def m(x: pd.DataFrame) -> str:
        return f"{x['net_slip'].mean():+.3f} ({len(x):,})" if len(x) else "-"

    lines += [
        "",
        f"## 2. Chosen: {model} / {e}",
        "",
        "| Period | All fades | Accepted |",
        "| --- | --- | --- |",
        f"| XAUUSD check 2022 to 2026-01-09 | {m(test)} | {m(acc2)} |",
        f"| FxPro 2022 on | {m(fd)} | {m(accf)} |",
        f"| FxPro 2026 | {m(fd[fd['ts'].dt.year == 2026])} | {m(acc26)} |",
        "",
        "Daily correlation of the accepted fades with the five (FxPro): "
        + ", ".join(f"{k} {v:+.2f}" for k, v in corr.items())
        + ".",
        "",
        "| Gate | Met |",
        "| --- | --- |",
        *[f"| {n} | {'yes' if v else 'no'} |" for n, v in zip(
            ["1. Walk-forward", "2. Check", "3. FxPro", "4. Correlation < +0.2"], gates,
            strict=True)],
        "",
        f"**Decision (§3): {'shadow strategy' if all(gates) else 'dropped'}.**",
    ]  # fmt: skip
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research gold-fade")
    ap.add_argument("step", choices=("build",))
    ap.add_argument("--export", type=Path, required=True, help="FxPro GOLD M1 export")
    args = ap.parse_args(argv)
    REPORT.write_text(build(args.export), encoding="utf-8", newline="\n")
    print(f"wrote {REPORT}")
    return 0
