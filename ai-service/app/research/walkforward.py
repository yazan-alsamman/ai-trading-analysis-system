"""Walk-forward protocol (P4 task 2): folds, purge and embargo, calibration, scoring metrics.

    python -m app research walkforward          # folds and E1 (rules only) on the test windows

Writes ``docs/phase4/walkforward_<rules>.md``. Models (E2-E4) plug into ``predict`` in task 3.

**Folds** (D23): test windows of ``walk_forward_test_months`` (6) months from the start of the
walk-forward period (2018-01-01) to its end (2024-07-01): 13 windows. A setup is in a test window
when its decision time is. The training set of a window is every earlier setup (from 2012,
expanding) whose outcome is known at least ``embargo_days`` (1) before the window starts: its exit
time plus the embargo is not after the window start. That one rule is both the purge (no training
outcome overlaps the test window) and the embargo (a full day between them).

**Label and weights** (``PREREG_P4.md`` §1): ``y = 1{net R > 0}``, every exit reason kept; the
design label (TP first, the dataset's ``y``) only as ``label="tp"``. Each fit set is weighted by
``|net R|`` scaled to mean 1 over that set, so the fitted score is R-weighted, not a probability.

**Calibration** (design §9.3, ``PREREG_P4.md`` §3): the last ``CAL_SHARE`` of a training set (by
decision time) is held out as the calibration slice, purged the same way from the part the model
is fitted on. **Platt scaling only**, fitted unweighted on that slice, so the calibrated ``p``
estimates P(y = 1).

**Metrics** on the pooled test predictions (and per window, as diagnostics; ``PREREG_P4.md`` §6):
Brier score; Brier skill against the training base rate of each window (climatology, known before
the window); ECE over ``ECE_BINS`` equal-mass bins, and the debiased ECE: ECE minus the mean ECE
of ``ECE_SIMS`` label sets drawn as Bernoulli(p) on the same predictions, with a weekly block
bootstrap 95% interval (``ECE_BOOT`` resamples, each debiased with its own ``ECE_SIMS`` draws);
calibration intercept and slope (logistic regression of y on logit p). Expected value and the H2
test are in ``app/research/meta.py``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from app.config import splits
from app.data.importer import DEFAULT_OUT as STORE
from app.research.baselines import block_ci, week_of

OUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "phase4"
CAL_SHARE = 0.25
ECE_BINS = 10
ECE_SIMS = 1000
ECE_BOOT = 1000
SEED = 20261023
LABELS = ("net", "tp")


@dataclass(frozen=True)
class Fold:
    start: pd.Timestamp
    end: pd.Timestamp
    train: np.ndarray  # row positions in the dataset
    test: np.ndarray


def known_by(df: pd.DataFrame, t: pd.Timestamp, embargo_days: int) -> np.ndarray:
    """Rows whose outcome is known at least ``embargo_days`` before ``t``."""
    return (df["exit_utc"] + pd.Timedelta(days=embargo_days) <= t).to_numpy()


def folds(df: pd.DataFrame) -> list[Fold]:
    s = splits()
    start = pd.Timestamp(s.walk_forward[0], tz="UTC")
    stop = pd.Timestamp(s.walk_forward[1], tz="UTC")
    t = df["decision_utc"]
    out = []
    while start < stop:
        end = min(start + pd.DateOffset(months=s.walk_forward_test_months), stop)
        train = np.flatnonzero(known_by(df, start, s.embargo_days) & (t < start).to_numpy())
        test = np.flatnonzero(((t >= start) & (t < end)).to_numpy())
        out.append(Fold(start, end, train, test))
        start = end
    return out


def split_calibration(df: pd.DataFrame, train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit and calibration rows of a training set: the latest ``CAL_SHARE`` (by decision time)
    calibrates; the fit rows are purged and embargoed from its first decision."""
    order = train[np.argsort(df["decision_utc"].to_numpy()[train], kind="stable")]
    n_cal = max(1, int(round(len(order) * CAL_SHARE)))
    cal = order[-n_cal:]
    first = df["decision_utc"].iloc[cal[0]]
    rest = order[:-n_cal]
    fit = rest[known_by(df.iloc[rest], first, splits().embargo_days)]
    return fit, cal


