"""P4 task 3: meta-models E2-E4 on the walk-forward test windows, as registered in
``docs/phase4/PREREG_P4.md`` (2026-10-23, before any fit).

    python -m app research meta --model lr                 # trial 7: E2, primary (H2)
    python -m app research meta --model lgbm               # trial 8: E3
    python -m app research meta --model mlp                # trial 9: E4
    python -m app research meta --model lr --label tp      # trial 10: E2, design label
    python -m app research meta --model lr --arm context   # control: E1, 29 context features
    python -m app research meta --model lr --arm e0        # control: E0, 20 replications

Reads ``data/processed/p4_dataset_<rules>.parquet`` (``python -m app features build``) and, for
``--arm e0``, ``p4_e0_<rules>.parquet`` (``python -m app features e0``). Writes
``docs/phase4/meta_<tag>.md`` and ``data/processed/p4_meta_<tag>.parquet`` (one row per test
prediction, untracked), where the tag is the model, then ``_tp`` or the arm.

**Models** (§2; all on the protocol of ``walkforward.predict``: label ``1{net R > 0}``, ``|net R|``
weights, Platt):

* **E2**: elastic-net logistic regression (``saga``, ``l1_ratio`` 0.5) on median-imputed,
  standardised features (both from the fit rows). ``C`` from ``C_GRID`` by weighted log loss on
  ``INNER_FOLDS`` expanding folds of the fit rows: the fit rows, in decision order, split into
  ``INNER_FOLDS + 1`` blocks; fold ``i`` validates on block ``i`` and trains on the earlier rows
  whose exit plus the embargo is not after the block's first decision. The mean loss over the
  folds picks ``C``; the model is then refitted on all fit rows.
* **E3**: LightGBM with the fixed parameters of ``LGBM_PARAMS``, ``LGBM_ROUNDS`` rounds, NaN
  native. ``deterministic``, ``force_row_wise`` and one thread only make the run repeatable.
* **E4**: MLP (16, ReLU, ``alpha`` 1e-2, Adam, 300 iterations, no early stopping), imputed and
  scaled as E2; the mean of ``MLP_SEEDS`` seeds.

**Acceptance rule** (§4): per window, ``m1`` and ``m0`` are the mean net R of the training rows
(fit and calibration) with y = 1 and y = 0; a test setup is accepted when
``p * m1 + (1 - p) * m0 > 0``.

**H2** (§5): accepted mean net R minus the mean of every test row, by a weekly block bootstrap
(``H2_BOOT`` resamples of whole weeks, every instrument of a week together), one-sided 95%.
Supported only if the lower bound is above 0, at least ``MIN_ACCEPTED`` trades are accepted and
the accepted trades' yearly total R is not below all trades' in at least ``MIN_YEARS`` of the
years 2018-2024; under ``MIN_ACCEPTED`` the result is "insufficient". Decided on E2 alone.

**Deflated Sharpe** (§5) of the accepted per-trade series, with ``N_TRIALS`` trials. The
expected maximum Sharpe of ``N`` unskilled trials needs the variance of their Sharpe ratios; it
is taken as the estimator's variance under no skill, ``1 / (T - 1)``, because the registered
trials are not all measured on the same trade series.

**Controls** (§7, not used to choose anything): ``--arm context`` is E1 with the 29 context
features; ``--arm e0`` runs every replication of E0 (29 features) as its own walk-forward and
reports the distribution of the gains. Its report reads the main and context runs of the same
model, if present, for the comparison of §7. The diagnostics are label uniqueness (AFML ch. 4),
the LR coefficients, LightGBM SHAP (TreeSHAP, ``pred_contrib``) and their stability over the
windows."""

from __future__ import annotations

