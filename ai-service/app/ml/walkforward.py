"""Walk-forward evaluation of the Phase 3 models (protocol frozen before the first run).

    python -m app.ml.walkforward    # docs/phase3/walkforward.{md,json}

Test windows run from 2018 to 2024-06: each calendar year, then the first half of 2024. Each window
trains on every earlier setup whose trade had closed at least one day before the window starts
(purge plus a one-day embargo); the last 20% of those, in time, calibrate the probabilities (Platt
scaling) and the rest fit the model. Hyperparameters are fixed in advance; nothing is tuned on the
walk-forward period. The lockbox (2024-07 onward) is never loaded.

The decision rule takes a setup when its expected value after costs is positive,
``EV_R = p * R - (1 - p) - cost_R``. Value is the mean net R of the setups taken, against every
setup the rules produced, with a paired bootstrap CI of the difference, at 1x and 2x costs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.dataset import DATASET, FEATURES, OUT_DIR
from app.smc.report import DEV_END, LOCKBOX_START

EMBARGO = pd.Timedelta(days=1)
CALIBRATION_FRACTION = 0.2
N_BOOT = 10_000


def windows() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    starts = pd.date_range(DEV_END, LOCKBOX_START, freq="YS")
    edges = [*starts, LOCKBOX_START] if starts[-1] < LOCKBOX_START else list(starts)
    return list(zip(edges[:-1], edges[1:], strict=True))


def closed_before(df: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Rows whose trade closed at least the embargo before ``start`` (purge plus embargo)."""
    return df[df["exit_ts"] + EMBARGO <= start]


def fit_and_calibration(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The chronologically last share of ``train`` calibrates; earlier rows that closed before it
    (with the embargo) fit the model."""
    train = train.sort_values("decision_ts")
    n_cal = max(1, int(round(CALIBRATION_FRACTION * len(train))))
    cal = train.iloc[-n_cal:]
    fit = closed_before(train.iloc[:-n_cal], cal["decision_ts"].iloc[0])
    return fit, cal


# ---- models ------------------------------------------------------------------------------------


def _logistic():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=2000),
    )


def _gbm():
    return HistGradientBoostingClassifier(
        max_depth=2,
        learning_rate=0.05,
        max_iter=100,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=0,
    )


MODELS: dict[str, Callable[[], object]] = {"logistic": _logistic, "gbm": _gbm}


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


@dataclass
class Platt:
    """Platt scaling on the model's log-odds; identity when the calibration slice has one class."""

    a: float = 1.0
    b: float = 0.0

    @classmethod
    def fit(cls, p_raw: np.ndarray, y: np.ndarray) -> Platt:
        if len(np.unique(y)) < 2:
            return cls()
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(p_raw)[:, None], y)
        return cls(float(lr.coef_[0, 0]), float(lr.intercept_[0]))

    def __call__(self, p_raw: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-(self.a * _logit(p_raw) + self.b)))