def target(df: pd.DataFrame, label: str = "net") -> np.ndarray:
    """``net``: y = 1{net R > 0} (``PREREG_P4.md`` §1); ``tp``: the design label, TP first."""
    if label == "net":
        return (df["net_r"].to_numpy(float) > 0).astype(int)
    if label == "tp":
        return df["y"].to_numpy(int)
    raise ValueError(f"unknown label {label!r}; expected one of {LABELS}")


def fit_weights(net_r: np.ndarray) -> np.ndarray:
    """|net R| scaled to mean 1 over the rows of one fit set."""
    w = np.abs(np.asarray(net_r, float))
    return w / w.mean() if w.mean() > 0 else np.ones_like(w)


class Platt:
    def fit(self, p: np.ndarray, y: np.ndarray) -> Platt:
        self.lr = LogisticRegression(C=1e6).fit(_logit(p)[:, None], y)
        return self

    def predict(self, p: np.ndarray) -> np.ndarray:
        return self.lr.predict_proba(_logit(p)[:, None])[:, 1]


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def mass_bins(p: np.ndarray, bins: int = ECE_BINS) -> list[np.ndarray]:
    """Row positions of ``bins`` equal-mass bins of ``p`` (sorted; sizes differ by at most 1)."""
    return [b for b in np.array_split(np.argsort(p, kind="stable"), bins) if len(b)]


def _ece_rows(p: np.ndarray, ys: np.ndarray, bins: int) -> np.ndarray:
    """ECE of every row of ``ys`` (label sets) against the same predictions ``p``."""
    groups = mass_bins(p, bins)
    order = np.concatenate(groups)
    sizes = np.array([len(g) for g in groups])
    starts = np.r_[0, np.cumsum(sizes)[:-1]]
    mean_p = np.add.reduceat(p[order], starts) / sizes
    rate = np.add.reduceat(ys[:, order], starts, axis=1) / sizes
    return (np.abs(rate - mean_p) * sizes).sum(axis=1) / len(p)


def ece(p: np.ndarray, y: np.ndarray, bins: int = ECE_BINS) -> float:
    """Expected calibration error: bin-size-weighted |mean p - hit rate| over equal-mass bins."""
    return float(_ece_rows(p, np.asarray(y, float)[None, :], bins)[0])


def ece_debiased(
    p: np.ndarray, y: np.ndarray, rng: np.random.Generator, sims: int = ECE_SIMS
) -> float:
    """ECE minus the mean ECE of ``sims`` label sets drawn as Bernoulli(p): what a perfectly
    calibrated model would show on these predictions by noise alone."""
    noise = _ece_rows(p, (rng.random((sims, len(p))) < p).astype(float), ECE_BINS).mean()
    return ece(p, y) - float(noise)