import argparse
import math
import sys
import warnings
from pathlib import Path
from statistics import NormalDist

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from app.config import splits
from app.data.importer import DEFAULT_OUT as STORE
from app.features.setup_features import CONTEXT, E0_REPS, FEATURES
from app.research.baselines import week_of
from app.research.walkforward import (
    SEED,
    brier,
    ece,
    folds,
    known_by,
    predict,
    reliability,
    scores,
    target,
)

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase4"
C_GRID = np.logspace(-3, 1, 10)
INNER_FOLDS = 3
SAGA_MAX_ITER = 10_000
LGBM_PARAMS = {
    "objective": "binary",
    "num_leaves": 6,
    "max_depth": 3,
    "min_data_in_leaf": 40,
    "extra_trees": True,
    "lambda_l2": 10.0,
    "path_smooth": 5.0,
    "max_bin": 63,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "seed": SEED,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbose": -1,
}
LGBM_ROUNDS = 200
MLP_SEEDS = 5
H2_BOOT = 10_000
MIN_ACCEPTED = 30
YEARS = tuple(range(2018, 2025))
MIN_YEARS = 4
N_TRIALS = 10
EULER = 0.5772156649015329
TOP = 10


def _counting(fn, *args, **kwargs):
    """Run ``fn`` and count the convergence warnings it raised (they are reported, not hidden)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        out = fn(*args, **kwargs)
    return out, sum(issubclass(w.category, ConvergenceWarning) for w in caught)


class _Scaled:
    """Median imputation and standardisation, both from the fit rows only."""

    def _prepare(self, x: np.ndarray) -> np.ndarray:
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True).fit(x)
        self.scaler = StandardScaler().fit(self.imputer.transform(x))
        return self._x(x)

    def _x(self, x: np.ndarray) -> np.ndarray:
        return self.scaler.transform(self.imputer.transform(x))


def inner_folds(rows: pd.DataFrame, k: int = INNER_FOLDS) -> list[tuple[np.ndarray, np.ndarray]]:
    """(train, validation) positions in ``rows``: ``k`` expanding folds, purged and embargoed
    like the outer protocol."""
    order = np.argsort(rows["decision_utc"].to_numpy(), kind="stable")
    blocks = np.array_split(order, k + 1)
    out = []
    for i in range(1, k + 1):
        val = blocks[i]
        before = np.concatenate(blocks[:i])
        first = rows["decision_utc"].iloc[val].min()
        train = before[known_by(rows.iloc[before], first, splits().embargo_days)]
        out.append((train, val))
    return out


def _lr(c: float) -> LogisticRegression:
    return LogisticRegression(
        C=c, l1_ratio=0.5, solver="saga", max_iter=SAGA_MAX_ITER, random_state=SEED
    )


class E2(_Scaled):
    """Elastic-net logistic regression, ``C`` by purged inner CV (weighted log loss)."""

    name = "E2 elastic-net logistic regression"

    def fit(self, x, y, sample_weight, rows) -> E2:
        self.unconverged = 0
        losses = np.zeros(len(C_GRID))
        used = 0
        for tr, va in inner_folds(rows):
            if len(np.unique(y[tr])) < 2 or len(np.unique(y[va])) < 2:
                continue
            used += 1
            inner = _Scaled()
            xt, xv = inner._prepare(x[tr]), inner._x(x[va])
            w = sample_weight[tr] / sample_weight[tr].mean()
            for i, c in enumerate(C_GRID):
                m, n = _counting(_lr(c).fit, xt, y[tr], sample_weight=w)
                self.unconverged += n
                p = m.predict_proba(xv)[:, 1]
                losses[i] += log_loss(y[va], p, sample_weight=sample_weight[va], labels=[0, 1])
        if used == 0:
            raise ValueError("no inner fold has both classes: C cannot be chosen")
        self.losses = losses / used
        self.c = float(C_GRID[int(np.argmin(self.losses))])
        xs = self._prepare(x)
        self.model, n = _counting(_lr(self.c).fit, xs, y, sample_weight=sample_weight)
        self.unconverged += n
        return self

    def predict_proba(self, x):
        return self.model.predict_proba(self._x(x))

    def info(self, x_test) -> dict:
        return {"C": self.c, "importance": self.model.coef_[0], "unconverged": self.unconverged}


class E3:
    """LightGBM-small, fixed parameters, no tuning."""

    name = "E3 LightGBM-small"

    def fit(self, x, y, sample_weight, rows) -> E3:
        data = lgb.Dataset(x, label=y, weight=sample_weight, free_raw_data=False)
        self.booster = lgb.train(LGBM_PARAMS, data, num_boost_round=LGBM_ROUNDS)
        return self

    def predict_proba(self, x):
        p = self.booster.predict(x)
        return np.c_[1 - p, p]

    def info(self, x_test) -> dict:
        contrib = self.booster.predict(x_test, pred_contrib=True)[:, :-1]
        return {"importance": np.abs(contrib).mean(axis=0), "unconverged": 0}


class E4(_Scaled):
    """MLP (16), the mean of ``MLP_SEEDS`` seeds."""

    name = "E4 MLP (16)"

    def fit(self, x, y, sample_weight, rows) -> E4:
        xs = self._prepare(x)
        self.models, self.unconverged = [], 0
        for i in range(MLP_SEEDS):
            mlp = MLPClassifier(
                hidden_layer_sizes=(16,),
                activation="relu",
                alpha=1e-2,
                solver="adam",
                max_iter=300,
                early_stopping=False,
                random_state=SEED + i,
            )
            m, n = _counting(mlp.fit, xs, y, sample_weight=sample_weight)
            self.models.append(m)
            self.unconverged += n
        return self

    def predict_proba(self, x):
        xs = self._x(x)
        p = np.mean([m.predict_proba(xs)[:, 1] for m in self.models], axis=0)
        return np.c_[1 - p, p]

    def info(self, x_test) -> dict:
        return {"unconverged": self.unconverged}


MODELS = {"lr": E2, "lgbm": E3, "mlp": E4}
TRIAL = {("lr", "net"): 7, ("lgbm", "net"): 8, ("mlp", "net"): 9, ("lr", "tp"): 10}


def accept(df: pd.DataFrame, pred: pd.DataFrame, label: str = "net") -> pd.DataFrame:
    """``pred`` with the window's ``m1``, ``m0``, the expected value and ``accepted`` (§4); the
    means come from the window's training rows only."""
    y = target(df, label)
    r = df["net_r"].to_numpy(float)
    fs = folds(df)
    m = {k: (r[fs[k].train][y[fs[k].train] == 1].mean(), r[fs[k].train][y[fs[k].train] == 0].mean())
         for k in pred["fold"].unique()}  # fmt: skip
    out = pred.copy()
    out["m1"] = out["fold"].map(lambda k: m[k][0])
    out["m0"] = out["fold"].map(lambda k: m[k][1])
    out["ev"] = out["p"] * out["m1"] + (1 - out["p"]) * out["m0"]
    out["accepted"] = out["ev"] > 0
    return out