def predict_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Calibrated probabilities of every model for the setups decided in [start, end)."""
    test = df[(df["decision_ts"] >= start) & (df["decision_ts"] < end)].copy()
    train = closed_before(df, start)
    if test.empty or train["y"].nunique() < 2:
        return test.iloc[0:0]
    fit, cal = fit_and_calibration(train)
    test["window"] = f"{start:%Y-%m}"
    test["n_train"] = len(train)
    test["p_base_rate"] = train["y"].mean()
    for name, make in MODELS.items():
        model = make().fit(fit[FEATURES], fit["y"])
        platt = Platt.fit(model.predict_proba(cal[FEATURES])[:, 1], cal["y"].to_numpy())
        test[f"p_{name}"] = platt(model.predict_proba(test[FEATURES])[:, 1])
    return test


def walk_forward(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["decision_ts"] < LOCKBOX_START]
    parts = [predict_window(df, start, end) for start, end in windows()]
    return pd.concat(parts, ignore_index=True)


# ---- metrics -----------------------------------------------------------------------------------


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over equal-width probability bins."""
    idx = np.minimum((p * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(total)


def expected_value(p: np.ndarray, r: np.ndarray, cost_r: np.ndarray) -> np.ndarray:
    return p * r - (1 - p) - cost_r


def _ci(x: np.ndarray) -> list[float]:
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def evaluate(pred: pd.DataFrame, seed: int = 0) -> dict:
    """Out-of-sample metrics on the pooled walk-forward predictions."""
    rng = np.random.default_rng(seed)
    y = pred["y"].to_numpy(float)
    n = len(y)
    boot = rng.integers(0, n, size=(N_BOOT, n))
    base = pred["p_base_rate"].to_numpy()
    out: dict = {"setups": n, "win_rate": float(y.mean()), "models": {}}
    for name in ["base_rate", *MODELS]:
        p = pred[f"p_{name}"].to_numpy()
        se, se_base = (p - y) ** 2, (base - y) ** 2
        bss_boot = 1 - se[boot].mean(axis=1) / se_base[boot].mean(axis=1)
        m = {
            "brier": brier(p, y),
            "brier_skill": 1 - se.mean() / se_base.mean(),
            "brier_skill_ci95": _ci(bss_boot),
            "ece": ece(p, y),
            "auc": float(roc_auc_score(y, p)) if 0 < y.sum() < n else float("nan"),
        }
        for label, k in (("costs_1x", 1.0), ("costs_2x", 2.0)):
            cost = k * pred["cost_r"].to_numpy()
            net = pred["realized_r"].to_numpy() - cost
            take = expected_value(p, pred["r_multiple"].to_numpy(), cost) > 0
            taken_mean = net[boot] * take[boot]
            counts = take[boot].sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                taken_boot = taken_mean.sum(axis=1) / counts
            diff_boot = taken_boot - net[boot].mean(axis=1)
            m[label] = {
                "taken": int(take.sum()),
                "mean_net_r_taken": float(net[take].mean()) if take.any() else float("nan"),
                "mean_net_r_taken_ci95": _ci(taken_boot[counts > 0]) if take.any() else None,
                "mean_net_r_all": float(net.mean()),
                "mean_net_r_all_ci95": _ci(net[boot].mean(axis=1)),
                "difference_ci95": _ci(diff_boot[counts > 0]) if take.any() else None,
            }
        out["models"][name] = m
    out["by_window"] = {
        w: {
            "setups": len(g),
            "win_rate": float(g["y"].mean()),
            "n_train": int(g["n_train"].iloc[0]),
            **{
                f"brier_{name}": brier(g[f"p_{name}"].to_numpy(), g["y"].to_numpy(float))
                for name in ["base_rate", *MODELS]
            },
        }
        for w, g in pred.groupby("window")
    }
    return out


def _f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def render(res: dict) -> str:
    lines = [
        "# Phase 3 — walk-forward evaluation (2018 → 2024-06)",
        "",
        "_Generated by `python -m app.ml.walkforward`. Out of sample: each window trains only on "
        "setups that closed at least a day before it starts. The lockbox is not loaded._",
        "",
        f"Setups: **{res['setups']}**; win rate {res['win_rate']:.1%}.",
        "",
        "## Probability quality",
        "",
        "| Model | Brier | Brier skill (95% CI) | ECE | AUC |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, m in res["models"].items():
        lo, hi = m["brier_skill_ci95"]
        lines.append(
            f"| {name} | {_f(m['brier'])} | {_f(m['brier_skill'])} ({_f(lo)} to {_f(hi)}) | "
            f"{_f(m['ece'])} | {_f(m['auc'])} |"
        )
    for label, title in (("costs_1x", "costs as recorded"), ("costs_2x", "2× costs (stress)")):
        lines += [
            "",
            f"## Value of the EV filter, {title}",
            "",
            "| Model | Taken | Mean net R taken (95% CI) | Mean net R, all rules (95% CI) | "
            "Difference (95% CI) |",
            "| --- | --- | --- | --- | --- |",
        ]
        for name, m in res["models"].items():
            v = m[label]
            t, a, d = v["mean_net_r_taken_ci95"], v["mean_net_r_all_ci95"], v["difference_ci95"]
            lines.append(
                f"| {name} | {v['taken']} | {_f(v['mean_net_r_taken'])}"
                + (f" ({_f(t[0])} to {_f(t[1])})" if t else "")
                + f" | {_f(v['mean_net_r_all'])} ({_f(a[0])} to {_f(a[1])}) | "
                + (f"{_f(d[0])} to {_f(d[1])}" if d else "n/a")
                + " |"
            )
    names = ["base_rate", *MODELS]
    lines += [
        "",
        "## By test window",
        "",
        "| Window | Setups | Win rate | Training rows | "
        + " | ".join(f"Brier {n}" for n in names)
        + " |",
        "| --- | --- | --- | --- | " + " | ".join("---" for _ in names) + " |",
    ]
    for w, b in res["by_window"].items():
        lines.append(
            f"| {w} | {b['setups']} | {b['win_rate']:.1%} | {b['n_train']} | "
            + " | ".join(_f(b[f"brier_{n}"]) for n in names)
            + " |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    df = pd.read_parquet(DATASET)
    pred = walk_forward(df)
    res = evaluate(pred)
    pred.to_parquet(DATASET.with_name("phase3_walkforward_predictions.parquet"), index=False)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "walkforward.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    (args.out / "walkforward.md").write_text(render(res), encoding="utf-8")
    print(f"wrote {args.out / 'walkforward.md'}")


if __name__ == "__main__":
    main()