def ece_debiased_ci(
    p: np.ndarray, y: np.ndarray, weeks: np.ndarray, rng: np.random.Generator,
    boot: int = ECE_BOOT, sims: int = ECE_SIMS,
) -> tuple[float, float]:  # fmt: skip
    """95% interval of the debiased ECE by a weekly block bootstrap (whole weeks resampled)."""
    blocks = list(pd.Series(np.arange(len(p))).groupby(weeks).indices.values())
    vals = np.empty(boot)
    for b in range(boot):
        idx = np.concatenate([blocks[k] for k in rng.integers(0, len(blocks), len(blocks))])
        vals[b] = ece_debiased(p[idx], y[idx], rng, sims)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def calibration_line(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Intercept and slope of the logistic recalibration of y on logit p (0 and 1 if calibrated)."""
    lr = LogisticRegression(C=1e6).fit(_logit(p)[:, None], y)
    return float(lr.intercept_[0]), float(lr.coef_[0, 0])


def reliability(p: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    """Per equal-mass bin: trades, mean p and hit rate (the reliability diagram as a table)."""
    return pd.DataFrame(
        [{"n": len(b), "mean_p": p[b].mean(), "rate": y[b].mean()} for b in mass_bins(p)]
    )


def predict(
    df: pd.DataFrame,
    features: list[str],
    make_model: Callable[[], object],
    label: str = "net",
    info: list | None = None,
) -> pd.DataFrame:
    """Out-of-sample calibrated probabilities for every test row of every fold.

    ``make_model()`` returns an object with ``fit(x, y, sample_weight, rows)`` (``rows``: the fit
    rows of ``df``, for a model that needs their times) and ``predict_proba(x)``; if it has
    ``info(x_test)``, its result for each window is appended to ``info``."""
    rows = []
    y = target(df, label)
    r = df["net_r"].to_numpy(float)
    x = df[features].to_numpy(float)
    for k, f in enumerate(folds(df)):
        if len(f.test) == 0:
            continue
        fit, cal = split_calibration(df, f.train)
        model = make_model()
        model.fit(x[fit], y[fit], sample_weight=fit_weights(r[fit]), rows=df.iloc[fit])
        platt = Platt().fit(model.predict_proba(x[cal])[:, 1], y[cal])
        raw = model.predict_proba(x[f.test])[:, 1]
        if info is not None and hasattr(model, "info"):
            info.append({"fold": k, **model.info(x[f.test])})
        rows.append(
            pd.DataFrame(
                {
                    "row": f.test,
                    "fold": k,
                    "p_raw": raw,
                    "p": platt.predict(raw),
                    "base_rate": y[f.train].mean(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def scores(
    pred: pd.DataFrame, y: np.ndarray, weeks: np.ndarray | None = None, seed: int = SEED
) -> dict:
    """Pooled calibration reading of ``PREREG_P4.md`` §6; the ECE interval only with ``weeks``
    (the week of each prediction row)."""
    yy = y[pred["row"].to_numpy()]
    p = pred["p"].to_numpy()
    ref = brier(pred["base_rate"].to_numpy(), yy)
    b = brier(p, yy)
    rng = np.random.default_rng(seed)
    out = {
        "brier": b,
        "brier_ref": ref,
        "bss": 1 - b / ref,
        "ece": ece(p, yy),
        "ece_debiased": ece_debiased(p, yy, rng),
        "n": len(p),
    }
    out["intercept"], out["slope"] = calibration_line(p, yy)
    if weeks is not None:
        out["ece_debiased_ci"] = ece_debiased_ci(p, yy, weeks, rng)
    return out


def render(df: pd.DataFrame, fs: list[Fold], rules: str) -> str:
    rng = np.random.default_rng(SEED)
    lines = [
        f"# P4: walk-forward folds and E1 on the test windows ({rules})",
        "",
        "_Generated by `python -m app research walkforward`; protocol in"
        " `app/research/walkforward.py`. Rules frozen (L1, 2026-10-23) before this run._",
        "",
        "| Window | Train (fit / calibration) | Test | Train base rate | E1 TP | E1 mean net R |"
        " E1 total R |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    y = df["y"].to_numpy(int)
    for f in fs:
        fit, cal = split_calibration(df, f.train)
        te = df.iloc[f.test]
        lines.append(
            f"| {f.start:%Y-%m} | {len(f.train)} ({len(fit)} / {len(cal)}) | {len(f.test)} |"
            f" {y[f.train].mean():.1%} | {te['y'].mean():.1%} | {te['net_r'].mean():+.3f} |"
            f" {te['net_r'].sum():+.1f} |"
        )
    test = df.iloc[np.concatenate([f.test for f in fs])]
    lo, hi = block_ci(test["net_r"].to_numpy(float), week_of(test["decision_utc"]), rng)
    lines += [
        "",
        f"E1 on all test windows (2018-01 to 2024-06): **{len(test)} trades**, TP"
        f" {test['y'].mean():.1%}, mean net R **{test['net_r'].mean():+.3f}** (95% weekly block"
        f" {lo:+.3f} to {hi:+.3f}), at 2x costs {test['net_r_2x'].mean():+.3f}, total"
        f" {test['net_r'].sum():+.1f} R.",
        "",
        "| Instrument | Trades | TP | Mean net R |",
        "| --- | --- | --- | --- |",
        *[
            f"| {s} | {len(g)} | {g['y'].mean():.1%} | {g['net_r'].mean():+.3f} |"
            for s, g in test.groupby("symbol")
        ],
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m app research walkforward")
    ap.add_argument("--rules", default="L1")
    ap.add_argument("--store", type=Path, default=STORE)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    path = args.store / f"p4_dataset_{args.rules}.parquet"
    if not path.exists():
        print(f"{path} missing: run python -m app features build", file=sys.stderr)
        return 1
    df = pd.read_parquet(path).sort_values("decision_utc").reset_index(drop=True)
    fs = folds(df)
    args.out.mkdir(parents=True, exist_ok=True)
    report = render(df, fs, args.rules)
    (args.out / f"walkforward_{args.rules}.md").write_text(report, encoding="utf-8", newline="\n")
    print(report)
    return 0