def scored_rows(df: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    """Every test row with its prediction, acceptance and outcome."""
    t = df.iloc[pred["row"].to_numpy()].reset_index(drop=True)
    return pd.concat([t, pred.drop(columns=["row"]).reset_index(drop=True)], axis=1)


def _weekly_diff(t: pd.DataFrame, rng, boot: int) -> np.ndarray:
    """Bootstrap of accepted mean minus all mean, whole weeks resampled."""
    g = pd.DataFrame(
        {
            "w": week_of(t["decision_utc"]),
            "s": t["net_r"],
            "sa": t["net_r"].where(t["accepted"], 0.0),
            "ca": t["accepted"].astype(float),
        }
    ).groupby("w")
    s, c = g["s"].sum().to_numpy(), g["s"].count().to_numpy(float)
    sa, ca = g["sa"].sum().to_numpy(), g["ca"].sum().to_numpy()
    idx = rng.integers(0, len(s), size=(boot, len(s)))
    with np.errstate(invalid="ignore", divide="ignore"):
        return sa[idx].sum(1) / ca[idx].sum(1) - s[idx].sum(1) / c[idx].sum(1)


def sign_test(diffs: np.ndarray) -> tuple[int, int, float]:
    """Positive differences, non-zero differences, two-sided binomial p."""
    d = diffs[~np.isnan(diffs) & (diffs != 0)]
    n, k = len(d), int((d > 0).sum())
    if n == 0:
        return 0, 0, 1.0
    tail = sum(math.comb(n, i) for i in range(min(k, n - k) + 1)) / 2**n
    return k, n, min(1.0, 2 * tail)


def h2(t: pd.DataFrame, seed: int = SEED, boot: int = H2_BOOT) -> dict:
    """The H2 test of §5 on the test rows ``t`` (with ``accepted``)."""
    acc = t[t["accepted"]]
    n = len(acc)
    out = {
        "trades": len(t),
        "accepted": n,
        "share": n / len(t),
        "all_mean": t["net_r"].mean(),
        "all_mean_2x": t["net_r_2x"].mean(),
        "acc_mean": acc["net_r"].mean() if n else np.nan,
        "acc_mean_2x": acc["net_r_2x"].mean() if n else np.nan,
        "precision": (acc["net_r"] > 0).mean() if n else np.nan,
    }
    out["diff"] = out["acc_mean"] - out["all_mean"]
    diffs = _weekly_diff(t, np.random.default_rng(seed), boot)
    out["undefined"] = int(np.isnan(diffs).sum())
    out["lower"] = float(np.nanpercentile(diffs, 5)) if n else np.nan
    year = t["decision_utc"].dt.year
    tot_all = t.groupby(year)["net_r"].sum()
    tot_acc = acc.groupby(year[t["accepted"]])["net_r"].sum()
    out["years"] = {y: (float(tot_acc.get(y, 0.0)), float(tot_all.get(y, 0.0))) for y in YEARS}
    out["years_ok"] = sum(a >= b for a, b in out["years"].values())
    win = acc.groupby("fold")["net_r"].mean().reindex(t["fold"].unique())
    win = win - t.groupby("fold")["net_r"].mean().reindex(win.index)
    out["sign"] = sign_test(win.to_numpy(float))
    if n < MIN_ACCEPTED:
        out["status"] = "insufficient"
    elif out["lower"] > 0 and out["years_ok"] >= MIN_YEARS:
        out["status"] = "supported"
    else:
        out["status"] = "not supported"
    return out


def deflated_sharpe(r: np.ndarray, n_trials: int = N_TRIALS) -> dict:
    """Per-trade Sharpe of ``r`` and the probability that it beats the expected maximum Sharpe of
    ``n_trials`` unskilled trials (Bailey and Lopez de Prado, 2014)."""
    r = np.asarray(r, float)
    t = len(r)
    if t < 3 or r.std(ddof=1) == 0:
        return {"sharpe": np.nan, "sr0": np.nan, "dsr": np.nan, "t": t}
    sr = r.mean() / r.std(ddof=1)
    z = (r - r.mean()) / r.std(ddof=0)
    g3, g4 = float((z**3).mean()), float((z**4).mean())
    nd = NormalDist()
    sr0 = 0.0
    if n_trials > 1:
        sr0 = math.sqrt(1 / (t - 1)) * (
            (1 - EULER) * nd.inv_cdf(1 - 1 / n_trials)
            + EULER * nd.inv_cdf(1 - 1 / (n_trials * math.e))
        )
    denom = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr**2, 1e-12))
    return {"sharpe": sr, "sr0": sr0, "dsr": nd.cdf((sr - sr0) * math.sqrt(t - 1) / denom), "t": t}


def uniqueness(df: pd.DataFrame) -> np.ndarray:
    """AFML ch. 4 average uniqueness of each label: the mean, over the 15-minute bars from its
    decision bar to its exit bar, of 1 / the number of labels spanning that bar."""
    q = np.int64(15 * 60 * 10**9)
    s = df["decision_utc"].to_numpy("datetime64[ns]").astype(np.int64) // q
    e = df["exit_utc"].to_numpy("datetime64[ns]").astype(np.int64) // q
    base = s.min()
    s, e = s - base, e - base
    c = np.zeros(e.max() + 2)
    np.add.at(c, s, 1)
    np.add.at(c, e + 1, -1)
    c = np.cumsum(c)[:-1]
    inv = np.r_[0.0, np.cumsum(np.where(c > 0, 1 / np.maximum(c, 1), 0.0))]
    return (inv[e + 1] - inv[s]) / (e - s + 1)


def run(df: pd.DataFrame, model: str, features: list[str], label: str = "net"):
    """Predictions, acceptance and window diagnostics of one family on one dataset."""
    info: list = []
    pred = predict(df, features, MODELS[model], label, info)
    return accept(df, pred, label), info


def _r(x: float) -> str:
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.3f}"


def _gain(t: pd.DataFrame) -> float:
    return t.loc[t["accepted"], "net_r"].mean() - t["net_r"].mean()


def render(
    t: pd.DataFrame, df: pd.DataFrame, info: list, model: str, label: str, arm: str | None,
    features: list[str], rules: str,
) -> str:  # fmt: skip
    """Report of a run on E1 (all features or ``--arm context``)."""
    y = target(df, label)
    h = h2(t)
    s = scores(t[["fold", "p", "base_rate"]].assign(row=np.arange(len(t))), target(t, label),
               week_of(t["decision_utc"]))  # fmt: skip
    trial = TRIAL.get((model, label)) if arm is None else None
    gate = "pass" if s["bss"] > 0 and s["ece_debiased"] < 0.05 else "fail"
    lo, hi = s["ece_debiased_ci"]
    ds = deflated_sharpe(t.loc[t["accepted"], "net_r"].to_numpy())
    lines = [
        f"# P4: {MODELS[model].name}"
        + ("" if label == "net" else ", design label (TP first)")
        + ("" if arm is None else f", control arm `{arm}`"),
        "",
        "_Generated by `python -m app research meta`; protocol registered in"
        " `docs/phase4/PREREG_P4.md` (2026-10-23) before any fit; code in"
        " `app/research/meta.py` and `app/research/walkforward.py`."
        f" Rules {rules}; {len(features)} features; label"
        f" {'1{net R > 0}' if label == 'net' else '1{TP first}'} weighted by |net R|; Platt;"
        f" seed {SEED}. Secondary holdout and lockbox not loaded._",
        "",
        f"Trial: **{trial}** in `docs/phase3/TRIALS.md`."
        if trial
        else "Control run (`PREREG_P4.md` §7): not a trial, not used to choose anything.",
        "",
        "## H2: accepted trades against all trades (13 test windows, 2018-01 to 2024-06)",
        "",
        "| | Value |",
        "| --- | --- |",
        f"| Test trades | {h['trades']} |",
        f"| Accepted (EV > 0) | {h['accepted']} ({h['share']:.1%}) |",
        f"| Mean net R, accepted | {_r(h['acc_mean'])} |",
        f"| Mean net R, all | {_r(h['all_mean'])} |",
        f"| Difference (accepted - all) | {_r(h['diff'])} |",
        f"| One-sided 95% lower bound (weekly block, {H2_BOOT} resamples) | {_r(h['lower'])} |",
        f"| Years 2018-2024 with accepted total R >= all total R | {h['years_ok']} of"
        f" {len(YEARS)} (need {MIN_YEARS}) |",
        f"| Precision (accepted with net R > 0) | {h['precision']:.1%} |"
        if h["accepted"]
        else "| Precision (accepted with net R > 0) | - |",
        f"| Mean net R at 2x costs, accepted / all | {_r(h['acc_mean_2x'])} /"
        f" {_r(h['all_mean_2x'])} |",
        f"| Sign test of the window differences | {h['sign'][0]} of {h['sign'][1]} positive,"
        f" p = {h['sign'][2]:.3f} |",
        f"| **H2** | **{h['status']}** (minimum {MIN_ACCEPTED} accepted"
        + ("; decided on E2 alone" if model != "lr" else "")
        + ") |",
        "",
    ]
    if h["undefined"]:
        lines += [f"{h['undefined']} bootstrap resamples had no accepted trade and are left out.",
                  ""]  # fmt: skip
    lines += [
        "## Calibration (pooled test predictions; P4 gate)",
        "",
        "| | Value |",
        "| --- | --- |",
        f"| Brier / climatology | {s['brier']:.4f} / {s['brier_ref']:.4f} |",
        f"| Brier skill (gate > 0) | {s['bss']:+.4f} |",
        f"| ECE, 10 equal-mass bins | {s['ece']:.4f} |",
        f"| Debiased ECE (gate < 0.05) | {s['ece_debiased']:+.4f} (95% weekly block"
        f" {lo:+.4f} to {hi:+.4f}) |",
        f"| Calibration intercept / slope | {s['intercept']:+.3f} / {s['slope']:.3f} |",
        f"| **Gate** | **{gate}** |",
        "",
        "Reliability (equal-mass bins):",
        "",
        "| Bin | Trades | Mean p | Hit rate |",
        "| --- | --- | --- | --- |",
        *[f"| {i + 1} | {int(b.n)} | {b.mean_p:.3f} | {b.rate:.3f} |"
          for i, b in enumerate(reliability(t["p"].to_numpy(), target(t, label)).itertuples())],
        "",
        "## Per window (diagnostics)",
        "",
        "| Window | Train | Test | Base rate | m1 / m0 | Accepted | Mean net R acc. / all |"
        " Brier | ECE |" + (" C |" if model == "lr" else ""),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |" + (" --- |" if model == "lr"
                                                                    else ""),
    ]  # fmt: skip
    fs = folds(df)
    by_fold = {d["fold"]: d for d in info}
    for k, g in t.groupby("fold"):
        f = fs[k]
        yy = target(g, label)
        acc = g[g["accepted"]]
        lines.append(
            f"| {f.start:%Y-%m} | {len(f.train)} | {len(g)} | {y[f.train].mean():.1%} |"
            f" {_r(g['m1'].iloc[0])} / {_r(g['m0'].iloc[0])} | {len(acc)} |"
            f" {_r(acc['net_r'].mean() if len(acc) else np.nan)} / {_r(g['net_r'].mean())} |"
            f" {brier(g['p'].to_numpy(), yy):.4f} | {ece(g['p'].to_numpy(), yy):.4f} |"
            + (f" {by_fold[k]['C']:.4g} |" if model == "lr" else "")
        )
    lines += [
        "",
        "## Per instrument (XAUUSD first) and per year",
        "",
        "| Instrument | Trades | Accepted | Mean net R acc. / all |",
        "| --- | --- | --- | --- |",
    ]
    order = ["XAUUSD", *sorted(s for s in t["symbol"].unique() if s != "XAUUSD")]
    for sym in order:
        g = t[t["symbol"] == sym]
        if len(g):
            acc = g[g["accepted"]]
            lines.append(
                f"| {sym} | {len(g)} | {len(acc)} |"
                f" {_r(acc['net_r'].mean() if len(acc) else np.nan)} / {_r(g['net_r'].mean())} |"
            )
    lines += ["", "| Year | Trades | Accepted | Total R acc. / all |", "| --- | --- | --- | --- |"]
    for yr, (a, b) in h["years"].items():
        n_all = int((t["decision_utc"].dt.year == yr).sum())
        n_acc = int((t.loc[t["accepted"], "decision_utc"].dt.year == yr).sum())
        lines.append(f"| {yr} | {n_all} | {n_acc} | {a:+.1f} / {b:+.1f} |")
    dsr = "-" if np.isnan(ds["dsr"]) else f"{ds['dsr']:.3f}"
    lines += [
        "",
        f"## Deflated Sharpe (accepted trades, N = {N_TRIALS})",
        "",
        f"Per-trade Sharpe {_r(ds['sharpe'])} on {ds['t']} trades; expected maximum of"
        f" {N_TRIALS} unskilled trials {_r(ds['sr0'])}; deflated Sharpe ratio {dsr}"
        " (trial Sharpe variance taken as 1 / (T - 1)).",
        "",
    ]
    lines += _diagnostics(df, info, features)
    return "\n".join(lines)


def top_counts(m: np.ndarray, k: int = TOP) -> np.ndarray:
    """Windows (rows of ``m``) in which each feature is among the ``k`` largest by |value|; a zero
    value is never counted, so ties among zero coefficients rank nothing."""
    top = np.argsort(-np.abs(m), axis=1, kind="stable")[:, :k]
    hit = np.take_along_axis(m, top, axis=1) != 0
    return np.bincount(top[hit], minlength=m.shape[1])


def _diagnostics(df: pd.DataFrame, info: list, features: list[str]) -> list[str]:
    u_all = uniqueness(df)
    lines = [
        "## Diagnostics (not used to choose anything)",
        "",
        "Label uniqueness (AFML ch. 4), median over the labelled setups of 2012 to 2024-06:"
        f" across instruments {np.median(u_all):.3f};"
        + "; ".join(f" {s} {np.median(uniqueness(g)):.3f}" for s, g in df.groupby("symbol"))
        + ". No uniqueness weights are used in this amendment (§7).",
        "",
    ]
    unconverged = sum(d.get("unconverged", 0) for d in info)
    if unconverged:
        lines += [f"Convergence warnings over all windows: {unconverged}.", ""]
    imps = [d["importance"] for d in info if "importance" in d]
    if imps:
        m = np.vstack(imps)
        in_top = top_counts(m)
        nonzero = (m != 0).sum(axis=0)
        positive = (m > 0).sum(axis=0)
        mean = m.mean(axis=0)
        rank = np.argsort(-np.abs(mean))
        lines += [
            "Model reading over the windows: mean value (LR: standardised coefficient; LightGBM:"
            f" mean |SHAP| on the test rows), windows in the top {TOP} (non-zero values only),"
            " windows non-zero and positive.",
            "",
            "| Feature | Mean | Top 10 | Non-zero | Positive |",
            "| --- | --- | --- | --- | --- |",
            *[f"| `{features[i]}` | {mean[i]:+.4f} | {in_top[i]} | {nonzero[i]} | {positive[i]} |"
              for i in rank],
            "",
        ]  # fmt: skip
    return lines


def render_e0(gains: pd.DataFrame, model: str, rules: str, store: Path, features: list[str]) -> str:
    """Report of the E0 control arm, with the reading of §7 if the E1 runs are in the store."""
    q = gains["gain"].quantile([0.05, 0.5, 0.95])
    lines = [
        f"# P4: {MODELS[model].name}, control arm `e0` (matched random entries)",
        "",
        "_Generated by `python -m app research meta --arm e0`; `PREREG_P4.md` §7. Each E0"
        f" replication is its own walk-forward on the {len(features)} context features, same"
        f" folds, label, weights, Platt and EV rule. Rules {rules}; seed {SEED}. Control run:"
        " not a trial, not used to choose anything._",
        "",
        "| Replication | Test trades | Accepted | Mean net R acc. / all | Gain (acc. - all) |",
        "| --- | --- | --- | --- | --- |",
        *[f"| {int(r.rep)} | {int(r.trades)} | {int(r.accepted)} | {_r(r.acc_mean)} /"
          f" {_r(r.all_mean)} | {_r(r.gain)} |" for r in gains.itertuples()],
        "",
        f"Gains over {len(gains)} replications: 5th percentile {_r(q[0.05])}, median"
        f" {_r(q[0.5])}, 95th percentile {_r(q[0.95])}.",
        "",
    ]  # fmt: skip
    found = {}
    for arm, tag in (("all 38 features", model), ("context only", f"{model}_context")):
        path = store / f"p4_meta_{tag}.parquet"
        if path.exists():
            found[arm] = _gain(pd.read_parquet(path))
    if found:
        lines += ["## Reading (§7)", "", "| E1 run | Gain (acc. - all) |", "| --- | --- |",
                  *[f"| meta(E1), {k} | {_r(v)} |" for k, v in found.items()], ""]  # fmt: skip
        if len(found) == 2:
            full, ctx = found["all 38 features"], found["context only"]
            adds = full > ctx and full > q[0.95]
            lines += [
                "The SMC pattern adds value only if meta(E1) with 38 features beats meta(E1) with"
                " the context features and its gain lies above the 95th percentile of the"
                f" meta(E0) gains: **{'yes' if adds else 'no'}** ({_r(full)} against"
                f" {_r(ctx)} and {_r(q[0.95])}). Not a gate.",
                "",
            ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research meta")
    ap.add_argument("--model", choices=sorted(MODELS), required=True)
    ap.add_argument("--label", choices=["net", "tp"], default="net")
    ap.add_argument("--arm", choices=["context", "e0"])
    ap.add_argument("--rules", default="L1")
    ap.add_argument("--reps", type=int, default=E0_REPS, help="E0 replications (--arm e0)")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    if args.label == "tp" and (args.model != "lr" or args.arm):
        print("the design label is registered for E2 on E1 only (trial 10)", file=sys.stderr)
        return 2
    tag = args.model + ("_tp" if args.label == "tp" else "") + (f"_{args.arm}" if args.arm else "")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.arm == "e0":
        path = args.store / f"p4_e0_{args.rules}.parquet"
        if not path.exists():
            print(f"{path} missing: run python -m app features e0", file=sys.stderr)
            return 1
        e0 = pd.read_parquet(path)
        rows, preds = [], []
        for rep in range(args.reps):
            df = e0[e0["rep"] == rep].sort_values("decision_utc").reset_index(drop=True)
            pred, _ = run(df, args.model, CONTEXT)
            t = scored_rows(df, pred)
            preds.append(t.assign(rep=rep))
            acc = t[t["accepted"]]
            rows.append({"rep": rep, "trades": len(t), "accepted": len(acc),
                         "acc_mean": acc["net_r"].mean(), "all_mean": t["net_r"].mean(),
                         "gain": _gain(t)})  # fmt: skip
            print(f"E0 replication {rep}: {len(acc)} of {len(t)} accepted", file=sys.stderr)
        pd.concat(preds, ignore_index=True).to_parquet(
            args.store / f"p4_meta_{tag}.parquet", index=False
        )
        report = render_e0(pd.DataFrame(rows), args.model, args.rules, args.store, CONTEXT)
    else:
        path = args.store / f"p4_dataset_{args.rules}.parquet"
        if not path.exists():
            print(f"{path} missing: run python -m app features build", file=sys.stderr)
            return 1
        df = pd.read_parquet(path).sort_values("decision_utc").reset_index(drop=True)
        features = CONTEXT if args.arm == "context" else FEATURES
        pred, info = run(df, args.model, features, args.label)
        t = scored_rows(df, pred)
        t.to_parquet(args.store / f"p4_meta_{tag}.parquet", index=False)
        report = render(t, df, info, args.model, args.label, args.arm, features, args.rules)
    (args.out / f"meta_{tag}.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0
